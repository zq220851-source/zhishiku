import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  stageSemanticEvidence, projectReviewedStage, reviewStagedEvidence, compatibleSemanticExtractor,
  type BoundReview,
} from '../lib/semantic-pipeline';
import type { SemanticProposal, ProposedEvent } from '../lib/semantic-proposal';
import type { VisitEvidence } from '../lib/five-assets';

const raw='医生没问主要终点，却问了外推。我回来想想，之前讲过头了。';
const data={ usage:'TEST_ONLY' as const, rawVersion:1, rawText:raw };
function span(quote:string){const start=Array.from(raw.slice(0,raw.indexOf(quote))).length;return {quote,startCp:start,endCp:start+Array.from(quote).length};}
function event(id:string, quote:string, attrs:Partial<ProposedEvent>):ProposedEvent {
  return {id,action:'QUESTION',agent:'EXPERT',when:'DURING_VISIT',factuality:'REPORTED',negationScope:'NO_NEGATION',capabilityId:'extrapolation',...span(quote),...attrs};
}
function proposal(): SemanticProposal {
  return {...data,events:[
    event('q-denied','医生没问主要终点',{factuality:'DENIED',negationScope:'TARGET_EVENT',capabilityId:'endpoint'}),
    event('q-real','却问了外推',{negationScope:'DIFFERENT_EVENT'}),
    event('r-later','我回来想想，之前讲过头了',{action:'REFLECTION',agent:'REP',when:'AFTER_VISIT',capabilityId:'extrapolation'})
  ],links:[]};
}
function base():VisitEvidence {return {usage:'TEST_ONLY',visitId:'v08-visit',taskId:'v08-task',repId:'v08-rep',expertId:'v08-expert',researchId:'research-A',snapshotHash:'frozen-hash',rawVersion:1,rawText:raw,occurredAt:'2026-11-01T01:00:00Z',forecast:{selectedCapabilityIds:['endpoint'],candidateCapabilityIds:['endpoint','extrapolation'],budget:1},observations:[],knowledgeChecks:[],practices:[]};}
function review(id:string,hash:string,factuality:BoundReview['verifiedFactuality']):BoundReview {return {eventId:id,proposalHash:hash,reviewerId:'independent-test-reviewer',reason:'逐条核查了原文、否定范围和说话人身份',checkedRawVersion:1,verifiedFactuality:factuality,verdict:'APPROVE_TEST_ONLY'};}

