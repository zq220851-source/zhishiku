/**
 * Module 1 -> Module 2 read-only TEST_ONLY bridge.
 * Source shapes follow module1 knowledge.py, workflow.Engine.prepare/create/evaluate.
 * A preparation recommendation is not proof it was rehearsed; selectedOptionIds is
 * separately confirmed by the caller and never inferred from sheet.priorities.
 */
import { createHash } from 'node:crypto';
import type { TaskInput } from './types';
import type { PracticeEvidence, VisitEvidence, EvidenceObservation } from './five-assets';
import { validateTaskInput } from './fixture';
import { validateVisitEvidence } from './five-assets';
import type { PreparationContext, PlanDelta } from './b-evolution';

const digest=(v:unknown)=>createHash('sha256').update(JSON.stringify(v)).digest('hex');
const ident=(v:string)=>typeof v==='string' && /^[a-zA-Z0-9._:-]{1,120}$/.test(v);
const requireId=(v:string,name:string)=>{if(!ident(v))throw new Error(`${name} ID 不合法`);return v;};
const uniq=(xs:string[])=>new Set(xs).size===xs.length;
const text=(v:unknown,name:string)=>{if(typeof v!=='string'||!v.trim())throw new Error(`${name} 不能为空`);return v;};

interface M1Source { id:string;title:string;text:string;status:string; }
interface M1Criterion { id:string;label:string;expected:string;source_ids?:string[]; }
interface M1Option { id:string;title:string;why:string;question:string;criteria:M1Criterion[]; }
export interface M1SnapshotPacket {
  kind:'M1_FICTIONAL_BRIDGE_V1'; usage:'TEST_ONLY';
  taskId:string; researchId:string; repId:string; expertId:string|null;
  preparedAt:string; lesson:{id:string;title:string;status:'fictional_test_material';sources:M1Source[];blocks?:M1Source[]};
  visit:{id:string;title:string;lesson_id:string;options:M1Option[]};
  sheet:{id:string;visit_id:string;priorities:M1Option[];created_at:number};
  /** Explicit TEST ONLY assertion of rehearsed options, distinct from suggested priorities. */
  selectedOptionIds:string[];
}
export interface M1ReviewObservation {
  criterion_id:string;status:'demonstrated'|'needs_work'|'uncertain';
  evidence_id:string|null;quote:string;turn_index:number;reason:string;source_ids:string[];
}
export interface M1ReviewedRun {
  id:string;sheet_id:string;state:'review';attempt:number;updated_at:number;
  source_status:'fictional_test_material';
  task:{question:string;criteria:M1Criterion[]}; transcript:{role:string;text:string}[];
  review:{observations:M1ReviewObservation[];assessment_status:'formative_suggestion';medical_accuracy:'NA';independent_mastery:false};
}
export interface M1Bridge {
  task:TaskInput; snapshotHash:string; taskId:string; repId:string;expertId:string|null;
  researchId:string; preparedAt:string;lessonId:string;sheetId:string;
  options:{id:string;capabilityIds:string[];question:string}[];
  selectedOptionIds:string[]; candidateCapabilities:string[]; selectedCapabilities:string[];
  /** M1 criterion_id -> cross-module stable ID in this *lesson* only. */
  criterionCapabilities:Record<string,string>;
}
const capId=(lessonId:string,criterionId:string)=>`m1:${lessonId}:${criterionId}`;

