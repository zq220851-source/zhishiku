/** Three-module TEST_ONLY data-level integration; real business code, synthetic task/observations. */
import {spawnSync} from 'node:child_process';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {join,resolve} from 'node:path';
import type {M1SnapshotPacket,M1ReviewedRun} from '../../lib/module1-integration';
import {importModule1Snapshot,createTestVisit,mergeM1PracticeIntoVerifiedVisit,m1PreparationContext,recommendModule1Options} from '../../lib/module1-integration';
import {analyzeFiveAssets,proposeNextPreparation} from '../../lib/b-evolution';
import {projectVisit} from '../../lib/five-assets';
import type {M3Packet,M3SearchResponse} from '../../lib/module3-integration';
import {validateM3Packet,requestM3Search,makeModule1ReviewInbox} from '../../lib/module3-integration';

const all=resolve(__dirname,'../../../..');
const m1=join(all,'module1_source'),m2=join(all,'medrep_coach_with_ai_rules/module2'),m3=join(all,'medrep-daily');
const ex=join(all,'shared_exchange');mkdirSync(ex,{recursive:true});
const run=(cmd:string,args:string[])=>{const r=spawnSync(cmd,args,{encoding:'utf8',cwd:all});if(r.status!==0)throw Error(`${cmd} 失败: ${(r.stderr||r.stdout||'').slice(0,1000)}`);return r.stdout.trim();};
const write=(name:string,v:unknown)=>{const p=join(ex,name);writeFileSync(p,JSON.stringify(v,null,2),'utf8');return p;};
// Regenerate from module 1's actual Python course and scene definitions, not a hand-made replacement.
run('python3',[join(m2,'integrations/module1/export_fictional_handoff.py'),'--module1',m1,
  '--out',join(m2,'fixtures/module1/m1-fictional-packet.json')]);
const m1Packet=JSON.parse(readFileSync(join(m2,'fixtures/module1/m1-fictional-packet.json'),'utf8')) as M1SnapshotPacket;
const bridge=importModule1Snapshot(m1Packet);
const m3file=join(ex,'module3-external-candidates.json');
run(process.execPath,[join(m3,'integrations/medrep-coach/export-sample.mjs'),m3file]);
const m3Packet=validateM3Packet(JSON.parse(readFileSync(m3file,'utf8')) as M3Packet);
// A human-verified, fictional visit is deliberately supplied instead of pretending this was NLP model output.
const rawText='拜访中医生实际追问了没有比较组为什么还说更好，我没能解释清楚。';
const quote='医生实际追问了没有比较组为什么还说更好';
const cap=bridge.criterionCapabilities['evidence_scope:comparison'];
let visit=createTestVisit({bridge,visitId:'three-module-fictional-visit-1',at:'2026-10-31T10:00:00Z',rawText,
  observations:[{id:'doctor-q-1',kind:'EXPERT_QUESTION',mode:'REPORTED',capabilityId:cap,quote,
    startCp:Array.from(rawText.slice(0,rawText.indexOf(quote))).length,
    endCp:Array.from(rawText.slice(0,rawText.indexOf(quote))).length+Array.from(quote).length}]});
const opt=m1Packet.visit.options.find(x=>x.id==='followup')!;
const answer='我不确定要查什么，先记下来吧。';
const practice:M1ReviewedRun={id:'three-module-synthetic-run-1',sheet_id:m1Packet.sheet.id,state:'review',attempt:1,
  updated_at:Date.parse('2026-10-31T09:00:00Z')/1000,source_status:'fictional_test_material',
  task:{question:opt.question,criteria:opt.criteria},transcript:[{role:'医生',text:opt.question},{role:'药代',text:answer}],
  review:{assessment_status:'formative_suggestion',medical_accuracy:'NA',independent_mastery:false,
    observations:[{criterion_id:'next',status:'needs_work',evidence_id:'T1',quote:answer,turn_index:1,
      reason:'无法说明查证途径和下次反馈时间',source_ids:['demo-evidence:sections.2']}]}};
visit=mergeM1PracticeIntoVerifiedVisit(visit,bridge,practice);
visit.knowledgeChecks.push({observationId:'doctor-q-1',capabilityId:cap,status:'NOT_FOUND',queriedEvidenceIds:[],
  queryAttempts:['查找虚构课程 C-17 中关于比较研究证据的说明'],knowledgeVersion:bridge.task.knowledgeVersion});
// Second, independently observed practice result: the earlier personal gap improved.
const secondText='第二次准备时把资料核对和反馈安排说清楚；没有报告新的医生问题。';
let second=createTestVisit({bridge,visitId:'three-module-fictional-visit-2',at:'2026-11-01T10:00:00Z',rawText:secondText,observations:[]});
const betterAnswer='我会检查原始资料，核对没有测量的指标，并与医生约定反馈的时间。';
const improved:M1ReviewedRun={...practice,id:'three-module-synthetic-run-2',updated_at:Date.parse('2026-11-01T09:00:00Z')/1000,
  transcript:[{role:'医生',text:opt.question},{role:'药代',text:betterAnswer}],
  review:{...practice.review,observations:[{...practice.review.observations[0],status:'demonstrated',quote:betterAnswer,
    reason:'明确了需要核实的内容与反馈安排'}]}};
