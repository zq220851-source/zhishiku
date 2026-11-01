import {test} from 'node:test';import assert from 'node:assert/strict';
import {Store} from '../lib/store';
import {analyzeFiveAssets,proposeNextPreparation,evaluateNextPreparation,validateFrozenVisits} from '../lib/b-evolution';
import {BReviewLedger,buildCandidates} from '../lib/b-review';
import {sampleVisits,visit,revisedV3,K,study} from '../labs/b-closed-loop/fictional';

const data=sampleVisits(),asOf='2026-01-15T00:00:00Z';
const analyze=(visits=data,at=asOf)=>analyzeFiveAssets({source:'HUMAN_VERIFIED_SYNTHETIC',visits,asOf:at});
const context=(startsAt='2026-01-06T00:00:00Z')=>({taskId:'next-task',researchId:study,repId:'repA',expertId:'expertX',startsAt,
  candidates:[K.endpoint,K.subgroup,K.extrapolation,K.safety],baselineSelected:[K.endpoint,K.subgroup],mandatory:[K.endpoint],budget:2});

test('B five assets: evidence provenance, five independent outcomes, no future at analysis time',()=>{
  const a=analyze();assert.ok(a.sourceDigest.length===64);
  assert.ok(a.personal.length>0&&a.forecast.length>0&&a.knowledge.length>0&&a.experts.length>0&&a.cohort.length>0);
  assert.equal(a.blocked.length,1);assert.equal(a.blocked[0].visitId,'v5');
  assert.throws(()=>analyze(data,'2026-01-05T00:00:00Z'),/未来/);
});
test('B personal: older GAP does not erase later observed SATISFIED, still retention and not mastered',()=>{
  const result=analyze().personal.find(x=>x.repId==='repA'&&x.capabilityId===K.extrapolation)!;
  assert.equal(result.lastPractice,'SATISFIED');assert.equal(result.status,'RETEST_OR_RETENTION');
  assert.match(result.reason,/复查/);
  const before=analyze(data.slice(0,1),'2026-01-03T00:00:00Z').personal[0];
  assert.equal(before.lastPractice,'GAP');assert.equal(before.status,'CONFLICT_RECHECK'); // same-visit order not proven, conservatively re-check
});
test('B personal: difficulty without practice triggers diagnostic, NOT clinical grade',()=>{
  const d=analyze().personal.find(x=>x.repId==='repD'&&x.capabilityId===K.extrapolation)!;
  assert.equal(d.status,'NEEDS_DIAGNOSIS');assert.equal(d.lastPractice,null);
});
test('B forecast: only actual reported event, never denied/hypothetical',()=>{
  const row=analyze().forecast.find(x=>x.capabilityId===K.extrapolation)!;
  assert.equal(row.questionVisits,3);assert.equal(row.coveredVisits,1);assert.equal(row.selectedOutVisits,2);
  assert.equal(row.absentFromPoolVisits,0);assert.equal(row.diagnosis,'MIXED');
});
test('B knowledge: NOT_FOUND never becomes established medical gap',()=>{
  const k=analyze().knowledge.find(x=>x.capabilityId===K.safety)!;
  assert.equal(k.recommendation,'REVIEW_RETRIEVAL');assert.equal(k.status,'CANDIDATE');
  assert.ok(k.evidence.every(x=>x.observationIds.length===1));
});
test('B expert: repeated observation still not stable personality or expert truth',()=>{
  const x=analyze().experts.find(x=>x.expertId==='expertX')!;
  assert.equal(x.visits,2);assert.equal(x.reporters,1);assert.equal(x.status,'REPEATED_REPORTED_OBSERVATION');
  assert.match(x.description,/不是专家稳定偏好/);
});
test('B cohort: distinct reps, experts and denominators, no false counts from denial',()=>{
  const c=analyze().cohort.find(x=>x.capabilityId===K.extrapolation)!;
  assert.equal(c.reportedVisits,3);assert.equal(c.reportingReps,2);assert.equal(c.reportingExperts,2);assert.equal(c.denominatorVisits,6);
  assert.equal(c.status,'PATTERN_FOR_REVIEW');
  const safety=analyze().cohort.find(x=>x.capabilityId===K.safety)!;
  assert.equal(safety.reportingReps,1);assert.equal(safety.status,'DESCRIPTIVE_ONLY');
});
test('B revision: corrected v3 removes current expert/prediction/cohort support but keeps immutable prior record',()=>{
  const revised=revisedV3(data[2]),curr=analyze([...data,revised]);
  assert.equal(curr.cohort.find(x=>x.capabilityId===K.extrapolation)!.reportedVisits,2);
  assert.equal(curr.cohort.find(x=>x.capabilityId===K.extrapolation)!.status,'DESCRIPTIVE_ONLY');
  assert.equal(curr.experts.some(x=>x.expertId==='expertY'),false);
  assert.equal(validateFrozenVisits([...data,revised]).length,6);
  assert.throws(()=>validateFrozenVisits([...data,{...data[2],rawText:'伪造内容'}]),/原文|冲突/);
});
test('B next prep: only older observations, mandatory stays and budget fixed',()=>{
  const p=context(),proposed=proposeNextPreparation(p,data);
  assert.deepEqual(proposed.proposed,[K.endpoint,K.extrapolation]);
  assert.deepEqual(proposed.added,[K.extrapolation]);assert.deepEqual(proposed.displaced,[K.subgroup]);
  assert.deepEqual(proposed.usedVisitIds,['v1','v2']);
  assert.ok(!proposed.usedVisitIds.includes('v3'));
  assert.ok(proposed.reasons[K.extrapolation].some(x=>x.includes('当前个人')));
  assert.equal(proposed.status,'COMPARISON_ONLY');
});
test('B next prep: old GAP is not forever after satisfied practice',()=>{
  const p=context('2026-01-05T00:00:00Z');const before=proposeNextPreparation(p,data);
  const later=proposeNextPreparation({...p,startsAt:'2026-01-06T00:00:00Z'},data);
  const beforeSignal=before.reasons[K.extrapolation].join(' '),afterSignal=later.reasons[K.extrapolation].join(' ');
  assert.match(beforeSignal,/CONFLICT_RECHECK/);
  assert.match(afterSignal,/RETEST_OR_RETENTION/);
});
test('B next prep: future scenario cannot influence earlier forecast',()=>{
  const p={...context(),startsAt:'2026-01-02T00:00:00Z'};
  const result=proposeNextPreparation(p,data);
  assert.deepEqual(result.usedVisitIds,[]);assert.deepEqual(result.proposed,[K.endpoint,K.subgroup]);
});
test('B next prep: invalid budget or mandatory constraints rejected',()=>{
  const p=context();assert.throws(()=>proposeNextPreparation({...p,budget:1},data),/基线题量/);
  assert.throws(()=>proposeNextPreparation({...p,mandatory:[K.endpoint,K.subgroup,K.extrapolation]},data),/必选/);
});
test('B held-out future episode: compare coverage, disclose displaced skills, not real world improvement',()=>{
  const p=context();const plan=proposeNextPreparation(p,data);
  const holdout=evaluateNextPreparation(plan,p,{id:'future-case',preparedAt:p.startsAt,observedVisitId:'v3',testOnly:true},data);
  assert.equal(holdout.oldCovered,0);assert.equal(holdout.newCovered,1);assert.equal(holdout.passedBudget,true);
  assert.deepEqual(holdout.lost,[K.subgroup]);
  assert.throws(()=>evaluateNextPreparation(plan,p,{id:'leaky',preparedAt:p.startsAt,observedVisitId:'v1',testOnly:true},data),/准备之后/);
});
test('B candidate decision: no automatic knowledge/strategy release, all have source refs',()=>{
  const a=analyze(),cs=buildCandidates(a);
  assert.ok(cs.some(x=>x.kind==='PERSONAL_TRAINING'));
  assert.ok(cs.some(x=>x.kind==='KNOWLEDGE_REVIEW'));
  assert.ok(cs.some(x=>x.kind==='COHORT_HYPOTHESIS'));
  assert.ok(cs.every(x=>x.state==='CANDIDATE'&&x.sourceRefs.length));
});
test('B review store: immutable runs, evidence-bound decisions, no production publication path',()=>{
  const store=new Store(':memory:');try{
    const ledger=new BReviewLedger(store),args={runId:'run1',visits:data,asOf,preparation:{...context(),startsAt:'2026-01-15T02:00:00Z'}};
    const r=ledger.execute(args);const same=ledger.execute(args);assert.deepEqual(r,same);
    assert.ok(r.next?.delta.proposed.includes(K.extrapolation));
    assert.throws(()=>ledger.execute({...args,asOf:'2026-01-15T01:00:00Z'}),/覆盖/);
    const c=r.candidates.find(x=>x.kind==='KNOWLEDGE_REVIEW')!;
    assert.throws(()=>ledger.review('run1',{id:'review1',candidateId:c.id,actor:'reviewer1',reviewedDigest:'incorrect',decision:'APPROVE_TEST_ONLY',reason:'测试审核记录，不是正式许可',at:asOf}),/指纹/);
    ledger.review('run1',{id:'review1',candidateId:c.id,actor:'reviewer1',reviewedDigest:c.sourceDigest,decision:'NEEDS_MORE_EVIDENCE',reason:'未检索到不代表知识库没有内容',at:asOf});
    assert.equal(ledger.decisions('run1').length,1);
    assert.throws(()=>ledger.review('run1',{id:'review1',candidateId:c.id,actor:'reviewer1',reviewedDigest:c.sourceDigest,decision:'APPROVE_TEST_ONLY',reason:'试图重复审核记录',at:asOf}),/重复/);
    assert.throws(()=>store.db.prepare('DELETE FROM b_runs').run(),/immutable/);
  }finally{store.close();}
});
test('B invalid provenance cannot be silently ingested',()=>{
  const v=visit({id:'invalid',rep:'repA',expert:'expertX',time:'2026-01-01T10:00:00Z',questions:[{cap:K.extrapolation,phrase:'医生问了外推。'}]});
  assert.throws(()=>analyze([{...v,usage:'REAL' as any}]),/虚构/);
  assert.throws(()=>analyze([{...v,observations:[{...v.observations[0],quote:'伪造原话'}]}]),/原文/);
});
import {testMethodCandidate,authorizeTestMethod,testPreparationWithApprovedMethod, type MethodExperiment, type MethodTrial} from '../lib/b-method-loop';

