import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import { importModule1Snapshot,importModule1Review,mergeM1PracticeIntoVerifiedVisit,createTestVisit,m1PreparationContext,recommendModule1Options } from '../lib/module1-integration';
import type { M1SnapshotPacket, M1ReviewedRun } from '../lib/module1-integration';
import { analyzeFiveAssets, proposeNextPreparation,evaluateNextPreparation } from '../lib/b-evolution';
import { projectVisit } from '../lib/five-assets';
const fixture=JSON.parse(readFileSync(require('node:path').join(__dirname,'../fixtures/module1/m1-fictional-packet.json'),'utf8')) as M1SnapshotPacket;
const clone=<T>(v:T):T=>JSON.parse(JSON.stringify(v)) as T;
const prepared=()=>importModule1Snapshot(clone(fixture));
const review=(status:'needs_work'|'demonstrated'='needs_work'):M1ReviewedRun=>({
  id:'fictional-run-001',sheet_id:'fictional-sheet-001',state:'review',attempt:1,
  updated_at:Date.parse('2026-10-31T09:00:00Z')/1000,source_status:'fictional_test_material',
  task:{question:fixture.visit.options.find(o=>o.id==='followup')!.question,
    criteria:fixture.visit.options.find(o=>o.id==='followup')!.criteria},
  transcript:[{role:'医生',text:'那接下来如何核实？'}, {role:'药代',text:'我不确定要查什么，先记下来吧。'}],
  review:{assessment_status:'formative_suggestion',medical_accuracy:'NA',independent_mastery:false,
    observations:[{criterion_id:'next',status,evidence_id:'T1',quote:'我不确定要查什么，先记下来吧。',turn_index:1,
      reason:'没有说明核实来源和具体安排',source_ids:['demo-evidence:sections.2']}]}
});
const observation=(rawText:string,quote:string,kind:'EXPERT_QUESTION'|'REP_DIFFICULTY',capabilityId:string,mode:'REPORTED'|'DENIED'='REPORTED')=>({
  id:kind==='EXPERT_QUESTION'?'q1':'d1',kind,mode,capabilityId,quote,
  startCp:Array.from(rawText.slice(0,rawText.indexOf(quote))).length,endCp:Array.from(rawText.slice(0,rawText.indexOf(quote))).length+Array.from(quote).length
});

test('M1真实虚构课程选题进入M2冻结任务，选题≠已经演练，能力名称不与其他选题串线',()=>{
  const b=prepared();assert.equal(b.task.plan.length,2);assert.equal(b.options.length,3);
  assert.equal(b.task.evidence.length,4);
  assert.ok(b.task.plan.every(p=>!p.skillId.endsWith('evidence_scope')));
  assert.notEqual(b.criterionCapabilities['evidence_scope:next'],b.criterionCapabilities['followup:next']);
  const reread=prepared();assert.equal(b.snapshotHash,reread.snapshotHash);
});

test('未审核的课程、错误的资料、重复选题和随意声称已演练都不能入库',()=>{
  for(const mutation of [
    (p:M1SnapshotPacket)=>{p.lesson.status='pending_medical_review' as any;},
    (p:M1SnapshotPacket)=>{p.lesson.sources[0].status='pending_medical_review';},
    (p:M1SnapshotPacket)=>{p.selectedOptionIds=['nonexistent'];},
    (p:M1SnapshotPacket)=>{p.visit.options[1].criteria[0].source_ids=['bad'];},
    (p:M1SnapshotPacket)=>{p.selectedOptionIds=['needs','needs'];},
  ]){const p=clone(fixture);mutation(p);assert.throws(()=>importModule1Snapshot(p));}
});

test('M1来源锚定的逐项评价转为能力证据，不能当成医学评分或长期掌握',()=>{
  const b=prepared();const x=importModule1Review(review(),b);
  assert.equal(x.length,1);assert.equal(x[0].result,'GAP');
  assert.equal(x[0].capabilityId,b.criterionCapabilities['followup:next']);
  const fake=review('demonstrated');fake.review.observations[0].reason='这次表现满足观察项';
  assert.equal(importModule1Review(fake,b)[0].result,'SATISFIED');
  const invalid=review();invalid.review.medical_accuracy='PASS' as any;
  assert.throws(()=>importModule1Review(invalid,b));
  const noAnchor=review();noAnchor.review.observations[0].quote='不是原话';
  assert.throws(()=>importModule1Review(noAnchor,b));
  const wrongRound=review();wrongRound.review.observations[0].evidence_id='T0';
  assert.throws(()=>importModule1Review(wrongRound,b));
});

