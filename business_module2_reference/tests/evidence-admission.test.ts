import { test } from 'node:test';
import assert from 'node:assert/strict';
import { admitReviewedEvents, reviewedQuestionObservations, withReviewedQuestions, type EventReview } from '../lib/evidence-admission';
import type { ReviewEvidenceSnapshot } from '../lib/semantic-evidence';
import { projectVisit, type VisitEvidence } from '../lib/five-assets';
const raw='医生没有问终点，却追问了外推。';
const span=(quote:string)=>({quote,startCp:Array.from(raw.slice(0,raw.indexOf(quote))).length,endCp:Array.from(raw.slice(0,raw.indexOf(quote))).length+Array.from(quote).length});
const snap=():ReviewEvidenceSnapshot=>({usage:'TEST_ONLY',rawVersion:1,rawText:raw,events:[{id:'question1',kind:'EXPERT_QUESTION',factuality:'REPORTED',capabilityId:'extrapolation',...span('却追问了外推')},{id:'question2',kind:'EXPERT_QUESTION',factuality:'REPORTED',capabilityId:'endpoint',...span('医生没有问终点')}],links:[]});
const review=(eventId:string,verdict:EventReview['verdict'],verifiedFactuality:EventReview['verifiedFactuality']='REPORTED'):EventReview=>({eventId,verdict,reviewerId:'test-reviewer',reason:'检查了否定作用域、说话人和事实发生性',checkedRawVersion:1,verifiedFactuality});
const visit=():VisitEvidence=>({usage:'TEST_ONLY',visitId:'visit-1',taskId:'task-1',repId:'rep-1',expertId:'expert-1',researchId:'research-1',snapshotHash:'hash-1',rawVersion:1,rawText:raw,occurredAt:'2026-11-01T00:00:00Z',forecast:{selectedCapabilityIds:[],candidateCapabilityIds:['extrapolation'],budget:0},observations:[],knowledgeChecks:[],practices:[]});
test('a verified positive question is admitted while negated target is withheld by reviewer',()=>{
  const x=reviewedQuestionObservations(snap(),[review('question1','APPROVE_TEST_ONLY'),review('question2','REJECT','DENIED')]);
  assert.deepEqual(x.observations.map(o=>o.id),['question1']);assert.equal(x.withheld.length,1);
  const entries=projectVisit(withReviewedQuestions(visit(),snap(),[review('question1','APPROVE_TEST_ONLY'),review('question2','REJECT','DENIED')])).entries;
  assert.equal(entries.filter(e=>e.kind==='EXPERT_OBSERVATION').length,1);
  assert.equal(entries.filter(e=>e.kind==='FORECAST').length,1);
  assert.equal(entries.filter(e=>e.kind==='COHORT_EVENT').length,1);
});
test('without review no model allegation can be projected into five assets',()=>{
  assert.deepEqual(projectVisit(withReviewedQuestions(visit(),snap(),[])).entries,[]);
});
test('review factuality disagreement cannot be silently promoted',()=>{
  const x=admitReviewedEvents(snap(),[review('question1','APPROVE_TEST_ONLY','DENIED')]);
  assert.equal(x.accepted.length,0); assert.match(x.withheld[0].reason,/冲突/);
});
test('raw version mismatch, false span, duplicate reviewer and unsupported verdict fail closed',()=>{
  assert.throws(()=>withReviewedQuestions({...visit(),rawVersion:2},snap(),[]),/原文或版本/);
  const corrupted=snap();corrupted.events[0].quote='不存在';
  assert.throws(()=>admitReviewedEvents(corrupted,[]),/原文位置/);
  assert.throws(()=>admitReviewedEvents(snap(),[review('question1','REJECT'),review('question1','APPROVE_TEST_ONLY')]),/审查重复/);
  assert.throws(()=>admitReviewedEvents(snap(),[{...review('question1','APPROVE_TEST_ONLY'),checkedRawVersion:2}]),/版本/);
});
test('hypothetical / uncertain questions never gain approval via TEST_ONLY gate',()=>{
  for(const mode of ['DENIED','HYPOTHETICAL','UNCERTAIN'] as const){const s=snap();s.events[0].factuality=mode;const r=admitReviewedEvents(s,[review('question1','APPROVE_TEST_ONLY',mode)]);assert.equal(r.accepted.length,0);}
});

test('reviewed-question path rejects prefilled observations rather than silently bypassing approval',()=>{
 const v=visit();v.observations=[{id:'unreviewed',kind:'EXPERT_QUESTION',mode:'REPORTED',capabilityId:'extrapolation',...span('却追问了外推')}];
 assert.throws(()=>withReviewedQuestions(v,snap(),[]),/专用专家提问接口/);
});