test('B method learning: regression or no heldout improvement vetoes proposed method',()=>{
  const proposed:MethodExperiment={id:'sample-method',version:1,why:'解释旧例中漏选的原因',conditions:['有历史需求'],action:'按试验权重排序',exclusions:['不改医学知识'],evidenceVisitIds:['v1'],
    weights:{personalGap:0,personalDifficulty:0,personalRetention:0,expertObservation:0,pastUnselected:0},state:'DRAFT'};
  const p=context('2026-01-06T00:00:00Z');
  const future:MethodTrial[]=[{id:'trial-val',split:'validation',context:p,holdout:{id:'future-v3',preparedAt:p.startsAt,observedVisitId:'v3',testOnly:true}},
    {id:'trial-hold',split:'holdout',context:p,holdout:{id:'future-v4',preparedAt:p.startsAt,observedVisitId:'v4',testOnly:true}}];
  const r=testMethodCandidate(proposed,future,data);assert.equal(r.method.state,'REJECTED');
  assert.throws(()=>authorizeTestMethod(r,{actor:'auditor',reason:'我希望测试这个方法',allow:true}),/未经/);
  assert.throws(()=>testPreparationWithApprovedMethod(p,data,proposed),/未经/);
  assert.throws(()=>testMethodCandidate(proposed,[future[0]],data),/留出/);
});
test('B method test rejects evidence leakage and repeated holdout visits',()=>{
  const method:MethodExperiment={id:'leaky-method',version:1,why:'尝试用将来案例调参',conditions:['缺口'],action:'修复',exclusions:['不正式发布'],evidenceVisitIds:['v3'],
    weights:{personalGap:4,personalDifficulty:4,personalRetention:1,expertObservation:2,pastUnselected:2},state:'DRAFT'};
  const p=context();const trials:MethodTrial[]=[{id:'validation',split:'validation',context:p,holdout:{id:'v3-val',preparedAt:p.startsAt,observedVisitId:'v3',testOnly:true}},
    {id:'holdout',split:'holdout',context:p,holdout:{id:'v4-hold',preparedAt:p.startsAt,observedVisitId:'v4',testOnly:true}}];
  assert.throws(()=>testMethodCandidate(method,trials,data),/泄露/);
});
import {auditScenarioCoverage} from '../lib/b-scenario-audit';

