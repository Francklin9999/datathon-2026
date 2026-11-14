import {spawnSync} from 'node:child_process';
const result=spawnSync(process.execPath,['node_modules/aws-cdk/bin/cdk','synth','--app','node src/app.mjs','--quiet'],{stdio:'inherit'});
process.exit(result.status ?? 1);
