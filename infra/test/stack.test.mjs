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
  const files = {};
  const visit = (directory,prefix='') => {
    for (const entry of fs.readdirSync(directory,{withFileTypes:true})) {
      const relative=`${prefix}${entry.name}`;
      if(entry.isDirectory()) visit(path.join(directory,entry.name),`${relative}/`);
      else files[relative]=createHash('sha256').update(fs.readFileSync(path.join(directory,entry.name))).digest('hex');
    }
  };
  visit(dir);
  fs.writeFileSync(path.join(dir,'aplomb-artifact.json'),JSON.stringify({runtime:'python3.12',architecture:'x86_64',lambdaRuntimeImportCheck:true,files}));
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
    fs.writeFileSync(path.join(dir,'shadow.py'),'unverified');
    assert.throws(()=>validateApplication(appConfig(dir)),/unlisted/);
    fs.rmSync(path.join(dir,'shadow.py'));
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
    t.resourceCountIs('AWS::Lambda::Version',2);
    t.hasResourceProperties('AWS::Lambda::EventInvokeConfig',{MaximumRetryAttempts:1,MaximumEventAgeInSeconds:60,
      Qualifier:Match.not('$LATEST')});
    t.resourceCountIs('AWS::SQS::Queue',1);
    t.hasResourceProperties('AWS::SQS::Queue',{SqsManagedSseEnabled:true,MessageRetentionPeriod:1209600});
    t.hasResourceProperties('AWS::Lambda::EventInvokeConfig',{DestinationConfig:{OnFailure:{Destination:Match.anyValue()}}});
    t.resourceCountIs('AWS::CloudWatch::Dashboard',1);
    const raw=t.toJSON();
    for(const role of Object.values(raw.Resources).filter(r=>r.Type==='AWS::IAM::Role')) {
      assert.equal(role.Properties.ManagedPolicyArns,undefined,'Lambda roles must not inherit broad managed policies');
      assert.equal(role.DeletionPolicy,'Retain','A retained version must retain its execution role');
    }
    assert.ok(!JSON.stringify(raw).includes('AWSLambdaBasicExecutionRole'));
    for(const policy of Object.values(raw.Resources).filter(r=>r.Type==='AWS::IAM::Policy')) {
      assert.equal(policy.DeletionPolicy,'Retain','A retained execution role must retain its grants');
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

test('release changes publish new isolated IAM and retain old version delivery configuration',()=>{
  const dir=artifact();
  try {
    const first=Template.fromStack(new AplombStack(new App(),'Release',{application:appConfig(dir)})).toJSON();
    const next=Template.fromStack(new AplombStack(new App(),'Release',{application:{...appConfig(dir),revision:'next'}})).toJSON();
    const ids=(t,type)=>Object.entries(t.Resources).filter(([,r])=>r.Type===type).map(([id])=>id);
    assert.ok(ids(first,'AWS::IAM::Role').every(id=>!ids(next,'AWS::IAM::Role').includes(id)));
    const delivery=Object.values(next.Resources).find(r=>r.Type==='AWS::Lambda::EventInvokeConfig');
    assert.equal(delivery.DeletionPolicy,'Retain');
    const qualifier=delivery.Properties.Qualifier['Fn::GetAtt'];
    assert.equal(qualifier[1],'Version');
    assert.equal(next.Resources[qualifier[0]].Type,'AWS::Lambda::Version');
    for(const v of Object.values(next.Resources).filter(r=>r.Type==='AWS::Lambda::Version')) assert.equal(v.DeletionPolicy,'Retain');
  } finally {fs.rmSync(dir,{recursive:true});}
});
