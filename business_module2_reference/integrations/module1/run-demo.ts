/** Deterministic two-round fictional demonstration using actual M1 fixture source. */
import { readFileSync,writeFileSync,mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { importModule1Snapshot,importModule1Review,createTestVisit,mergeM1PracticeIntoVerifiedVisit,m1PreparationContext,recommendModule1Options } from '../../lib/module1-integration';
import type { M1ReviewedRun,M1SnapshotPacket } from '../../lib/module1-integration';
import { analyzeFiveAssets,proposeNextPreparation,evaluateNextPreparation } from '../../lib/b-evolution';
import { projectVisit } from '../../lib/five-assets';
const packet=JSON.parse(readFileSync(join(__dirname,'../../fixtures/module1/m1-fictional-packet.json'),'utf8')) as M1SnapshotPacket;
const bridge=importModule1Snapshot(packet);
const explanation='我不确定要查什么，先记下来吧。';
function reviewed(id:string,result:'needs_work'|'demonstrated',timestamp:string,answer:string):M1ReviewedRun{
  const option=packet.visit.options.find(o=>o.id==='followup')!;
  return {id,sheet_id:packet.sheet.id,state:'review',attempt:1,updated_at:Date.parse(timestamp)/1000,
    source_status:'fictional_test_material',task:{question:option.question,criteria:option.criteria},
    transcript:[{role:'医生',text:option.question},{role:'药代',text:answer}],
    review:{assessment_status:'formative_suggestion',medical_accuracy:'NA',independent_mastery:false,
      observations:[{criterion_id:'next',status:result,evidence_id:'T1',quote:answer,turn_index:1,
        reason:result==='needs_work'?'没有说明查证途径与反馈安排':'说明了核对材料及后续反馈计划',
        source_ids:['demo-evidence:sections.2']}]}};
}
const observation=(text:string,fragment:string,kind:'EXPERT_QUESTION'|'REP_DIFFICULTY',cap:string)=>{
  const prefix=text.slice(0,text.indexOf(fragment)), startCp=Array.from(prefix).length;
  return {id:kind==='EXPERT_QUESTION'?'q1':'d1',kind,mode:'REPORTED' as const,capabilityId:cap,quote:fragment,startCp,endCp:startCp+Array.from(fragment).length};
};
const firstText='这次医生实际追问了资料没有比较组能否说明更好，我只能说回头再核实。';
const missingCap=bridge.criterionCapabilities['evidence_scope:comparison'];
const priorCap=bridge.criterionCapabilities['followup:next'];
let v1=createTestVisit({bridge,visitId:'fictional-v1',at:'2026-10-31T10:00:00Z',rawText:firstText,
  observations:[observation(firstText,'医生实际追问了资料没有比较组能否说明更好','EXPERT_QUESTION',missingCap)]});
v1=mergeM1PracticeIntoVerifiedVisit(v1,bridge,reviewed('fictional-run-1','needs_work','2026-10-31T09:00:00Z',explanation));
const secondText='第二次沟通我确认了还需要补充哪些依据；这次没有报告新的医生追问。';
let v2=createTestVisit({bridge,visitId:'fictional-v2',at:'2026-11-01T10:00:00Z',rawText:secondText,observations:[]});
v2=mergeM1PracticeIntoVerifiedVisit(v2,bridge,reviewed('fictional-run-2','demonstrated','2026-11-01T09:00:00Z','我要查看原始材料，再核对未测量的指标，并约定下一次带回结果。'));
const asOf='2026-11-02T09:00:00Z';
const before=analyzeFiveAssets({source:'HUMAN_VERIFIED_SYNTHETIC',visits:[v1],asOf:'2026-11-01T08:00:00Z'});
const after=analyzeFiveAssets({source:'HUMAN_VERIFIED_SYNTHETIC',visits:[v1,v2],asOf});
const ctx=m1PreparationContext(bridge,{taskId:'fictional-m1-next',startsAt:asOf,budget:2,
  mandatoryCapabilityIds:[bridge.criterionCapabilities['needs:focus']]});
const change=proposeNextPreparation(ctx,[v1,v2]);
const selection=recommendModule1Options(bridge,change,2,['needs']);
const packet2: M1SnapshotPacket=JSON.parse(JSON.stringify(packet));
packet2.taskId='fictional-m1-next';packet2.sheet.id='fictional-sheet-002';packet2.selectedOptionIds=selection.selectedOptionIds;
packet2.preparedAt=asOf;packet2.sheet.created_at=Date.parse(asOf)/1000;
const next=importModule1Snapshot(packet2);
const futureText='接下来专家仍然问了能不能从这个资料推断更好。';
const future=createTestVisit({bridge:next,visitId:'fictional-v3-holdout',at:'2026-11-04T10:00:00Z',rawText:futureText,
  observations:[observation(futureText,'专家仍然问了能不能从这个资料推断更好','EXPERT_QUESTION',missingCap)]});
const holdout=evaluateNextPreparation(change,ctx,{id:'fictional-holdout',preparedAt:asOf,observedVisitId:future.visitId,testOnly:true},[v1,v2,future]);
if(!selection.selectedOptionIds.includes('evidence_scope')||!change.added.includes(missingCap)||holdout.newCovered<=holdout.oldCovered)
  throw new Error('两轮准备没有产生所需的可观察差异');
const result={scope:'TEST_ONLY - no API, no medical approval, no actual model inference',m1Source:'module1 knowledge.py fictional demo-evidence and demo-visit',
  initial:{selectedOptionIds:packet.selectedOptionIds,candidateOptionIds:bridge.options.map(o=>o.id),snapshotHash:bridge.snapshotHash},
  first:{visitId:v1.visitId,observedCapability:missingCap,practice:v1.practices,assets:projectVisit(v1).entries,
    personalStatus:before.personal.find(p=>p.capabilityId===priorCap)?.status},
  second:{visitId:v2.visitId,practice:v2.practices,personalStatus:after.personal.find(p=>p.capabilityId===priorCap)?.status},
  next:{oldCapabilities:change.old,newCapabilities:change.proposed,added:change.added,displaced:change.displaced,
    oldOptionIds:packet.selectedOptionIds,newOptionIds:selection.selectedOptionIds,selectionStatus:selection.status,
    nextTaskSnapshotHash:next.snapshotHash,usedVisitIds:change.usedVisitIds},
  holdout,limitations:['Selected options and review transcripts are synthetic examples conforming to actual M1 shapes; not exported user history',
    'M1 has not consumed this candidate through its production Engine.prepare()',
    'Knowledge/course data is fictional and not a medically reviewed corpus',
    'M1 Python service and M2 Next.js have not been started together']};
const out=join(__dirname,'../../demo/module1-bridge');mkdirSync(out,{recursive:true});
writeFileSync(join(out,'results.json'),JSON.stringify(result,null,2),'utf8');
console.log(JSON.stringify({before:result.initial.selectedOptionIds,after:result.next.newOptionIds,first:result.first.personalStatus,
  second:result.second.personalStatus,holdout:result.holdout},null,2));