test('B L2 scene diagnosis distinguishes missing catalog, partial task and complete task',()=>{
  const req={researchId:study,capabilityId:K.extrapolation,requiredDimensions:['CONCEPT','EVIDENCE_BOUNDARY','FOLLOW_UP'] as const,sourceEvidenceIds:['fictional-e1']};
  const input={...req,requiredDimensions:[...req.requiredDimensions]};
  const empty=auditScenarioCoverage(input,[],'SUPPORTED');assert.equal(empty.action,'CREATE_CANDIDATE');
  const partial=auditScenarioCoverage(input,[{id:'scene-old',version:'v1',researchId:study,capabilityId:K.extrapolation,dimensions:['CONCEPT'],status:'ELIGIBLE_TEST_ONLY'}],'SUPPORTED');
  assert.equal(partial.action,'REVISE_CANDIDATE');assert.deepEqual(partial.missingDimensions,['EVIDENCE_BOUNDARY','FOLLOW_UP']);
  const full=auditScenarioCoverage(input,[{id:'scene-new',version:'v2',researchId:study,capabilityId:K.extrapolation,dimensions:['CONCEPT','EVIDENCE_BOUNDARY','FOLLOW_UP'],status:'ELIGIBLE_TEST_ONLY'}],'SUPPORTED');
  assert.equal(full.action,'REUSE_CONTENT');
});
test('B L2 does not invent medical answer when evidence is not supported',()=>{
  const d=auditScenarioCoverage({researchId:study,capabilityId:K.safety,requiredDimensions:['EVIDENCE_BOUNDARY'],sourceEvidenceIds:[]},[],'NOT_FOUND');
  assert.equal(d.action,'ASK_FOR_KNOWLEDGE');assert.match(d.proposedTestOnlyEdit,/医学/);
});