second=mergeM1PracticeIntoVerifiedVisit(second,bridge,improved);
const assets=projectVisit(visit);const asOf='2026-11-02T09:00:00Z';
const learning=analyzeFiveAssets({source:'HUMAN_VERIFIED_SYNTHETIC',visits:[visit,second],asOf});
if(!learning.knowledge.length||!learning.personal.length||assets.entries.length<5)throw Error('五资产投射或个人能力积累不完整');
const request=requestM3Search(learning.knowledge[0],{
  requestId:'c17-evidence-methods-001',requestedAt:asOf,queryTerm:'真实世界证据',
  question:'研究C-17缺少比较证据：有哪些公开资料可帮助学习如何核对证据来源与局限？'});
const reqPath=write('module2-to-module3-search.json',request);
const responsePath=join(ex,'module3-to-module2-search.json');
run(process.execPath,[join(m3,'integrations/medrep-coach/search-local.mjs'),reqPath,m3file,responsePath]);
const response=JSON.parse(readFileSync(responsePath,'utf8')) as M3SearchResponse;
const inbox=makeModule1ReviewInbox(request,response,m3Packet);
const inboxPath=write('module3-to-module1-review-queue.json',inbox);
const ctx=m1PreparationContext(bridge,{taskId:'three-module-next-preparation',startsAt:asOf,budget:2,
  mandatoryCapabilityIds:[bridge.criterionCapabilities['needs:focus']]});
const plan=proposeNextPreparation(ctx,[visit,second]);
const next=m1PreparationContext(bridge,{taskId:ctx.taskId,startsAt:asOf,budget:2,
  mandatoryCapabilityIds:[bridge.criterionCapabilities['needs:focus']]});
const suggestion=recommendModule1Options(bridge,plan,next.budget,['needs']);
const candidatePath=write('module2-to-module1-next-preparation.json',suggestion);
const checks={m1FrozenSnapshot:true,m1ReviewAnchored:visit.practices.length===1,m2FiveAssetTypes:[...new Set(assets.entries.map(x=>x.kind))],
  m2KnowledgeCheckStatus:learning.knowledge[0].recommendation,
  m3ActualSourceIds:response.matches.map(x=>x.sourceId),
  m3StillUnreviewed:inbox.candidates.every(x=>!x.appliedToTraining&&x.approvalStatus==='PENDING_MEDICAL_REVIEW'),
  m1VersionUnchanged:bridge.task.knowledgeVersion===visit.knowledgeChecks[0].knowledgeVersion,
  nextPreparationStatus:suggestion.status,
  nextSelection:suggestion.selectedOptionIds,
  academicIdentityNotInferred:m3Packet.academicExample.linkedModule1ExpertId===null};
if(!checks.m1ReviewAnchored||checks.m2FiveAssetTypes.length!==5||!checks.m3ActualSourceIds.includes('example-rwe')||
  !suggestion.selectedOptionIds.includes('evidence_scope')||
  !checks.m3StillUnreviewed||!checks.m1VersionUnchanged||checks.nextPreparationStatus!=='CANDIDATE_NOT_APPLIED'||
  !checks.academicIdentityNotInferred)throw Error('三模块联动不满足底线检查');
const output={kind:'THREE_MODULE_TEST_ONLY_RESULT',
  scope:'实际 M1 课程代码 + 实际 M3 本地筛选函数 + 实际 M2 五资产/策略函数；训练/拜访为虚构数据，不联网',
  module1:{source:'module1_source/knowledge.py',lessonId:bridge.lessonId,preparedSheetId:bridge.sheetId,
    snapshotHash:bridge.snapshotHash,selectedBefore:bridge.selectedOptionIds,
    trainingCriterion:visit.practices[0].capabilityId,trainingResult:visit.practices[0].result},
  module2:{visitId:visit.visitId,secondVisitId:second.visitId,firstPractice:visit.practices,secondPractice:second.practices,assets:assets.entries,personal:learning.personal,forecast:learning.forecast,
    knowledge:learning.knowledge,experts:learning.experts,cohort:learning.cohort,
    nextPreparation:{before:bridge.selectedOptionIds,after:suggestion.selectedOptionIds,
      added:suggestion.addedOptionIds,displaced:suggestion.displacedOptionIds,status:suggestion.status,
      usedVisitIds:plan.usedVisitIds}},
  module3:{source:'medrep-daily/src/core.mjs:SEEDS/assemble',sourceCandidates:m3Packet.sourceItems.length,
    query:request.queryTerm,searchStatus:response.status,found:response.matches.map(x=>({id:x.sourceId,title:x.title,url:x.sourceUrl})),
    reviewCandidates:inbox.candidates,publicAcademicIdentity:m3Packet.academicExample.identityVerification},
  exchange:{request:reqPath,response:responsePath,medicalReviewInbox:inboxPath,nextPreparationCandidate:candidatePath},
  checks,limitations:['没有调用外部文献检索或实时模型','模块1正式课程知识与历史训练数据没有接入',
    '模块3仅返回本地历史示例，不能证明知识缺口得到解决','模块1的正式 prepare 函数没有消费新候选；本次是数据契约的离线三向交换']};
write('three-module-results.json',output);
console.log(JSON.stringify({assets:checks.m2FiveAssetTypes,search:checks.m3ActualSourceIds,
  status:suggestion.status,selection:checks.nextSelection,medicalApproval:false,publicExpertMatched:false},null,2));
