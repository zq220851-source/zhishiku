import {useEffect,useState} from 'react';
import {request} from './api';
interface Source {feedbackId:string;visitId:string;title:string;revision:string;rawVersion:number;observations:string[];options:{index:number;question:string;selected:boolean}[]}
interface Candidate {id:string;revision:number;level:string;state:string;teamId:string;option:{question:string;criteria:{label:string;expected:string}[]};reason:string;evaluation?:{reason:string;cases:{split:string;budget:number;baselineCoverage:number;proposedCoverage:number}[]}}
interface State {sources:Source[];teams:{id:string;name:string}[];candidates:Candidate[];releases:{id:string}[];notice:string}
const labels:Record<string,string>={DRAFT:'待独立验证',VALIDATED:'待共享审核',APPROVED:'已共享',REVOKED:'已撤回',STALE:'来源已变化'};
export default function EvolutionWorkspace({reviewer,staff,disabled=false}:{reviewer:boolean;staff:{id:string;display_name:string}[];disabled?:boolean}){
 const [data,setData]=useState<State|null>(null),[target,setTarget]=useState(''),[team,setTeam]=useState(''),[source,setSource]=useState(''),[option,setOption]=useState(0),[level,setLevel]=useState('L2'),[reason,setReason]=useState(''),[cases,setCases]=useState(['','']),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [refresh,setRefresh]=useState(0);
 const path='/v1/mobile/review/evolution';
 useEffect(()=>{let alive=true;setData(null);setSource('');setCases(['','']);setError('');setBusy(true);
  request<State>(path+(target?'?'+new URLSearchParams({target_user_id:target}):'')).then(d=>{if(alive){setData(d);setTeam(d.teams[0]?.id||'');}}).catch(e=>{if(alive)setError(e.message);}).finally(()=>{if(alive)setBusy(false);});
  return()=>{alive=false;};
 },[target,refresh]);
 async function action(action:string,c?:Candidate){setBusy(true);setError('');try{
  await request(path,'POST',{action,target_user_id:target||undefined,id:c?.id,expectedRevision:c?.revision,level,teamId:team,feedbackId:source,optionIndex:option,reason,caseFeedbackIds:cases});
  setData(await request<State>(path+(target?'?'+new URLSearchParams({target_user_id:target}):'')));
 }catch(e){setError(e instanceof Error?e.message:'操作未完成');}finally{setBusy(false);}}
 const locked=busy||disabled;
 return <details className="studio-materials"><summary><strong>团队共享场景与选题策略 · L2 / L3</strong></summary>
  <p className="minor">L2 复用原资料训练场景；L3 调整已知候选优先级。提案、验证、留出必须来自三次独立实际交流，另由团队审核人批准。原资料的医学审核状态保持不变。</p>
  {error&&<p className="error" role="alert">{error}</p>}
  {reviewer&&<label>审核对象<select disabled={locked} value={target} onChange={e=>setTarget(e.target.value)}><option value="">我自己的记录</option>{staff.map(s=><option key={s.id} value={s.id}>{s.display_name}</option>)}</select></label>}
  <button className="outline" disabled={locked} onClick={()=>setRefresh(v=>v+1)}>刷新共享记录</button>
  <p>{data?.sources.length||0} 份合格来源 · {data?.releases.length||0} 个有效共享版本</p>
  {data&&!data.teams.length&&<p className="notice">当前账户尚未关联可用团队。请由管理员配置真实团队及审核人后使用共享流程。</p>}
  <label>共享团队<select disabled={locked} value={team} onChange={e=>setTeam(e.target.value)}>{data?.teams.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
  {!target&&<><label>候选类型<select disabled={locked} value={level} onChange={e=>setLevel(e.target.value)}><option value="L2">L2 · 共享原资料训练场景</option><option value="L3">L3 · 调整漏选重点的优先级</option></select></label>
   <label>提案来源<select disabled={locked} value={source} onChange={e=>{setSource(e.target.value);setOption(data?.sources.find(s=>s.feedbackId===e.target.value)?.options[0]?.index||0);}}><option value="">选择已分析的实际交流</option>{data?.sources.map(s=><option key={s.feedbackId} value={s.feedbackId}>{s.title} · {s.feedbackId.slice(0,8)}</option>)}</select></label>
   <label>原始场景<select disabled={locked} value={option} onChange={e=>setOption(Number(e.target.value))}>{data?.sources.find(s=>s.feedbackId===source)?.options.map(o=><option key={o.index} value={o.index}>{o.question} · {o.selected?'原计划已选':'原计划未选'}</option>)}</select></label></>}
  {[...new Set([source,...cases])].filter(Boolean).map(id=>{const s=data?.sources.find(v=>v.feedbackId===id);return s?<details key={id}><summary>{s.title} · 原文 v{s.rawVersion} · {id.slice(0,8)}</summary>{s.observations.map((quote,i)=><blockquote key={i}>{quote}</blockquote>)}<small>资料版本：{s.revision}</small></details>:null;})}
  <label>用途或审核说明<textarea disabled={locked} value={reason} minLength={8} maxLength={1000} onChange={e=>setReason(e.target.value)} placeholder="说明适用范围；审核时确认问题已脱敏、适合团队训练，且引用和标准保持原样。"/></label>
  {!target&&<button className="outline" disabled={locked||!team||!source||reason.trim().length<8} onClick={()=>void action('propose')}>保存待验证候选</button>}
  {reviewer&&<fieldset><legend>独立验证来源</legend>{cases.map((v,i)=><label key={i}>{i===0?'验证记录':'留出记录'}<select disabled={locked} value={v} onChange={e=>setCases(prev=>prev.map((x,j)=>i===j?e.target.value:x))}><option value="">选择另一独立任务的实际交流</option>{data?.sources.map(s=><option key={s.feedbackId} value={s.feedbackId}>{s.title} · {s.feedbackId.slice(0,8)}</option>)}</select></label>)}</fieldset>}
  {data?.candidates.map(c=><article className="studio-output" key={c.id}><h4>{c.level} · {labels[c.state]||c.state} · v{c.revision}</h4><p>{c.option.question}</p><p>{c.reason}</p><details><summary>原资料观察标准</summary>{c.option.criteria.map((v,i)=><p key={i}><strong>{v.label}：</strong>{v.expected}</p>)}</details>
   {c.evaluation&&<><p>{c.evaluation.reason}</p>{c.evaluation.cases.map(v=><p key={v.split}>{v.split==='holdout'?'留出':'验证'} · 预算 {v.budget} · 覆盖 {v.baselineCoverage} → {v.proposedCoverage}{c.level==='L2'?'（场景相关性复核，不作为策略增益）':''}</p>)}</>}
   {reviewer&&<div className="studio-actions">{c.state==='DRAFT'&&<button className="outline" disabled={locked||cases.some(x=>!x)||reason.trim().length<8} onClick={()=>void action('evaluate',c)}>核验独立记录</button>}{c.state==='VALIDATED'&&<button className="primary" disabled={locked||reason.trim().length<8} onClick={()=>void action('approve',c)}>确认适合团队训练并共享</button>}{['APPROVED','STALE'].includes(c.state)&&<button className="outline" disabled={locked||reason.trim().length<8} onClick={()=>void action('revoke',c)}>撤回共享</button>}</div>}
  </article>)}<p className="minor">{data?.notice}</p>
 </details>;
}
