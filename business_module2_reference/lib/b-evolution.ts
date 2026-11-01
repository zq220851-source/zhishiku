/**
 * V1.0 TEST_ONLY longitudinal decision engine for the five assets.
 * Input is HUMAN-VERIFIED synthetic evidence, not unreviewed model output.
 * Never updates medical knowledge, employee scores, real expert traits or production strategies.
 */
import { createHash } from 'node:crypto';
import type { VisitEvidence, EvidenceObservation, PracticeEvidence, KnowledgeCheck } from './five-assets';
import { validateVisitEvidence } from './five-assets';

export type EvidencePointer = { visitId:string; rawVersion:number; observationIds:string[]; practiceIds:string[] };
export type DevelopmentStatus = 'OBSERVATION'|'NEEDS_VERIFICATION'|'CANDIDATE'|'COMPARISON_ONLY';
export interface PersonalLearning {
  repId:string; capabilityId:string; selfReports:number; lastPractice:'GAP'|'SATISFIED'|'UNKNOWN'|null;
  status:'NEEDS_DIAGNOSIS'|'TARGETED_RETRAIN'|'RETEST_OR_RETENTION'|'CONFLICT_RECHECK'|'INSUFFICIENT_EVIDENCE';
  reason:string; evidence:EvidencePointer[];
}
export interface ForecastLearning {
  researchId:string; capabilityId:string; questionVisits:number; coveredVisits:number; selectedOutVisits:number; absentFromPoolVisits:number;
  diagnosis:'SOMETIMES_SELECTED'|'IN_POOL_NOT_SELECTED'|'MISSING_FROM_POOL'|'MIXED'|'UNKNOWN_POOL';
  status:DevelopmentStatus; reason:string; evidence:EvidencePointer[];
}
export interface KnowledgeLearning {
  researchId:string; capabilityId:string; knowledgeVersion:string; observations:number;
  statuses:KnowledgeCheck['status'][]; recommendation:'REVIEW_RETRIEVAL'|'REVIEW_PARTIAL'|'REVIEW_CONTRADICTION'|'NO_MISSING_CLAIM';
  status:'CANDIDATE'|'OBSERVATION'; evidence:EvidencePointer[];
}
export interface ExpertLearning {
  expertId:string; researchId:string; capabilityId:string; visits:number; reporters:number;
  status:'SINGLE_REPORTED_OBSERVATION'|'REPEATED_REPORTED_OBSERVATION';
  description:string; evidence:EvidencePointer[];
}
export interface CohortLearning {
  researchId:string; capabilityId:string; reportedVisits:number; reportingReps:number; reportingExperts:number;
  denominatorVisits:number; denominatorReps:number;
  status:'DESCRIPTIVE_ONLY'|'PATTERN_FOR_REVIEW'; reason:string; evidence:EvidencePointer[];
}
export interface FiveAssetLearning {
  purpose:'TEST_ONLY'|'INTERNAL_READING'; source:'HUMAN_VERIFIED_SYNTHETIC'|'SOURCE_ANCHORED_REPORTED'; sourceDigest:string; generatedAt:string;
  personal:PersonalLearning[]; forecast:ForecastLearning[]; knowledge:KnowledgeLearning[];
  experts:ExpertLearning[]; cohort:CohortLearning[];
  blocked:{visitId:string;observationId:string;reason:string}[];
}
const sha=(v:unknown)=>createHash('sha256').update(JSON.stringify(v)).digest('hex');
const pointer=(v:VisitEvidence, obs:string[]=[], practice:string[]=[]):EvidencePointer=>({visitId:v.visitId,rawVersion:v.rawVersion,observationIds:obs,practiceIds:practice});
const sortBy=<T>(array:T[],key:(x:T)=>string)=>array.sort((a,b)=>key(a).localeCompare(key(b)));
const group=<T>(xs:T[], key:(v:T)=>string):Map<string,T[]>=>{const result=new Map<string,T[]>(); for(const x of xs){const k=key(x); const prior=result.get(k)??[];prior.push(x);result.set(k,prior);}return result;};
const distinct=(xs:string[])=>new Set(xs).size;

