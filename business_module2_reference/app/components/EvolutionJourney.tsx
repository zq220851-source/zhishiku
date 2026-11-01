'use client';
import { useState } from 'react';

type Row={reason?:string;description?:string;status?:string;diagnosis?:string;recommendation?:string;capabilityId:string};
type Assets={personal:Row[];forecast:Row[];knowledge:Row[];experts:Row[];cohort:Row[]};
type MethodItem={id:string;state:string;changeReason:string;method:{condition:string;action:string;reason:string;exceptions:string[];supports:{episode_id:string;quote:string}[];counters:{episode_id:string;quote:string}[]};evaluation?:{reason:string};createdAt:string};
type MethodState={sourceCount:number;distinctVisits:number;methods:MethodItem[]};
type Stage='source'|'assets'|'method'|'next';
type Key=keyof Assets;
const keys:Key[]=['personal','forecast','knowledge','experts','cohort'];
const info:Record<Key,{title:string;hint:string;next:string;icon:string}>={
  personal:{title:'个人能力',hint:'哪些地方还要练',next:'下一次补学与表达练习',icon:'◎'},
  forecast:{title:'预测经验',hint:'候选与重点哪里偏了',next:'调整下一次预测重点',icon:'◇'},
  knowledge:{title:'知识覆盖',hint:'哪些资料还缺证据',next:'补查资料或调整内容',icon:'▤'},
  experts:{title:'专家观察',hint:'记录实际报告的关切',next:'结合背景辅助以后准备',icon:'◈'},
  cohort:{title:'企业群体',hint:'是否出现跨人的共性',next:'有充分证据再做团队改进',icon:'▦'},
};
const stages:{id:Stage;name:string;hint:string}[]=[
  {id:'source',name:'复盘证据',hint:'发现差异'},
  {id:'assets',name:'经验更新',hint:'写入五层'},
  {id:'method',name:'方法验证',hint:'比较新旧'},
  {id:'next',name:'下次准备',hint:'受控应用'},
];
const methodStatus:Record<string,string>={DRAFT:'待验证',TESTED_CANDIDATE:'待审核',APPROVED_TEST_ONLY:'仅测试授权',STALE:'来源失效',REJECTED:'验证未通过'};
const examples:Assets={
  personal:[{capabilityId:'demo',description:'回答适用范围时仍有不确定'}],
  forecast:[{capabilityId:'demo',description:'候选中有外推问题，但访前未选为重点'}],
  knowledge:[{capabilityId:'demo',description:'需要进一步核对资料的适用边界'}],
  experts:[{capabilityId:'demo',description:'本人报告医生追问过适用范围'}],
  cohort:[],
};
function valueOf(row:Row){return row.reason||row.description||row.recommendation||row.diagnosis||row.status||'已记录证据，待进一步解释';}
export function EvolutionJourney({assets,simulatedAssets,methods,analysisCount,hasFrozenForecast,busy,modelReady,onPropose}:{
  assets?:Assets|null;simulatedAssets?:Assets|null;methods:MethodState|null;analysisCount:number;hasFrozenForecast:boolean;busy:boolean;modelReady:boolean;onPropose:()=>Promise<void>;
}){
  const [stage,setStage]=useState<Stage>('assets');
  const [selected,setSelected]=useState<Key>('forecast');
  const [demo,setDemo]=useState(false);
  const [selectedMethod,setSelectedMethod]=useState<string>('');
  const actualAssets=demo?examples:assets;
  const count=(k:Key)=>actualAssets?.[k]?.length||0;
  const total=keys.reduce((n,k)=>n+count(k),0);
  const actualMethods=methods?.methods||[];
  const method=actualMethods.find(m=>m.id===selectedMethod)||actualMethods[0];
  const allowed=actualMethods.filter(m=>m.state==='APPROVED_TEST_ONLY');
  const stageDone:Record<Stage,boolean>={source:analysisCount>0||demo,assets:total>0,method:actualMethods.length>0&&!demo,next:allowed.length>0&&!demo};
  return <section className="ev-shell" aria-label="自进化过程">
    <div className="ev-heading"><div><span className="ev-eyebrow">EVOLUTION / WORKSPACE</span><h2>自进化轨迹</h2><p>从这次复盘，到下一次准备。</p></div><label className="ev-demo-switch"><input type="checkbox" checked={demo} onChange={e=>{setDemo(e.target.checked);setStage('assets');}}/>看流程示例</label></div>
    {demo&&<p className="ev-demo-note">示意内容 · 不读取或写入实际资产，也不表示验证通过</p>}
    <div className="ev-layout">
      <nav className="ev-rail" aria-label="进化阶段">{stages.map((s,i)=><button key={s.id} type="button" className={'ev-stage '+(stage===s.id?'current':'')} aria-current={stage===s.id?'step':undefined} onClick={()=>setStage(s.id)}><span className="ev-step-index">{stageDone[s.id]?'✓':String(i+1).padStart(2,'0')}</span><span><b>{s.name}</b><small>{s.hint}</small></span><i className={'ev-stage-dot '+(stageDone[s.id]?'done':'')}/></button>)}<div className="ev-rail-foot">每一步均可展开核对</div></nav>
      <div className="ev-work">
        {stage==='source'&&<><div className="ev-main-head"><span className="ev-kicker">01 / INPUT</span><h3>从哪里发现需要改进</h3></div><div className="ev-flow-list"><div className="ev-flow-row"><b>访前版本</b><span>{hasFrozenForecast?'已有冻结预测':'未提供冻结预测'}</span></div><div className="ev-flow-arrow">↓</div><div className="ev-flow-row"><b>复盘分析</b><span>{analysisCount?`已分析 ${analysisCount} 条`:'还没有可用分析'}</span></div><div className="ev-flow-arrow">↓</div><div className="ev-flow-row"><b>可用证据</b><span>{demo?'流程示例':total?`形成 ${total} 条五层记录`:'证据不足，暂不推断'}</span></div></div><p className="ev-hint">仅基于核对过的复盘和访前原始版本；未报告不等于未发生。</p><div className="ev-next-btn"><button onClick={()=>setStage('assets')}>查看更新结果 →</button></div></>}
        {stage==='assets'&&<><div className="ev-main-head"><span className="ev-kicker">02 / MEMORY</span><h3>这次让系统记住了什么</h3><p>点选一层，查看证据和后续影响。</p></div><div className="ev-node-grid">{keys.map(k=><button type="button" key={k} onClick={()=>setSelected(k)} className={'ev-node '+(selected===k?'selected':'')}><span className="ev-node-icon">{info[k].icon}</span><b>{info[k].title}</b><small>{count(k)?`${count(k)} 条证据`:'待积累'}</small></button>)}</div><div className="ev-result"><div className="ev-result-top"><span>已选 / {info[selected].title}</span><b>{count(selected)?'有新记录':'暂无更新'}</b></div>{actualAssets?.[selected]?.length?<ul>{actualAssets[selected].slice(0,3).map((r,i)=><li key={i}>{valueOf(r)}</li>)}</ul>:<p>没有足够证据，不生成结论。</p>}<div className="ev-bridge"><span>进入下一次</span><strong>{info[selected].next}</strong><small>建议方向，非已自动执行</small></div></div><div className="ev-next-btn"><button onClick={()=>setStage('method')}>继续看方法进化 →</button></div></>}
        {stage==='method'&&<><div className="ev-main-head"><span className="ev-kicker">03 / METHOD</span><h3>方法怎么改变</h3><p>多次经历 → 候选 → 独立验证 → 审核</p></div><div className="ev-method-meta"><span>独立交流 <b>{demo?'示例':methods?.distinctVisits??0}</b></span><span>方法候选 <b>{demo?'演示':actualMethods.length}</b></span></div><div className="ev-method-compare"><div><span>原做法</span><p>按既有规则选题与训练</p></div><div className="ev-compare-arrow">→</div><div><span>候选调整</span><p>{demo?'参考预测落差，重新权衡候选问题的优先级':method?.method.action||'尚无可验证的方法候选'}</p></div></div>{!demo&&<><div className="ev-method-controls"><button type="button" disabled={busy||!modelReady||(methods?.distinctVisits??0)<2} onClick={onPropose}>归纳方法候选</button><small>需要至少两次独立经历及模型连接</small></div>{actualMethods.length>1&&<div className="ev-method-list">{actualMethods.map(m=><button key={m.id} className={method?.id===m.id?'active':''} onClick={()=>setSelectedMethod(m.id)}>{m.method.condition.slice(0,38)} · {methodStatus[m.state]||m.state}</button>)}</div>}</>}
        <div className="ev-validation"><span>{demo?'待独立验证':method?methodStatus[method.state]||method.state:'尚无方法'}</span><p>{demo?'须独立样例比较，不能凭一两次复盘启用。':method?.evaluation?.reason||'未形成通过独立验证与审核的结论。'}</p></div><div className="ev-next-btn"><button onClick={()=>setStage('next')}>查看使用边界 →</button></div></>}
        {stage==='next'&&<><div className="ev-main-head"><span className="ev-kicker">04 / APPLY</span><h3>下次准备会怎样变</h3></div><div className="ev-next-panel"><span className="ev-light">{!demo&&allowed.length?'◉':'○'}</span><div><b>{!demo&&allowed.length?'存在测试授权方法':'暂无可直接启用的新方法'}</b><p>{demo?'验证和审核通过后，才允许在下一次准备中选择使用。':allowed.length?`${allowed.length} 个方法可在符合条件时，经本人选择用于测试准备。`:'五层记录可供下次准备参考；方法层仍按现有规则运行。'}</p></div></div><div className="ev-guard"><b>保持三条边界</b><span>不替换医学知识 · 不追认事后预测 · 不自动正式发布</span></div><div className="ev-next-btn"><a className="ev-next-link" href="http://127.0.0.1:8892/?flow=visit">进入访前准备 ↗</a></div></>}
      </div>
      <aside className="ev-inspector"><span className="ev-kicker">EVIDENCE / DETAIL</span><h3>依据与状态</h3>
        {stage==='assets'?<><b>{info[selected].title}</b><p>{info[selected].hint}</p><div className="ev-counter">{count(selected)} <small>条当前记录</small></div>{count(selected)?<p>展开选中的记录，核对来源后才能继续追踪。</p>:<p>证据不足时保持空白，不推测。</p>}</>:stage==='method'?<><b>{method?.method.condition||'方法候选'}</b><p>{method?.method.reason||'有规律才提出候选。'}</p>{method&&<details><summary>来源与反例</summary>{method.method.supports.map((s,i)=><blockquote key={i}>{s.quote}</blockquote>)}{method.method.counters.map((s,i)=><blockquote key={'c'+i}>反例：{s.quote}</blockquote>)}<p>不适用：{method.method.exceptions.join('；')||'未注明'}</p></details>}</>:stage==='next'?<><b>后续使用</b><p>只有符合条件且获测试授权的方法，才能在准备时由用户选择。</p><p>未获授权时沿用旧流程。</p></>:<><b>来源版本</b><p>{hasFrozenForecast?'保留拜访前的冻结记录。':'缺少冻结预测，预测差异为未知。'}</p><p>修改原文后，相关证据须重新检查。</p></>}
        {simulatedAssets&&keys.some(k=>simulatedAssets[k].length>0)&&!demo&&<details className="ev-sim-only"><summary>模拟记录（隔离）</summary><p>模拟联调结果不进入实际经历或方法候选。</p></details>}
      </aside>
    </div>
  </section>;
}
