import fs from 'node:fs';
import { App } from 'aws-cdk-lib';
import { AplombStack } from './stack.mjs';
const app = new App();
const file = process.env.APLOMB_INFRA_CONFIG;
const config = file ? JSON.parse(fs.readFileSync(file,'utf8')) : {};
new AplombStack(app,'Aplomb',{env:{region:'us-east-1'},...config});
app.synth();
