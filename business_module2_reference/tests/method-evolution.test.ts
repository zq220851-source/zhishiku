import test from 'node:test';
import assert from 'node:assert/strict';
import {Store} from '../lib/store';
import {MethodEvolution,captureEpisodes,validateMethod,dependencyHashes,sourcesCurrent,type MethodEpisode,type MethodVersion} from '../lib/method-evolution';
import type {Task,Feedback,Actor} from '../lib/types';
const episodes:MethodEpisode[]=[
  {id:'f1',revision:1,taskId:'t1',lessonId:'course-1',sourceVersion:'material-v1',text:'我在比较问题上先找有没有同期对照，再解释为什么不能外推。',evidenceType:'CONFIRMED_SELF_REPORT',outcome:'NOT_INDEPENDENTLY_VERIFIED'},
  {id:'f2',revision:1,taskId:'t2',lessonId:'course-1',sourceVersion:'material-v1',text:'另一位医生问是不是更好，我说先确认有没有直接比较依据。',evidenceType:'CONFIRMED_SELF_REPORT',outcome:'NOT_INDEPENDENTLY_VERIFIED'},
];
const method={condition:'要求比较两个方案时',action:'先核对证据是否存在直接比较',reason:'能避免自述中的外推过度',exceptions:['仅需解释定义时不强制套用'],
  supports:[{episode_id:'f1',revision:1,quote:'先找有没有同期对照'},{episode_id:'f2',revision:1,quote:'先确认有没有直接比较依据'}],counters:[]};
const actor:Actor={id:'11111111-1111-4111-8111-111111111111',role:'EMPLOYEE'};
test('anchored method requires two independent tasks, not two text fragments',()=>{
  assert.deepEqual(validateMethod(method,episodes),method);
  assert.throws(()=>validateMethod({...method,supports:[method.supports[0]]},episodes));
  assert.throws(()=>validateMethod({...method,supports:[method.supports[0],{...method.supports[1],quote:'原文不存在的医疗结论'}]},episodes));
  assert.throws(()=>validateMethod({...method,counters:[method.supports[0]]},episodes));
  assert.throws(()=>validateMethod(method,[episodes[0],{...episodes[1],taskId:'t1'}]));
});
test('source revision invalidates test approval and keeps history',()=>{
 const store=new Store(':memory:');const evolution=new MethodEvolution(store);
 const v:MethodVersion={id:'m1',ownerId:actor.id,parentId:null,lessonIds:['course-1'],method,
  dependencies:dependencyHashes(episodes,method),episodes,changeReason:'反思结果',state:'APPROVED_TEST_ONLY',createdAt:'2026-11-01'};
 store.put('m1','method_version',actor.id,v);
 assert.equal(evolution.active(actor,episodes).length,1);
 const changed=[{...episodes[0],revision:2,text:'已撤回原报告'},episodes[1]];
 assert.equal(sourcesCurrent(v,changed),false);
 assert.equal(evolution.active(actor,changed).length,0);
 assert.equal(evolution.list(actor)[0].state,'STALE');
 assert.throws(()=>evolution.approve({...actor,role:'TRAINING_REVIEWER'},'m1','测试授权并且已独立复核',episodes));
 store.close();
});
test('simulation and stale/non-analyzed feedback never become experience',()=>{
 const t1={id:'t1',snapshot:{origin:{lessonId:'course-1',revision:'v1'}}} as Task;
 const t2={id:'t2',snapshot:{origin:{lessonId:'course-1',revision:'v1'}}} as Task;
 const ok={id:'f1',state:'ANALYZED',analysisRawId:'r1',versions:[{id:'r1',version:1,text:'确认过的本人报告'}]} as Feedback;
 const stale={id:'f2',state:'ANALYZED',analysisRawId:'old',versions:[{id:'r2',version:2,text:'尚未分析的新版本'}]} as Feedback;
 const result=captureEpisodes([t1,t2],t=>t==='t1'?[ok]:[stale],id=>({exchangeMode:id==='f1'?'REPORTED_EXCHANGE':'SIMULATED_EXCHANGE'}));
 assert.equal(result.length,1);assert.equal(result[0].id,'f1');
 assert.equal(captureEpisodes([t1],()=>[ok],()=>({exchangeMode:'SIMULATED_EXCHANGE'})).length,0);
});
test('candidate cannot be activated without independent evaluation and human approval',()=>{
 const store=new Store(':memory:');const evolution=new MethodEvolution(store);
 store.put('draft','method_version',actor.id,{id:'draft',ownerId:actor.id,parentId:null,lessonIds:['course-1'],method,
  dependencies:dependencyHashes(episodes,method),episodes,changeReason:'归纳',state:'DRAFT',createdAt:'2026-11-01'});
 assert.throws(()=>evolution.approve({...actor,role:'TRAINING_REVIEWER'},'draft','已经审阅并同意测试',episodes));
 assert.equal(evolution.active(actor,episodes).length,0);
 store.close();
});