test('a model result is always only a staged proposal, with no automatic five-asset updates',async()=>{
 const s=await stageSemanticEvidence(data,async()=>proposal());
 assert.equal(s.stage,'REVIEW_REQUIRED'); assert.equal(s.snapshot.events.length,3); assert.equal(s.reanchored.length,0);
 assert.deepEqual(projectReviewedStage(base(),s,[]).projection.entries,[]);
});
test('only approved positive expert question affects forecast, expert and cohort assets',async()=>{
 const s=await stageSemanticEvidence(data,async()=>proposal());
 const x=projectReviewedStage(base(),s,[review('q-denied',s.proposalHash,'DENIED'),review('q-real',s.proposalHash,'REPORTED')]);
 assert.deepEqual(x.visit.observations.map(e=>e.id),['q-real']);
 assert.deepEqual(x.projection.entries.map(e=>e.kind).sort(),['COHORT_EVENT','EXPERT_OBSERVATION','FORECAST']);
 assert.equal(x.projection.entries.find(e=>e.kind==='FORECAST')?.label,'REPORTED_UNCOVERED');
 assert.equal(x.withheld.some(w=>w.eventId==='r-later'),true);
});
test('changing model-proposed quote while preserving the raw version invalidates the old review',async()=>{
 const s=await stageSemanticEvidence(data,async()=>proposal());
 const reviews=[review('q-real',s.proposalHash,'REPORTED')];
 const changed=proposal();changed.events[1]=event('q-real','问了外推',{negationScope:'DIFFERENT_EVENT'});
 const revised=await stageSemanticEvidence(data,async()=>changed);
 assert.notEqual(revised.proposalHash,s.proposalHash);
 assert.equal(projectReviewedStage(base(),revised,reviews).visit.observations.length,0);
});
test('a modified snapshot cannot reuse a signed staged proposal',async()=>{
 const s=await stageSemanticEvidence(data,async()=>proposal());
 s.snapshot.events[0].factuality='REPORTED';
 assert.throws(()=>projectReviewedStage(base(),s,[review('q-denied',s.proposalHash,'REPORTED')]),/快照|提案/);
});
test('a proposed narrative correction of an earlier question WITHHOLDS that target, even if it had an approval',async()=>{
 const p=proposal();p.events.push(event('fix','不是医生问的，我是自己想到的',{action:'NARRATION_CORRECTION',agent:'REP',when:'AFTER_VISIT',factuality:'REPORTED'}));
 // Use a different frozen input containing an explicit correction.
 const corrected=raw+'不是医生问的，我是自己想到的。';
 const cp={...data,rawText:corrected};
 p.rawText=corrected;
 const ix=Array.from(raw).length;
 p.events[3]={...p.events[3],startCp:ix,endCp:ix+Array.from('不是医生问的，我是自己想到的').length};
 p.links=[{from:'fix',to:'q-real',type:'REVISES_DESCRIPTION',evidenceEventIds:['fix','q-real']}];
 const s=await stageSemanticEvidence(cp,async()=>p);
 const b={...base(),rawText:corrected};
 const x=projectReviewedStage(b,s,[review('q-real',s.proposalHash,'REPORTED')]);
 assert.equal(x.visit.observations.length,0);
 assert.match(x.withheld.find(w=>w.eventId==='q-real')?.reason??'',/更正/);
});
test('review hash is invalid if entire staged object is tampered',async()=>{
 const s=await stageSemanticEvidence(data,async()=>proposal());
 s.proposal.events[1].capabilityId='new-capability';
 assert.throws(()=>reviewStagedEvidence(s,[]),/指纹/);
});
test('model cannot change source text, version, usage or remove arrays',async()=>{
 for (const x of [{...proposal(),rawText:'fake'},{...proposal(),rawVersion:2},{...proposal(),usage:'PRODUCTION'},{...proposal(),events:null}]) {
   await assert.rejects(()=>stageSemanticEvidence(data,async()=>x));
 }
});
test('unique quote offsets repaired, but repeated quotes with wrong offsets are rejected',async()=>{
 const p=proposal();p.events[1].startCp=0;p.events[1].endCp=1;
 const s=await stageSemanticEvidence(data,async()=>p);
 assert.equal(s.reanchored.length,1);assert.equal(s.reanchored[0].eventId,'q-real');
 const duplicated='医生问了外推。医生问了外推。';
 const p2:SemanticProposal={usage:'TEST_ONLY',rawVersion:1,rawText:duplicated,events:[event('q','医生问了外推',{quote:'医生问了外推',startCp:1,endCp:2})],links:[]};
 await assert.rejects(()=>stageSemanticEvidence({usage:'TEST_ONLY',rawVersion:1,rawText:duplicated},async()=>p2),/多次/);
});
test('invalid speaker, unsupported link, and contradictory negation fail BEFORE independent review',async()=>{
 const p=proposal();p.events[1].negationScope='TARGET_EVENT';
 await assert.rejects(()=>stageSemanticEvidence(data,async()=>p),/否定/);
 const q=proposal();q.links=[{from:'q-real',to:'no-such-id',type:'ANSWER_TO',evidenceEventIds:['q-real','no-such-id']}];
 await assert.rejects(()=>stageSemanticEvidence(data,async()=>q),/关系/);
});
test('unconfigured or non-authorized model refuses before network use',async()=>{
 const unconfigured=compatibleSemanticExtractor({baseUrl:'',model:'',apiKey:'',authorized:false});
 await assert.rejects(()=>unconfigured(data),/允许/);
});

test('compatible model adapter retries one invalid structured response, then stages the valid response (mock HTTP, no network)',async()=>{
 const previous=globalThis.fetch;
 const requests:{messages:{role:string;content:string}[]}[]=[];
 const outputs=[{...proposal(),events:[{...proposal().events[0],quote:'模型杜撰的话'}]}, proposal()];
 globalThis.fetch=(async(_url:unknown,init?:RequestInit)=>{
   requests.push(JSON.parse(String(init?.body)));
   const item=outputs[requests.length-1];
   return new Response(JSON.stringify({choices:[{message:{content:JSON.stringify(item)},finish_reason:'stop'}]}),{status:200});
 }) as typeof fetch;
 try {
   const ex=compatibleSemanticExtractor({baseUrl:'http://127.0.0.1:9999/v1',model:'TEST_MODEL',apiKey:'synthetic-placeholder',authorized:true});
   const staged=await stageSemanticEvidence(data,ex);
   assert.equal(staged.stage,'REVIEW_REQUIRED');
   assert.equal(requests.length,2);assert.equal(requests[0].messages[1].role,'user');
   assert.equal(requests[1].messages.some(m=>m.content.includes('validationError')),true);
   assert.equal(projectReviewedStage(base(),staged,[]).projection.entries.length,0);
 } finally { globalThis.fetch=previous; }
});

test('compatible model adapter refuses repeated fabricated quotes (mock HTTP, no network)',async()=>{
 const previous=globalThis.fetch;let calls=0;
 globalThis.fetch=(async()=>{
   calls++;
   return new Response(JSON.stringify({choices:[{message:{content:JSON.stringify({...proposal(),events:[{...proposal().events[0],quote:'不存在的原文片段'}]})},finish_reason:'stop'}]}),{status:200});
 }) as typeof fetch;
 try {
   const ex=compatibleSemanticExtractor({baseUrl:'http://127.0.0.1:9999/v1',model:'TEST_MODEL',apiKey:'synthetic-placeholder',authorized:true});
   await assert.rejects(()=>stageSemanticEvidence(data,ex),/校验|有效/);
   assert.equal(calls,2);
 } finally { globalThis.fetch=previous; }
});
