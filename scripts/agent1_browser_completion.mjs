/** Real local browser interactions; investor/model inputs are synthetic. No model gateway is used. */
import fs from 'node:fs/promises';
const out='docs/evidence/parallel/agent-1/browser';
await fs.mkdir(out,{recursive:true});
const tab=await (await fetch('http://localhost:9321/json/new?about:blank',{method:'PUT'})).json();
const ws=new WebSocket(tab.webSocketDebuggerUrl);
await new Promise(r=>ws.addEventListener('open',r,{once:true}));
let id=0;const pending=new Map(),errors=[];
ws.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.id){pending.get(m.id)?.(m);pending.delete(m.id);}if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text);if(m.method==='Runtime.consoleAPICalled'&&m.params.type==='error')errors.push(m.params.args.map(a=>a.value||a.description).join(' '));});
const send=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,m=>m.error?reject(new Error(JSON.stringify(m.error))):resolve(m.result));ws.send(JSON.stringify({id:n,method,params}));});
const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value;};
const delay=ms=>new Promise(r=>setTimeout(r,ms));
const wait=async(expression)=>{for(let i=0;i<120;i++){if(await evaluate(expression))return;await delay(250);}throw new Error('Wait failed: '+expression+'\n'+await evaluate('document.body.innerText'));};
const nav=async path=>{await send('Page.navigate',{url:'http://localhost:3101'+path});await wait(`document.readyState==='complete' && !document.body.innerText.includes('Compiling')`);await delay(800);};
const fill=async(selector,text)=>{await evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el)throw new Error('Missing '+${JSON.stringify(selector)});el.scrollIntoView({block:'center'});el.focus();el.select()})()`);await send('Input.insertText',{text});};
const change=async(selector,value)=>evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});if(!el)throw new Error('Missing control');const proto=el instanceof HTMLSelectElement?HTMLSelectElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(proto,'value').set.call(el,${JSON.stringify(value)});el.dispatchEvent(new Event('change',{bubbles:true}));el.dispatchEvent(new Event('input',{bubbles:true}))})()`);
const button=async text=>{const point=await evaluate(`(()=>{const el=[...document.querySelectorAll('button')].find(b=>b.textContent===${JSON.stringify(text)});if(!el)throw new Error('Missing button '+${JSON.stringify(text)});el.scrollIntoView({block:'center'});const r=el.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);await send('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...point});await send('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...point});};
const summary=async text=>evaluate(`(()=>{const el=[...document.querySelectorAll('summary')].find(b=>b.textContent===${JSON.stringify(text)});if(!el)throw new Error('Missing disclosure');el.click()})()`);
const text=()=>evaluate('document.body.innerText');
const shot=async name=>fs.writeFile(`${out}/${name}.png`,Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
await send('Runtime.enable');await send('Page.enable');
await send('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false});
const checks=[];checks.push=(...v)=>{Array.prototype.push.apply(checks,v);console.log(v.join('; '));};

await nav('/portfolio/'); await wait(`!!document.getElementById('joint-start')`);
const selected = await evaluate(`localStorage.getItem('aplomb.pref.profile')`);
await change('#joint-start','2026-11-15');await change('#joint-through','2028-12-31');await fill('#joint-return','0');await fill('#joint-inflation','0');
await fill('#joint-outside','1000000');await fill('#joint-outside-source','Synthetic additional capital for browser acceptance');
await evaluate(`document.querySelector('#joint-outside').closest('fieldset').querySelector('input[type=checkbox]').click()`);
await button('Calculate shared plan and priority alternative');await wait(`document.body.innerText.includes('shared-pool daily compounding')`);
checks.push('Joint chronological and priority model submitted through explicit-input form');
await fill('#account-edit-name','Browser edited account');await button('Save account edit');await wait(`document.querySelector('#account-edit-name')?.value==='Browser edited account'`);
checks.push('Account rename saved through versioned edit form');
const ticker=await evaluate(`document.querySelector('input[id^="quantity-"]:not([id^="quantity-date"]):not([id^="quantity-source"])')?.id.slice(9)`);
if(ticker){await fill('#quantity-'+ticker,'12');await change('#quantity-date-'+ticker,'2026-11-12');await fill('#quantity-source-'+ticker,'Synthetic imported account record');await button('Save documented quantities');await wait(`(async()=>{const r=await fetch('http://localhost:8101/v1/profiles/'+localStorage.getItem('aplomb.pref.profile'),{headers:{'X-Aplomb-Session':localStorage.getItem('aplomb.session')}});const p=await r.json();return p.portfolio.positions.some(x=>x.quantity===12&&x.quantitySource==='Synthetic imported account record')})()`);await button('Inspect saved position inputs');await wait(`document.body.innerText.includes('saved_profile')`);checks.push('Documented quantity retains date/source and exposes modeled value separately');}
await fill('#condition-name','Browser typed limit');await fill('#condition-require-key-0','SPY');await fill('#condition-require-threshold-0','5');await button('Save and evaluate conditional policy');await wait(`document.body.innerText.includes('Browser typed limit')`);checks.push('Typed condition-tree policy saved/evaluated through form');
await nav('/risk-intelligence/');await wait(`!!document.getElementById('liquidity-start')`);
await button('Calculate covariance');await wait(`document.body.innerText.includes('n=')`);checks.push('Covariance matrix or explicit unavailable sample renders via real endpoint');
await change('#liquidity-start','2026-11-15');await change('#liquidity-end','2026-12-31');await button('Calculate permitted sale scenario');await wait(`document.body.innerText.includes('Known net proceeds')`);checks.push('Liquidity form returns unknown holdings without assumed sale liquidity');
await fill('#active-factor-json',JSON.stringify({names:['market'],source:{origin:'user',description:'Synthetic insufficient sample',currency:'EUR',availableAt:'2026-11-12T00:00:00Z'},factors:[]}));await button('Calculate active-portfolio factors');await wait(`document.body.innerText.includes('insufficient data')`);checks.push('Active-portfolio factor UI submits and preserves insufficient-data handling');
const evidence={source_id:'synthetic',url:'https://example.com/synthetic',content_sha256:'a'.repeat(64),available_at:'2024-01-05T00:00:00Z',retrieved_at:'2024-01-06T00:00:00Z',licence:'synthetic'};
await fill('#nested-fund-json',JSON.stringify({asOf:'2026-11-12',historical:false,positions:{US0378331005:1},knownFunds:[],snapshots:[],maxDepth:4}));await button('Calculate nested fund exposure');await wait(`document.body.innerText.includes('Unresolved portfolio weight')`);checks.push('Nested exact-ISIN result inspected through real form');
const widths=[];await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
for(const route of ['/profiles/','/portfolio/','/risk-intelligence/','/decision-desk/']){await nav(route);widths.push({route,configuredViewport:390,...await evaluate(`({viewport:innerWidth,document:document.documentElement.scrollWidth})`)});}
if(widths.some(w=>w.viewport!==390||w.document!==390))throw Error('Mobile overflow '+JSON.stringify(widths));
if(errors.length)throw Error('Browser errors '+JSON.stringify(errors));
await fs.writeFile(`${out}/browser-completion.json`,JSON.stringify({syntheticInputs:true,liveModel:false,checks,widths,errors},null,2));console.log(JSON.stringify({checks,widths,errors}));ws.close();