export function importModule1Snapshot(p:M1SnapshotPacket):M1Bridge {
  if(p?.kind!=='M1_FICTIONAL_BRIDGE_V1'||p.usage!=='TEST_ONLY'||p.lesson?.status!=='fictional_test_material')throw new Error('只支持明确的虚构课程测试资料');
  for(const [name,value] of Object.entries({taskId:p.taskId,researchId:p.researchId,repId:p.repId,lessonId:p.lesson.id,visitId:p.visit.id,sheetId:p.sheet.id}))requireId(value,name);
  if(p.expertId!==null)requireId(p.expertId,'expertId');
  if(!Number.isFinite(Date.parse(p.preparedAt))||!Number.isFinite(p.sheet.created_at)||
    p.sheet.created_at*1000>Date.parse(p.preparedAt))throw new Error('准备时间无效或发生未来快照');
  if(p.visit.lesson_id!==p.lesson.id||p.sheet.visit_id!==p.visit.id)throw new Error('课程、拜访和准备单未匹配');
  if(!p.lesson.sources.length||p.lesson.sources.some(s=>!ident(s.id)||s.status!=='fictional_test_material'||!s.text?.trim()))throw new Error('来源未通过虚构资料核查');
  const allSources=[...p.lesson.sources,...(p.lesson.blocks??[])];
  if(allSources.some(s=>!ident(s.id)||s.status!=='fictional_test_material'||!s.text?.trim()))throw new Error('训练材料块未通过测试资料核查');
  const sourceIds=allSources.map(s=>s.id);
  if(!uniq(sourceIds))throw new Error('资料 ID 重复');
  const ids=p.visit.options.map(x=>x.id);
  if(!ids.length||!uniq(ids)||!ids.every(ident))throw new Error('候选选题有重复或缺失');
  const selected=p.selectedOptionIds;
  const proposed=p.sheet.priorities.map(x=>x.id);
  if(!selected.length||!uniq(selected)||selected.some(x=>!ids.includes(x)||!proposed.includes(x))||!uniq(proposed)||proposed.some(x=>!ids.includes(x)))throw new Error('已演练选题必须是准备单内明确选定的选题');
  for(const suggested of p.sheet.priorities){const origin=p.visit.options.find(o=>o.id===suggested.id)!;
    if(digest({question:suggested.question,criteria:suggested.criteria,title:suggested.title})!==
      digest({question:origin.question,criteria:origin.criteria,title:origin.title}))
      throw new Error('本测试桥接不允许用候选目录内容冒充冻结准备单，内容不一致需独立映射');}
  const options=p.visit.options.map(opt=>{
    text(opt.question,'医生问题'); text(opt.title,'场景名称');text(opt.why,'选题依据');
    if(!opt.criteria.length||!uniq(opt.criteria.map(c=>c.id)))throw new Error('训练评价项为空或重复');
    for(const c of opt.criteria){requireId(c.id,'criterion');text(c.label,'评价项');text(c.expected,'评价依据');
      if(c.source_ids&&(!c.source_ids.length||c.source_ids.some(id=>!sourceIds.includes(id))))throw new Error('评价项引用了不存在的资料');}
    return {id:opt.id,capabilityIds:[...new Set(opt.criteria.map(c=>capId(p.lesson.id,`${opt.id}:${c.id}`)))],question:opt.question};
  });
  // M1 reuses criterion IDs with different meanings across practice options.
  // Namespace by option: collapsing 'next' from two options would corrupt ability history.
  const criteria=p.visit.options.flatMap(o=>o.criteria.map(c=>({optionId:o.id,...c})));
  const capabilities=criteria.map(c=>({id:capId(p.lesson.id,`${c.optionId}:${c.id}`),description:`${c.label}：${c.expected}`}));
  const codebook={version:`m1-criteria:${digest(criteria).slice(0,16)}`,capabilities,
    skills:p.visit.options.map(o=>({id:`m1:${p.visit.id}:${o.id}`,topic:p.lesson.title,cognitiveTask:'回应医生并解释',
      evidenceBoundary:'仅限虚构课程原文和相应来源；不用于医学事实认证',capabilityIds:options.find(x=>x.id===o.id)!.capabilityIds}))};
  // Source ids on demo criterion may be absent in M1 demo options. An explicit
  // single fictional lesson source is a bounded adapter fallback, not approval.
  const evidence=allSources.map(s=>({id:s.id,version:digest(s.text),title:s.title,content:s.text,usage:'TEST_ONLY' as const}));
  const plan=selected.map(id=>{const o=p.visit.options.find(x=>x.id===id)!;
    const explicit=o.criteria.flatMap(c=>c.source_ids??[]);
    return {skillId:`m1:${p.visit.id}:${id}`,question:o.question,rationale:o.why,evidenceIds:[...new Set(explicit.length?explicit:sourceIds)]};
  });
  const task=validateTaskInput({fixtureId:`m1:${p.taskId}`,title:p.visit.title,knowledgeVersion:`m1-material:${digest(evidence)}`,
    scenarioVersion:`m1-options:${digest(p.visit.options)}`,strategyVersion:`m1-sheet:${digest(p.sheet)}`,codebook,evidence,plan});
  const criterionCapabilities=Object.fromEntries(criteria.map(c=>[`${c.optionId}:${c.id}`,capId(p.lesson.id,`${c.optionId}:${c.id}`)]));
  const snapshotHash=digest({task,payloadHash:digest(p)});
  return {task,snapshotHash,taskId:p.taskId,repId:p.repId,expertId:p.expertId,researchId:p.researchId,preparedAt:p.preparedAt,
    sheetId:p.sheet.id,lessonId:p.lesson.id,options,selectedOptionIds:[...selected],
    candidateCapabilities:[...new Set(options.flatMap(o=>o.capabilityIds))],
    selectedCapabilities:[...new Set(options.filter(o=>selected.includes(o.id)).flatMap(o=>o.capabilityIds))],criterionCapabilities};
}

