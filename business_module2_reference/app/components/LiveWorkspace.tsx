'use client';
import { useEffect,useState } from 'react';
import type { Task,Feedback } from '../../lib/types';
import { SpeechInput } from './SpeechInput';
import { EvolutionJourney } from './EvolutionJourney';
type MethodItem={id:string;state:string;changeReason:string;method:{condition:string;action:string;reason:string;exceptions:string[];supports:{episode_id:string;quote:string}[];counters:{episode_id:string;quote:string}[]};evaluation?:{reason:string};createdAt:string};
type MethodState={sourceCount:number;distinctVisits:number;methods:MethodItem[]};
type State={sourceTasks:{id:string;kind:string;title:string;state:string;forecastState?:string}[];tasks:Task[];task?:Task;feedback:Feedback[];notice:string;assets:AssetView[];model:{name:string;configured:boolean}};
type Row={reason?:string;description?:string;status?:string;diagnosis?:string;recommendation?:string;capabilityId:string};
type Assets={personal:Row[];forecast:Row[];knowledge:Row[];experts:Row[];cohort:Row[]};
type AssetView={taskId:string;state:string;assets:Assets|null;simulatedAssets?:Assets;gaps?:string[];retrieval?:{feedbackId:string;status:string;query:string;blocks:{id:string;title:string;text:string}[]}[]};
async function api<T>(value?:unknown,taskId?:string):Promise<T>{
  const r=await fetch('/api/live'+(taskId?'?taskId='+encodeURIComponent(taskId):''),{method:value?'POST':'GET',headers:{'Content-Type':'application/json','idempotency-key':crypto.randomUUID()},...(value?{body:JSON.stringify(value)}:{})});
  const d=await r.json();if(!r.ok)throw new Error(d.error?.message||'操作失败');return d.data;
}
async function methodApi(value?:unknown):Promise<any>{const r=await fetch('/api/live/methods',{method:value?'POST':'GET',headers:{'Content-Type':'application/json'},...(value?{body:JSON.stringify(value)}:{})});const d=await r.json();if(!r.ok)throw new Error(d.error?.message||'方法操作失败');return d.data;}
export function LiveWorkspace(){
  const [methods,setMethods]=useState<MethodState>(),[data,setData]=useState<State>(),[selected,setSelected]=useState<string>(),[raw,setRaw]=useState(''),[confirmed,setConfirmed]=useState(false),[occurred,setOccurred]=useState(false),[mode,setMode]=useState('REPORTED_EXCHANGE'),[error,setError]=useState(''),[busy,setBusy]=useState(false),[editing,setEditing]=useState<Feedback>();
  async function load(id=selected){setData(await api<State>(undefined,id));try{setMethods(await methodApi());}catch{/* method status is optional until connected */}}
  async function run(fn:()=>Promise<void>){setBusy(true);setError('');try{await fn();}catch(e){setError(e instanceof Error?e.message:'操作失败');}finally{setBusy(false);}}
  useEffect(()=>{run(async()=>{
    await api({action:'session'});
    const params=new URLSearchParams(window.location.search),sourceId=params.get('sourceId'),kind=params.get('sourceKind');
    if(sourceId&&['sheets','runs'].includes(kind||'')){
      const available=await api<State>();
      if(!available.sourceTasks.some(x=>x.id===sourceId&&x.kind===kind))throw new Error('当前浏览器无法访问原模块一任务。请在创建任务的同一浏览器打开，或返回模块一核对。');
      const task=await api<Task>({action:'import',id:sourceId,kind});setSelected(task.id);
      await load(task.id);
    }else await load();
  });},[]);
  const t=data?.task,view=data?.assets.find(v=>v.taskId===t?.id);
  const forecast=t?.snapshot.forecastSnapshot;
  const candidates=forecast?.candidateSkillIds||[],chosen=new Set(forecast?.selectedSkillIds||[]);
  const getSkill=(id:string)=>t?.snapshot.codebook.skills.find(s=>s.id===id);
  const getQuestion=(id:string)=>t?.snapshot.plan.find(p=>p.skillId===id)?.question||getSkill(id)?.cognitiveTask||id;
  function comparison(f:Feedback){
    if(!f.analysis)return null;
    if(!forecast)return <p className="muted">这份旧任务没有可核验的访前冻结候选池，不根据事后复盘补造预测。以下只展示原话分析。</p>;
    const matched=new Set(f.analysis.differences.map(d=>d.skillId).filter((v):v is string=>!!v));
    return <details open className="forecast-review"><summary>原预测与本次报告的差异 · {f.analysis.differences.length} 条关联</summary>
      <p className="muted">只比较访前冻结记录与本人报告，不代表医生现场提问全量或真实命中率。自动匹配有待人工核对。</p>
      {f.analysis.differences.map((d,i)=>{
        const u=f.analysis?.units.find(u=>u.id===d.questionUnitId),wasSelected=!!d.skillId&&chosen.has(d.skillId),wasCandidate=!!d.skillId&&candidates.includes(d.skillId);
        const label=wasSelected?'预测到且选作重点':wasCandidate?'原候选中有但没有选中':'未能匹配到原候选 · 待核对';
        return <article key={i}><b>{label}</b><blockquote>{u?.excerpt||'未找到独立可展示的问题原话'}</blockquote><p>{d.reason} · 原计划覆盖：{d.coverage}</p>{d.performance.some(x=>x.kind==='SELF_REPORTED_DIFFICULTY')&&<p>本人报告存在困难：应区分知识、表达和练习场景原因。</p>}</article>;
      })}
      {forecast.selectedSkillIds.filter(id=>!matched.has(id)).map(id=><p key={id}>访前选中「{getQuestion(id)}」：本次复盘未报告相应问题；不能据此断言现场未出现。</p>)}
    </details>;
  }
  return <main aria-busy={busy}><header><a href="/" className="brand">复盘与成长</a><a href="http://127.0.0.1:8892/">准备与演练</a><a href="http://127.0.0.1:8787/">知识与前沿</a></header>
    <section className="intro"><h1>复盘与成长</h1><p>关联访前预测，记录拜访，持续改进。</p><p><a href="http://127.0.0.1:8787/#scholar">① 找医生</a>　<a href="http://127.0.0.1:8892/?flow=visit">② 访前预测与准备</a>　<strong>③ 复盘与持续更新</strong></p></section>
    {error&&<p role="alert" className="alert error">{error}</p>}{!data?<p>正在载入任务…</p>:<><details className="live-source-note"><summary>资料与连接状态</summary><p>{data.notice}</p><p>模型：{data.model.configured?data.model.name:'未配置'}</p></details>
    <div className="workspace"><aside><section className="card"><h2>选择原任务</h2><p className="muted">真实拜访选访前准备；日常学习记录可单独查阅，不必提交拜访复盘。</p><button disabled={busy} onClick={()=>run(()=>load())}>刷新</button>{!data.sourceTasks.length&&<p>本浏览器尚无真实课程任务。请先在<a href="http://127.0.0.1:8892/">准备与演练</a>学习或创建访前准备，回来刷新。</p>}{data.sourceTasks.map(s=><button className="secondary wide" key={s.kind+s.id} disabled={busy} onClick={()=>run(async()=>{const created=await api<Task>({action:'import',id:s.id,kind:s.kind});setSelected(created.id);await load(created.id);})}>{s.kind==='sheets'?'访前任务 · ':'训练记录 · '}{s.title} · {({active:'练习中',review:'已完成',READY:'待复盘'} as Record<string,string>)[s.state]||s.state}{s.kind==='sheets'&&s.forecastState!=='FROZEN'?' · 无冻结预测':''}</button>)}<details><summary>已关联的复盘 · {data.tasks.length}</summary>{data.tasks.map(task=><button className="secondary wide" key={task.id} onClick={()=>run(async()=>{setSelected(task.id);setEditing(undefined);setRaw('');await load(task.id);})}>{task.title}</button>)}</details></section></aside>
    <div>{!t?<section className="card"><div className="empty-start"><span className="empty-number">01 — 02</span><h2>接着上次准备，做一次复盘。</h2><p>选中左侧的学习或访前任务，再记下这次交流中发生了什么。系统会对照访前原计划。</p><a href="http://127.0.0.1:8892/">还没有任务？先去准备一次 ↗</a></div></section>:<><section className="card"><h2>{t.title}</h2>{forecast?<section className="forecast-review"><h3>本次拜访前保留的先验预测</h3><p className="muted">冻结于 {new Date(forecast.frozenAt).toLocaleString('zh-CN')} · 原候选 {candidates.length} 个 · 选中 {chosen.size} 个 · 资料版本 {t.snapshot.knowledgeVersion.slice(0,12)}</p>{candidates.map(id=><p key={id}><b>{chosen.has(id)?'✓ 当时选中':'○ 当时未选'}</b> · {getQuestion(id)}</p>)}<p className="muted">候选集指当时系统生成的问题，不是所有可能问题的全集；记录不可事后重算。</p></section>:<p className="muted">该来源没有访前冻结预测；可以复盘，但预测与实际差异只能标为未知。</p>}<details><summary>资料来源与版本</summary><p>{t.snapshot.origin?.sourcePath}</p><p>版本 {t.snapshot.origin?.revision.slice(0,12)} · 仍待医学审核</p></details><p><a href={"http://127.0.0.1:8892/?lesson="+encodeURIComponent(t.snapshot.origin!.lessonId)+(t.snapshot.origin!.sourceKind==="runs"?"&run="+encodeURIComponent(t.snapshot.origin!.sourceTaskId):"&sheet="+encodeURIComponent(t.snapshot.origin!.sourceTaskId))}>回到原课程与原练习，继续补学或复练</a></p><details><summary>更新练习结果与查看准备依据</summary><button disabled={busy} onClick={()=>run(async()=>{await api({action:"refreshPractice",taskId:t.id});const f=data.feedback.find(f=>f.state==="ANALYZED");if(f)await api({action:"analyze",taskId:t.id,feedbackId:f.id,expectedVersion:f.versions.at(-1)?.version});await load();})}>同步练习记录</button>{t.snapshot.plan.map(p=><article key={p.skillId}><h3>{t.snapshot.codebook.skills.find(s=>s.id===p.skillId)?.cognitiveTask}</h3><p>{p.rationale}</p></article>)}<details><summary>原任务实际引用的正文</summary>{t.snapshot.evidence.map(e=><article key={e.id}><h3>{e.title}</h3><p style={{whiteSpace:'pre-wrap'}}>{e.content}</p><small>{e.id} · {e.version.slice(0,12)}</small></article>)}</details></details></section>
    <section className="card"><h2>{editing?'修订已确认原文':'聊聊这次交流'}</h2><label>记录性质<select value={mode} onChange={e=>setMode(e.target.value)}><option value="REPORTED_EXCHANGE">本人报告的实际交流</option><option value="SIMULATED_EXCHANGE">根据真实课程进行模拟联调，不计入实际历史</option></select></label><SpeechInput testOnly={false} disabled={busy} onText={text=>{setRaw(v=>v+text);setConfirmed(false);}}/><textarea aria-label="复盘原文" value={raw} onChange={e=>{setRaw(e.target.value);setConfirmed(false);}} placeholder="写自己实际记得的内容，不需要补造问题。"/><label><input type="checkbox" checked={occurred} onChange={e=>setOccurred(e.target.checked)}/>我确认所选性质下的交流已发生</label><label><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>我已核对原文；这不代表医学结论或现场事实已认证</label><button disabled={busy||!confirmed||!occurred||!raw.trim()} onClick={()=>run(async()=>{await api({action:'saveRaw',taskId:t.id,exchangeMode:mode,...(editing?{feedbackId:editing.id}:{}),raw:{text:raw,confirmed:true,exchangeOccurred:true,...(editing?{expectedVersion:editing.versions.at(-1)!.version}:{})}});setRaw('');setEditing(undefined);setConfirmed(false);setOccurred(false);await load();})}>确认并保存原文</button></section>
    {data.feedback.map(f=><section className="card" key={f.id}><h2>复盘记录 · V{f.versions.at(-1)?.version}</h2><details><summary>查看已确认原文</summary><blockquote>{f.versions.at(-1)?.text}</blockquote></details><button disabled={busy} onClick={()=>run(async()=>{await api({action:'analyze',taskId:t.id,feedbackId:f.id,expectedVersion:f.versions.at(-1)?.version});await load();})}>{busy?'处理中…':'结合原计划与资料分析'}</button><button disabled={busy} onClick={()=>{setEditing(f);setRaw(f.versions.at(-1)!.text);setConfirmed(false);setOccurred(false);}}>修订原文</button>{f.errorCode&&<p role="alert">{f.errorCode}；未生成替代结果。</p>}{f.analysis&&comparison(f)}{f.analysis&&<details><summary>查看原文提取与覆盖依据</summary>{f.analysis.differences.map((d,i)=><p key={i}>{d.coverage} · {d.reason}</p>)}{f.analysis.units.map(u=><blockquote key={u.id}>{u.excerpt}<small>{u.types.join(' / ')} · {u.mapping}</small></blockquote>)}</details>}</section>)}
    </>}</div></div></>}
    <EvolutionJourney assets={view?.assets} simulatedAssets={view?.simulatedAssets} methods={methods??null} analysisCount={data?.feedback.filter(f=>!!f.analysis).length??0} hasFrozenForecast={!!forecast} busy={busy} modelReady={!!data?.model.configured} onPropose={async()=>run(async()=>{const result=await methodApi({action:'propose'});setMethods(await methodApi());if(!result.candidate)setError('证据不足，新方法未生成；旧版继续有效。');})}/>
    <footer>原知识库联动 · 没有真实员工或专家数据时保持缺项 · 不自动发布医学知识或正式选题策略</footer></main>;
}