export function validateFrozenVisits(visits:VisitEvidence[]):VisitEvidence[]{
  const current=new Map<string,VisitEvidence>();
  const accepted=new Map<string,string>();
  for(const v of visits){
    validateVisitEvidence(v);
    if(v.rawVersion>1&&!v.reviewedAt)throw new Error('修订缺少审核时间，不能证明历史决策时已知该更正');
    if(v.reviewedAt&&Date.parse(v.reviewedAt)<Date.parse(v.occurredAt))throw new Error('审核时间不可早于拜访时间');
    const id=`${v.visitId}/${v.rawVersion}`,hash=sha(v);
    if(accepted.has(id)&&accepted.get(id)!==hash)throw new Error('同一原文版本含冲突内容');
    accepted.set(id,hash);
    const old=current.get(v.visitId);
    if(old&&(old.repId!==v.repId||old.taskId!==v.taskId||old.researchId!==v.researchId||old.snapshotHash!==v.snapshotHash||old.expertId!==v.expertId))throw new Error('原文修订不能修改冻结身份');
    if(!old||old.rawVersion<v.rawVersion) current.set(v.visitId,v);
  }
  return [...current.values()].sort((a,b)=>a.occurredAt.localeCompare(b.occurredAt)||a.visitId.localeCompare(b.visitId));
}
function observed(v:VisitEvidence):EvidenceObservation[]{
  return v.observations.filter(o=>o.kind==='EXPERT_QUESTION'&&o.mode==='REPORTED'&&o.capabilityId);
}
const dedupQuestions=(v:VisitEvidence)=>[...group(observed(v),o=>o.capabilityId!).values()].map(grouped=>grouped[0]);
const validTime=(v:VisitEvidence)=>Date.parse(v.occurredAt);

