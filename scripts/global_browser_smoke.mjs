/** Local headless-CDP smoke; start a separate Chrome on port 9224 and the API/web on 8001/3001. No models, AWS writes or fixtures. */
import fs from 'node:fs/promises';
const root=process.env.APLOMB_QA_SITE || 'http://localhost:3001';
const out=process.env.APLOMB_QA_OUTPUT || 'docs/evidence/global-platform';
await fs.mkdir(out,{recursive:true});
const tab=await (await fetch('http://localhost:9224/json/new?about:blank',{method:'PUT'})).json();
const ws=new WebSocket(tab.webSocketDebuggerUrl);
await new Promise(r=>ws.addEventListener('open',r,{once:true}));
let id=0;const pending=new Map();const errors=[];
ws.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.id){pending.get(m.id)?.(m);pending.delete(m.id);}if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text);});
const send=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,m=>m.error?reject(new Error(JSON.stringify(m.error))):resolve(m.result));ws.send(JSON.stringify({id:n,method,params}));});
const evaluate=async expression=>(await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true})).result.value;
const delay=ms=>new Promise(r=>setTimeout(r,ms));
await send('Runtime.enable');await send('Page.enable');
const pages=[];
for(const path of ['/markets/','/risk-intelligence/','/sources/','/portfolio/','/profiles/','/world-explorer/']){
 await send('Page.navigate',{url:root+path});
 for(let i=0;i<30;i++){await delay(1000);if(await evaluate('document.body.innerText.includes("Simulation") && !document.body.innerText.includes("Loading profile")')){if(i>=3)break;}}
 if(path==='/markets/'){
   await evaluate(`Array.from(document.querySelectorAll('button')).find(x=>x.textContent==='SPY')?.click()`);await delay(2000);
 }
 const text=await evaluate('document.body.innerText');
 if(!text.includes('Simulation') || /This site can’t be reached|contract validation|failed to fetch|something went wrong/i.test(text)) throw new Error(`Invalid application page: ${path}`);
 if(path==='/markets/' && !text.includes('Period return')) throw new Error('SPY analytics did not open');
 pages.push({path,text});
 const screenshot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
 await fs.writeFile(`${out}/browser-${path.split('/')[1]||'home'}.png`,Buffer.from(screenshot.data,'base64'));
}
await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
await send('Page.navigate',{url:root+'/markets/'});await delay(3000);
const mobile=await evaluate('JSON.stringify({viewport:innerWidth,scroll:document.documentElement.scrollWidth})');
await fs.writeFile(`${out}/browser.json`,JSON.stringify({pages,errors,mobile:JSON.parse(mobile)},null,2));
if(errors.length || JSON.parse(mobile).scroll>JSON.parse(mobile).viewport) throw new Error('Browser exceptions or document overflow');
console.log(JSON.stringify({pages:pages.map(p=>({path:p.path,chars:p.text.length,errors:p.text.match(/contract validation|upstream unavailable|failed to fetch|something went wrong/ig)})),errors,mobile}));
ws.close();
