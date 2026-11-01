'use strict';
const $ = id => document.getElementById(id);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state = {config:null,run:null,sheet:null,busy:false,recording:null,audio:null,pending:null};
async function api(path, body, timeout=90000) {
  const r = await fetch(path, {method:body === undefined?'GET':'POST', headers:body === undefined?{}:{'Content-Type':'application/json'}, body:body===undefined?undefined:JSON.stringify(body), signal:AbortSignal.timeout(timeout)});
  const d = await r.json(); if(!r.ok) throw new Error(d.error || '操作失败'); return d;
}
function error(e) { $('error').textContent=e.message || String(e); $('error').hidden=false; }
function clearError() { $('error').hidden=true; }
async function busy(fn) {
  if(state.busy) return;
  state.busy=true; clearError(); $('notice').textContent='正在处理，请稍候…';
  document.querySelectorAll('button').forEach(b=>b.disabled=true);
  try {await fn();} catch(e) {error(e);} finally {
    state.busy=false; document.querySelectorAll('button').forEach(b=>b.disabled=false);
    $('voice-start').disabled=!window.MedRepVoice?.isReady()||state.run?.state!=='active';
    if($('notice').textContent==='正在处理，请稍候…')$('notice').textContent='';
  }
}
function tab(name) {
  clearError();
  for(const n of ['learn','visit','history']) {$(n+'-panel').hidden=n!==name; $(n+'-tab').setAttribute('aria-pressed',String(n===name));}
  $('practice-panel').hidden=true; stopAudio(); cancelRecording();
}
function sources(items) {
  return '<div class="source-list">'+items.map(x=>{
    let title=esc(x.title); if(/^https?:\/\//.test(x.url||'')) title=`<a href="${esc(x.url)}" target="_blank" rel="noopener noreferrer">${title} ↗</a>`;
    return `<p>${title} · ${esc(x.locator||'')} · ${esc(x.status)}</p>`;
  }).join('')+'</div>';
}
let lessonLoad = 0;
async function renderLesson() {
  const generation = ++lessonLoad;
  const d = await api('/api/courses/'+encodeURIComponent($('lesson-select').value));
  if(generation!==lessonLoad)return;
  state.material=d;
  $('lesson').innerHTML=MaterialUI.render(d);
  $('search-results').innerHTML='';
  revealMaterialHash();
}
function revealMaterialHash(){
  if(!location.hash)return;
  let id;try{id=decodeURIComponent(location.hash.slice(1));}catch{return;}
  const target=document.getElementById(id);if(!target)return;
  if(target.matches('details'))target.open=true;
  target.scrollIntoView({block:'start'});
}
addEventListener('hashchange',revealMaterialHash);
function reviewLink(s) {return 'http://127.0.0.1:3302/?sourceKind=sheets&sourceId='+encodeURIComponent(s.id);}
function renderSheet() {
  const s=state.sheet;if(!s)return;
  const frozen=s.forecast?.status==='FROZEN';const selected=new Set(s.forecast?.selected_ids||[]);
  const points=s.priorities||[];
  $('sheet').innerHTML=`<h2>${esc(s.visit.title)}</h2><p class="goal">本次目标：${esc(s.visit.goal)}</p>
    <p class="lesson-notice">${esc(s.notice)}</p>
    ${s.method_offer?`<details><summary>本次方法使用情况</summary><p>${esc(s.method_application?.reason||'未采用')} · 测试方法版本 ${esc(s.method_offer.version)}</p></details>`:''}
    <section class="forecast-card"><h3>${frozen?'访前先验预测 · 已冻结':'第 1 步 · 访前候选预测（待确认）'}</h3>
    <p>${frozen?'这份候选及选中重点已于 '+new Date(s.forecast.frozen_at*1000).toLocaleString('zh-CN')+' 冻结，访后不能重写。':'这些是依据当前背景与课程资料生成的候选，不是医生必问；请在真实拜访之前选定准备重点并冻结。'}</p>
    ${!frozen?'<p class="muted">勾选你决定优先准备的问题；未选中的候选也会保留，供拜访后检验选题取舍。</p>':''}
    ${points.map(p=>`<div class="forecast-choice"><label>${frozen?`<strong>${selected.has(p.id)?'✓ 已选重点':'· 原候选未选'}</strong>`:`<input type="checkbox" data-select-forecast="${esc(p.id)}" ${selected.has(p.id)?'checked':''}>`}
      <span><b>${esc(p.title)}</b><small>${esc(p.question||'问题待确认')}</small></span></label><p>${esc(p.why)}</p><details><summary>预测依据</summary><small>${esc((p.fact_ids||[]).join('、')||'依据待核对')}</small></details>
      <button data-practice="${esc(p.id)}" class="quiet">根据这一问题试练</button></div>`).join('')}
    ${!frozen?`<label class="forecast-attest"><input id="previsit-ack" type="checkbox">我确认真实拜访尚未发生，现在保存的是访前判断</label><button id="freeze-forecast" type="button">冻结预测并保留全部候选 ↗</button>`:`<p class="lesson-notice">已选 ${selected.size} 项 · 原始候选 ${points.length} 项 · 资料版本 ${esc(s.forecast.lesson_revision?.slice(0,12)||'未知')}</p><a class="flow-link" href="${reviewLink(s)}">真实拜访结束后，带着这份预测进入模块二复盘 →</a>`}</section>
    <details><summary>已知背景与原始依据</summary>${s.visit.facts.map(f=>`<div class="context-fact">${esc(f.text)}<div class="muted">${esc(f.id)} · ${esc(f.source)} · ${esc(f.status)}</div></div>`).join('')}</details>
    <details><summary>会面提醒和待确认事项</summary><h3>提醒</h3><ul>${s.reminders.map(x=>`<li>${esc(x)}</li>`).join('')}</ul><h3>仍需核实</h3><ul>${s.unknowns.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></details>
    ${s.practice_results.length?'<details><summary>访前试练后补充</summary>'+s.practice_results.map(r=>`<p><b>${esc(r.title)}</b> ${esc(r.feedback)} · ${esc(r.focus)}</p>`).join('')+'</details>':''}`;
  $('sheet').querySelectorAll('[data-practice]').forEach(b=>b.onclick=()=>busy(async()=>openRun(await api('/api/runs',{mode:'visit',sheet_id:s.id,option_id:b.dataset.practice}))));
  if(!frozen)$('freeze-forecast').onclick=()=>busy(async()=>{
    const ids=[...$('sheet').querySelectorAll('[data-select-forecast]:checked')].map(x=>x.dataset.selectForecast);
    if(!ids.length)throw new Error('至少选中一个准备重点。');
    if(!$('previsit-ack').checked)throw new Error('请确认这是真实拜访前的判断；访后不得补记先验预测。');
    state.sheet=await api('/api/sheets/'+encodeURIComponent(s.id)+'/freeze',{selected_ids:ids,previsit_confirmed:true});
    renderSheet();await listSheets();$('notice').textContent='访前预测已冻结。拜访后请从这份任务进入复盘。';
  });
}
async function listSheets(){const d=await api('/api/sheets');$('sheet-list').innerHTML=d.sheets.length?d.sheets.map(s=>`<div class="history-row"><div><b>${esc(s.doctor)}</b><p class="muted">${esc(s.goal)} · ${s.forecast_status==='FROZEN'?'预测已冻结':'预测未冻结'}</p></div><button data-sheet="${esc(s.id)}" class="quiet">打开</button></div>`).join(''):'<p class="muted">还没有访前任务；可以先从搜索医生开始，也可以直接填写背景。</p>';
 $('sheet-list').querySelectorAll('[data-sheet]').forEach(b=>b.onclick=()=>busy(async()=>{state.sheet=await api('/api/sheets/'+encodeURIComponent(b.dataset.sheet));renderSheet();$('sheet').scrollIntoView({block:'start',behavior:'smooth'});}));}
function openRun(run) {
  cancelRecording();stopAudio();
  state.run=run;localStorage.setItem('medrep-last-run',run.id);$('practice-panel').hidden=false;
  $('practice-title').textContent=(run.mode==='learn'?'应用练习 · ':'访前试练 · ')+run.title;
  $('practice-meta').textContent=`第 ${run.attempt} 次尝试 · ${run.source_status==='fictional_test_material'?'虚构材料验证':'候选资料，仅作行为初评'}${run.support_used?' · 本次看过提示':''} · 医学准确性 NA`;
  $('transcript').innerHTML=run.transcript.map(m=>`<div class="bubble ${m.role==='药代'?'rep':''}"><strong>${esc(m.role)}</strong>${esc(m.text)}</div>`).join('');
  $('answer-form').hidden=run.state!=='active';$('retry-error').hidden=!['retryable','evaluating'].includes(run.state);
  $('retry-btn').hidden=run.state!=='review';$('correct-btn').hidden=!run.transcript.some(m=>m.role==='药代');
  $('return-sheet').hidden=!run.sheet_id;
  $('feedback').innerHTML=run.review?`<h3>这次回答的反馈</h3><p>${esc(run.review.feedback)}</p>${run.review.observations.map(o=>`<div class="observation"><b>${esc(({demonstrated:'本次已体现',needs_work:'还有遗漏',uncertain:'待核实'})[o.status])}</b> · ${esc(o.reason)}${o.quote?`<details><summary>查看原话依据</summary><blockquote>${esc(o.quote)}</blockquote><small class="muted">${o.source_ids.map(id=>{const b=run.material?.blocks.find(x=>x.id===id);return b?`<a href="#run-material-${esc(b.locator)}" data-material-ref>${esc(b.title)}</a>`:esc(id);}).join('、')}</small></details>`:''}</div>`).join('')}<p>下一步：${esc(run.review.focus)}</p><p class="muted">本次${run.support_used?'使用过提示，不能视为独立完成':'表现仅用于安排练习'}；不输出总分或永久掌握结论。</p>`:'';
  $('support').hidden=true;$('answer').value='';
  if(run.material)$('support').innerHTML=MaterialUI.render(run.material,'run-material-');
  $('finish-btn').hidden=run.state!=='active' || !run.transcript.some(m=>m.role==='药代');
  $('feedback').querySelectorAll('[data-material-ref]').forEach(a=>a.onclick=()=>{$('support').hidden=false;});
  window.MedRepVoice?.bind(run);
  $('practice-panel').scrollIntoView({behavior:'smooth',block:'start'});
}
async function submitAnswer(payload) {
  await window.MedRepVoice?.stop();
  try { const r=await api('/api/runs/'+state.run.id+'/answer',payload);state.pending=null;openRun(r); }
  catch(e) {state.pending=payload;try {openRun(await api('/api/runs/'+state.run.id));}catch(_){}throw e;}
}
function stopAudio(){window.MedRepVoice?.stop();if(state.audio){state.audio.pause();URL.revokeObjectURL(state.audio.src);state.audio=null;}}
function cancelRecording(){} // Voice lifecycle is owned by the LiveKit client.
async function history(){
  const d=await api('/api/history');$('history').innerHTML=d.runs.length?d.runs.map(r=>`<div class="history-row"><div><b>${esc(r.title)}</b><p class="muted">${esc(r.mode==='learn'?'学习练习':'访前试练')} · 第${r.attempt}次 · ${esc(({active:'进行中',retryable:'反馈待重试',review:'本轮已完成',evaluating:'待继续'})[r.state])}</p></div><button data-open="${esc(r.id)}" class="quiet">继续查看</button></div>`).join(''):'<p>还没有练习记录。</p>';
  $('history').querySelectorAll('[data-open]').forEach(b=>b.onclick=()=>busy(async()=>openRun(await api('/api/runs/'+b.dataset.open))));
}
async function init(){
  state.config=await api('/api/config');$('model-status').textContent=state.config.test_mode?'自动测试模式 · 模型为测试替身':state.config.model.ready?'模型已连接 · '+state.config.model.model:'未连接模型 · 可以阅读与整理资料';
  $('lesson-select').innerHTML=state.config.lessons.filter(x=>x.id!=='visit-communication').map(d=>`<option value="${esc(d.id)}">${esc(d.title)}${d.id==='demo-evidence'?'（虚构验证材料）':''}</option>`).join('');
  const requested=new URLSearchParams(location.search).get('lesson');
  if(requested&&state.config.lessons.some(x=>x.id===requested))$('lesson-select').value=requested;
  else $('lesson-select').value='D-NSCLC__CE';
  await renderLesson();
  $('visit-lesson').innerHTML+=$('lesson-select').innerHTML.replace(/<option value="demo-evidence">.*?<\/option>/,'');
  $('lesson-select').onchange=()=>renderLesson().catch(error);
  const incoming=new URLSearchParams(location.search);
  if(incoming.get('flow')==='visit')tab('visit');
  if(incoming.get('flow')==='doctor'){
    $('doctor').value=(incoming.get('doctor')||'').slice(0,80);
    $('visit-facts').value=(incoming.get('facts')||'').slice(0,2000);
    tab('visit');$('notice').textContent='已带入模块三的公开检索线索。请核对医生身份、交流目的和来源后，再形成预测。';
  }

  $('learn-tab').onclick=()=>tab('learn');$('visit-tab').onclick=()=>{tab('visit');listSheets().catch(error);};$('history-tab').onclick=()=>busy(async()=>{tab('history');await history();});
  $('config-toggle').onclick=()=>{$('config').hidden=!$('config').hidden;};
  $('credentials').onsubmit=e=>{e.preventDefault();busy(async()=>{await api('/api/credentials',{key:$('api-key').value});$('api-key').value='';$('config').hidden=true;state.config=await api('/api/config');$('model-status').textContent='模型已连接 · '+state.config.model.model;});};
  $('start-learn').onclick=()=>busy(async()=>openRun(await api('/api/runs',{mode:'learn',lesson_id:$('lesson-select').value})));
  $('visit-select').onchange=()=>{$('custom-context').hidden=$('visit-select').value!=='custom';};
  $('visit-form').onsubmit=e=>{e.preventDefault();busy(async()=>{state.sheet=await api('/api/prepare',{visit_id:$('visit-select').value,context:{doctor:$('doctor').value,goal:$('goal').value,facts:$('visit-facts').value,lesson_id:$('visit-lesson').value},use_approved_methods:$('use-methods').checked});localStorage.setItem('medrep-last-sheet',state.sheet.id);renderSheet();await listSheets();});};
  $('answer-form').onsubmit=e=>{e.preventDefault();if(state.recording){error(new Error('请先停止录音、核对转写后再提交。'));return;}busy(()=>submitAnswer({answer:$('answer').value,revision:state.run.revision,request_id:crypto.randomUUID()}));};
  $('retry-feedback').onclick=()=>busy(()=>state.run.finish_pending?api('/api/runs/'+state.run.id+'/finish',{}).then(openRun):submitAnswer(state.pending||{answer:state.run.pending_request.answer,request_id:state.run.pending_request.id,revision:state.run.revision}));
  $('support-btn').onclick=()=>busy(async()=>{const d=await api('/api/runs/'+state.run.id+'/support',{});state.run.support_used=true;$('support').innerHTML=d.material?MaterialUI.render(d.material,'run-material-'):d.sections.map(s=>`<h3>${esc(s.title)}</h3><p>${esc(s.body)}</p>`).join('')+sources(d.sources);$('support').hidden=false;$('practice-meta').textContent+=' · 已使用提示';});
  $('retry-btn').onclick=()=>busy(async()=>openRun(await api('/api/runs/'+state.run.id+'/retry',{})));
  $('correct-btn').onclick=()=>{const old=[...state.run.transcript].reverse().find(m=>m.role==='药代');const answer=prompt('修订最后一段药代原话。旧评价将撤回，修订后重新生成反馈。',old.text);if(answer!==null)busy(async()=>{openRun(await api('/api/runs/'+state.run.id+'/correct',{answer,revision:state.run.revision}));});};
  $('return-sheet').onclick=()=>busy(async()=>{state.sheet=await api('/api/sheets/'+state.run.sheet_id);tab('visit');renderSheet();});
  $('leave-practice').onclick=()=>{$('practice-panel').hidden=true;stopAudio();cancelRecording();};
  $('finish-btn').onclick=()=>busy(async()=>openRun(await api('/api/runs/'+state.run.id+'/finish',{})));
  $('material-search').onsubmit=e=>{e.preventDefault();busy(async()=>{const d=await api('/api/materials/search',{lesson_id:$('lesson-select').value,query:$('search-query').value});$('search-results').innerHTML=d.blocks.length?d.blocks.map(b=>`<article><a href="#material-${esc(b.locator)}">${esc(b.title)}</a><p>${esc(b.text.slice(0,500))}</p></article>`).join(''):'<p>本课未找到相应内容；请换个问法或补充资料。</p>';});};
  await listSheets();
  const requestedRun=new URLSearchParams(location.search).get('run');if(requestedRun){try{openRun(await api('/api/runs/'+encodeURIComponent(requestedRun)));}catch(e){error(e);}}
  const sheet=incoming.get('flow')==='doctor'?null:(incoming.get('sheet')||localStorage.getItem('medrep-last-sheet'));if(sheet){try{state.sheet=await api('/api/sheets/'+encodeURIComponent(sheet));tab('visit');renderSheet();}catch(_){localStorage.removeItem('medrep-last-sheet');}}
}
window.addEventListener('beforeunload',()=>{stopAudio();state.recording?.stream.getTracks().forEach(t=>t.stop());});
init().catch(error);