export function analyzeFiveAssets(input:{source:'HUMAN_VERIFIED_SYNTHETIC'|'SOURCE_ANCHORED_REPORTED';visits:VisitEvidence[];asOf:string}):FiveAssetLearning{
  if(!['HUMAN_VERIFIED_SYNTHETIC','SOURCE_ANCHORED_REPORTED'].includes(input.source)||!Number.isFinite(Date.parse(input.asOf)))throw new Error('来源或时间无效');
  if(input.visits.some(v=>v.usage!==(input.source==='SOURCE_ANCHORED_REPORTED'?'INTERNAL_READING':'TEST_ONLY')))throw new Error('真实来源与虚构测试不能混算');
  const now=Date.parse(input.asOf);
  // Historical replay may include later revisions, but must not read them before they were reviewed.
  if(input.visits.some(v=>validTime(v)>now))throw new Error('分析不得读取未来的拜访');
  const visits=validateFrozenVisits(input.visits.filter(v=>!v.reviewedAt||Date.parse(v.reviewedAt)<=now));
  const blocked:{visitId:string;observationId:string;reason:string}[]=[];
  for(const v of visits) for(const o of v.observations) if(o.kind==='EXPERT_QUESTION'&&o.mode!=='REPORTED')blocked.push({visitId:v.visitId,observationId:o.id,reason:`${o.mode} 不可作为实际专家提问`});
  type Q={v:VisitEvidence;o:EvidenceObservation};
  const qs:Q[]=visits.flatMap(v=>dedupQuestions(v).map(o=>({v,o})));
  const personal:PersonalLearning[]=[];
  type P={v:VisitEvidence;p?:PracticeEvidence;o?:EvidenceObservation};
  const personalTime=(x:P)=>x.p?.origin?Date.parse(x.p.origin.observedAt):validTime(x.v);
  const personals:P[]=visits.flatMap(v=>[...v.observations.filter(o=>o.kind==='REP_DIFFICULTY'&&o.mode==='REPORTED'&&o.capabilityId).map(o=>({v,o})),...v.practices.map(p=>({v,p}))]);
  for(const [,items] of group(personals,x=>`${x.v.repId}|${x.o?.capabilityId??x.p?.capabilityId}`)){
    items.sort((a,b)=>personalTime(a)-personalTime(b)||a.v.visitId.localeCompare(b.v.visitId));
    const last=items[items.length-1],cap=last.o?.capabilityId??last.p!.capabilityId,rep=last.v.repId;
    const practices=items.filter(x=>x.p),reports=items.filter(x=>x.o),latestPractice=practices.length?practices[practices.length-1]:null;
    const lastReport=reports.length?reports[reports.length-1]:null;
    let status:PersonalLearning['status']='INSUFFICIENT_EVIDENCE',reason='只有不明确的练习证据，保留验证需求';
    if(lastReport&&(!latestPractice || personalTime(lastReport)>=personalTime(latestPractice))){status=latestPractice?'CONFLICT_RECHECK':'NEEDS_DIAGNOSIS';reason=latestPractice?'旧训练不能抵消新的自述困难；安排重新验证':'员工报告困难，但未观察到经评价的练习缺项';}
    else if(latestPractice?.p?.result==='GAP'){status='TARGETED_RETRAIN';reason=`实际练习在「${latestPractice.p.criterion}」存在缺项，应针对该标准训练`;}
    else if(latestPractice?.p?.result==='SATISFIED'){status='RETEST_OR_RETENTION';reason='最新练习满足一个标准，仍需换问法或间隔复查';}
    personal.push({repId:rep,capabilityId:cap!,selfReports:reports.length,lastPractice:latestPractice?.p?.result??null,status,reason,
      evidence:items.map(x=>pointer(x.v,x.o?[x.o.id]:[],x.p?[x.p.trainingAttemptId]:[]))});
  }
  const forecast:ForecastLearning[]=[];
  for(const [,items] of group(qs,x=>`${x.v.researchId}|${x.o.capabilityId}`)){
    const first=items[0];const covered=items.filter(x=>x.v.forecast.selectedCapabilityIds.includes(x.o.capabilityId!));
    const poolNot=items.filter(x=>x.v.forecast.candidateCapabilityIds.includes(x.o.capabilityId!)&&!x.v.forecast.selectedCapabilityIds.includes(x.o.capabilityId!));
    const absent=items.filter(x=>x.v.forecast.candidatePoolKnown!==false&&!x.v.forecast.candidateCapabilityIds.includes(x.o.capabilityId!));
    const diagnoses=Number(covered.length>0)+Number(poolNot.length>0)+Number(absent.length>0);
    const diagnosis:ForecastLearning['diagnosis']=diagnoses>1?'MIXED':absent.length?'MISSING_FROM_POOL':poolNot.length?'IN_POOL_NOT_SELECTED':covered.length?'SOMETIMES_SELECTED':'UNKNOWN_POOL';
    forecast.push({researchId:first.v.researchId,capabilityId:first.o.capabilityId!,questionVisits:distinct(items.map(x=>x.v.visitId)),coveredVisits:covered.length,
      selectedOutVisits:poolNot.length,absentFromPoolVisits:absent.length,diagnosis,status:'CANDIDATE',
      reason:'仅记录被报告问题相对于当时冻结候选池和预算的差异；不宣称真实预测命中率或归因',
      evidence:items.map(x=>pointer(x.v,[x.o.id]))});
  }
  const knowledge:KnowledgeLearning[]=[];
  type K={v:VisitEvidence;k:KnowledgeCheck};const kItems:K[]=visits.flatMap(v=>v.knowledgeChecks.map(k=>({v,k})));
  for(const [,items] of group(kItems,x=>`${x.v.researchId}|${x.k.capabilityId}|${x.k.knowledgeVersion}`)){
    const first=items[0],statuses=[...new Set(items.map(x=>x.k.status))];
    const recommendation:KnowledgeLearning['recommendation']=statuses.includes('CONTRADICTED')?'REVIEW_CONTRADICTION':statuses.includes('PARTIAL')?'REVIEW_PARTIAL':statuses.includes('NOT_FOUND')?'REVIEW_RETRIEVAL':'NO_MISSING_CLAIM';
    knowledge.push({researchId:first.v.researchId,capabilityId:first.k.capabilityId,knowledgeVersion:first.k.knowledgeVersion,observations:items.length,statuses,
      recommendation,status:recommendation==='NO_MISSING_CLAIM'?'OBSERVATION':'CANDIDATE',evidence:items.map(x=>pointer(x.v,[x.k.observationId]))});
  }
  const experts:ExpertLearning[]=[];
  for(const [,items] of group(qs.filter(x=>x.v.expertId),x=>`${x.v.expertId}|${x.v.researchId}|${x.o.capabilityId}`)){
    const first=items[0],vs=distinct(items.map(x=>x.v.visitId)),rs=distinct(items.map(x=>x.v.repId));
    experts.push({expertId:first.v.expertId!,researchId:first.v.researchId,capabilityId:first.o.capabilityId!,visits:vs,reporters:rs,
      status:vs>1?'REPEATED_REPORTED_OBSERVATION':'SINGLE_REPORTED_OBSERVATION',
      description:`${vs} 次独立拜访中有员工报告该专家提出相关问题（${rs} 位报告者）；不是专家稳定偏好或人格结论`,
      evidence:items.map(x=>pointer(x.v,[x.o.id]))});
  }
  const cohort:CohortLearning[]=[];
  const denom=group(visits,v=>v.researchId);
  for(const [,items] of group(qs,x=>`${x.v.researchId}|${x.o.capabilityId}`)){
    const first=items[0],visitsInStudy=denom.get(first.v.researchId)??[];
    const nVisits=distinct(items.map(x=>x.v.visitId)),nReps=distinct(items.map(x=>x.v.repId)),nExperts=distinct(items.map(x=>x.v.expertId).filter((id):id is string=>!!id));
    const eligible=nVisits>=2&&nReps>=2&&nExperts>=2;
    cohort.push({researchId:first.v.researchId,capabilityId:first.o.capabilityId!,reportedVisits:nVisits,reportingReps:nReps,reportingExperts:nExperts,
      denominatorVisits:visitsInStudy.length,denominatorReps:distinct(visitsInStudy.map(v=>v.repId)),
      status:eligible?'PATTERN_FOR_REVIEW':'DESCRIPTIVE_ONLY',reason:eligible?'测试性多员工、多专家重复信号；仍须检验场景差异与反例':'样本独立性不足，仅保留分层描述，不能形成企业普遍结论',
      evidence:items.map(x=>pointer(x.v,[x.o.id]))});
  }
  return {purpose:input.source==='SOURCE_ANCHORED_REPORTED'?'INTERNAL_READING':'TEST_ONLY',source:input.source,generatedAt:input.asOf,
    sourceDigest:sha(visits.map(v=>[v.visitId,v.rawVersion,sha(v)])),
    personal:sortBy(personal,x=>`${x.repId}|${x.capabilityId}`),forecast:sortBy(forecast,x=>`${x.researchId}|${x.capabilityId}`),
    knowledge:sortBy(knowledge,x=>`${x.researchId}|${x.capabilityId}|${x.knowledgeVersion}`),experts:sortBy(experts,x=>`${x.expertId}|${x.capabilityId}`),
    cohort:sortBy(cohort,x=>`${x.researchId}|${x.capabilityId}`),blocked};
}