test('训练评价影响M2个人需求，再影响下一轮选题；留出未来拜访绝不泄露',()=>{
  const b=prepared();const raw='我在核实问题上还是不够清楚，医生实际追问了资料的范围。';
  const practice=review();const cap=b.criterionCapabilities['followup:next'];
  let v=createTestVisit({bridge:b,visitId:'m1-visit-a',at:'2026-10-31T10:00:00Z',rawText:raw,observations:[
    observation(raw,'医生实际追问了资料的范围','EXPERT_QUESTION',b.criterionCapabilities['evidence_scope:comparison'])]});
  v=mergeM1PracticeIntoVerifiedVisit(v,b,practice);
  assert.equal(v.practices[0].result,'GAP');assert.ok(projectVisit(v).entries.some(x=>x.kind==='PERSONAL_SKILL'&&x.status==='TRAINING_EVIDENCE'));
  const learned=analyzeFiveAssets({source:'HUMAN_VERIFIED_SYNTHETIC',visits:[v],asOf:'2026-11-01T00:00:00Z'});
  assert.ok(learned.personal.some(x=>x.capabilityId===cap&&x.status==='TARGETED_RETRAIN'));
  const ctx=m1PreparationContext(b,{taskId:'m1-prep-next',startsAt:'2026-11-02T09:00:00Z',budget:2,mandatoryCapabilityIds:[b.criterionCapabilities['needs:focus']]});
  const proposal=proposeNextPreparation(ctx,[v]);
  assert.ok(proposal.usedVisitIds.includes(v.visitId));assert.ok(proposal.proposed.includes(cap));
  const mapped=recommendModule1Options(b,proposal,2,['needs']);
  assert.equal(mapped.status,'CANDIDATE_NOT_APPLIED');assert.ok(mapped.selectedOptionIds.includes('followup'));
  const futureRaw='医生还是问了怎样核实。';
  const future=createTestVisit({bridge:b,visitId:'m1-future',at:'2026-11-04T10:00:00Z',rawText:futureRaw,
    observations:[observation(futureRaw,'医生还是问了怎样核实','EXPERT_QUESTION',cap)]});
  const result=evaluateNextPreparation(proposal,ctx,{id:'holdout-m1',preparedAt:ctx.startsAt,observedVisitId:'m1-future',testOnly:true},[v,future]);
  assert.ok(result.passedBudget);assert.ok(result.newCovered>=result.oldCovered);
  const contaminated=proposeNextPreparation(ctx,[v,future]); // future visit must be filtered internally
  assert.deepEqual(contaminated.proposed,proposal.proposed);
});

test('异常练习发生时间、身份和重复写入都被拒绝',()=>{
  const b=prepared(),raw='我需要查资料。';
  const v=createTestVisit({bridge:b,visitId:'m1-visit-b',at:'2026-10-31T10:00:00Z',rawText:raw,observations:[]});
  const merged=mergeM1PracticeIntoVerifiedVisit(v,b,review());
  assert.throws(()=>mergeM1PracticeIntoVerifiedVisit(merged,b,review()));
  const futureReview=review();futureReview.updated_at=Date.parse('2026-11-03T10:00:00Z')/1000;
  assert.throws(()=>mergeM1PracticeIntoVerifiedVisit(v,b,futureReview));
  assert.throws(()=>mergeM1PracticeIntoVerifiedVisit({...v,repId:'other-rep'},b,review()));
});

test('真实冻结准备单与候选目录内容冲突不得静默替换',()=>{
  const bad=clone(fixture);bad.sheet.priorities[0].question='另一道并非当时的题';
  assert.throws(()=>importModule1Snapshot(bad),/内容不一致/);
  const time=clone(fixture);time.sheet.created_at=Date.parse('2026-11-03T10:00:00Z')/1000;
  assert.throws(()=>importModule1Snapshot(time),/准备时间/);
});

test('训练记录不属于原冻结选题时不能冒认已完成训练',()=>{
  const bad=review();bad.task.question='另一个问题';
  assert.throws(()=>importModule1Review(bad,prepared()),/不是冻结准备单所选场景/);
});
