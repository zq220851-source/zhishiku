import { useEffect, useState } from 'react';
import RealtimeVoice from './RealtimeVoice';
import {
  ApiError, readLearningCatalog, readCoachSheets, readCoachSheet, prepareVisit, freezeVisit,
  readCoachRuns, readCoachRun, startLesson, startVisitPractice, finishCoachRun,
  supportCoachRun, retryCoachRun, request,
} from './api';
import type {CoachSheet, CoachRun, CoachSupport, LessonMeta} from './api';

type StudioTab = 'prepare'|'visit-practice'|'learn-practice'|'history';

function msg(e:unknown):string {
  return e instanceof ApiError && e.status===503 ? '模块一尚未连接或模型暂不可用，请确认真实服务配置。'
    : e instanceof Error ? e.message : '请求失败，请稍后重试';
}
function reviewContent(review:unknown) {
  if(typeof review === 'string') return <p>{review}</p>;
  if(review && typeof review==='object') {
    const r=review as {feedback?:string;focus?:string;observations?:{reason?:string;status?:string}[]};
    return <>
      {r.feedback&&<p>{r.feedback}</p>}
      {Array.isArray(r.observations)&&r.observations.map((o,i)=><p key={i}><strong>{o.status||'观察'}：</strong>{o.reason||'待核实'}</p>)}
      {r.focus&&<p><strong>下一步练习建议：</strong>{r.focus}</p>}
      {!r.feedback&&!r.focus&&<pre>{JSON.stringify(review,null,2)}</pre>}
    </>;
  }
  return <p>暂无反馈，请确认本轮练习是否结束。</p>;
}

