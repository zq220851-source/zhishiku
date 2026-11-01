import assert from 'node:assert/strict';
import {test} from 'node:test';
import {createHmac} from 'node:crypto';
import {Store} from '../lib/store';
import {Service} from '../lib/service';
import {LiveEvolution} from '../lib/live-evolution';
import {adaptModule1,type Module1Export} from '../lib/live-module1';
import {actor as parseActor} from '../lib/http';
import type {Actor,Feedback} from '../lib/types';
// Isolated protocol evidence; never inserted in the real workspace.
function fixture(owner='owner'){
 const store=new Store(':memory:'),service=new Service(store),e=new LiveEvolution(store);
 const author:Actor={id:owner,role:'EMPLOYEE',scope:{tenant:'tenant',actorId:'author-real-id',reviewer:false,teams:[{id:'team',name:'Protocol test',owners:[owner,'colleague']}]}};
 const reviewer:Actor={...author,scope:{...author.scope!,actorId:'reviewer-real-id',reviewer:true}};
 const colleague:Actor={...author,id:'colleague'};
 function record(key:string,selected='a'){
  const source:Module1Export={system:'MODULE1',sourceKind:'sheets',sourceTaskId:key,lessonId:'course',title:'Protocol fixture',sourcePath:'test-only',sourceHash:'hash',material:{revision:'r1',status:'pending_review',blocks:[{id:'B',title:'Test',text:'Protocol material only.',revision:'r1'}],references:[]},options:['a','b'].map(id=>({id,question:'Test question '+id,criteria:[{id,label:'criterion '+id,expected:'observe '+id,source_ids:['B']}]})),forecast:{status:'FROZEN',candidate_ids:['a','b'],selected_ids:[selected],budget:1,generated_at:1000,frozen_at:1001,lesson_revision:'r1',note:'test'}};
  const task=service.createTask(author,adaptModule1(source),'task-'+key),raw='Reported question B';
  const f=service.saveRaw(author,task.id,{text:raw,confirmed:true,exchangeOccurred:true},'raw-'+key),skill=task.snapshot.codebook.skills[1].id;
  const feedback:Feedback={...f,state:'ANALYZED',analysisRawId:f.versions[0].id,analysis:{units:[{id:'u',startCp:0,endCp:raw.length,excerpt:raw,types:['REPORTED_QUESTION'],attribution:'OTHER_REPORTED',certainty:'REPORTED',codes:[],skillIds:[skill],mapping:'CANDIDATE',selfAssessment:[]}],relations:[],findings:[{id:'finding',kind:'QUESTION',questionUnitId:'u',responseUnitIds:[],correctionUnitIds:[],linkage:'UNKNOWN',linkageEvidenceUnitIds:[],skillIds:[skill],evidence:[],assessment:{coverage:'NONE',personalSignal:'UNKNOWN'},eligibleForSharedChange:true,limitations:[]}],codebookVersion:task.snapshot.codebook.version,model:'test',promptVersion:'test',differences:[],limitations:[]}};
  store.put('source:'+task.id,'live_source',author.id,source);store.put(f.id,'feedback',author.id,feedback);store.put('meta:'+f.id,'live_feedback_meta',author.id,{exchangeMode:'REPORTED_EXCHANGE'});
  return {source,task,feedback};
 }
 const records=[record('one'),record('two'),record('three')];
 const propose=(level='L3')=>e.propose(author,{level,teamId:'team',feedbackId:records[0].feedback.id,optionIndex:1,reason:'Only protocol evidence for independent tests'});
 return {store,e,author,reviewer,colleague,records,record,propose};
}
test('live L3: independent fixed-budget review, sanitized sharing, tenant isolation and revocation',()=>{
 const f=fixture();try{
  const d=f.propose();assert.equal(f.e.active(f.colleague).length,0);
  assert.throws(()=>f.e.evaluate({...f.author,scope:{...f.author.scope!,reviewer:true}},d.id,1,f.records.slice(1).map(x=>x.feedback.id),'Self review attempt'),{status:403});
  const checked=f.e.evaluate(f.reviewer,d.id,1,f.records.slice(1).map(x=>x.feedback.id),'Reviewed source and fixed-budget comparison');
  assert.equal(checked.evaluation!.cases[1].budget,1);assert.deepEqual(checked.evaluation!.cases[1].proposed,['b']);
  f.e.approve(f.reviewer,d.id,2,'Reviewed for sanitized team training');
  const visible=f.e.active(f.colleague);assert.equal(visible.length,1);assert.equal('dependencies' in visible[0],false);assert.equal('ownerId' in visible[0],false);
  assert.throws(()=>f.e.approve(f.reviewer,d.id,2,'Concurrent stale approval attempt'),{status:409});
  assert.equal(f.e.active({...f.colleague,scope:{...f.colleague.scope!,tenant:'other'}}).length,0);
  assert.equal(f.e.active({...f.colleague,scope:{...f.colleague.scope!,teams:[]}}).length,0);
  assert.equal(f.e.active({...f.colleague,scope:{...f.colleague.scope!,teams:[{id:'team',name:'test',owners:['colleague']}]}}).length,0);
  const events=f.store.db.prepare("SELECT actor FROM events WHERE type='LIVE_EVOLUTION_APPROVED'").all();assert.equal(events[0].actor,'reviewer-real-id');
  f.e.revoke(f.reviewer,d.id,3,'Withdraw team training content');assert.equal(f.e.active(f.colleague).length,0);
 }finally{f.store.close();}
});
test('source correction invalidates L2 release; old snapshot survives and remains revocable',()=>{
 const f=fixture();try{
  const d=f.propose('L2');f.e.evaluate(f.reviewer,d.id,1,f.records.slice(1).map(x=>x.feedback.id),'Reviewed two independent source reports');f.e.approve(f.reviewer,d.id,2,'Reviewed for sanitized team training');assert.equal(f.e.active(f.colleague).length,1);
  const v=f.records[1].feedback;f.store.put(v.id,'feedback',f.author.id,{...v,analysis:{...v.analysis,model:'reanalyzed'}});
  assert.equal(f.e.active(f.colleague).length,0);assert.equal(f.e.list(f.author)[0].state,'STALE');
  f.e.revoke(f.reviewer,d.id,3,'Withdraw after source correction');assert.equal(f.store.get<{state:string}>(d.id,'live_evolution',f.author.id).state,'REVOKED');
 }finally{f.store.close();}
});
test('simulated, stale, unanchored and selected personal signals cannot become L3',()=>{
 const f=fixture();try{
  const r=f.records[0];f.store.put('meta:'+r.feedback.id,'live_feedback_meta',f.author.id,{exchangeMode:'SIMULATED_EXCHANGE'});assert.throws(()=>f.propose());
  f.store.put('meta:'+r.feedback.id,'live_feedback_meta',f.author.id,{exchangeMode:'REPORTED_EXCHANGE'});
  f.store.put(r.feedback.id,'feedback',f.author.id,{...r.feedback,analysisRawId:'outdated'});assert.throws(()=>f.propose());
  f.store.put(r.feedback.id,'feedback',f.author.id,{...r.feedback,analysis:{...r.feedback.analysis,units:r.feedback.analysis!.units.map(u=>({...u,excerpt:'invented quote'}))}});assert.throws(()=>f.propose());
  const selected=f.record('already-selected','b');assert.throws(()=>f.e.propose(f.author,{level:'L3',teamId:'team',feedbackId:selected.feedback.id,optionIndex:1,reason:'Cannot call selected candidate a miss'}));
  assert.throws(()=>f.e.sources({id:'owner',role:'TRAINING_REVIEWER'}),{status:403});
 }finally{f.store.close();}
});
test('validation rejects repeated visits, changed criteria, no improvement and wrong team',()=>{
 const f=fixture();try{
  const d=f.propose();assert.throws(()=>f.e.evaluate(f.reviewer,d.id,1,[f.records[0].feedback.id,f.records[2].feedback.id],'Repeated proposal is not independent'));
  assert.throws(()=>f.e.evaluate(f.reviewer,d.id,1,[f.records[1].feedback.id,f.records[1].feedback.id],'Repeated validation is not independent'));
  const selected=f.record('holdout-selected','b');assert.throws(()=>f.e.evaluate(f.reviewer,d.id,1,[f.records[1].feedback.id,selected.feedback.id],'Holdout has no measured improvement'));
  const src=f.records[1];f.store.put('source:'+src.task.id,'live_source',f.author.id,{...src.source,options:src.source.options.map(o=>({...o,criteria:o.criteria.map(c=>({...c,expected:'changed'}))}))});
  assert.throws(()=>f.e.evaluate(f.reviewer,d.id,1,f.records.slice(1).map(x=>x.feedback.id),'Changed evidence cannot validate'));
  assert.throws(()=>f.e.propose({...f.author,scope:{...f.author.scope!,teams:[]}},{level:'L2',teamId:'team',feedbackId:f.records[0].feedback.id,optionIndex:1,reason:'Cross-team request rejected'}),{status:403});
 }finally{f.store.close();}
});
test('HMAC platform identity alone carries live scope; forged signatures rejected',()=>{
 const previous=process.env.MEDREP_MODULE2_BRIDGE_SECRET;process.env.MEDREP_MODULE2_BRIDGE_SECRET='test-only-bridge-secret-'.repeat(3);
 try{
  const payload=Buffer.from(JSON.stringify({id:'11111111-1111-4111-8111-111111111111',role:'EMPLOYEE',expires:Math.floor(Date.now()/1000)+60,scope:{tenant:'t',actorId:'real',reviewer:false,teams:[]}})).toString('base64url');
  const signature=createHmac('sha256',process.env.MEDREP_MODULE2_BRIDGE_SECRET).update(payload).digest('hex');
  const r=(v:string)=>new Request('http://localhost/api/live/evolution',{headers:{'x-medrep-identity':v}});
  assert.equal(parseActor(r(payload+'.'+signature)).scope?.actorId,'real');assert.throws(()=>parseActor(r(payload+'.'+'0'.repeat(64))),{status:401});
 }finally{if(previous===undefined)delete process.env.MEDREP_MODULE2_BRIDGE_SECRET;else process.env.MEDREP_MODULE2_BRIDGE_SECRET=previous;}
});

