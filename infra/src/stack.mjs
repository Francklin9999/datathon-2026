import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { Stack, Duration, RemovalPolicy, CfnOutput } from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as iam from 'aws-cdk-lib/aws-iam';
import { AccessLogFormat } from 'aws-cdk-lib/aws-apigateway';
import * as apigw from 'aws-cdk-lib/aws-apigatewayv2';
import * as integrations from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import { rewriteCode } from './rewrite.mjs';

export const flags = ['bilingual','world_explorer','world_layer_facilities','world_layer_hazards',
  'time_machine','profile_creator','goal_requests','sabotage_demo','research_open_web',
  'guardrails','on_demand_tickers','frontier_chart'];

export class AplombStack extends Stack {
  constructor(scope, id, options = {}) {
    const { application, ...stackProps } = options;
    super(scope, id, stackProps);
    const bucketProps = { blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED, enforceSSL: true,
      versioned: true, removalPolicy: RemovalPolicy.RETAIN };
    const web = new s3.Bucket(this, 'Web', bucketProps);
    const data = new s3.Bucket(this, 'Data', bucketProps);
    const rewrite = new cloudfront.Function(this, 'StaticRoutes', {
      code: cloudfront.FunctionCode.fromInline(rewriteCode),
      runtime: cloudfront.FunctionRuntime.JS_2_0 });
    const distribution = new cloudfront.Distribution(this, 'Site', {
      defaultRootObject: 'index.html',
      defaultBehavior: { origin: origins.S3BucketOrigin.withOriginAccessControl(web),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
        responseHeadersPolicy: cloudfront.ResponseHeadersPolicy.SECURITY_HEADERS,
        functionAssociations: [{ function: rewrite,
          eventType: cloudfront.FunctionEventType.VIEWER_REQUEST }] },
      // Serve the exported 404 page with an actual 404, never an SPA success fallback.
      errorResponses: [{httpStatus: 403, responseHttpStatus: 404, responsePagePath: '/404.html', ttl: Duration.seconds(0)},
        {httpStatus: 404, responseHttpStatus: 404, responsePagePath: '/404.html', ttl: Duration.seconds(0)}] });
    const tables = {};
    for (const name of ['Profiles', 'Runs', 'Cache']) {
      tables[name] = new dynamodb.Table(this, name, {
        partitionKey: {name:'pk', type:dynamodb.AttributeType.STRING},
        sortKey: {name:'sk', type:dynamodb.AttributeType.STRING},
        billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
        encryption: dynamodb.TableEncryption.AWS_MANAGED,
        pointInTimeRecoverySpecification: {pointInTimeRecoveryEnabled:true},
        removalPolicy: RemovalPolicy.RETAIN,
        ...(name === 'Cache' ? {timeToLiveAttribute:'expiresAt'} : {}) });
    }
    for (const [indexName, partition, sort] of [
      ['bySession','sessionKey','sessionSort'], ['byProfile','profileKey','profileSort']]) {
      tables.Runs.addGlobalSecondaryIndex({indexName,
        partitionKey:{name:partition,type:dynamodb.AttributeType.STRING},
        sortKey:{name:sort,type:dynamodb.AttributeType.STRING},
        projectionType:dynamodb.ProjectionType.ALL});
    }
    for (const [name, value] of Object.entries({SiteUrl:`https://${distribution.distributionDomainName}`,
      WebBucket:web.bucketName, DataBucket:data.bucketName, DistributionId:distribution.distributionId,
      ProfilesTable:tables.Profiles.tableName, RunsTable:tables.Runs.tableName,
      CacheTable:tables.Cache.tableName, Region:this.region,
      DeploymentStage:application ? 'application-packaged-unverified' : 'foundation-only'})) {
      new CfnOutput(this, name, {value});
    }
    if (!application) return;
    validateApplication(application);
    const workerName = `${this.stackName}-worker`;
    const commonEnv = {APLOMB_ENV:'aws', APLOMB_WORKER_FUNCTION:workerName, APLOMB_DATA_VERSION:application.dataVersion,
      APLOMB_DATA_BUCKET:data.bucketName, APLOMB_DATA_PREFIX:application.dataPrefix,
      APLOMB_DATA_DIR:'/tmp/aplomb-data', APLOMB_PROFILES_TABLE:tables.Profiles.tableName,
      APLOMB_RUNS_TABLE:tables.Runs.tableName, APLOMB_CACHE_TABLE:tables.Cache.tableName,
      APLOMB_MODEL_STRONG:application.strongModel, APLOMB_MODEL_FAST:application.fastModel,
      APLOMB_ALLOWED_ORIGINS:[`https://${distribution.distributionDomainName}`,
        ...(application.allowedOrigins ?? ['http://localhost:3000'])].join(','),
      APLOMB_SOURCE_USER_AGENT:application.sourceUserAgent,
      APLOMB_RUN_TARGET_SECONDS:'90',APLOMB_RUN_HARD_SECONDS:'180',
      APLOMB_MAX_REVISE:'2',APLOMB_MAX_LLM_CALLS:'12',APLOMB_MAX_RESEARCH_CALLS:'12',
      ...Object.fromEntries(flags.map(f=>[`APLOMB_FEATURE_${f.toUpperCase()}`,'false'])) };
    const code = lambda.Code.fromAsset(application.artifact);
    const makeFunction = (name, handler, timeout, concurrency) => {
      const logGroup = new logs.LogGroup(this, `${name}Logs`, {
        retention:logs.RetentionDays.ONE_WEEK, removalPolicy:RemovalPolicy.RETAIN });
      const role = new iam.Role(this, `${name}Role`, {
        assumedBy:new iam.ServicePrincipal('lambda.amazonaws.com')});
      role.addToPolicy(new iam.PolicyStatement({actions:['logs:CreateLogStream','logs:PutLogEvents'],
        resources:[logGroup.logGroupArn]}));
      return new lambda.Function(this, name, {runtime:lambda.Runtime.PYTHON_3_12,
        architecture:lambda.Architecture.X86_64, code, handler, timeout:Duration.seconds(timeout),
        memorySize:1024, ...(name === 'Worker' ? {functionName:workerName} : {}),
        reservedConcurrentExecutions:concurrency, environment:commonEnv, logGroup, role,
        tracing:lambda.Tracing.DISABLED});
    };
    const worker = makeFunction('Worker','aplomb.agents.worker.handler',210,2);
    const api = makeFunction('Api','aplomb.api.lambda_handler.handler',30,5);
    api.addEnvironment('APLOMB_WORKER_FUNCTION',worker.functionName);
    api.addToRolePolicy(new iam.PolicyStatement({actions:['lambda:InvokeFunction'],resources:[worker.functionArn]}));
    for (const fn of [api,worker]) {
      for (const table of Object.values(tables)) fn.addToRolePolicy(new iam.PolicyStatement({
        actions:fn === worker && table === tables.Profiles ? ['dynamodb:GetItem','dynamodb:Query'] :
          // Transactions authorize their underlying item operations, not a
          // dynamodb:TransactWriteItems IAM action (see AWS transaction IAM docs).
          ['dynamodb:GetItem','dynamodb:PutItem','dynamodb:UpdateItem','dynamodb:DeleteItem',
          'dynamodb:Query'],
        resources:[table.tableArn,`${table.tableArn}/index/*`]}));
      fn.addToRolePolicy(new iam.PolicyStatement({actions:['s3:GetObject','s3:GetObjectVersion'],
        resources:[data.arnForObjects(`${application.dataPrefix}*`)]}));
      fn.addToRolePolicy(new iam.PolicyStatement({actions:['s3:GetObject','s3:PutObject'],
        resources:[data.arnForObjects('evidence/*')]}));
      // Cross-region inference profiles require both the source profile and destination models.
      fn.addToRolePolicy(new iam.PolicyStatement({actions:['bedrock:InvokeModel','bedrock:InvokeModelWithResponseStream'],
        resources:application.modelResourceArns}));
    }
    new lambda.EventInvokeConfig(this,'WorkerAsync',{function:worker,
      maxEventAge:Duration.minutes(5),retryAttempts:1});
    const accessLogs = new logs.LogGroup(this,'HttpAccessLogs',{
      retention:logs.RetentionDays.ONE_WEEK,removalPolicy:RemovalPolicy.RETAIN});
    const http = new apigw.HttpApi(this,'Http',{
      createDefaultStage:false,
      defaultIntegration:new integrations.HttpLambdaIntegration('ApiIntegration',api),
      corsPreflight:{allowOrigins:[`https://${distribution.distributionDomainName}`,
        ...(application.allowedOrigins ?? ['http://localhost:3000'])],
        allowMethods:[apigw.CorsHttpMethod.GET,apigw.CorsHttpMethod.POST,apigw.CorsHttpMethod.PATCH,apigw.CorsHttpMethod.PUT,
          apigw.CorsHttpMethod.DELETE,apigw.CorsHttpMethod.OPTIONS],
        allowHeaders:['content-type','x-aplomb-session','idempotency-key','x-request-id','accept-language'],
        exposeHeaders:['x-request-id','x-aplomb-data-version'],maxAge:Duration.minutes(5)}});
    new apigw.HttpStage(this,'HttpDefaultStage',{httpApi:http,stageName:'$default',autoDeploy:true,
      throttle:{rateLimit:100,burstLimit:200},
      accessLogSettings:{destination: new apigw.LogGroupLogDestination(accessLogs),
        format:AccessLogFormat.custom(JSON.stringify({requestId:'$context.requestId',
          status:'$context.status',responseLength:'$context.responseLength',
          routeKey:'$context.routeKey'}))}});
    for (const [name,fn] of [['Api',api],['Worker',worker]]) {
      new cloudwatch.Alarm(this,`${name}Errors`,{metric:fn.metricErrors({period:Duration.minutes(1)}),
        threshold:1,evaluationPeriods:1,treatMissingData:cloudwatch.TreatMissingData.NOT_BREACHING});
      new cloudwatch.Alarm(this,`${name}Throttles`,{metric:fn.metricThrottles({period:Duration.minutes(1)}),
        threshold:1,evaluationPeriods:1,treatMissingData:cloudwatch.TreatMissingData.NOT_BREACHING});
    }
    new CfnOutput(this,'ApiBase',{value:`${http.apiEndpoint}/v1`});
    new CfnOutput(this,'WorkerFunction',{value:worker.functionName});
    new CfnOutput(this,'DataVersion',{value:application.dataVersion});
    new CfnOutput(this,'Revision',{value:application.revision});
  }
}