export default function CoachStudio({demo,visible=true,lessonRequest,prepareRequest,onReview}:{demo:boolean;visible?:boolean;lessonRequest?:{id:string;nonce:number;taskId?:string};prepareRequest?:{doctor?:string;facts:string;goal?:string;nonce:number};onReview?:(id:string,kind:'runs'|'sheets')=>void}) {
  const [lessons,setLessons]=useState<LessonMeta[]>([]);
  const [lesson,setLesson]=useState('');
  const [useMethods,setUseMethods]=useState(false);
  const [shared,setShared]=useState<{id:string;level:string;lessonId:string;option:{question:string}}[]>([]);
  const [sharedIds,setSharedIds]=useState<string[]>([]),[sharedBudget,setSharedBudget]=useState(1);
  const [doctor,setDoctor]=useState('');
  const [goal,setGoal]=useState('');
  const [facts,setFacts]=useState('');
  const [sheets,setSheets]=useState<CoachSheet[]>([]);
  const [sheet,setSheet]=useState<CoachSheet|null>(null);
  const [selected,setSelected]=useState<string[]>([]);
  const [previsit,setPrevisit]=useState(false);
  const [runs,setRuns]=useState<CoachRun[]>([]);
  const [run,setRun]=useState<CoachRun|null>(null);
  const [support,setSupport]=useState<CoachSupport|null>(null);
  const [voiceActive,setVoiceActive]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [notice,setNotice]=useState('');
  const [tab,setTab]=useState<StudioTab>('prepare');

  useEffect(()=>{if(lessonRequest){setLesson(lessonRequest.id);setRun(null);setTab('learn-practice');setNotice('已带入对应课程，可开始实时语音训练。');}},[lessonRequest?.nonce]);
  useEffect(()=>{if(prepareRequest){setFacts(prev=>(prev?prev+'\n\n':'')+prepareRequest.facts);if(prepareRequest.doctor)setDoctor(prepareRequest.doctor);if(prepareRequest.goal)setGoal(prepareRequest.goal);setTab('prepare');setNotice('已带入公开来源，请核对背景并选择本次课程。');}},[prepareRequest?.nonce]);
  useEffect(()=>{if(run?.state==='review'&&lessonRequest?.taskId&&run.mode==='learn'){
    void request('/v1/mobile/review/action','POST',{action:'linkPractice',taskId:lessonRequest.taskId,runId:run.id},30000).then(()=>setNotice('补练结果已关联回原复盘任务。')).catch(e=>setError(e.message));
  }},[run?.id,run?.state]);
  async function refresh(){if(demo)return;setBusy(true);setError('');
    try{
      const [catalog,oldSheets,oldRuns,teamShared]=await Promise.all([readLearningCatalog(),readCoachSheets(),readCoachRuns(),request<{releases:typeof shared}>('/v1/mobile/review/evolution')]);
      setLessons(catalog.lessons);setSheets(oldSheets.sheets);setRuns(oldRuns.runs);
      setLesson(prev=>prev||catalog.lessons[0]?.id||'');
      setShared(teamShared.releases);
    }catch(e){setError(msg(e));}finally{setBusy(false);}
  }
  useEffect(()=>{if(!demo)void refresh();},[demo]);
  async function task<T>(fn:()=>Promise<T>,onSuccess:(data:T)=>void){
    if(demo)return;setBusy(true);setError('');setNotice('');
    try{const data=await fn();onSuccess(data);}catch(e){setError(msg(e));}finally{setBusy(false);}
  }
  function showSheet(s:CoachSheet){setSheet(s);setSelected(s.forecast?.selected_ids||[]);setPrevisit(false);setTab('prepare');}
  async function loadSheet(id:string){await task(()=>readCoachSheet(id),showSheet);}
  async function createSheet(ev:React.FormEvent){ev.preventDefault();
    await task(()=>prepareVisit({doctor:doctor.trim(),goal:goal.trim(),facts:facts.trim(),lesson_id:lesson,use_approved_methods:useMethods,shared_release_ids:sharedIds.filter(id=>shared.some(r=>r.id===id&&r.lessonId===lesson)),shared_budget:sharedBudget}),
      data=>{showSheet(data);setSheets(a=>[data,...a]);setNotice('准备资料和候选预测已经生成。先阅读依据，再确认访前重点，然后进入模拟实战。');});
  }
  async function doFreeze(){
    if(!sheet||!previsit||!selected.length)return;
    await task(()=>freezeVisit(sheet.id,selected),data=>{
      showSheet(data);setNotice('访前预测已冻结。下一步：进入访前模拟实战，与医生开展多轮对话。');
      setSheets(a=>a.map(s=>s.id===data.id?data:s));
    });
  }
  function showRun(r:CoachRun){
    setRun(r);setSupport(null);
    // 访前实战与学课表达必须是两个独立的训练入口。
    setTab(r.mode==='visit'?'visit-practice':'learn-practice');
  }
  async function startVisit(optionId:string){
    if(!sheet)return;
    await task(()=>startVisitPractice(sheet.id,optionId),showRun);
  }
  async function loadSupport(){
    if(!run)return;
    await task(()=>supportCoachRun(run.id),data=>setSupport(data));
  }
  function activeRunFor(target:'visit'|'learn'){
    return run?.mode===target?run:null;
  }
  const frozen=sheet?.forecast?.status==='FROZEN';
  const chosen=sheet?.forecast?.selected_ids||selected;
  const sheetPriorities=(sheet?.priorities||[]).filter(p=>chosen.includes(p.id));
  const evidence=sheet?.material?.blocks||[];
  const visitRun=activeRunFor('visit');
  const learnRun=activeRunFor('learn');

  function conversation(r:CoachRun){
    return <article className="studio-output" key={r.id}>
      <h4>{r.mode==='visit'?'访前模拟实战 · ':'课程表达练习 · '}{r.title||'医生对话'}</h4>
      <small>第 {r.attempt||1} 轮练习 · 状态：{r.state||'未知'} · 记录版本：{r.revision}</small>
      {r.mode==='visit'&&<p className="minor">医生会围绕这次拜访的预测重点追问。这里是训练模拟，不代表真实医生必然如此提问。</p>}
      <div className="studio-transcript" aria-live="polite">{(r.transcript||[]).map((entry,i)=><div className="studio-line" key={i}>
        <strong>{entry.role}</strong><p>{entry.text}</p>
      </div>)}</div>
      {r.review!=null&&<div className="studio-review"><strong>本轮真实训练反馈</strong>
        {reviewContent(r.review)}<p className="minor">反馈仅供训练参考，不替代医学审核。</p>
      </div>}
      {r.state==='active'&&<RealtimeVoice kind="coach" recordId={r.id} onRun={setRun} onActive={setVoiceActive} disabled={busy} enabled={visible}/>}
      {['retryable','evaluating'].includes(r.state||'')&&<div className="notice"><p>上一段回答已保留，可继续处理并恢复反馈。</p><button className="outline" disabled={busy} onClick={()=>void task(()=>request<CoachRun>('/v1/mobile/coach/runs/'+r.id+'/resume','POST',{},120000),showRun)}>继续处理已保存的回答</button></div>}
      <div className="studio-actions">
        <button className="outline" type="button" disabled={busy||voiceActive} onClick={()=>void task(()=>readCoachRun(r.id),showRun)}>刷新对话</button>
        <button className="outline" type="button" disabled={busy} onClick={()=>void loadSupport()}>查看资料提示</button>
        {r.state==='active'&&(r.transcript||[]).some(m=>m.role==='药代')&&<button className="outline" type="button" disabled={busy||voiceActive} onClick={()=>void task(()=>finishCoachRun(r.id),showRun)}>暂停语音后结束并查看反馈</button>}
        {r.state==='review'&&<button className="primary" type="button" disabled={busy||voiceActive} onClick={()=>void task(()=>retryCoachRun(r.id),showRun)}>换种问法再练一次 ↗</button>}
        {r.state==='review'&&<button className="outline" onClick={()=>onReview?.(r.sheet_id||r.id,r.sheet_id?'sheets':'runs')}>关联原任务，进入复盘 →</button>}
        {r.mode==='visit'&&<button className="outline" type="button" onClick={()=>setTab('prepare')}>返回访前准备单</button>}
        <button className="outline" type="button" disabled={voiceActive} onClick={()=>setRun(null)}>结束查看，选择其他练习</button>
      </div>
      {support&&<details className="studio-materials" open><summary>本轮相关资料提示（已使用提示）</summary>
        {(support.material?.blocks||[]).length>0?(support.material?.blocks||[]).map((b,i)=><div className="studio-material-row" key={b.id||i}><strong>{b.title||'资料段落'}</strong><p>{b.text||b.body||'以原始课程资料为准'}</p><small>{b.locator||''}</small></div>):
          (support.sections||[]).map((s,i)=><div className="studio-material-row" key={i}><strong>{s.title}</strong><p>{s.body}</p></div>)}
      </details>}
    </article>;
  }

  return <section className="studio-panel">
    <div className="studio-heading"><h3>模块一 · 准备、实战与表达</h3><small>两种练习独立保留：访前模拟实战 ≠ 课程表达练习</small></div>
    {demo?<p className="notice">演示模式不提供真实 AI 对话。请以员工账号登录，并连接模块一服务。</p>:
    <>
      <div className="studio-tabs" role="tablist" aria-label="模块一两种训练入口">
        <button disabled={voiceActive} className={tab==='prepare'?'active':''} onClick={()=>setTab('prepare')}>访前准备</button>
        <button disabled={voiceActive} className={tab==='visit-practice'?'active':''} onClick={()=>setTab('visit-practice')}>访前模拟实战</button>
        <button disabled={voiceActive} className={tab==='learn-practice'?'active':''} onClick={()=>setTab('learn-practice')}>学课表达练习</button>
        <button disabled={voiceActive} className={tab==='history'?'active':''} onClick={()=>setTab('history')}>我的记录</button>
      </div>
      {error&&<p role="alert" className="error">{error}</p>}
      {notice&&<p role="status" className="success">{notice}</p>}
      {tab==='prepare'&&<>
        <p className="studio-step-note">流程：填写资料 → 生成访前预测 → 确认冻结 → <strong>进入访前模拟实战</strong> → 医生追问与反馈。</p>
        <form className="studio-form" onSubmit={e=>void createSheet(e)}>
          <label>选择课程资料<select required value={lesson} onChange={e=>setLesson(e.target.value)}>
            {!lessons.length&&<option value="">请先连接真实课程服务</option>}
            {lessons.map(x=><option key={x.id} value={x.id}>{x.title}</option>)}
          </select></label>
          <label>拜访对象称呼（建议脱敏）<input value={doctor} maxLength={80} required onChange={e=>setDoctor(e.target.value)} placeholder="例如：某科室医生"/></label>
          <label>本次沟通目标<textarea value={goal} maxLength={300} required onChange={e=>setGoal(e.target.value)} placeholder="本次希望了解或讨论的问题"/></label>
          <label>已知背景（不得包含患者身份信息）<textarea value={facts} maxLength={2000} required onChange={e=>setFacts(e.target.value)} placeholder="逐条记录已知事实与未核实信息"/></label>
          <label className="studio-confirm"><input type="checkbox" checked={useMethods} onChange={e=>setUseMethods(e.target.checked)}/>使用本课程已获授权的方法（仅测试范围）</label>
          <details><summary>使用已审核的团队场景或选题策略</summary><p className="minor">仅展示本课程仍有效的共享版本。一次准备最多使用一个 L3 策略。</p>{shared.filter(r=>r.lessonId===lesson).map(r=><label className="studio-confirm" key={r.id}><input type="checkbox" checked={sharedIds.includes(r.id)} onChange={e=>setSharedIds(ids=>e.target.checked?[...ids.filter(id=>r.level!=='L3'||shared.find(v=>v.id===id)?.level!=='L3'),r.id]:ids.filter(id=>id!==r.id))}/>{r.level} · {r.option.question}</label>)}{!shared.some(r=>r.lessonId===lesson)&&<p>本课程暂无有效共享版本。</p>}<label>使用共享版本时的固定准备预算<input type="number" min={1} max={20} value={sharedBudget} onChange={e=>setSharedBudget(Number(e.target.value))}/></label></details>
          <button className="primary" disabled={busy||!lesson} type="submit">{busy?'处理中…':'生成准备资料和预测'} <span>→</span></button>
        </form>
        {sheet&&<article className="studio-output"><h4>准备单 · {sheet.visit?.doctor||'当前拜访'}</h4>
          <p>{sheet.notice||'请检查资料来源和背景，不代表医生必然如此提问。'}</p>
          <small>预测状态：{frozen?'已冻结':'尚未冻结'} · {sheet.method||'模块一生成'}</small>
          <h4>第一节 · 资料与依据</h4>
          <p className="minor">以下来自本次准备单的实际课程资料；不是生成的演示答案。</p>
          {evidence.length>0?<details className="studio-materials" open><summary>查看本次参考资料（{evidence.length} 段）</summary>
            {evidence.map((b,i)=><div key={b.id||i} className="studio-material-row"><strong>{b.title||`资料段落 ${i+1}`}</strong>
              <p>{b.text||b.body||'请查看课程原始资料。'}</p><small>{b.locator||''}</small></div>)}
          </details>:<p className="minor">当前准备单未提供可展开的资料段落，请以课程材料为准。</p>}
          {(sheet.reminders||[]).length>0&&<details><summary>会面提醒</summary><ul>{sheet.reminders?.map((x,i)=><li key={i}>{x}</li>)}</ul></details>}
          <h4>第二节 · 访前预测与重点</h4>
          {sheet.evolution&&<aside className="notice"><p>{sheet.evolution.notice}</p><p>固定预算 {sheet.evolution.budget} 项 · 基础方案：{sheet.evolution.baseline.map(id=>sheet.priorities?.find(p=>p.id===id)?.title||id).join('、')}；共享方案：{sheet.evolution.proposed.map(id=>sheet.priorities?.find(p=>p.id===id)?.title||id).join('、')}</p><p>实际采用的共享版本：{sheet.consumed_evolution_versions?.length||0} 个{!frozen?'（尚未冻结）':''}</p>{!frozen&&<button className="outline" disabled={busy||voiceActive} onClick={()=>setSelected(sheet.evolution!.proposed)}>选择共享方案，稍后确认冻结</button>}</aside>}
          <div className="studio-priorities">{(sheet.priorities||[]).map(p=><label className="studio-priority" key={p.id}>
            <input type="checkbox" disabled={!!frozen||busy} checked={selected.includes(p.id)} onChange={e=>setSelected(prev=>e.target.checked?[...prev,p.id]:prev.filter(x=>x!==p.id))}/>
            <span><strong>{p.title||p.id}</strong>{p.question&&<small>{p.question}</small>}{p.why&&<small>{p.why}</small>}</span>
          </label>)}</div>
          {!frozen&&<><label className="studio-confirm"><input type="checkbox" checked={previsit} onChange={e=>setPrevisit(e.target.checked)}/>我确认真实拜访尚未发生；现在进行访前预测冻结，之后不能修改。</label>
            <button type="button" className="outline" disabled={busy||!previsit||!selected.length} onClick={()=>void doFreeze()}>确认冻结访前预测</button>
            <details><summary>冻结前可选试练</summary><p className="minor">可以先试练候选问题，再决定本次重点。</p>{(sheet.priorities||[]).map(p=><button className="outline" disabled={busy||voiceActive} key={p.id} onClick={()=>void startVisit(p.id)}>试练：{p.title||p.id}</button>)}</details>
          </>}
          {frozen&&<button className="outline" onClick={()=>onReview?.(sheet.id,'sheets')}>实际交流后，关联这份准备单复盘 →</button>}
          {frozen&&<div className="studio-next-stage"><h4>第三节 · 模拟实战对话</h4>
            <p>预测已经冻结。接下来选择重点，进入医生多轮追问；你回答后可查看反馈、资料提示和换题复练。</p>
            <button type="button" className="primary" disabled={busy||sheetPriorities.length===0} onClick={()=>setTab('visit-practice')}>进入访前模拟实战 <span>→</span></button>
          </div>}
        </article>}
      </>}
      {tab==='visit-practice'&&<>
        <div className="studio-next-stage"><h4>访前模拟实战 · 第二种对话练习</h4>
          <p>围绕本次准备资料和预测问题，与模拟医生开展实时语音对话。</p>
        </div>
        {!visitRun&&<>
          {!sheet||!frozen?<><p className="notice">请先选择已有访前准备单，或者生成准备单并冻结预测，再进入实战。</p>
            <button type="button" className="outline" onClick={()=>setTab('prepare')}>返回访前准备与预测</button>
            {!!sheets.length&&<div className="studio-history"><h4>可选择的历史准备单</h4>{sheets.map(s=><button key={s.id} onClick={()=>void loadSheet(s.id)}>
              {s.visit?.doctor||s.doctor||'访前准备单'} <small>{s.forecast?.status==='FROZEN'||s.forecast_status==='FROZEN'?'已冻结':'待冻结'}</small>
            </button>)}</div>}
          </>:<><h4>本次已冻结的模拟重点</h4>
            <p className="minor">准备单：{sheet.visit?.doctor||'本次拜访'}；请从已冻结的重点中选择一项与医生实战对话。</p>
            <div className="studio-visit-options">{sheetPriorities.map(p=><button className="studio-visit-option" type="button" disabled={busy} key={p.id} onClick={()=>void startVisit(p.id)}>
              <strong>{p.title||p.id}</strong><small>{p.question||'进入此重点对应的医生追问'}</small><span>开始模拟实战 →</span>
            </button>)}</div>
            <button type="button" className="outline" onClick={()=>setTab('prepare')}>回看准备资料与冻结记录</button>
          </>}
        </>}
        {visitRun&&conversation(visitRun)}
      </>}
      {tab==='learn-practice'&&<>
        <p className="studio-step-note">学课表达练习：根据课程材料进行表达训练，与访前预测后的模拟实战分别保存。</p>
        {!learnRun&&<div className="studio-form"><label>选择课程<select value={lesson} onChange={e=>setLesson(e.target.value)}>
          {lessons.map(l=><option key={l.id} value={l.id}>{l.title}</option>)}
        </select></label><button className="primary" type="button" disabled={busy||!lesson} onClick={()=>void task(()=>startLesson(lesson),showRun)}>开始课程表达练习 <span>→</span></button></div>}
        {learnRun&&conversation(learnRun)}
      </>}
      {tab==='history'&&<><button className="outline" disabled={busy} onClick={()=>void refresh()}>刷新我的记录</button>
        <h4>访前准备单</h4><div className="studio-history">{sheets.map(s=><button key={s.id} onClick={()=>void loadSheet(s.id)}>
          {s.visit?.doctor||s.doctor||'未命名准备'} <small>{s.forecast?.status==='FROZEN'||s.forecast_status==='FROZEN'?'已冻结':'未冻结'}</small>
        </button>)}{!sheets.length&&<p className="minor">暂无访前准备单。</p>}</div>
        <h4>历史实战 / 表达练习</h4><div className="studio-history">{runs.map(r=><button key={r.id} onClick={()=>void task(()=>readCoachRun(r.id),showRun)}>
          {r.title||'练习'} <small>{r.mode==='visit'?'访前实战':'学课表达'} · {r.state||'记录'}</small>
        </button>)}{!runs.length&&<p className="minor">暂无训练记录。</p>}</div>
      </>}
      <p className="minor">两类训练均通过实时语音进行。对话转写用于回看；不会代替你的语音作答。</p>
    </>}
  </section>;
}
