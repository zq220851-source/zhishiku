import { test } from 'node:test';
import assert from 'node:assert/strict';
import { validateSemanticProposal, reanchorUniqueQuotes, type SemanticProposal } from '../lib/semantic-proposal';
import { reviewedQuestionObservations, type EventReview } from '../lib/evidence-admission';
const raw='医生没有问终点，却追问了外推。';
const span=(quote:string)=>({quote,startCp:Array.from(raw.slice(0,raw.indexOf(quote))).length,endCp:Array.from(raw.slice(0,raw.indexOf(quote))).length+Array.from(quote).length});
function base():SemanticProposal {return {usage:'TEST_ONLY',rawVersion:1,rawText:raw,links:[],events:[
 {id:'a',action:'QUESTION',agent:'EXPERT',when:'DURING_VISIT',factuality:'DENIED',negationScope:'TARGET_EVENT',capabilityId:'endpoint',...span('医生没有问终点')},
 {id:'b',action:'QUESTION',agent:'EXPERT',when:'DURING_VISIT',factuality:'REPORTED',negationScope:'DIFFERENT_EVENT',capabilityId:'extrapolation',...span('却追问了外推')}
]};}
const approve=(id:string,status:EventReview['verifiedFactuality']):EventReview=>({eventId:id,reviewerId:'reviewer-1',reason:'人工核对了每个事件的否定对象与说话人',checkedRawVersion:1,verifiedFactuality:status,verdict:'APPROVE_TEST_ONLY'});
test('the contract represents two contrastive questions with different factuality, without collapsing the sentence',()=>{
 const result=validateSemanticProposal(base());assert.deepEqual(result.events.map(e=>e.factuality),['DENIED','REPORTED']);
 const admitted=reviewedQuestionObservations(result,[approve('a','DENIED'),approve('b','REPORTED')]);
 assert.deepEqual(admitted.observations.map(x=>x.id),['b']);
});
test('unknown speaker cannot be silently converted into an expert event',()=>{
 const p=base();p.events[1].agent='UNKNOWN';const s=validateSemanticProposal(p);
 assert.equal(s.events.some(e=>e.id==='b'),false);
});
test('a sentence-level denial erroneously attached to a reported event fails the contract',()=>{
 const p=base();p.events[1].negationScope='TARGET_EVENT';assert.throws(()=>validateSemanticProposal(p),/否定/);
});
test('incorrect quote span, future fact, and invalid lexical schema fail closed',()=>{
 const p=base();p.events[1].quote='杜撰的原文';assert.throws(()=>validateSemanticProposal(p),/引文/);
 const f=base();f.events[1].when='FUTURE';assert.throws(()=>validateSemanticProposal(f),/未来/);
 const g=base();(g.events[1] as any).agent='DOCTOR';assert.throws(()=>validateSemanticProposal(g),/agent/);
});

test('unique verbatim quote can be reanchored without silently editing source; duplicate quotes are rejected',()=>{
 const p=base();p.events[1].startCp=0;p.events[1].endCp=1;
 const {proposal,adjustments}=reanchorUniqueQuotes(p);
 assert.equal(adjustments.length,1);
 assert.deepEqual(validateSemanticProposal(proposal).events.map(e=>e.id),['a','b']);
 const duplicate:SemanticProposal={...p,rawText:'医生问外推。医生问外推。',events:[{...p.events[0],quote:'医生问外推',startCp:1,endCp:2}],links:[]};
 assert.throws(()=>reanchorUniqueQuotes(duplicate),/多次/);
});
