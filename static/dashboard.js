'use strict';
const $ = id => document.getElementById(id);
const names = {pi:'PI · realimentación',pi_ff_literal:'PI + FF literal',pi_ff_nominal:'PI + FF sostenido'};
const colors = {pi:'#355a82',pi_ff_literal:'#d69a39',pi_ff_nominal:'#148e79'};
const strategies = Object.keys(names);
let results=null, busy=false, charts={};
let playback=null;
const fmt = (x,d=2) => Number(x).toLocaleString('es-PE',{minimumFractionDigits:d,maximumFractionDigits:d});
for(let i=0;i<3;i++){
  const row=document.createElement('div'); row.className='tune-row';
  row.innerHTML=`<span>C${i+1}</span><input id="kc${i}" type="number" max="-0.0001" step="any" value="${[-62,-76,-85][i]}" aria-label="Kc celda ${i+1}" required><input id="ti${i}" type="number" min="0.1" step="any" value="${[56,30,44][i]}" aria-label="Tiempo integral celda ${i+1}" required><input id="ff${i}" type="number" min="0" max="1" step="0.01" value="${[.8,.8,1][i]}" aria-label="Ganancia feedforward celda ${i+1}" required>`;
  $('tuning-fields').appendChild(row);
}
const labels=document.createElement('div');labels.className='tune-row tune-labels';labels.innerHTML='<span></span><span>Kc</span><span>τI [s]</span><span>Kff</span>';$('tuning-fields').prepend(labels);
async function api(path,data){
  const response=await fetch(path,{method:data===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});
  const body=await response.json();if(!response.ok)throw new Error(body.error||'No se pudo completar la solicitud.');return body;
}
function configuration(){
  const feed=+$('feed').value,step=+$('step').value;
  if(feed+step<0)throw new Error('La perturbación produciría un caudal de alimentación negativo.');
  return {duration:+$('duration').value,plant:$('plant').value,feed_nominal:feed,noise_std_cm:+$('noise').value,
    setpoint_events:[0,1,2].map(i=>[180,i,+$('sp'+(i+1)).value]),feed_events:[[300,feed+step],[450,feed]],
    kc:[0,1,2].map(i=>+$('kc'+i).value),ti:[0,1,2].map(i=>+$('ti'+i).value),kff:[0,1,2].map(i=>+$('ff'+i).value)};
}
function notice(message,error=false){$('notice').textContent=message;$('notice').classList.toggle('error',error);}
async function run(){
  if(busy||!$('config').reportValidity())return;
  stopPlayback();busy=true;$('run').disabled=true;$('run').textContent='Calculando en Python…';$('run-state').textContent='Calculando';
  try{
    const next=await api('/api/compare',configuration()); results=next; render();$('export').disabled=false;
  }catch(error){notice(error.message,true);$('run-state').textContent='Error';}
  finally{busy=false;$('run').disabled=false;$('run').innerHTML='Ejecutar simulación <span>↗</span>';}
}
function render(){
  const r=results.pi_ff_nominal, last=r.records.at(-1);
  $('time-slider').max=r.records.length-1;$('time-slider').value=r.records.length-1;snapshot();
  const total=r.metrics.reduce((a,m)=>a+m.iae,0),base=results.pi.metrics.reduce((a,m)=>a+m.iae,0);
  const complete=strategies.every(s=>results[s].status==='completed');
  $('total-iae').innerHTML=fmt(total,2)+'<small> cm·s</small>';
  const improvement=base>1e-12?100*(base-total)/base:null;
  $('improvement').innerHTML=(complete&&improvement!==null?fmt(improvement,1):'—')+'<small> %</small>';
  $('improvement-note').textContent=complete?(improvement===null?'PI tiene error acumulado cero':'IAE total de las tres celdas'):'Horizontes distintos: no comparar';
  $('horizon').innerHTML=fmt(last.time,0)+'<small> s</small>';
  $('completion-note').textContent=r.status==='completed'?'Simulación completada':'Interrumpida por límite de nivel';
  $('sample-info').textContent='Δt '+r.config.dt+' s · '+r.records.length+' muestras';
  $('run-state').textContent=complete?'Cálculo completado':'Límite físico alcanzado';$('run-state').classList.toggle('warn',!complete);
  $('metrics-table').replaceChildren();
  const totals=strategies.map(s=>results[s].metrics.reduce((a,m)=>a+m.iae,0));
  const best=complete?strategies[totals.indexOf(Math.min(...totals))]:null;
  $('strategy-bars').replaceChildren();
  for(const s of strategies){
    const item=results[s],tr=document.createElement('tr');if(s===best)tr.className='best';
    const label=document.createElement('td');label.innerHTML=`<i class="legend-dot ${s==='pi'?'navy':s==='pi_ff_literal'?'amber':'teal'}"></i>`;label.append(document.createTextNode(names[s]+(item.status!=='completed'?' · parcial':'')));tr.appendChild(label);
    for(const m of item.metrics){const td=document.createElement('td');td.textContent=fmt(m.iae);tr.appendChild(td);}
    const td=document.createElement('td');td.textContent=fmt(item.metrics.reduce((a,m)=>a+m.total_variation,0),1);tr.appendChild(td);$('metrics-table').appendChild(tr);
    const sum=totals[strategies.indexOf(s)],bar=document.createElement('div');bar.className='strategy-summary';
    bar.innerHTML=`<header><span>${s==='pi'?'PI':s==='pi_ff_literal'?'FF literal':'FF sostenido'}</span><strong>${fmt(sum,1)}</strong></header><div class="strategy-track"><div class="strategy-fill"></div></div><small>${s===best?'Menor error acumulado':complete?'IAE total · cm·s':'IAE parcial · cm·s'}</small>`;
    bar.querySelector('.strategy-fill').style.width=(Math.max(...totals)>0?sum/Math.max(...totals)*100:0)+'%';bar.querySelector('.strategy-fill').style.background=colors[s];$('strategy-bars').appendChild(bar);
  }
  if(!complete){const endings=strategies.filter(s=>results[s].status!=='completed').map(s=>names[s]+' ('+fmt(results[s].boundary_event.time,0)+' s)');notice('Cálculo detenido al superar el intervalo físico de nivel 0–45 cm: '+endings.join(', ')+'. Los IAE parciales no son directamente comparables. Revisa la sintonización.',true);}
  else notice('Simulación completada en Python. Escenario ilustrativo con filtro causal de 10 muestras, saturación y anti-windup. Los valores no son una reproducción exacta de los IAE del artículo.');
  drawCharts();
}
function snapshot(){
  if(!results)return;const r=results.pi_ff_nominal, row=r.records[+$('time-slider').value];
  $('feed-display').textContent=fmt(row.feed,1);
  $('snapshot-time').textContent='Instantánea · t = '+fmt(row.time,0)+' s';
  $('playback-time').textContent=fmt(row.time,0)+' / '+fmt(r.records.at(-1).time,0)+' s';
  for(let i=0;i<3;i++){
    const tank=$('tank'+(i+1));tank.querySelector('.liquid').style.height=(row.level[i]/45*100)+'%';
    tank.querySelector('.setpoint-marker').style.bottom=(row.setpoint[i]/45*100)+'%';
    tank.querySelector('.tank-level').innerHTML=fmt(row.level[i],2)+'<small>cm</small>';
    $('q'+(i+1)).textContent='Q '+fmt(row.outflow[i],1)+' L/min';
    tank.setAttribute('aria-label','Celda '+(i+1)+': '+fmt(row.level[i],2)+' centímetros; consigna '+fmt(row.setpoint[i],1));
  }
}
function stopPlayback(){if(playback)clearInterval(playback);playback=null;$('play').textContent='▶';$('play').setAttribute('aria-label','Reproducir evolución de las celdas');}
function plot(id,series,unit){
  const canvas=$(id), rect=canvas.getBoundingClientRect(), ratio=window.devicePixelRatio||1;
  if(!rect.width)return;
  canvas.width=Math.round(rect.width*ratio);canvas.height=Math.round(rect.height*ratio);
  const ctx=canvas.getContext('2d');ctx.scale(ratio,ratio);const w=rect.width,h=rect.height;
  const box={left:43,top:17,right:w-13,bottom:h-27};
  ctx.font='10px Segoe UI';
  if(!series.length){ctx.fillStyle='#91a2a9';ctx.textAlign='center';ctx.fillText('Los resultados aparecerán aquí',w/2,h/2);return;}
  let low=Infinity,high=-Infinity,xmax=1;
  for(const s of series)for(const p of s.points){low=Math.min(low,p[1]);high=Math.max(high,p[1]);xmax=Math.max(xmax,p[0]);}
  const pad=Math.max((high-low)*.16,unit==='cm'?.3:3);low-=pad;high+=pad;
  if(unit!=='cm')low=Math.max(0,low);
  const x=v=>box.left+v/xmax*(box.right-box.left),y=v=>box.bottom-(v-low)/(high-low)*(box.bottom-box.top);
  if(unit==='cm'){
    ctx.fillStyle='#f4f8faff';ctx.fillRect(x(180),box.top,Math.max(0,x(Math.min(300,xmax))-x(180)),box.bottom-box.top);
    ctx.fillStyle='#f8f7f2';if(xmax>300)ctx.fillRect(x(300),box.top,x(Math.min(450,xmax))-x(300),box.bottom-box.top);
  }
  ctx.strokeStyle='#e8eeee';ctx.lineWidth=1;ctx.textAlign='right';ctx.fillStyle='#8b9ba2';
  for(let k=0;k<=4;k++){let value=low+(high-low)*k/4,py=y(value);ctx.beginPath();ctx.moveTo(box.left,py);ctx.lineTo(box.right,py);ctx.stroke();ctx.fillText(fmt(value,unit==='cm'?1:0),box.left-8,py+3);}
  ctx.textAlign='center';for(let k=0;k<=6;k++){let value=xmax*k/6;ctx.fillText(fmt(value,0),x(value),h-9);}
  ctx.textAlign='left';ctx.fillText(unit,2,9);
  ctx.save();ctx.beginPath();ctx.rect(box.left,box.top,box.right-box.left,box.bottom-box.top);ctx.clip();
  for(const s of series){ctx.beginPath();ctx.strokeStyle=s.color;ctx.lineWidth=s.dash?1.3:2;ctx.setLineDash(s.dash?[5,4]:[]);s.points.forEach((p,j)=>{if(j===0)ctx.moveTo(x(p[0]),y(p[1]));else ctx.lineTo(x(p[0]),y(p[1]));});ctx.stroke();}
  ctx.restore();
  ctx.setLineDash([]);charts[id]={box,xmax};
}
function drawCharts(){
  if(!results){plot('level-chart',[],'cm');plot('flow-chart',[],'L/min');return;}
  const cell=+$('cell').value;
  const levels=strategies.map(s=>({color:colors[s],points:results[s].records.map(r=>[r.time,r.level[cell]])}));
  levels.push({color:'#8c9ba8',dash:true,points:results.pi.records.map(r=>[r.time,r.setpoint[cell]])});
  plot('level-chart',levels,'cm');
  const rows=results.pi_ff_nominal.records;
  plot('flow-chart',[{color:'#168c7c',points:rows.map(r=>[r.time,r.outflow[cell]])},{color:'#9aabba',dash:true,points:rows.map(r=>[r.time,r.inlet[cell]])}],'L/min');
}
$('config').addEventListener('submit',e=>{e.preventDefault();run();});
$('cell').addEventListener('change',drawCharts);
$('time-slider').addEventListener('input',()=>{stopPlayback();snapshot();});
$('to-end').addEventListener('click',()=>{stopPlayback();$('time-slider').value=$('time-slider').max;snapshot();});
$('play').addEventListener('click',()=>{
  if(!results)return;if(playback){stopPlayback();return;}
  if(+$('time-slider').value>=+$('time-slider').max)$('time-slider').value=0;
  $('play').textContent='Ⅱ';$('play').setAttribute('aria-label','Pausar evolución');snapshot();
  playback=setInterval(()=>{const range=$('time-slider');range.value=Math.min(+range.max,+range.value+3);snapshot();if(+range.value>=+range.max)stopPlayback();},60);
});
document.querySelectorAll('[data-preset]').forEach(button=>button.addEventListener('click',()=>{
  $('config').reset();const preset=button.dataset.preset;
  if(preset==='disturbance'){[30,34,33].forEach((v,i)=>$('sp'+(i+1)).value=v);$('step').value=12;}
  if(preset==='noise')$('noise').value=0.08;
  document.querySelectorAll('[data-preset]').forEach(b=>{b.classList.toggle('selected',b===button);b.setAttribute('aria-pressed',b===button?'true':'false');});
  $('model-help').textContent='Ganancia integradora: 0.001018 cm/s por L/min.';$('tune-note').textContent='';markDirty();
}));
function markDirty(){if(!results||busy)return;stopPlayback();$('run-state').textContent='Cambios sin simular';$('run-state').classList.add('warn');$('export').disabled=true;notice('Los gráficos muestran la última ejecución. Ejecuta la simulación para aplicar los cambios.');}
$('config').addEventListener('input',event=>{if(event.target.matches('input,select')){document.querySelectorAll('[data-preset]').forEach(b=>{b.classList.remove('selected');b.setAttribute('aria-pressed','false');});markDirty();}});
$('config').addEventListener('change',event=>{if(event.target.matches('select'))markDirty();});
$('plant').addEventListener('change',()=>{$('model-help').textContent=$('plant').value==='published'?'Ganancia integradora: 0.001018 cm/s por L/min.':'Balance geométrico: 0.018519 cm/s por L/min. Requiere sintonización propia.';$('tune-note').textContent='';});
$('reset-config').addEventListener('click',()=>{$('config').reset();$('model-help').textContent='Ganancia integradora: 0.001018 cm/s por L/min.';$('tune-note').textContent='';document.querySelectorAll('[data-preset]').forEach(b=>b.classList.toggle('selected',b.dataset.preset==='reference'));markDirty();});
$('simc').addEventListener('click',async()=>{
  try{const b=$('plant').value==='published'?0.001018:1000/(60*900);
    const values=await Promise.all([7,6,3].map(delay=>api('/api/tune',{k_prime:-b,delay_s:delay,tau_c_s:Math.max(15,delay)})));
    values.forEach((v,i)=>{$('kc'+i).value=v.kc.toFixed(4);$('ti'+i).value=v.ti_s;});
    $('tune-note').textContent='SIMC calculado en Python con τc = 15 s. Punto de partida; valida la respuesta antes de interpretarla.';
    markDirty();
  }catch(e){notice(e.message,true);}
});
$('export').addEventListener('click',()=>{
  if(!results)return;
  const lines=['strategy,time_s,cell,level_cm,setpoint_cm,outflow_lpm,inlet_lpm,filtered_cm'];
  for(const s of strategies)for(const r of results[s].records)for(let i=0;i<3;i++)lines.push([s,r.time,i+1,r.level[i],r.setpoint[i],r.outflow[i],r.inlet[i],r.filtered[i]].join(','));
  const url=URL.createObjectURL(new Blob([lines.join('\r\n')],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='flotacion-comparacion.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
$('level-chart').addEventListener('pointermove',event=>{
  if(!results||!charts['level-chart'])return;const chart=charts['level-chart'],rect=event.currentTarget.getBoundingClientRect();
  const t=Math.max(0,Math.min(chart.xmax,(event.clientX-rect.left-chart.box.left)/(chart.box.right-chart.box.left)*chart.xmax));
  const i=+$('cell').value;const lines=['t = '+fmt(t,0)+' s'];
  for(const s of strategies){const rows=results[s].records,index=Math.round(t/results[s].config.dt);if(index<rows.length)lines.push(names[s]+': '+fmt(rows[index].level[i])+' cm');}
  const tip=$('level-tooltip');tip.textContent=lines.join('\n');tip.style.whiteSpace='pre';tip.style.left=Math.min(rect.width-195,Math.max(0,event.clientX-rect.left+10))+'px';tip.style.top='12px';tip.hidden=false;
});
$('level-chart').addEventListener('pointerleave',()=>{$('level-tooltip').hidden=true;});
new ResizeObserver(drawCharts).observe($('level-chart').parentElement);
async function init(){
  drawCharts();try{await api('/health');$('connection').innerHTML='<span class="status-dot"></span> Motor Python conectado';await run();}catch(e){$('connection').textContent='Motor no disponible';notice('No se pudo conectar con el servidor Python. '+e.message,true);}
}init();