export function validateApplication(a) {
  for (const key of ['artifact','dataVersion','dataPrefix','strongModel','fastModel','sourceUserAgent','revision']) {
    if (typeof a[key] !== 'string' || !a[key].trim()) throw new Error(`application.${key} required`);
  }
  if (!/^snap-\d{8}-[a-z0-9][a-z0-9-]*$/.test(a.dataVersion)) throw new Error('dataVersion must be snap-YYYYMMDD-label');
  if (!a.dataPrefix.endsWith('/') || a.dataPrefix.startsWith('/') || a.dataPrefix.includes('..')) {
    throw new Error('dataPrefix must be a relative immutable prefix ending /');
  }
  for (const file of ['aplomb/api/lambda_handler.py','aplomb/agents/worker.py','pydantic/__init__.py',
    'pydantic_core/__init__.py','mangum/__init__.py','boto3/__init__.py']) {
    if (!fs.existsSync(path.join(a.artifact,file))) throw new Error(`artifact missing ${file}`);
  }
  const manifestPath = path.join(a.artifact,'aplomb-artifact.json');
  if (!fs.existsSync(manifestPath)) throw new Error('artifact requires Lambda runtime import evidence');
  const manifest = JSON.parse(fs.readFileSync(manifestPath,'utf8'));
  if (manifest.runtime !== 'python3.12' || manifest.architecture !== 'x86_64' || manifest.lambdaRuntimeImportCheck !== true) {
    throw new Error('artifact Lambda runtime import check required');
  }
  if (!manifest.files || !Object.keys(manifest.files).length) throw new Error('artifact file hashes required');
  for (const [file,hash] of Object.entries(manifest.files)) {
    if (file.startsWith('/') || file.split('/').includes('..') ||
        createHash('sha256').update(fs.readFileSync(path.join(a.artifact,file))).digest('hex') !== hash) {
      throw new Error('artifact integrity check failed');
    }
  }
  if (!Array.isArray(a.modelResourceArns) || a.modelResourceArns.length < 2 ||
      a.modelResourceArns.some(arn => !/^arn:aws:bedrock:[a-z0-9-]+:\d*:((inference-profile|foundation-model)\/)[^*]+$/.test(arn))) {
    throw new Error('exact verified modelResourceArns required; wildcard regions/models forbidden');
  }
  for (const model of [a.strongModel,a.fastModel]) {
    const foundation = model.replace(/^(us|global|eu|apac)\./,'');
    if (!a.modelResourceArns.some(arn => arn.endsWith(`:inference-profile/${model}`)) ||
        !a.modelResourceArns.some(arn => arn.endsWith(`::foundation-model/${foundation}`))) {
      throw new Error(`exact inference profile and destination foundation ARN required for ${model}`);
    }
  }
  for (const origin of a.allowedOrigins ?? []) {
    const u = new URL(origin);
    if (origin !== u.origin || !['https:','http:'].includes(u.protocol) ||
      (u.protocol === 'http:' && u.hostname !== 'localhost')) throw new Error('exact HTTPS/localhost origins required');
  }
}
