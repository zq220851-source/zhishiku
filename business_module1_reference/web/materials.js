'use strict';
// Source-bound reader. Never use model-generated HTML as course content.
const MaterialUI = (() => {
 const e = v => String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const labels={title:'标题',body:'讲解',prompt:'想一想',hint:'提示',answer:'参考回答',limit:'类比的边界',instruction:'怎么看',observation:'观察',myth:'常见说法',correction:'课程中的纠正',why:'为什么',question:'问题',explanation:'讲解',eyebrow:'情境',promise:'这节课解决什么',prerequisites:'已有基础',core:'核心关系',unlocks:'学后可以做什么',facts:'要点',nodes:'概念',edges:'关系',from:'起点',to:'终点',label:'关系',id:'标识',description:'说明',text:'内容',options:'选项',items:'内容'};
 function value(v) {
   if(Array.isArray(v))return '<ul>'+v.map(x=>`<li>${value(x)}</li>`).join('')+'</ul>';
   if(v&&typeof v==='object')return Object.entries(v).map(([k,x])=>`<div class="material-field"><b>${e(labels[k]||k)}</b> ${value(x)}</div>`).join('');
   return `<span>${e(v)}</span>`;
 }
 function visual(v){
   if(v.kind==='comparison'&&Array.isArray(v.items))return `<p>${e(v.instruction)}</p><div class="comparison-grid">${v.items.map(x=>`<section><h4>${e(x.title)}</h4>${value(x.facts||x)}</section>`).join('')}</div><p>${e(v.observation)}</p>`;
   if(v.kind==='process'&&Array.isArray(v.stages||v.items))return `<p>${e(v.instruction)}</p><ol class="process-list">${(v.stages||v.items).map(x=>`<li>${value(x)}</li>`).join('')}</ol><p>${e(v.observation)}</p>`;
   if(v.kind==='concept-map'&&Array.isArray(v.nodes))return `<p>${e(v.instruction)}</p><div class="concept-nodes">${v.nodes.map(n=>`<section><h4>${e(n.label)}</h4>${(n.connectsTo||[]).map(id=>{const target=v.nodes.find(x=>x.id===id);return target?`<p class="map-edge">↓ ${e(target.label)}</p>`:'';}).join('')}</section>`).join('')}</div><p>${e(v.observation)}</p>`;
   const copy={...v};delete copy.kind;return `<div class="concept-map">${value(copy)}</div>`;
 }
 function render(m,prefix='material-'){
   return `<details class="material-provenance"><summary>${m.status==='fictional_test_material'?'虚构测试资料':'课程资料 · 待医学审核'}</summary><p class="lesson-notice">${e(m.notice)}</p><p class="muted">材料版本 ${e(m.revision.slice(0,12))}</p></details>`+[...m.blocks].sort((a,b)=>(b.locator==='hook'?1:0)-(a.locator==='hook'?1:0)).map(b=>{
     let body;
     try{const v=JSON.parse(b.text);body=b.locator==='visual'?visual(v):value(v);}catch(_){body=`<p>${e(b.text)}</p>`;}
     const anchor=prefix+b.locator;
     if(b.locator.startsWith('checks.'))return `<details id="${e(anchor)}" class="optional-check"><summary>${e(b.title)}（可选）</summary>${body}</details>`;
     if(b.locator==='recall')return `<details id="${e(anchor)}"><summary>回忆提示与参考回答（按需展开）</summary>${body}</details>`;
     return `<details class="material-block" id="${e(anchor)}" ${b.locator==='hook'?'open':''}><summary>${e(b.title)}</summary>${body}</details>`;
   }).join('')+`<details><summary>参考来源与材料状态</summary>${m.references.map(r=>`<div class="source-list"><b>${e(r.title)}</b><p>${e(r.locator)}</p>${/^https?:\/\//.test(r.url||'')?`<a href="${e(r.url)}" target="_blank" rel="noopener noreferrer">外部参考链接 ↗</a><p>该链接的原始文件未随课程收录。</p>`:'<p>课程说明，未提供外部原文。</p>'}</div>`).join('')}</details>`;
 }
 return {render,value};
})();
