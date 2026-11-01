import {test} from 'node:test';
import assert from 'node:assert/strict';
import {reportedExpertQuestions,validateReviewEvidence,type ReviewEvidenceSnapshot} from '../lib/semantic-evidence';
const raw='医生问了外推。我当时说应该可以。回来觉得这句话说得太满。';
const span=(x:string)=>({quote:x,startCp:Array.from(raw.slice(0,raw.indexOf(x))).length,endCp:Array.from(raw.slice(0,raw.indexOf(x))).length+Array.from(x).length});
const sample=():ReviewEvidenceSnapshot=>({usage:'TEST_ONLY',rawVersion:1,rawText:raw,events:[
 {id:'q',kind:'EXPERT_QUESTION',factuality:'REPORTED',capabilityId:'extrapolation',...span('医生问了外推。')},
 {id:'a',kind:'REP_RESPONSE',factuality:'REPORTED',capabilityId:'extrapolation',...span('我当时说应该可以。')},
 {id:'r',kind:'REP_REFLECTION',factuality:'REPORTED',capabilityId:'extrapolation',...span('回来觉得这句话说得太满。')},
],links:[{from:'a',to:'q',type:'ANSWER_TO',evidenceEventIds:['a','q']},{from:'r',to:'a',type:'REFLECTS_ON',evidenceEventIds:['r','a']}]});
test('separate reflection on an actual answer from historical correction',()=>{const x=sample();assert.doesNotThrow(()=>validateReviewEvidence(x));assert.equal(reportedExpertQuestions(x).length,1);});
test('denied question does not become reported expert event',()=>{const x=sample();x.events[0].factuality='DENIED';assert.equal(reportedExpertQuestions(x).length,0);});
test('hypothetical and uncertain expert questions do not create current observations',()=>{for(const m of ['HYPOTHETICAL','UNCERTAIN'] as const){const x=sample();x.events[0].factuality=m;assert.equal(reportedExpertQuestions(x).length,0);}});
test('invented span and unsupported relation rejected',()=>{const x=sample();x.events[0].quote='医生根本没问';assert.throws(()=>validateReviewEvidence(x),/原文/);const y=sample();y.links[1].type='REVISES_DESCRIPTION';assert.throws(()=>validateReviewEvidence(y),/更正/);});
