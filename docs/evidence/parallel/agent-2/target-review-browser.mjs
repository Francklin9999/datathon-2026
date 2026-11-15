import fs from 'node:fs/promises';
const target=await(await fetch('http://127.0.0.1:9322/json/new?http://127.0.0.1:3102/agents-system/',{method:'PUT'})).json();
const socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise(r=>socket.addEventListener('open',r,{once:true}));let id=0;const pending=new Map();socket.addEventListener('message',({data})=>{const m=JSON.parse(data);if(m.id&&pending.has(m.id)){pending.get(m.id)(m);pending.delete(m.id)}});
async function call(method,params={}){return await new Promise(r=>{const n=++id;pending.set(n,r);socket.send(JSON.stringify({id:n,method,params}))})}
async function ev(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.result.exceptionDetails)throw Error(r.result.exceptionDetails.text);return r.result.result.value}
async function wait(test){for(let n=0;n<100;n++){if(await ev(test))return;await new Promise(r=>setTimeout(r,500))}throw Error('Timeout: '+test)}
await call('Emulation.setDeviceMetricsOverride',{width:1365,height:900,deviceScaleFactor:1,mobile:false});
await wait(`document.readyState==='complete'`);
await wait(`!!document.querySelector('#review-targets')`);
if (!(await ev(`!!document.querySelector('[aria-label="Fictional investor: Robert"]')`))) {
  await ev(`document.querySelector('[aria-label^="Fictional investor:"]').click()`);
  await wait(`[...document.querySelectorAll('[role=option]')].some(e=>e.textContent.includes('Robert'))`);
  await ev(`[...document.querySelectorAll('[role=option]')].find(e=>e.textContent.includes('Robert')).click()`);
  await wait(`!!document.querySelector('[aria-label="Fictional investor: Robert"]')`);
}
await ev(`[...document.querySelectorAll('button')].find(x=>x.textContent.trim()==='Later')?.click()`);
await ev(`window.__initialTargets = document.querySelector('#review-targets').value`);
await ev(`[...document.querySelectorAll('button')].find(x=>x.textContent.includes('Run reviewed analysis')).click()`);
await wait(`document.body.innerText.includes('Inspect execution')`);
await wait(`document.body.innerText.includes('Target policy checks') || document.body.innerText.includes('Open the deterministic comparison')`);
console.log('SCRIPTED GATEWAY: no LLM; real HTTP workflow');
console.log('initial',await ev(`document.body.innerText.includes('Target policy checks') && document.body.innerText.includes('1 tool call(s)')`));
if (!await ev(`document.body.innerText.includes('Target policy checks') && document.body.innerText.includes('1 tool call(s)')`)) throw Error('Missing result or preparation tool receipt');
console.log(await ev('document.body.innerText'));
const successShot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});await fs.writeFile('docs/evidence/parallel/agent-2/target-review-success.png',Buffer.from(successShot.result.data,'base64'));
await ev(`(()=>{const e=document.querySelector('#review-targets');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(e,'XBB.TO 100');e.dispatchEvent(new Event('input',{bubbles:true}));})()`);
await wait(`!document.body.innerText.includes('Target policy checks') && !document.body.innerText.includes('Inspect execution')`);
console.log('PASS editing target clears previously rendered signed run');
await ev(`(()=>{const e=document.querySelector('#review-targets');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(e,window.__initialTargets);e.dispatchEvent(new Event('input',{bubbles:true}));window.__originalFetch=window.fetch;window.fetch=async(...a)=>{const response=await window.__originalFetch(...a);if(String(a[0]).endsWith('/v1/runs') && a[1]?.method==='POST') await new Promise(r=>setTimeout(r,2500));return response;}})()`);
await ev(`[...document.querySelectorAll('button')].find(x=>x.textContent.includes('Run reviewed analysis')).click()`);
await wait(`document.querySelector('#review-targets').disabled`);
await ev(`document.querySelector('[aria-label^="Fictional investor:"]').click()`);
await wait(`[...document.querySelectorAll('[role=option]')].some(e=>e.textContent.includes('Amira'))`);
await ev(`[...document.querySelectorAll('[role=option]')].find(e=>e.textContent.includes('Amira')).click()`);
await wait(`document.querySelector('[aria-label="Fictional investor: Amira"]') && !document.querySelector('#review-targets').disabled`);
await new Promise(r=>setTimeout(r,3000));
if (await ev(`document.body.innerText.includes('Inspect execution') || document.body.innerText.includes('Target policy checks')`)) throw Error('Previous profile run leaked after delayed response');
if (await ev(`document.querySelector('#review-targets').value`)===await ev(`window.__initialTargets`)) throw Error('Profile targets did not reset');
console.log('PASS switching investor during pending request prevents stale signed run');
await ev(`window.fetch=window.__originalFetch`);
console.log('controls',await ev(`JSON.stringify([...document.querySelectorAll('input,button,select,textarea')].map(e=>({id:e.id,text:e.innerText,value:e.value,disabled:e.disabled})))`));
const shot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});await fs.writeFile('docs/evidence/parallel/agent-2/target-review-scripted.png',Buffer.from(shot.result.data,'base64'));
socket.close();
