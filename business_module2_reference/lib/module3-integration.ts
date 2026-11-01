/** Test-only module 3 evidence adapter. Not a medical reviewer and not an identity resolver. */
import {createHash} from 'node:crypto';
import type {KnowledgeLearning} from './b-evolution';

export interface M3Candidate {
  sourceId:string;sourceType:string;sourceUrl:string;title:string;publishedAt:string|null;sourceName:string;
  excerpt:string;limitations:string;sourceReviewStatus:'not_reviewed';sourceMode:'sample';
  contentHash:string;approval:'UNREVIEWED';usage:'LEARNING_CANDIDATE_ONLY';
}
export interface M3Packet {
  kind:'M3_EXTERNAL_CANDIDATES_V1';usage:'TEST_ONLY';sourceSystem:'MEDREP_DAILY';
  sourceFeed:string;generatedAt:string;sourceItems:M3Candidate[];
  academicExample:{name:string;fictional:true;identityVerification:'NOT_VERIFIED';linkedModule1ExpertId:null};
}
export interface M2EvidenceSearchRequest {
  kind:'M2_TO_M3_SEARCH_V1';usage:'TEST_ONLY';requestId:string;researchId:string;capabilityId:string;
  knowledgeVersion:string;queryTerm:string;question:string;requestedAt:string;
  state:'REQUEST_FOR_EXTERNAL_CANDIDATES';
}
export interface M3SearchResponse {
  kind:'M3_TO_M2_SEARCH_RESPONSE_V1';usage:'TEST_ONLY';requestId:string;
  status:'LOCAL_SAMPLE_MATCHES_NOT_VERIFIED'|'NO_LOCAL_MATCH';
  matches:M3Candidate[];searchedAt:string;
}
const sha=(x:unknown)=>createHash('sha256').update(JSON.stringify(x)).digest('hex');
const validId=(v:string)=>typeof v==='string'&&/^[a-zA-Z0-9._:-]{1,160}$/.test(v);
export function validateM3Packet(p:M3Packet):M3Packet {
  if(p?.kind!=='M3_EXTERNAL_CANDIDATES_V1'||p.usage!=='TEST_ONLY'||p.sourceSystem!=='MEDREP_DAILY'||
     !Number.isFinite(Date.parse(p.generatedAt))||!Array.isArray(p.sourceItems)||!p.sourceItems.length)
    throw Error('不是可追溯的模块3测试资讯快照');
  const ids=new Set<string>();
  for(const i of p.sourceItems){
    if(!validId(i.sourceId)||ids.has(i.sourceId)||i.sourceReviewStatus!=='not_reviewed'||
       i.approval!=='UNREVIEWED'||i.usage!=='LEARNING_CANDIDATE_ONLY'||i.sourceMode!=='sample'||
       !i.title?.trim()||!i.excerpt?.trim()||!i.sourceName?.trim()||!i.contentHash)
      throw Error('来源、去重或审核状态不满足测试约束');
    const url=new URL(i.sourceUrl);if(url.protocol!=='https:')throw Error('外部资料必须为 HTTPS 来源');
    const hash=sha({title:i.title,summary:i.excerpt,limitations:i.limitations,url:i.sourceUrl});
    if(i.contentHash!==hash)throw Error('模块3来源内容指纹不一致');
    ids.add(i.sourceId);
  }
  if(p.academicExample?.identityVerification!=='NOT_VERIFIED'||p.academicExample.linkedModule1ExpertId!==null||
     p.academicExample.fictional!==true)throw Error('未核实的公开学术样例不能绑定为已确认专家');
  return p;
}
export function requestM3Search(knowledge:KnowledgeLearning,context:{requestId:string;queryTerm:string;question:string;requestedAt:string}):M2EvidenceSearchRequest {
  if(knowledge.status!=='CANDIDATE'||!['REVIEW_RETRIEVAL','REVIEW_PARTIAL'].includes(knowledge.recommendation)||
     !validId(context.requestId)||!context.queryTerm.trim()||context.queryTerm.length>120||
     !context.question.trim()||!Number.isFinite(Date.parse(context.requestedAt)))
    throw Error('只有有证据的知识覆盖候选才能发起测试检索');
  return {kind:'M2_TO_M3_SEARCH_V1',usage:'TEST_ONLY',requestId:context.requestId,
    researchId:knowledge.researchId,capabilityId:knowledge.capabilityId,knowledgeVersion:knowledge.knowledgeVersion,
    queryTerm:context.queryTerm,question:context.question,requestedAt:context.requestedAt,
    state:'REQUEST_FOR_EXTERNAL_CANDIDATES'};
}
export function makeModule1ReviewInbox(req:M2EvidenceSearchRequest,reply:M3SearchResponse,packet:M3Packet){
  validateM3Packet(packet);
  if(req.kind!=='M2_TO_M3_SEARCH_V1'||req.usage!=='TEST_ONLY'||reply.kind!=='M3_TO_M2_SEARCH_RESPONSE_V1'||
    reply.requestId!==req.requestId||reply.usage!=='TEST_ONLY'||!Number.isFinite(Date.parse(reply.searchedAt))||
    Date.parse(reply.searchedAt)<Date.parse(req.requestedAt)||reply.matches.length>packet.sourceItems.length)
    throw Error('搜索请求和响应不匹配');
  const ids=new Set<string>();
  for(const m of reply.matches){
    const origin=packet.sourceItems.find(i=>i.sourceId===m.sourceId);
    if(!origin||origin.contentHash!==m.contentHash||ids.has(m.sourceId)||
      !`${m.title} ${m.excerpt}`.includes(req.queryTerm))throw Error('模块3结果未能核对原始来源或检索词');
    ids.add(m.sourceId);
  }
  if((reply.matches.length>0)!==(reply.status==='LOCAL_SAMPLE_MATCHES_NOT_VERIFIED'))throw Error('搜索状态不一致');
  return {kind:'M3_TO_M1_REVIEW_INBOX_V1',usage:'TEST_ONLY',sourceSystem:'MEDREP_DAILY',
    targetSystem:'MODULE1_KNOWLEDGE_REVIEW',requestId:req.requestId,requestedCapabilityId:req.capabilityId,
    priorKnowledgeVersion:req.knowledgeVersion,
    candidates:reply.matches.map(x=>({sourceId:x.sourceId,sourceUrl:x.sourceUrl,title:x.title,
      sourceVersion:x.contentHash,sourceType:x.sourceType,excerpt:x.excerpt,limitations:x.limitations,
      approvalStatus:'PENDING_MEDICAL_REVIEW' as const,appliedToTraining:false})),
    searchStatus:reply.status,knowledgeGapResolved:false,
    note:'模块3仅提供历史学习资料线索；即使检索有结果，也不代表C-17研究缺口已被补足。模块1知识版本不会自动更新。'};
}
