// Included inline by bundle.mjs. Uses the original shell; no demo identities.
function sourceText(value){try{const data=JSON.parse(value);const flatten=v=>v===null?'':Array.isArray(v)?v.map(flatten).filter(Boolean).join('\n'):typeof v==='object'?Object.values(v).map(flatten).filter(Boolean).join('\n'):typeof v==='boolean'||typeof v==='number'?'':String(v);return flatten(data);}catch{return String(value);}}
let connectedLesson='',connectedQuery='',connectedMaterial=null,connectedMatches=null,connectedProduct='',connectedLive=true,connectedSearching=false;
async function connectedRead(path){const r=await fetch(path,{signal:AbortSignal.timeout(35000)}),d=await r.json();if(!r.ok)throw Error(d.error||'读取失败');return d;}
function renderConnected(){
 const corpus=config.knowledge;
 all('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===view));
 $('#sidebar .avatar').textContent='·';$('#reader-name').textContent='员工档案未接入';$('#reader-scope').textContent='模块一原知识库 · 无虚构分配';
 const selector='<label for="connected-course">今天想了解哪个主题</label><select id="connected-course">'+corpus.courses.map(c=>'<option value="'+esc(c.lesson_id)+'" '+(c.lesson_id===connectedLesson?'selected':'')+'>'+esc(c.title)+'</option>').join('')+'</select>';
 const products='<label for="connected-product">本次关注产品（不代表员工负责分配）</label><select id="connected-product"><option value="">暂不选择 · 只读行业动态</option>'+config.products.map(p=>'<option value="'+esc(p.id)+'" '+(p.id===connectedProduct?'selected':'')+'>'+esc(p.name)+'</option>').join('')+'</select>';
 let html=heading('知识与前沿','读取课程与资料。')+'<div class="notice"><p>'+esc(config.notice)+'</p></div>';
 if(view==='profile'){
  html+=heading('工作背景与知识范围','没有真实员工档案时，不生成岗位、医院、医生或关键人。')+'<p>实际员工资料尚未接入，个性化分配和自动投递未启用。以下是知识库的内容范围，不是你的负责关系。</p><h2>原知识库产品</h2>'+corpus.products.map(p=>'<article class="entry"><h3>'+esc(p.brand)+' · '+esc(p.generic_name)+'</h3><p>'+esc(p.mechanism_topic)+' · '+esc(p.review_status)+'</p><small>原记录：'+esc(p.product_id)+' · 来源：'+esc(p.reference_source)+'</small></article>').join('')+'<p><a href="#sources">查看信息来源与采集说明</a></p>';
 }else if(view==='scholar'){
  html+=heading('医生公开学术资料','按真实医院与姓名检索；结果可能是同名作者，不能推断真实偏好。')+'<form id="connected-scholar"><label>医院全称<input name="hospital" required value="'+esc(scholarInput.hospital)+'"></label><label>姓名<input name="name" required value="'+esc(scholarInput.name)+'"></label><button class="btn primary" '+(scholarLoading?'disabled':'')+'>查询公开来源</button></form>';
  if(scholarLoading)html+='<p>正在检索公开学术来源…</p>';
  if(scholarError)html+='<p role="alert">'+esc(scholarError)+'</p>';
  if(scholar){html+='<p>'+esc(scholar.note)+'</p><p><a class="btn primary" rel="noreferrer" href="'+esc(doctorPrepUrl(scholar))+'">带入模块一访前准备 →</a></p><p class="small">只带入公开学术线索，姓名、身份及本次目的需在模块一核对。</p>'+[...scholar.papers,...scholar.events].map(x=>'<article class="entry"><h3>'+esc(x.translatedTitle||x.title)+'</h3><p>'+esc(x.verification||'待核对')+'</p><a href="'+url(x.sourceUrl||x.url)+'" target="_blank" rel="noopener noreferrer">原始来源</a></article>').join('');if(!scholar.papers.length&&!scholar.events.length)html+='<p>没有匹配记录，不补充示例。</p>';}
 }else if(view==='sources'){
  html+='<h2>模块一知识库原始来源</h2>'+corpus.sources.map(s=>'<article class="entry"><h3>'+esc(s.title||s.source_id)+'</h3><p>'+esc(s.url||s.reference_url||'')+'</p><small>'+esc(s.source_id)+'</small></article>').join('')+'<h2>外部实时采集来源</h2>'+config.sources.map(s=>'<p>'+esc(s.name)+' · '+esc(s.url)+'</p>').join('');
 }else if(view==='saved'||view==='history'){
  html+=collection(view);
 }else{
  html+='<div class="actions"><button class="btn '+(connectedLive?'primary':'')+'" id="connected-live">日常日报</button><button class="btn '+(!connectedLive?'primary':'')+'" id="connected-corpus">原课程资料</button><a class="btn" href="#scholar">搜索医生并准备拜访 →</a></div>';
  if(connectedLive){
   html+=products+'<button class="btn primary" id="connected-refresh" '+(loading?'disabled':'')+'>更新实时内容</button><p>知识库是已有资料，下面单独展示实际采集的外部内容；不把旧知识标成今日新闻。</p>';
   if(loading)html+='<p>正在连接外部来源…</p>';
   if(!digest&&!loading)html+='<p>日报尚未读取；点击“更新实时内容”获取当前公开信息。</p>';
   if(error)html+='<p role="alert">'+esc(error)+'</p>';
   if(digest){html+='<h2>全员行业动态</h2>'+((digest.industry||[]).map(i=>entry(i)).join('')||'<p>本次没有可显示内容。</p>')+'<h2>本次关注产品与在研学习</h2>'+((digest.learning||[]).map(i=>entry(i,true)).join('')||'<p>未选择产品或本次没有匹配内容。</p>');html+=(digest.sources||[]).map(s=>'<p>'+esc(s.name)+' · '+esc(s.status)+(s.error?' · '+esc(s.error):'')+'</p>').join('');}
  }else{
   html+=selector+'<div class="actions"><input aria-label="知识库查询" id="connected-query" value="'+esc(connectedQuery)+'" placeholder="在这份原课程中查找"><button class="btn" id="connected-search" '+(connectedSearching?'disabled':'')+'>'+(connectedSearching?'检索中…':'实际检索')+'</button></div>';
   const c=corpus.courses.find(c=>c.lesson_id===connectedLesson);
   if(c)html+='<details><summary>资料来源与版本 · 待医学审核</summary><p>'+esc(c.sourcePath)+' · '+esc(c.revision.slice(0,12))+' · '+esc(c.status)+'</p></details><a class="btn primary" href="http://127.0.0.1:8892/?lesson='+encodeURIComponent(c.lesson_id)+'">用这份资料进入模块一学习与演练</a>';
   if(error)html+='<p role="alert">'+esc(error)+'</p>';
   const blocks=[...(connectedMatches?.blocks||connectedMaterial?.blocks||[])].sort((a,b)=>(/hook/.test(b.id)?1:0)-(/hook/.test(a.id)?1:0));
   if(connectedMatches&&!blocks.length)html+='<p>没有检索命中，不生成替代内容。</p>';
   html+=blocks.map(b=>'<details class="reading-block" '+(/hook/.test(b.id)?'open':'')+'><summary>'+esc(b.title)+'</summary><p style="white-space:pre-wrap">'+esc(sourceText(b.text))+'</p><small>'+esc(b.id)+'</small></details>').join('');
   html+=(corpus.questionDrafts||[]).filter(q=>q.subject_id===connectedLesson.split('__')[0]).map(q=>'<details><summary>'+esc(q.prompt)+'</summary><p>'+esc(q.expected_checks)+'</p><small>'+esc(q.item_id)+' · '+esc(q.source_id)+' · '+esc(q.review_status)+'</small></details>').join('');
   html+='<h2>原知识库中的产品问题</h2><p>保留原产品关联和审核状态；不是自动批准的训练题。</p>'+corpus.questions.filter(q=>q.product_id===(connectedProduct?config.products.find(p=>p.id===connectedProduct)?.module1ProductId:connectedLesson.split('__')[0])).map(q=>'<details><summary>'+esc(q.question)+'</summary><p>'+esc(q.key_points)+'</p><small>'+esc(q.question_id)+' · '+esc(q.review_status)+'</small></details>').join('');
  }
 }
 $('#app').innerHTML=html+footer();
 if($('#connected-course'))$('#connected-course').onchange=async e=>{connectedLesson=e.target.value;connectedMatches=null;await loadConnectedMaterial();};
 if($('#connected-search'))$('#connected-search').onclick=async()=>{if(connectedSearching)return;connectedQuery=$('#connected-query').value;connectedSearching=true;render();try{connectedMatches=await connectedRead('/api/knowledge/search?'+new URLSearchParams({lessonId:connectedLesson,q:connectedQuery}));error='';}catch(e){error=e.message;}finally{connectedSearching=false;render();}};
 if($('#connected-corpus'))$('#connected-corpus').onclick=()=>{connectedLive=false;error='';render();};
 if($('#connected-live'))$('#connected-live').onclick=()=>{connectedLive=true;error='';render();};
 if($('#connected-product'))$('#connected-product').onchange=e=>{connectedProduct=e.target.value;};
 if($('#connected-refresh'))$('#connected-refresh').onclick=loadConnectedDigest;
 if($('#connected-scholar'))$('#connected-scholar').onsubmit=e=>{e.preventDefault();const f=new FormData(e.target);scholarInput={hospital:String(f.get('hospital')),name:String(f.get('name'))};loadScholar();};
 all('[data-open]').forEach(b=>b.onclick=()=>openDetail(b.dataset.open));all('[data-save]').forEach(b=>b.onclick=()=>toggleBookmark(b.dataset.save));all('[data-home]').forEach(b=>b.onclick=()=>location.hash='home');
}
async function loadConnectedMaterial(){try{connectedMaterial=await connectedRead('/api/knowledge/course?'+new URLSearchParams({lessonId:connectedLesson}));error='';}catch(e){connectedMaterial=null;error=e.message;}render();}
async function loadConnectedDigest(){loading=true;error='';render();try{digest=await connectedRead('/api/digest?'+new URLSearchParams({mode:'live',products:connectedProduct,length:'standard'}));}catch(e){digest=null;error=e.message;}finally{loading=false;render();}}
