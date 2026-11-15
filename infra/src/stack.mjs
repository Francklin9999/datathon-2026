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
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as destinations from 'aws-cdk-lib/aws-lambda-destinations';
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
    // Retained execution roles and policies isolate each release's IAM as well as
    // its code/environment. Old published workers keep their exact model/data grants.
    const releaseHash = createHash('sha256').update(JSON.stringify({
      ...application, artifact:undefined,
      infrastructure:fs.readFileSync(new URL('./stack.mjs',import.meta.url),'utf8'),
      files:JSON.parse(fs.readFileSync(path.join(application.artifact,'aplomb-artifact.json'),'utf8')).files
    })).digest('hex').slice(0,12);
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
      ...Object.fromEntries(flags.map(f=>[`APLOMB_FEATURE_${f.toUpperCase()}`,String(application.features?.includes(f) ?? false)])),
      ...(application.guardrail ? {APLOMB_GUARDRAIL_ID:application.guardrail.id,
        APLOMB_GUARDRAIL_VERSION:application.guardrail.version} : {}) };
    const code = lambda.Code.fromAsset(application.artifact);
    const makeFunction = (name, handler, timeout, concurrency) => {
      const logGroup = new logs.LogGroup(this, `${name}Logs`, {
        retention:logs.RetentionDays.ONE_WEEK, removalPolicy:RemovalPolicy.RETAIN });
      const role = new iam.Role(this, `${name}Role${releaseHash}`, {
        assumedBy:new iam.ServicePrincipal('lambda.amazonaws.com')});
      role.applyRemovalPolicy(RemovalPolicy.RETAIN);
      role.addToPolicy(new iam.PolicyStatement({actions:['logs:CreateLogStream','logs:PutLogEvents'],
        resources:[logGroup.logGroupArn]}));
      return new lambda.Function(this, name, {runtime:lambda.Runtime.PYTHON_3_12,
        architecture:lambda.Architecture.X86_64, code, handler, timeout:Duration.seconds(timeout),
        memorySize:1024, ...(name === 'Worker' ? {functionName:workerName} : {}),
        reservedConcurrentExecutions:concurrency, environment:commonEnv, logGroup, role,
        tracing:lambda.Tracing.DISABLED});
    };
    const worker = makeFunction('Worker','aplomb.agents.worker.handler',210,2);
    const workerVersion = worker.currentVersion;
    workerVersion.applyRemovalPolicy(RemovalPolicy.RETAIN);
    const api = makeFunction('Api','aplomb.api.lambda_handler.handler',30,5);
    api.addEnvironment('APLOMB_WORKER_FUNCTION',workerVersion.functionArn);
    // Only numeric versions of this one project function; never unrelated Lambdas.
    api.addToRolePolicy(new iam.PolicyStatement({actions:['lambda:InvokeFunction'],resources:[`${worker.functionArn}:*`]}));
    if (application.guardrail) worker.addToRolePolicy(new iam.PolicyStatement({
      actions:['bedrock:ApplyGuardrail'],resources:[application.guardrail.arn,...(application.guardrail.profileResourceArns ?? [])]}));
    for (const fn of [api,worker]) {
      for (const table of Object.values(tables)) {
        if (fn === worker && table !== tables.Runs) continue; // frozen inputs; worker only mutates run state
        fn.addToRolePolicy(new iam.PolicyStatement({
        actions:fn === worker ? ['dynamodb:GetItem','dynamodb:PutItem','dynamodb:Query'] :
          // Transactions authorize their underlying item operations, not a
          // dynamodb:TransactWriteItems IAM action (see AWS transaction IAM docs).
          ['dynamodb:GetItem','dynamodb:PutItem','dynamodb:UpdateItem','dynamodb:DeleteItem',
          'dynamodb:Query'],
        resources:fn === worker ? [table.tableArn] : [table.tableArn,`${table.tableArn}/index/*`]}));
      }
      fn.addToRolePolicy(new iam.PolicyStatement({actions:['s3:GetObject','s3:GetObjectVersion'],
        resources:[data.arnForObjects(`${application.dataPrefix}*`)]}));
      fn.addToRolePolicy(new iam.PolicyStatement({actions:['s3:GetObject','s3:PutObject'],
        resources:[data.arnForObjects('evidence/*')]}));
      // Cross-region inference profiles require both the source profile and destination models.
      fn.addToRolePolicy(new iam.PolicyStatement({actions:['bedrock:InvokeModel','bedrock:InvokeModelWithResponseStream'],
        resources:fn === worker ? application.modelResourceArns : application.modelResourceArns.filter(arn=>
          arn.endsWith(`:inference-profile/${application.fastModel}`) ||
          arn.endsWith(`::foundation-model/${application.fastModel.replace(/^(us|global|eu|apac)\./,'')}`))}));
    }
    for (const fn of [api,worker]) fn.role.node.findChild('DefaultPolicy').applyRemovalPolicy(RemovalPolicy.RETAIN);
    const failures = new sqs.Queue(this,'WorkerFailures',{encryption:sqs.QueueEncryption.SQS_MANAGED,
      retentionPeriod:Duration.days(14),enforceSSL:true,removalPolicy:RemovalPolicy.RETAIN});
    const delivery = new lambda.EventInvokeConfig(this,`WorkerAsync${releaseHash}`,{function:worker,qualifier:workerVersion.version,
      maxEventAge:Duration.minutes(1),retryAttempts:1,onFailure:new destinations.SqsDestination(failures)});
    delivery.applyRemovalPolicy(RemovalPolicy.RETAIN);
    new cloudwatch.Alarm(this,'WorkerFailureQueueAlarm',{metric:failures.metricApproximateNumberOfMessagesVisible(),
      threshold:1,evaluationPeriods:1,treatMissingData:cloudwatch.TreatMissingData.NOT_BREACHING});
    new cloudwatch.Alarm(this,'WorkerAsyncDropped',{metric:worker.metric('AsyncEventsDropped',{statistic:'Sum'}),
      threshold:1,evaluationPeriods:1,treatMissingData:cloudwatch.TreatMissingData.NOT_BREACHING});
    const workflowMetric = (name,kind,statistic='Sum') => new cloudwatch.Metric({namespace:'Aplomb/Workflows',
      metricName:name,dimensionsMap:{RunKind:kind},statistic,period:Duration.minutes(1)});
    new cloudwatch.Alarm(this,'WorkflowFailures',{metric:new cloudwatch.MathExpression({
      expression:'decision + brief + draft',period:Duration.minutes(1),usingMetrics:{decision:workflowMetric('Failed','decision'),
        brief:workflowMetric('Failed','portfolio_brief'),draft:workflowMetric('Failed','profile_draft')}}),
      threshold:1,evaluationPeriods:1,treatMissingData:cloudwatch.TreatMissingData.NOT_BREACHING});
    const dashboard = new cloudwatch.Dashboard(this,'Operations',{dashboardName:`${this.stackName}-operations`});
    dashboard.addWidgets(
      new cloudwatch.GraphWidget({title:'API / worker execution',left:[api.metricInvocations(),worker.metricInvocations()],
        right:[api.metricErrors(),worker.metricErrors(),worker.metricThrottles()]}),
      new cloudwatch.GraphWidget({title:'Worker latency and async age',left:[worker.metricDuration({statistic:'p95'}),
        worker.metric('AsyncEventAge',{statistic:'Maximum'})]}),
      new cloudwatch.GraphWidget({title:'Durable audited outcomes',left:['decision','portfolio_brief','profile_draft'].flatMap(
        kind=>[workflowMetric('Succeeded',kind),workflowMetric('Failed',kind)])}),
      new cloudwatch.GraphWidget({title:'Actual Bedrock token usage',left:['decision','portfolio_brief','profile_draft'].flatMap(
        kind=>[workflowMetric('InputTokens',kind),workflowMetric('OutputTokens',kind)])}),
      new cloudwatch.GraphWidget({title:'Delivery failures awaiting inspection',left:[failures.metricApproximateNumberOfMessagesVisible(),
        worker.metric('AsyncEventsDropped',{statistic:'Sum'})]})
    );
    new CfnOutput(this,'FailureQueueUrl',{value:failures.queueUrl});
    new CfnOutput(this,'OperationsDashboard',{value:`https://${this.region}.console.aws.amazon.com/cloudwatch/home?region=${this.region}#dashboards:name=${this.stackName}-operations`});
    const accessLogs = new logs.LogGroup(this,'HttpAccessLogs',{
      retention:logs.RetentionDays.ONE_WEEK,removalPolicy:RemovalPolicy.RETAIN});
    const http = new apigw.HttpApi(this,'Http',{
      createDefaultStage:false,
      defaultIntegration:new integrations.HttpLambdaIntegration('ApiIntegration',api.currentVersion),
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
    new CfnOutput(this,'WorkerVersionArn',{value:workerVersion.functionArn});
    api.currentVersion.applyRemovalPolicy(RemovalPolicy.RETAIN);
    new CfnOutput(this,'DataVersion',{value:application.dataVersion});
    new CfnOutput(this,'Revision',{value:application.revision});
  }
}