test('live HTTP actions preserve the signed reviewer through propose, validate, approve and consume listing',async()=>{
 const f=fixture('11111111-1111-4111-8111-111111111111');
 const previous=process.env.MEDREP_MODULE2_BRIDGE_SECRET;process.env.MEDREP_MODULE2_BRIDGE_SECRET='http-protocol-secret-'.repeat(3);
 const state=globalThis as typeof globalThis&{liveEvolution?:LiveEvolution};state.liveEvolution=f.e;
 const {GET,POST}=await import('../app/api/live/evolution/route');
 function request(who:Actor,body?:unknown,active=false){
  const payload=Buffer.from(JSON.stringify({...who,expires:Math.floor(Date.now()/1000)+60})).toString('base64url');
  const signature=createHmac('sha256',process.env.MEDREP_MODULE2_BRIDGE_SECRET!).update(payload).digest('hex');
  return new Request('http://127.0.0.1:3402/api/live/evolution'+(active?'?active=1':''),{method:body?'POST':'GET',headers:{host:'127.0.0.1:3402',origin:'http://127.0.0.1:3402','content-type':'application/json','x-medrep-identity':payload+'.'+signature},...(body?{body:JSON.stringify(body)}:{})});
 }
 try{
  const create=await POST(request(f.author,{action:'propose',level:'L3',teamId:'team',feedbackId:f.records[0].feedback.id,optionIndex:1,reason:'HTTP source-backed protocol candidate'}));assert.equal(create.status,200);
  const draft=(await create.json()).data;
  const evaluation=await POST(request(f.reviewer,{action:'evaluate',id:draft.id,expectedRevision:1,caseFeedbackIds:f.records.slice(1).map(r=>r.feedback.id),reason:'Independent evidence reviewed over HTTP'}));assert.equal(evaluation.status,200);
  const approve=await POST(request(f.reviewer,{action:'approve',id:draft.id,expectedRevision:2,reason:'Team training content reviewed over HTTP'}));assert.equal(approve.status,200);
  const active=(await (await GET(request(f.author,undefined,true))).json()).data;assert.equal(active.releases.length,1);assert.equal(active.releases[0].version,3);
  const revoked=await POST(request(f.reviewer,{action:'revoke',id:draft.id,expectedRevision:3,reason:'Withdrawal tested through real route'}));assert.equal(revoked.status,200);
  assert.equal((await (await GET(request(f.author,undefined,true))).json()).data.releases.length,0);
  assert.equal((await GET(request({...f.author,scope:undefined}))).status,403);
 }finally{delete state.liveEvolution;f.store.close();if(previous===undefined)delete process.env.MEDREP_MODULE2_BRIDGE_SECRET;else process.env.MEDREP_MODULE2_BRIDGE_SECRET=previous;}
});
