import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { adaptModule1,type Module1Export } from '../lib/live-module1';
import { Service } from '../lib/service';
import { Store } from '../lib/store';
import { analyzeFiveAssets } from '../lib/b-evolution';
import type { VisitEvidence } from '../lib/five-assets';
const sourcePath='reference/coach/course-specs-ce/daboshu__PB.json';
const course=JSON.parse(readFileSync(path.resolve(process.cwd(),'../business_module1_reference',sourcePath),'utf8'));
const realText=course.steps[0].body as string;
const source:Module1Export={system:'MODULE1',sourceKind:'runs',sourceTaskId:'owned-run',lessonId:'daboshu__PB',sourcePath,sourceHash:'original-file-hash',title:course.meta.title,
 material:{revision:'frozen-source-version',status:'pending_medical_review',blocks:[{id:'daboshu__PB:steps.0',title:course.steps[0].title,text:realText,revision:'frozen-source-version'}],references:course.sources},
 options:[{question:course.hero.question,criteria:[{id:'boundary',label:course.steps[0].title,expected:course.goal,source_ids:['daboshu__PB:steps.0']}]}]};
test('actual module1 content survives task validation and immutable snapshot; source records never overwrite task entities',()=>{
 const store=new Store(':memory:'),service=new Service(store),actor={id:'owned-user',role:'EMPLOYEE' as const};
 try{
  const input=adaptModule1(source),task=service.createTask(actor,input,'source-import');
  assert.equal(task.snapshot.kind,'MODULE1_SNAPSHOT');assert.equal(task.snapshot.evidence[0].content,realText);
  assert.equal(task.snapshot.evidence[0].usage,'INTERNAL_READING');
  assert.equal(task.snapshot.origin?.candidatePoolKnown,false);
  store.put('source:'+task.id,'live_source',actor.id,source);
  assert.equal(service.getTask(actor,task.id).snapshot.evidence[0].content,realText);
  assert.equal(store.get<Module1Export>('source:'+task.id,'live_source',actor.id).sourceTaskId,'owned-run');
  input.evidence[0].content='changed';assert.equal(service.getTask(actor,task.id).snapshot.evidence[0].content,realText);
  assert.throws(()=>service.getTask({...actor,id:'other'},task.id));
 }finally{store.close();}
});
test('fictional sources and missing source citations cannot be imported',()=>{
 assert.throws(()=>adaptModule1({...source,lessonId:'demo-evidence'}));
 assert.throws(()=>adaptModule1({...source,sourcePath:''}));
 assert.throws(()=>adaptModule1({...source,options:[{criteria:[{id:'x',label:'x',expected:'x',source_ids:['nonexistent']}]}]}));
});
test('unknown original candidate pool does not turn an unlisted capability into a recall failure',()=>{
 const raw='我还不清楚。';
 const v:VisitEvidence={usage:'INTERNAL_READING',sourceOrigin:{system:'MODULE1',lessonId:'daboshu__PB',revision:'v1',sourcePath},visitId:'v1',taskId:'t1',repId:'rep1',expertId:null,researchId:'daboshu__PB',snapshotHash:'h1',rawVersion:1,rawText:raw,occurredAt:'2026-11-01T00:00:00Z',forecast:{selectedCapabilityIds:[],candidateCapabilityIds:[],candidatePoolKnown:false,budget:0},observations:[{id:'q1',kind:'EXPERT_QUESTION',mode:'REPORTED',quote:raw,startCp:0,endCp:Array.from(raw).length,capabilityId:'not-in-original-plan'}],knowledgeChecks:[],practices:[]};
 const a=analyzeFiveAssets({source:'SOURCE_ANCHORED_REPORTED',visits:[v],asOf:'2026-11-01T01:00:00Z'});
 assert.equal(a.forecast[0].diagnosis,'UNKNOWN_POOL');assert.equal(a.forecast[0].absentFromPoolVisits,0);assert.equal(a.experts.length,0);
 assert.throws(()=>analyzeFiveAssets({source:'HUMAN_VERIFIED_SYNTHETIC',visits:[v],asOf:'2026-11-01T01:00:00Z'}));
});