test('B method learning: independent future cases can promote comparison-only method with explicit reviewer approval',()=>{
  const cases=[
    visit({id:'past-a',rep:'repA',expert:'expertX',time:'2026-01-01T10:00:00Z',questions:[{cap:K.extrapolation,phrase:'医生问了外推。'}],difficulties:[{cap:K.extrapolation,phrase:'我解释不清外推。'}],
      practices:[{capabilityId:K.extrapolation,trainingAttemptId:'method-p1',criterion:'边界',result:'GAP'}]}),
    visit({id:'past-b',rep:'repB',expert:'expertY',time:'2026-01-02T10:00:00Z',questions:[{cap:K.safety,phrase:'医生问安全性问题。'}]}),
    visit({id:'past-c',rep:'repC',expert:'expertZ',time:'2026-01-03T10:00:00Z',questions:[{cap:K.safety,phrase:'另一位医生也问安全性。'}]}),
    visit({id:'future-a',rep:'repD',expert:'expertW',time:'2026-01-07T10:00:00Z',questions:[{cap:K.safety,phrase:'医生又问安全性。'}]}),
    visit({id:'future-b',rep:'repE',expert:'expertV',time:'2026-01-08T10:00:00Z',questions:[{cap:K.safety,phrase:'医生追问安全性解释。'}]})];
  const candidate:MethodExperiment={id:'cohort-recall-test',version:1,why:'历史多个拜访报告的缺项可能被个人训练信号淹没',conditions:['同预算'],action:'提高历史未选中权重',
    exclusions:['不得突破必选约束'],evidenceVisitIds:['past-a','past-b','past-c'],weights:{personalGap:0,personalDifficulty:0,personalRetention:0,expertObservation:0,pastUnselected:6},state:'DRAFT'};
  const p=context('2026-01-06T00:00:00Z');
  const trial=(id:string,split:'validation'|'holdout',observedVisitId:string):MethodTrial=>({id,split,context:p,holdout:{id,preparedAt:p.startsAt,observedVisitId,testOnly:true}});
  const verdict=testMethodCandidate(candidate,[trial('val','validation','future-a'),trial('hold','holdout','future-b')],cases);
  assert.equal(verdict.method.state,'TESTED_CANDIDATE');assert.ok(verdict.results.every(x=>x.newCovered>x.oldCovered));
  const approved=authorizeTestMethod(verdict,{actor:'independent-reviewer',allow:true,reason:'独立留出改进且测试覆盖不退步，仅授权测试环境'});
  const plan=testPreparationWithApprovedMethod(p,cases,approved);
  assert.deepEqual(plan.proposed,[K.endpoint,K.safety]);assert.match(plan.methodVersion,/B_METHOD/);
  assert.equal(plan.status,'COMPARISON_ONLY');
});

test('B causal replay: later correction cannot retroactively change an earlier forecast',()=>{
 const all=[...data,revisedV3(data[2])];
 const prep={...context('2026-01-10T00:00:00Z'),repId:'repB',expertId:'expertY'};
 const result=proposeNextPreparation(prep,all);
 assert.ok(result.usedVisitIds.includes('v3')); // at this time original description was still in force
 const updated=proposeNextPreparation({...prep,startsAt:'2026-01-15T00:00:00Z'},all);
 assert.ok(updated.usedVisitIds.includes('v3')); // visit remains, but its question is DENIED at this later time
 assert.ok(!updated.reasons[K.extrapolation]?.some(x=>x.includes('目标专家过往被报告追问：v3')));
 const undated={...revisedV3(data[2]),reviewedAt:undefined};
 assert.throws(()=>proposeNextPreparation({...prep,startsAt:'2026-01-15T00:00:00Z'},[...data,undated]),/审核时间/);
});

test('B historical portfolio cannot apply a correction before its review timestamp',()=>{
  const events=[...data.slice(0,3),revisedV3(data[2])];
  const before=analyze(events,'2026-01-10T00:00:00Z');
  const after=analyze(events,'2026-01-15T00:00:00Z');
  assert.ok(before.experts.some(x=>x.expertId==='expertY'));
  assert.ok(!after.experts.some(x=>x.expertId==='expertY'));
});
