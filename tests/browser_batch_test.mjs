import fs from 'node:fs/promises';
const base='http://127.0.0.1:8080';
const prior=JSON.parse(await fs.readFile('build/validation/browser-submit.json','utf8'));
const tab=(await fetch('http://127.0.0.1:9223/json').then(r=>r.json())).find(t=>t.id===prior.tabId);
const ws=new WebSocket(tab.webSocketDebuggerUrl);await new Promise(r=>ws.onopen=r);let sequence=0;const pending=new Map();
ws.onmessage=e=>{const m=JSON.parse(e.data);if(pending.has(m.id)){pending.get(m.id)(m.result);pending.delete(m.id);}};
const send=(method,params={})=>new Promise(r=>{const id=++sequence;pending.set(id,r);ws.send(JSON.stringify({id,method,params}));});
const evaluate=async expression=>(await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true})).result.value;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
await send('Page.reload');
for(let i=0;i<80;i++){if(await evaluate('document.querySelectorAll("#pickup option:not(:disabled)").length===69'))break;await sleep(200);}
const resume=process.argv[2];
const pickup=process.env.QA_PICKUP||'B0019',delivery=process.env.QA_DELIVERY||'B0003';
const food=resume||('默认倍率批量-'+Date.now());
if(!resume)await evaluate(`document.querySelector('#pickup').value=${JSON.stringify(pickup)};document.querySelector('#delivery').value=${JSON.stringify(delivery)};document.querySelector('#food').value=${JSON.stringify(food)};document.querySelector('#quantity').value='3';document.querySelector('#order-form').requestSubmit();`);
let saved={};if(resume)try{saved=JSON.parse(await fs.readFile('build/validation/browser-batch-observations.json','utf8'));}catch{}
let maximum=saved.food===food?saved.maximum:0,movingMaximum=saved.food===food?saved.movingMaximum:0;const traces=new Map();const started=Date.now();let orders=[];let captured=false;
while(Date.now()-started<360000){
 const state=await fetch(base+'/api/state').then(r=>r.json());orders=state.orders.filter(o=>o.food===food);
 maximum=Math.max(maximum,state.cars.filter(c=>orders.some(o=>o.id===c.order_id)).length);
 let moving=0;
 for(const car of state.cars){const old=traces.get(car.id);if(old&&Math.abs(old.x-car.x)+Math.abs(old.y-car.y)>.2&&car.order_id)moving++;traces.set(car.id,car);}
 movingMaximum=Math.max(movingMaximum,moving);
 if(orders.length===3&&!captured&&Date.now()-started>4000){
  const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await fs.writeFile('build/validation/web-active.png',Buffer.from(shot.data,'base64'));captured=true;
 }
 if(orders.length===3&&orders.every(o=>o.status==='DELIVERED'))break;
 if(orders.some(o=>['REJECTED','INTERRUPTED'].includes(o.status)))throw Error('order failed');
 await sleep(1000);
}
await fs.writeFile('build/validation/browser-batch-observations.json',JSON.stringify({food,maximum,movingMaximum}));
if(orders.length!==3||!orders.every(o=>o.status==='DELIVERED')||maximum!==3||movingMaximum<2)throw Error(JSON.stringify({orders,maximum,movingMaximum}));
await sleep(1400);
await evaluate("document.querySelector('#filter').value='done';document.querySelector('#filter').dispatchEvent(new Event('change'));document.querySelector('#quantity').value='1';");
const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await fs.writeFile('build/validation/web-completed.png',Buffer.from(shot.data,'base64'));
const result={result:'passed',timescale:1,batch_count:3,max_active_cars:maximum,max_moving_cars:movingMaximum,elapsed_seconds:(Math.max(...orders.map(o=>o.updated_ms))-Math.min(...orders.map(o=>o.created_ms)))/1000,orders};await fs.writeFile('build/validation/browser-batch-result.json',JSON.stringify(result,null,2));
console.log(JSON.stringify({...result,orders:orders.map(o=>({id:o.id,status:o.status,car_id:o.car_id}))}));ws.close();
