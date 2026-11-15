import fs from 'node:fs/promises';
const target=await(await fetch('http://127.0.0.1:9322/json/new?http://127.0.0.1:3102/time-machine/',{method:'PUT'})).json();
const socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise(r=>socket.addEventListener('open',r,{once:true}));let id=0;const pending=new Map();socket.addEventListener('message',({data})=>{const m=JSON.parse(data);if(m.id&&pending.has(m.id)){pending.get(m.id)(m);pending.delete(m.id)}});
async function call(method,params={}){return await new Promise(r=>{const n=++id;pending.set(n,r);socket.send(JSON.stringify({id:n,method,params}))})}
async function ev(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.result.exceptionDetails)throw Error(r.result.exceptionDetails.text);return r.result.result.value}
async function wait(test){for(let n=0;n<100;n++){if(await ev(test))return;await new Promise(r=>setTimeout(r,500))}throw Error('Timeout: '+test)}
await call('Emulation.setDeviceMetricsOverride',{width:1365,height:900,deviceScaleFactor:1,mobile:false});
await wait(`!!document.querySelector('#move-ticker')`);
await ev(`document.querySelectorAll('button').forEach(b=>{if(b.textContent.trim()==='Later')b.click()})`);
await ev(`document.querySelectorAll('button').forEach(b=>{if(b.textContent.includes('2022-12-30: end of 2022'))b.click()})`);
await ev(`(()=>{for(const [id,v] of [['move-ticker','TSLA'],['move-size','5']]){const e=document.getElementById(id);Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,v);e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));}})()`);
await wait(`[...document.querySelectorAll('button')].some(x=>x.textContent.includes('Run historical replay')&&!x.disabled)`);
await ev(`[...document.querySelectorAll('button')].find(x=>x.textContent.includes('Run historical replay')).click()`);
await wait(`document.body.innerText.includes('Reveal outcomes') || document.body.innerText.includes('Reveal what happened') || document.body.innerText.includes('Reveal')`);
await ev(`[...document.querySelectorAll('button')].find(x=>x.textContent.includes('Reveal later outcomes')).click()`);
await wait(`document.body.innerText.includes('Checked: the run was re-read after the reveal')`);
console.log((await ev('document.body.innerText')).slice(-7500));
console.log('CONTROLS',await ev(`JSON.stringify([...document.querySelectorAll('input,button')].map(e=>({id:e.id,text:e.innerText,value:e.value,disabled:e.disabled})))`));
const shot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});await fs.writeFile('docs/evidence/parallel/agent-2/history-browser-reveal.png',Buffer.from(shot.result.data,'base64'));socket.close();
