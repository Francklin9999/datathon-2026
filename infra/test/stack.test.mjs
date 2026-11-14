import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import vm from 'node:vm';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {App} from 'aws-cdk-lib';
import {Template, Match} from 'aws-cdk-lib/assertions';
import {AplombStack, flags, validateApplication} from '../src/stack.mjs';
import {rewriteCode} from '../src/rewrite.mjs';

function artifact() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(),'aplomb-infra-test-'));
  // Only synthesis fixtures: these files never become a deployment artifact.
  for(const f of ['aplomb/api/lambda_handler.py','aplomb/agents/worker.py','pydantic/__init__.py',
    'pydantic_core/__init__.py','mangum/__init__.py','boto3/__init__.py']) {
    fs.mkdirSync(path.dirname(path.join(dir,f)),{recursive:true}); fs.writeFileSync(path.join(dir,f),'');
  }
  fs.writeFileSync(path.join(dir,'aplomb-artifact.json'),JSON.stringify({runtime:'python3.12',architecture:'x86_64',lambdaRuntimeImportCheck:true,files:{'aplomb/api/lambda_handler.py':createHash('sha256').update('').digest('hex')}}));
  return dir;
}
const appConfig = artifact => ({artifact,dataVersion:'snap-20261114-test',dataPrefix:'snapshots/test/',
  strongModel:'us.anthropic.claude-sonnet-4-6',fastModel:'us.anthropic.claude-haiku-5-5',
  sourceUserAgent:'Aplomb test contact@example.com',revision:'test-only',modelResourceArns:[
    'arn:aws:bedrock:us-east-1:010526248118:inference-profile/us.anthropic.claude-sonnet-4-6',
    'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-4-6',
    'arn:aws:bedrock:us-east-1:010526248118:inference-profile/us.anthropic.claude-haiku-5-5',
    'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-haiku-5-5']});
test('foundation retains private data and cannot imply a working API',()=>{
  const t=Template.fromStack(new AplombStack(new App(),'Foundation'));
  t.resourceCountIs('AWS::Lambda::Function',0);
  t.resourceCountIs('AWS::DynamoDB::Table',3);
  t.hasResourceProperties('AWS::S3::Bucket',{PublicAccessBlockConfiguration:{
    BlockPublicAcls:true,BlockPublicPolicy:true,IgnorePublicAcls:true,RestrictPublicBuckets:true}});
  t.hasResource('AWS::DynamoDB::Table',{DeletionPolicy:'Retain'});
  t.hasResourceProperties('AWS::CloudFront::Distribution',{DistributionConfig:{
    CustomErrorResponses:Match.arrayWith([{ErrorCode:403,ResponseCode:404,ResponsePagePath:'/404.html',ErrorCachingMinTTL:0}])}});
});
test('routes rewrite deep links and exclude static assets',()=>{
  const context=vm.createContext({}); vm.runInContext(rewriteCode,context);
  for(const [uri,want] of [['/','/index.html'],['/portfolio','/portfolio/index.html'],
    ['/portfolio/','/portfolio/index.html'],['/_next/static/a.js','/_next/static/a.js'],
    ['/404.html','/404.html'],['/data/file.json','/data/file.json']]) {
    assert.equal(context.handler({request:{uri}}).uri,want);
  }
});
test('real handlers/artifacts and bounded model IAM are required',()=>{
  assert.throws(()=>validateApplication(appConfig('/tmp/nonexistent-aplomb-artifact')),/artifact missing/);
  const dir=artifact();
  try {
    const a=appConfig(dir); a.modelResourceArns=['*']; assert.throws(()=>validateApplication(a),/exact verified/);
    const invalid=appConfig(dir); invalid.dataVersion='test'; assert.throws(()=>validateApplication(invalid),/dataVersion/);
    const missing=appConfig(dir); missing.modelResourceArns=missing.modelResourceArns.slice(0,2);
    assert.throws(()=>validateApplication(missing),/foundation ARN required/);
  }
  finally {fs.rmSync(dir,{recursive:true});}
});
test('application has exact handlers, finite concurrency and least privilege',()=>{
  const dir=artifact();
  try {
    const t=Template.fromStack(new AplombStack(new App(),'Application',{application:appConfig(dir)}));
    t.resourceCountIs('AWS::Lambda::Function',2);
    t.hasResourceProperties('AWS::ApiGatewayV2::Api',{CorsConfiguration:{AllowMethods:Match.arrayWith(['PUT']),AllowHeaders:Match.arrayWith(['accept-language'])}});
    t.hasResourceProperties('AWS::ApiGatewayV2::Stage',{DefaultRouteSettings:{ThrottlingRateLimit:100,ThrottlingBurstLimit:200}});
    t.hasResourceProperties('AWS::Lambda::Function',{Handler:'aplomb.agents.worker.handler',
      Timeout:210,ReservedConcurrentExecutions:2,Runtime:'python3.12',Architectures:['x86_64']});
    t.hasResourceProperties('AWS::Lambda::Function',{Handler:'aplomb.api.lambda_handler.handler',
      Timeout:30,ReservedConcurrentExecutions:5,Environment:{Variables:Match.objectLike(
        Object.fromEntries(flags.map(f=>[`APLOMB_FEATURE_${f.toUpperCase()}`,'false'])))}});
    t.hasResourceProperties('AWS::DynamoDB::Table',{GlobalSecondaryIndexes:Match.arrayWith([
      Match.objectLike({IndexName:'bySession',KeySchema:[{AttributeName:'sessionKey',KeyType:'HASH'},
        {AttributeName:'sessionSort',KeyType:'RANGE'}]})])});
    t.hasResourceProperties('AWS::Lambda::EventInvokeConfig',{MaximumRetryAttempts:1,MaximumEventAgeInSeconds:300});
    const raw=t.toJSON();
    for(const role of Object.values(raw.Resources).filter(r=>r.Type==='AWS::IAM::Role')) {
      assert.equal(role.Properties.ManagedPolicyArns,undefined,'Lambda roles must not inherit broad managed policies');
    }
    assert.ok(!JSON.stringify(raw).includes('AWSLambdaBasicExecutionRole'));
    for(const policy of Object.values(raw.Resources).filter(r=>r.Type==='AWS::IAM::Policy')) {
      for(const statement of policy.Properties.PolicyDocument.Statement) {
        const actions=Array.isArray(statement.Action)?statement.Action:[statement.Action];
        if(actions.some(action=>action.startsWith('logs:'))) {
          assert.deepEqual(actions,['logs:CreateLogStream','logs:PutLogEvents']);
          assert.notEqual(statement.Resource,'*');
        }
      }
    }
    for(const r of Object.values(raw.Resources).filter(r=>r.Type==='AWS::IAM::Policy')) {
      for(const s of r.Properties.PolicyDocument.Statement) {
        assert.notEqual(s.Resource,'*');
        assert.ok(!(Array.isArray(s.Action)?s.Action:[s.Action]).some(a=>[
          '*','bedrock:*','dynamodb:*','s3:*','dynamodb:TransactWriteItems'
        ].includes(a)));
      }
    }
  } finally {fs.rmSync(dir,{recursive:true});}
});
