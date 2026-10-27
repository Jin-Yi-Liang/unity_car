const $ = s => document.querySelector(s);
const STATUS = {QUEUED:'排队中',ASSIGNED:'前往取餐',PICKUP:'配送中',DELIVERED:'已送达',REJECTED:'无法执行',REQUEUED:'重新排队',INTERRUPTED:'服务重启中断'};
const ACTIVE = new Set(['QUEUED','REQUEUED','ASSIGNED','PICKUP']);
let state = {orders:[],cars:[],buildings:[]}, initialized = false, busy = false;
const escape = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const badge = s => `<span class="state ${escape(s)}">${STATUS[s] || escape(s)}</span>`;
function message(kind,text){$('#'+kind).textContent=text;$('#'+kind).hidden=!text;}
function time(ms){return new Date(ms).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'});}
function populate(){
 const available=state.buildings.filter(b=>b.navigation_status==='simulation_dock');
 const other=state.buildings.filter(b=>b.navigation_status!=='simulation_dock');
 const options=available.map(b=>`<option value="${b.stable_id}">${b.stable_id} · ${escape(b.display_name)}</option>`).join('')+
 '<optgroup label="尚未配置停靠点（仅供查询）">'+other.map(b=>`<option disabled value="${b.stable_id}">${b.stable_id} · ${escape(b.display_name)} — 不可下单</option>`).join('')+'</optgroup>';
 $('#pickup').innerHTML=options;$('#delivery').innerHTML=options;
 $('#pickup').value='B0019';$('#delivery').value='B0003';
 initialized=true;
}
function render(){
 if(!initialized&&state.buildings.length)populate();
 $('#connection').textContent=state.online?'● 后端已连接':'● 后端未连接';
 $('#connection').className='connection '+(state.online?'online':'offline');
 $('#total-count').textContent=state.orders.length;
 $('#active-count').textContent=state.orders.filter(o=>ACTIVE.has(o.status)).length;
 $('#done-count').textContent=state.orders.filter(o=>o.status==='DELIVERED').length;
 $('#car-count').textContent=state.cars.length;
 $('#submit').disabled=busy||!state.online;
 $('#fleet-list').innerHTML=state.cars.length?state.cars.slice().sort((a,b)=>a.id-b.id).map(c=>{
  const order=state.orders.find(o=>o.session===state.session&&o.id===c.order_id);
  return `<article class="vehicle" data-car-id="${c.id}"><div class="vehicle-icon">▰</div><div><h3>CAR ${c.id.toString().padStart(2,'0')}</h3><p>${order?'订单 #'+order.id+' → '+escape(order.delivery_name):'等待新任务'}</p><p>地图坐标 ${c.has_position?Number(c.x).toFixed(1)+', '+Number(c.y).toFixed(1):'同步中'}</p></div>${badge(order?order.status:'空闲')}</article>`;
 }).join(''):'<div class="empty">尚无车辆连接，请在团结中按 Play。</div>';
 const filter=$('#filter').value;
 const orders=state.orders.filter(o=>filter==='all'||(filter==='active'&&ACTIVE.has(o.status))||(filter==='done'&&o.status==='DELIVERED')||(filter==='failed'&&['REJECTED','INTERRUPTED'].includes(o.status)));
 $('#order-list').innerHTML=orders.map(o=>`<tr data-order-key="${escape(o.key)}" data-status="${o.status}"><td><strong>#${o.id} ${o.priority?'· 优先':''}</strong><small>${escape(o.food)}</small></td><td><strong>${escape(o.pickup_name)} <span class="route">→</span> ${escape(o.delivery_name)}</strong><small>${escape(o.pickup_id)} → ${escape(o.delivery_id)}</small></td><td>${badge(o.status)}</td><td>${o.car_id?'CAR '+o.car_id:'—'}</td><td>${time(o.created_ms)}</td></tr>`).join('');
 $('#orders-empty').hidden=orders.length>0;
 renderBuildings();
}
function renderBuildings(){const query=$('#building-search').value.trim().toLowerCase();$('#building-list').innerHTML=state.buildings.filter(b=>(b.stable_id+' '+b.display_name).toLowerCase().includes(query)).map(b=>`<tr><td><strong>${b.stable_id}</strong></td><td>${escape(b.display_name)}</td><td>${escape(b.map_label)}</td><td>${b.navigation_status==='simulation_dock'?'<span class="state DELIVERED">可下单</span>':'<span class="state">未配置停靠点</span>'}</td></tr>`).join('');}
async function refresh(){try{const res=await fetch('/api/state',{cache:'no-store'});if(!res.ok)throw Error('Web 服务响应异常');state=await res.json();render();}catch(e){$('#connection').textContent='● Web 连接中断';$('#connection').className='connection offline';$('#submit').disabled=true;}}
$('#order-form').addEventListener('submit',async event=>{
 event.preventDefault();if(busy)return;message('success','');message('error','');
 const pickup=$('#pickup').value,delivery=$('#delivery').value,quantity=Number($('#quantity').value);
 if(pickup===delivery){message('error','取餐地点和送达地点必须不同');return;}
 if(!Number.isInteger(quantity)||quantity<1||quantity>8){message('error','一次可发送 1～8 笔订单');return;}
 busy=true;render();message('error','');message('success','');
 let sent=0;
 try{
  for(let i=0;i<quantity;i++){
   const result=await fetch('/api/orders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pickup_id:pickup,delivery_id:delivery,food:$('#food').value,priority:Number($('#priority').value),request_key:(crypto.randomUUID?crypto.randomUUID():Date.now()+"-"+Math.random().toString(16).slice(2))})});
   const data=await result.json();if(!result.ok)throw Error(data.error||'下单失败');sent++;
  }
  message('success',`已发送 ${sent} 笔订单，空闲车辆将自动接单。`);
 }catch(e){message('error',`${sent?'已成功发送 '+sent+' 笔；其余未发送。':''}${e.message}`);}
 finally{busy=false;await refresh();}
});
$('#swap').onclick=()=>{const a=$('#pickup').value;$('#pickup').value=$('#delivery').value;$('#delivery').value=a;};
$('#filter').onchange=render;$('#building-search').oninput=renderBuildings;
for(const button of document.querySelectorAll('.nav'))button.onclick=()=>{for(const item of document.querySelectorAll('.nav'))item.classList.toggle('active',item===button);$('#dispatch-page').hidden=button.dataset.page!=='dispatch';$('#buildings-page').hidden=button.dataset.page!=='buildings';$('#page-title').textContent=button.dataset.page==='dispatch'?'配送工作台':'建筑目录';};
refresh();setInterval(refresh,1000);