test('pre-visit freeze records generated candidate set separately from selected priorities',()=>{
 const sourceFrozen:Module1Export={...source,sourceKind:'sheets',sourceTaskId:'sheet-frozen',
   options:[
     {id:'selected',question:'当时准备的已选问题',why:'有公开背景',criteria:[{id:'boundary',label:'解释边界',expected:course.goal,source_ids:['daboshu__PB:steps.0']}]},
     {id:'unselected',question:'当时候选但未选的问题',why:'优先级较低',criteria:[{id:'other',label:'另一问题',expected:course.goal,source_ids:['daboshu__PB:steps.0']}]}
   ],forecast:{status:'FROZEN',candidate_ids:['selected','unselected'],selected_ids:['selected'],budget:1,
     generated_at:1793000000,frozen_at:1793000050,lesson_revision:'frozen-source-version',note:'访前已确认'}
 };
 const input=adaptModule1(sourceFrozen);
 assert.equal(input.origin?.candidatePoolKnown,true);
 assert.equal(input.codebook.skills.length,2);
 assert.equal(input.plan.length,1);
 assert.equal(input.forecastSnapshot?.candidateSkillIds.length,2);
 assert.equal(input.forecastSnapshot?.selectedSkillIds.length,1);
 assert.notEqual(input.forecastSnapshot?.candidateSkillIds[1],input.forecastSnapshot?.selectedSkillIds[0]);
 const store=new Store(':memory:');try{
   const t=new Service(store).createTask({id:'owner',role:'EMPLOYEE'},input,'frozen-visit');
   assert.equal(t.snapshot.forecastSnapshot?.frozenAt,'2026-10-26T07:34:10.000Z');
   assert.equal(t.snapshot.plan.length,1);
 }finally{store.close();}
 assert.throws(()=>adaptModule1({...sourceFrozen,forecast:{...sourceFrozen.forecast!,selected_ids:['not-generated']}}));
 assert.throws(()=>adaptModule1({...sourceFrozen,forecast:{...sourceFrozen.forecast!,lesson_revision:'revision-after-visit'}}));
});

test('follow-up practice enters personal history only with matching criteria and verified quotes',async()=>{
 const {comparablePractices,followupKey}=await import('../lib/live-module1');
 const store=new Store(':memory:'),service=new Service(store),actor={id:'followup-owner',role:'EMPLOYEE' as const};
 try{
  const task=service.createTask(actor,adaptModule1(source),'new-task');
  const completed:Module1Export={...source,sourceTaskId:'followup-run',observedAt:'2026-11-01T00:00:00Z',transcript:[{role:'药代',text:'我会核对来源原文'}],review:{observations:[{criterion_id:'boundary',status:'demonstrated',quote:'核对来源',turn_index:0,source_ids:['daboshu__PB:steps.0']}]}};
  assert.equal(comparablePractices(task,source,completed).length,1);
  const repeated={...completed,attempt:2};
  assert.notEqual(followupKey(task.id,completed),followupKey(task.id,repeated));
  assert.notEqual(comparablePractices(task,source,completed)[0].trainingAttemptId,comparablePractices(task,source,repeated)[0].trainingAttemptId);
  assert.equal(comparablePractices(task,source,repeated)[0].origin?.attempt,2);
  assert.throws(()=>followupKey(task.id,{...completed,attempt:0}));
  const changed={...completed,options:[{criteria:[{...completed.options[0].criteria[0],expected:'不同标准'}]}]};
  assert.equal(comparablePractices(task,source,changed).length,0);
  assert.equal(comparablePractices(task,source,{...completed,transcript:[{role:'药代',text:'并未说过被引用的话'}]}).length,0);
  assert.equal(comparablePractices(task,source,{...completed,material:{...completed.material,revision:'changed'}}).length,0);
 }finally{store.close();}
});