export interface PreparationContext {
  taskId:string; researchId:string; repId:string; expertId:string|null; startsAt:string;
  candidates:string[]; baselineSelected:string[]; mandatory:string[]; budget:number;
}
export interface BPriorityWeights {personalGap:number;personalDifficulty:number;personalRetention:number;expertObservation:number;pastUnselected:number;}
export const DEFAULT_B_WEIGHTS:BPriorityWeights={personalGap:5,personalDifficulty:3,personalRetention:1,expertObservation:2,pastUnselected:1};
export interface PlanDelta {
  status:'COMPARISON_ONLY'; taskId:string; old:string[]; proposed:string[]; added:string[]; displaced:string[];
  reasons:Record<string,string[]>; usedVisitIds:string[]; asOf:string; methodVersion:string;
}
/** Test-only deterministic next-task selector. Never consumes the new visit's outcome or alters a frozen task. */
export function proposeNextPreparation(p:PreparationContext,history:VisitEvidence[],weights:BPriorityWeights=DEFAULT_B_WEIGHTS,methodVersion='B_TEST_HEURISTIC_V1'):PlanDelta{
  for(const n of Object.values(weights))if(!Number.isFinite(n)||n<0||n>100)throw new Error('试验权重无效');
  if(!p.taskId||!p.repId||!p.researchId||!Number.isFinite(Date.parse(p.startsAt))||!Number.isInteger(p.budget)||p.budget<1||p.budget>20)throw new Error('下一任务无效');
  for(const array of [p.candidates,p.baselineSelected,p.mandatory]) if(new Set(array).size!==array.length||array.some(x=>!x))throw new Error('能力列表重复或缺失');
  if(p.baselineSelected.length!==Math.min(p.budget,p.candidates.length)||p.mandatory.length>p.budget||[...p.mandatory,...p.baselineSelected].some(x=>!p.candidates.includes(x)))throw new Error('基线题量、必选或候选池不一致');
  // Filter revisions by *review time before* collapsing to the latest eligible raw version.
  const eligible=history.filter(v=>validTime(v)<Date.parse(p.startsAt)&&(!v.reviewedAt||Date.parse(v.reviewedAt)<Date.parse(p.startsAt)));
  const current=validateFrozenVisits(eligible).filter(v=>v.researchId===p.researchId);
  const byCap=new Map<string,{score:number;reasons:string[]}>();
  for(const id of p.candidates)byCap.set(id,{score:0,reasons:[]});
  const contributions=new Map<string,Set<string>>();
  const credit=(cap:string,key:string,value:number,reason:string)=>{
    const line=byCap.get(cap);if(!line)return;
    const set=contributions.get(cap)??new Set<string>();if(set.has(key))return;set.add(key);contributions.set(cap,set);
    line.score+=value;line.reasons.push(reason);
  };
  // Use the *latest* verified training state, not a cumulative pile of old mistakes.
  const learner=analyzeFiveAssets({source:'HUMAN_VERIFIED_SYNTHETIC',visits:current,asOf:p.startsAt})
    .personal.filter(x=>x.repId===p.repId);
  for(const item of learner){
    const weight=item.status==='TARGETED_RETRAIN'?weights.personalGap:
      item.status==='NEEDS_DIAGNOSIS'||item.status==='CONFLICT_RECHECK'?weights.personalDifficulty:
      item.status==='RETEST_OR_RETENTION'?weights.personalRetention:0;
    if(weight)credit(item.capabilityId,`personal:${item.capabilityId}`,weight,`当前个人训练需求：${item.status}（${item.reason}）`);
  }
  for(const v of current){
    for(const o of dedupQuestions(v)){
      if(v.expertId&&p.expertId===v.expertId)credit(o.capabilityId!,`expert:${v.visitId}:${o.capabilityId}`,weights.expertObservation,`目标专家过往被报告追问：${v.visitId}（仅观察）`);
      if(!v.forecast.selectedCapabilityIds.includes(o.capabilityId!))credit(o.capabilityId!,`uncovered:${v.visitId}:${o.capabilityId}`,weights.pastUnselected,`过往冻结任务未选中：${v.visitId}`);
    }
  }
  const scores=[...byCap.entries()].sort((a,b)=>b[1].score-a[1].score||p.candidates.indexOf(a[0])-p.candidates.indexOf(b[0]));
  const proposed=[...p.mandatory];
  for(const [cap] of scores)if(proposed.length<p.budget&&!proposed.includes(cap))proposed.push(cap);
  const reasons:Record<string,string[]>={};for(const id of proposed)reasons[id]=byCap.get(id)?.reasons.length?byCap.get(id)!.reasons:['保持默认候选顺序或必选约束'];
  return {status:'COMPARISON_ONLY',taskId:p.taskId,old:[...p.baselineSelected],proposed,
    added:proposed.filter(x=>!p.baselineSelected.includes(x)),displaced:p.baselineSelected.filter(x=>!proposed.includes(x)),
    reasons,usedVisitIds:current.map(v=>v.visitId),asOf:p.startsAt,methodVersion};
}
export interface BlindTrial { id:string; preparedAt:string; observedVisitId:string; testOnly:true; }
export interface TrialResult {trialId:string;oldCovered:number;newCovered:number;oldMisses:string[];newMisses:string[];lost:string[];passedBudget:boolean;}
/** Evaluation on future synthetic visits not provided to the next-task selector; never a clinical outcome metric. */
export function evaluateNextPreparation(plan:PlanDelta,p:PreparationContext,trial:BlindTrial,allVisits:VisitEvidence[]):TrialResult{
  if(!trial.testOnly||trial.preparedAt!==p.startsAt||plan.taskId!==p.taskId)throw new Error('冻结试验与准备任务不匹配');
  const all=validateFrozenVisits(allVisits),observed=all.find(x=>x.visitId===trial.observedVisitId);
  if(!observed||validTime(observed)<=Date.parse(p.startsAt)||observed.researchId!==p.researchId)throw new Error('必须使用时间在准备之后的独立同研究样例');
  if(plan.usedVisitIds.includes(observed.visitId))throw new Error('留出观察泄露进选题');
  const requires=[...new Set(dedupQuestions(observed).map(o=>o.capabilityId!))];
  const oldMisses=requires.filter(x=>!plan.old.includes(x)),newMisses=requires.filter(x=>!plan.proposed.includes(x));
  return {trialId:trial.id,oldCovered:requires.length-oldMisses.length,newCovered:requires.length-newMisses.length,oldMisses,newMisses,lost:plan.displaced,
    passedBudget:plan.old.length<=p.budget&&plan.proposed.length<=p.budget&&p.mandatory.every(id=>plan.proposed.includes(id))};
}