export function validateApplication(a) {
  if (a.features && (!Array.isArray(a.features) || a.features.some(f=>!flags.includes(f)))) throw new Error('Unknown feature flag');
  if (a.features?.includes('guardrails') && !a.guardrail) throw new Error('guardrails require frozen policy');
  if (a.guardrail && (!/^[a-z0-9]+$/.test(a.guardrail.id) || !/^[1-9][0-9]*$/.test(a.guardrail.version) ||
      !new RegExp(`^arn:aws:bedrock:[a-z0-9-]+:[0-9]{12}:guardrail/${a.guardrail.id}$`).test(a.guardrail.arn))) {
    throw new Error('Exact frozen Guardrail ID/version/ARN required');
  }
  if (a.guardrail?.profileResourceArns && (!Array.isArray(a.guardrail.profileResourceArns) ||
      a.guardrail.profileResourceArns.some(arn=>!/^arn:aws:bedrock:[a-z0-9-]+:[0-9]{12}:guardrail-profile\/[a-z0-9.-]+:[0-9]+$/.test(arn)))) {
    throw new Error('Exact Guardrail profile ARNs required');
  }
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
  const actualFiles = [];
  const visit = (directory,prefix='') => {
    for (const entry of fs.readdirSync(directory,{withFileTypes:true})) {
      const relative = `${prefix}${entry.name}`;
      if (entry.isSymbolicLink()) throw new Error('artifact symlinks forbidden');
      if (entry.isDirectory()) visit(path.join(directory,entry.name),`${relative}/`);
      else if (entry.isFile() && relative !== 'aplomb-artifact.json') actualFiles.push(relative);
    }
  };
  visit(a.artifact);
  if (actualFiles.length !== Object.keys(manifest.files).length || actualFiles.some(file=>!Object.hasOwn(manifest.files,file))) {
    throw new Error('artifact contains unlisted or missing files');
  }
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
