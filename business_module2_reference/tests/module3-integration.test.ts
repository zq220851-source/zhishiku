import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {validateM3Packet,requestM3Search,makeModule1ReviewInbox} from '../lib/module3-integration';
import type {M3Packet,M3SearchResponse} from '../lib/module3-integration';
import type {KnowledgeLearning} from '../lib/b-evolution';
const original=JSON.parse(readFileSync(join(__dirname,'../fixtures/module3/m3-sample.json'),'utf8')) as M3Packet;
const clone=<T>(v:T)=>JSON.parse(JSON.stringify(v)) as T;
const k:KnowledgeLearning={researchId:'m1-demo-c17',capabilityId:'m1:demo-evidence:evidence_scope:comparison',knowledgeVersion:'v1',observations:1,
 statuses:['NOT_FOUND'],recommendation:'REVIEW_RETRIEVAL',status:'CANDIDATE',evidence:[]};
const ctx={requestId:'review-1',queryTerm:'真实世界证据',question:'查找相关证据',requestedAt:'2026-11-02T09:00:00Z'};
const req=requestM3Search(k,ctx);
const reply=():M3SearchResponse=>({kind:'M3_TO_M2_SEARCH_RESPONSE_V1',usage:'TEST_ONLY',requestId:req.requestId,
 status:'LOCAL_SAMPLE_MATCHES_NOT_VERIFIED',searchedAt:'2026-11-02T09:02:00Z',
 matches:original.sourceItems.filter(x=>x.title.includes(ctx.queryTerm))});
test('模块3真实内容出口保持源链接/内容指纹/待审核状态',()=>{
 const p=validateM3Packet(clone(original));assert.ok(p.sourceItems.length>=2);assert.ok(p.sourceItems.every(x=>x.approval==='UNREVIEWED'));
});
test('模块3资讯被改写、伪造审批、混入非安全网址都不得进入适配层',()=>{
 for(const change of [
   (p:M3Packet)=>{p.sourceItems[0].excerpt='替换掉原文摘要';},
   (p:M3Packet)=>{p.sourceItems[0].approval='APPROVED' as any;},
   (p:M3Packet)=>{p.sourceItems[0].sourceUrl='http://external.test';},
   (p:M3Packet)=>{p.sourceItems.push(clone(p.sourceItems[0]));}
 ]){const p=clone(original);change(p);assert.throws(()=>validateM3Packet(p));}
});
test('模块2无知识缺口证据不能要求模块3找资料',()=>{
 assert.throws(()=>requestM3Search({...k,status:'OBSERVATION',recommendation:'NO_MISSING_CLAIM'},ctx));
});
test('检索有结果仍只能进入模块1待审核收件箱，不改知识库',()=>{
 const inbox=makeModule1ReviewInbox(req,reply(),original);
 assert.equal(inbox.knowledgeGapResolved,false);
 assert.equal(inbox.candidates[0].approvalStatus,'PENDING_MEDICAL_REVIEW');
 assert.equal(inbox.candidates[0].appliedToTraining,false);
});
test('模块3回应串错请求、伪造结果、审批时间倒流时会被拒绝',()=>{
 const a=reply();assert.throws(()=>makeModule1ReviewInbox(req,{...a,requestId:'another'},original));
 const b=reply();b.matches[0].contentHash='tampered';assert.throws(()=>makeModule1ReviewInbox(req,b,original));
 const c=reply();c.searchedAt='2026-01-01T00:00:00Z';assert.throws(()=>makeModule1ReviewInbox(req,c,original));
});
test('模块3未核对专家身份，不能擅自将学术线索绑定模块1专家',()=>{
 const p=clone(original);p.academicExample.linkedModule1ExpertId='expert-demo-zhou' as any;
 assert.throws(()=>validateM3Packet(p));
});