export function importModule1Review(run:M1ReviewedRun,bridge:M1Bridge):PracticeEvidence[]{
  if(run?.state!=='review'||run.sheet_id!==bridge.sheetId||run.source_status!=='fictional_test_material'||
    run.review?.assessment_status!=='formative_suggestion'||run.review.medical_accuracy!=='NA'||run.review.independent_mastery!==false)
    throw new Error('只接受来源匹配的已完成虚构练习反馈，不得伪造正式成绩');
  requireId(run.id,'runId');
  if(!Number.isInteger(run.attempt)||run.attempt<1||!Number.isFinite(run.updated_at)||run.updated_at*1000<Date.parse(bridge.preparedAt))throw new Error('练习时间或轮次不合法');
  const option=bridge.options.find(o=>o.question===run.task?.question && o.capabilityIds.length===run.task.criteria.length &&
    run.task.criteria.every(c=>o.capabilityIds.includes(bridge.criterionCapabilities[`${o.id}:${c.id}`])));
  if(!option||!bridge.selectedOptionIds.includes(option.id))throw new Error('该练习不是冻结准备单所选场景');
  if(!Array.isArray(run.review.observations)||run.review.observations.length!==run.task.criteria.length||
    !uniq(run.review.observations.map(o=>o.criterion_id))||run.review.observations.some(o=>!run.task.criteria.some(c=>c.id===o.criterion_id)))throw new Error('逐项评价不完整或出现额外评价项');
  return run.review.observations.map(o=>{
    const cap=bridge.criterionCapabilities[`${option.id}:${o.criterion_id}`];
    const idx=o.turn_index;
    const anchored=Number.isInteger(idx)&&idx>=0&&idx<run.transcript.length&&run.transcript[idx].role==='药代'&&
      !!o.quote&&run.transcript[idx].text.includes(o.quote);
    if(o.evidence_id!==null && o.evidence_id!==`T${idx}`)throw new Error('评价的证据编号与对话轮次不符');
    if(o.status!=='uncertain'&&!anchored)throw new Error('评价没有定位到药代真实作答');
    if(o.status==='uncertain'&&o.evidence_id!==null&&!anchored)throw new Error('不确定评价证据编号无法核查');
    const criterion=run.task.criteria.find(c=>c.id===o.criterion_id)!;
    const allowed=new Set(criterion.source_ids??[]);
    if(o.status==='demonstrated'&&!o.source_ids.length)throw new Error('通过评价缺少来源');
    if(o.source_ids.some(id=>!bridge.task.evidence.some(e=>e.id===id)||(allowed.size>0&&!allowed.has(id))))throw new Error('评价引用了未授权的资料');
    return {capabilityId:cap,trainingAttemptId:`m1:${run.id}:${run.attempt}:${o.criterion_id}`,
      criterion:`${criterion.label}：${o.reason}`,result:({demonstrated:'SATISFIED',needs_work:'GAP',uncertain:'UNKNOWN'} as const)[o.status],
      ...(anchored?{origin:{system:'MODULE1' as const,runId:run.id,attempt:run.attempt,criterionId:o.criterion_id,
        lessonId:bridge.lessonId,sourceStatus:'fictional_test_material' as const,quote:o.quote,turnIndex:idx,
        sourceIds:[...o.source_ids],observedAt:new Date(run.updated_at*1000).toISOString()}}:{})};
  });
}

