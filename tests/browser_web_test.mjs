import fs from 'node:fs/promises';
const base='http://127.0.0.1:8080';
const tab=await fetch('http://127.0.0.1:9223/json/new?about:blank',{method:'PUT'}).then(r=>r.json());
const ws=new WebSocket(tab.webSocketDebuggerUrl);await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
let sequence=0;const pending=new Map();
ws.onmessage=event=>{const m=JSON.parse(event.data);if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}};
const send=(method,params={})=>new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));});
const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value;};
const wait=async(check,seconds=15)=>{const deadline=Date.now()+seconds*1000;while(Date.now()<deadline){if(await check())return;await new Promise(r=>setTimeout(r,150));}throw Error('browser condition timeout');};
await send('Page.enable');await send('Runtime.enable');await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
await send('Page.navigate',{url:base});
await wait(()=>evaluate('document.querySelectorAll("#pickup option:not(:disabled)").length===69'));
const counts=await evaluate('({enabled:document.querySelectorAll("#pickup option:not(:disabled)").length,disabled:document.querySelectorAll("#pickup option:disabled").length})');
if(counts.enabled!==69||counts.disabled!==0)throw Error('incorrect catalog selection limits');
const initial=await fetch(base+'/api/state').then(r=>r.json());
const available=initial.buildings.filter(b=>b.navigation_status==='simulation_dock').map(b=>b.stable_id);
const submitted=[];
// A cyclic permutation covers every building as both pickup and delivery once.
// The complete 4,692-pair protocol and graph checks run separately.
for(let index=0;index<available.length;index++){
 const from=available[index],to=available[(index+17)%available.length];
 const food=`UI验收-${from}-${to}`;
 await evaluate(`document.querySelector('#pickup').value=${JSON.stringify(from)};document.querySelector('#delivery').value=${JSON.stringify(to)};document.querySelector('#food').value=${JSON.stringify(food)};document.querySelector('#quantity').value='1';document.querySelector('#order-form').requestSubmit();`);
 await wait(async()=>{const s=await fetch(base+'/api/state').then(r=>r.json());return s.orders.some(o=>o.session===s.session&&o.food===food);});
 const s=await fetch(base+'/api/state').then(r=>r.json());const order=s.orders.find(o=>o.session===s.session&&o.food===food);submitted.push({key:order.key,id:order.id,from,to,food});
 await wait(()=>evaluate('!document.querySelector("#submit").disabled'));
}
await evaluate("document.querySelector('#pickup').value='B0003';document.querySelector('#delivery').value='B0003';document.querySelector('#order-form').requestSubmit()");
await wait(()=>evaluate('document.querySelector("#error").textContent.includes("必须不同")'));
await evaluate("document.querySelector('[data-page=buildings]').click()");
await wait(()=>evaluate('document.querySelectorAll("#building-list tr").length===69'));
await evaluate("document.querySelector('[data-page=dispatch]').click()");
const screenshot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});
await fs.writeFile('build/validation/web-queued.png',Buffer.from(screenshot.data,'base64'));
await fs.writeFile('build/validation/browser-submit.json',JSON.stringify({tabId:tab.id,counts,submitted,invalidSameEndpointRejected:true},null,2));
console.log(JSON.stringify({submitted:submitted.length,counts,invalidSameEndpointRejected:true,tabId:tab.id}));ws.close();