export function mergeM1PracticeIntoVerifiedVisit(visit:VisitEvidence,bridge:M1Bridge,run:M1ReviewedRun):VisitEvidence{
  if(visit.taskId!==bridge.taskId||visit.snapshotHash!==bridge.snapshotHash||visit.repId!==bridge.repId||
    visit.researchId!==bridge.researchId||visit.expertId!==bridge.expertId)throw new Error('练习与拜访冻结身份不一致');
  if(run.updated_at*1000>Date.parse(visit.occurredAt))throw new Error('拜访发生后才产生的训练结果不得回填到先前历史');
  const practices=importModule1Review(run,bridge);
  if(visit.practices.some(p=>practices.some(a=>a.trainingAttemptId===p.trainingAttemptId)))throw new Error('重复练习评价不得再次计数');
  const result={...visit,practices:[...visit.practices,...practices]};validateVisitEvidence(result);return result;
}
/** Make an audited TEST_ONLY M2 proposal visible to M1 as option IDs, not partial capability IDs. */
export function recommendModule1Options(bridge:M1Bridge,plan:PlanDelta,optionBudget:number,mandatoryOptions:string[]=[]){
  if(plan.status!=='COMPARISON_ONLY'||plan.proposed.some(c=>!bridge.candidateCapabilities.includes(c))||Date.parse(plan.asOf)<=Date.parse(bridge.preparedAt)||!Number.isInteger(optionBudget)||optionBudget<1||optionBudget>bridge.options.length||
    !uniq(mandatoryOptions)||mandatoryOptions.some(id=>!bridge.options.some(o=>o.id===id)))throw new Error('测试选题方案无效');
  const added=new Set(plan.added),focus=new Set(plan.proposed);
  const ranking=bridge.options.map((o,index)=>({o,index,
    score:o.capabilityIds.filter(c=>added.has(c)).length*10+o.capabilityIds.filter(c=>focus.has(c)).length*2}));
  ranking.sort((a,b)=>b.score-a.score||a.index-b.index);
  const selected=[...mandatoryOptions];for(const {o} of ranking)if(selected.length<optionBudget&&!selected.includes(o.id))selected.push(o.id);
  const previous=[...bridge.selectedOptionIds];
  return {usage:'TEST_ONLY' as const,status:'CANDIDATE_NOT_APPLIED' as const,taskId:bridge.taskId,
    sourceSnapshotHash:bridge.snapshotHash,selectedOptionIds:selected,
    addedOptionIds:selected.filter(x=>!previous.includes(x)),displacedOptionIds:previous.filter(x=>!selected.includes(x)),
    evidenceVisitIds:[...plan.usedVisitIds],reasonByOption:Object.fromEntries(selected.map(id=>{
      const caps=bridge.options.find(o=>o.id===id)!.capabilityIds;
      return [id,caps.flatMap(c=>plan.reasons[c]??[])];}))};
}

export function m1PreparationContext(bridge:M1Bridge,input:{taskId:string;startsAt:string;budget:number;mandatoryCapabilityIds?:string[]}):PreparationContext{
  const candidates=bridge.candidateCapabilities;
  if(input.budget>candidates.length||input.budget<1)throw new Error('准备预算不合法');
  const baselineSelected=bridge.selectedCapabilities.slice(0,input.budget);
  if(baselineSelected.length!==input.budget)throw new Error('现有选题能力不足以构成冻结基线');
  return {taskId:input.taskId,startsAt:input.startsAt,repId:bridge.repId,researchId:bridge.researchId,expertId:bridge.expertId,
    budget:input.budget,candidates,baselineSelected,mandatory:input.mandatoryCapabilityIds??[]};
}
export function createTestVisit(input:{bridge:M1Bridge;visitId:string;at:string;rawText:string;observations:EvidenceObservation[];practices?:PracticeEvidence[];}):VisitEvidence{
  const b=input.bridge;const result:VisitEvidence={usage:'TEST_ONLY',visitId:input.visitId,taskId:b.taskId,repId:b.repId,expertId:b.expertId,
    researchId:b.researchId,snapshotHash:b.snapshotHash,rawVersion:1,rawText:input.rawText,occurredAt:input.at,
    forecast:{candidateCapabilityIds:[...b.candidateCapabilities],selectedCapabilityIds:[...b.selectedCapabilities],budget:b.selectedCapabilities.length},
    observations:input.observations,knowledgeChecks:[],practices:input.practices??[]};
  validateVisitEvidence(result);return result;
}
