/** Live team releases. No fixture teams, generated evidence, or medical approval. */
import {randomUUID} from 'node:crypto';
import {Store,digest} from './store';
import {Module2Error,invalid} from './errors';
import {adaptModule1,type Module1Export} from './live-module1';
import type {Actor,Feedback,Task} from './types';
type Option=Module1Export['options'][number];
type Dependency={feedbackId:string;taskId:string;visitId:string;hash:string};
type Source={feedback:Feedback;task:Task;source:Module1Export;dependency:Dependency;expected:number[]};
type Trial={feedbackId:string;split:'validation'|'holdout';baseline:string[];proposed:string[];expected:string[];budget:number;baselineCoverage:number;proposedCoverage:number};
export interface Release {
 id:string;revision:number;level:'L2'|'L3';state:'DRAFT'|'VALIDATED'|'APPROVED'|'REVOKED'|'STALE';
 ownerId:string;authorId:string;tenant:string;teamId:string;lessonId:string;sourceRevision:string;
 option:Option;signature:string;dependencies:Dependency[];reason:string;createdAt:string;
 evaluation?:{cases:Trial[];hash:string;reviewerId:string;reason:string};approval?:{actorId:string;reason:string;at:string};
}
const fail=(message:string,status=409):never=>{throw new Module2Error('EVOLUTION_REJECTED',message,status);};
export function optionSignature(option:Option):string {
 return digest(option.criteria.map(c=>({label:c.label,expected:c.expected,source_ids:[...(c.source_ids||[])].sort()})).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b))));
}
export class LiveEvolution {
 constructor(readonly store:Store){}
 private scope(actor:Actor){if(!actor.scope)return fail('共享内容需要平台签名的真实团队身份',403);return actor.scope;}
 private team(actor:Actor,id:string){const team=this.scope(actor).teams.find(t=>t.id===id&&t.owners.includes(actor.id));if(!team)return fail('不在该团队的授权范围',403);return team;}
 private source(owner:string,feedbackId:string):Source {
  const feedback=this.store.get<Feedback>(feedbackId,'feedback',owner),task=this.store.get<Task>(feedback.taskId,'task',owner);
  const source=this.store.get<Module1Export>('source:'+task.id,'live_source',owner),meta=this.store.get<{exchangeMode:string}>('meta:'+feedback.id,'live_feedback_meta',owner);
  if(meta.exchangeMode!=='REPORTED_EXCHANGE'||task.status!=='READY'||feedback.state!=='ANALYZED'||!feedback.analysis||feedback.analysisRawId!==feedback.versions.at(-1)?.id)fail('需要已分析、原文未变更的实际交流记录');
  if(source.sourceKind!=='sheets'||!task.snapshot.forecastSnapshot||!task.snapshot.origin||source.material.status==='fictional_test_material')fail('需要真实课程和访前已冻结的原始候选');
  if(new Date(feedback.createdAt).getTime()/1000<source.forecast!.frozen_at)fail('原文记录早于预测冻结，不能作为独立访前验证');
  const adapted=adaptModule1(source);
  if(adapted.scenarioVersion!==task.snapshot.scenarioVersion||adapted.knowledgeVersion!==task.snapshot.knowledgeVersion)fail('原任务快照与来源版本不一致');
  const raw=feedback.versions.at(-1)!;
  const supported=new Set(feedback.analysis!.findings.filter(f=>{
   const u=feedback.analysis!.units.find(u=>u.id===f.questionUnitId);
   return f.eligibleForSharedChange&&u&&u.types.includes('REPORTED_QUESTION')&&u.attribution==='OTHER_REPORTED'&&u.certainty==='REPORTED'&&Array.from(raw.text).slice(u.startCp,u.endCp).join('')===u.excerpt;
  }).flatMap(f=>f.skillIds));
  let offset=0;const expected:number[]=[];
  source.options.forEach((o,i)=>{const skills=task.snapshot.codebook.skills.slice(offset,offset+o.criteria.length);offset+=o.criteria.length;if(skills.some(s=>supported.has(s.id)))expected.push(i);});
  if(!expected.length)fail('没有定位到原文、可用于共享变更的问题证据');
  return {feedback,task,source,expected,dependency:{feedbackId,taskId:task.id,visitId:source.sourceTaskId,hash:digest({raw,analysis:feedback.analysis,source,snapshot:task.snapshot})}};
 }
 sources(actor:Actor){this.scope(actor);return this.store.list<Feedback>('feedback',actor.id).flatMap(f=>{
  try{const s=this.source(actor.id,f.id);return [{feedbackId:f.id,taskId:s.task.id,visitId:s.source.sourceTaskId,title:s.task.title,lessonId:s.source.lessonId,revision:s.source.material.revision,rawVersion:s.feedback.versions.at(-1)!.version,observations:s.feedback.analysis!.units.filter(u=>u.types.includes('REPORTED_QUESTION')&&u.attribution==='OTHER_REPORTED').map(u=>u.excerpt),options:s.expected.map(index=>({index,question:s.source.options[index].question,selected:s.source.forecast!.selected_ids.includes(s.source.options[index].id!)}))}];}catch{return [];}
 });}
 private current(r:Release,actor:Actor):boolean {
  if(r.tenant!==this.scope(actor).tenant||!this.scope(actor).teams.some(t=>t.id===r.teamId&&t.owners.includes(r.ownerId)))return false;
  return r.dependencies.every(d=>{try{return this.source(r.ownerId,d.feedbackId).dependency.hash===d.hash;}catch{return false;}});
 }
 private read(actor:Actor,id:string,revision?:number){
  const r=this.store.get<Release>(id,'live_evolution',actor.id);this.team(actor,r.teamId);
  if(r.tenant!==this.scope(actor).tenant)fail('团队不匹配',403);
  if(revision!==undefined&&revision!==r.revision)fail('版本已改变，请刷新后重试');
  if(!this.current(r,actor))fail('原文、分析或团队来源已变化，请重新提出候选');
  return r;
 }
 private save(actor:Actor,r:Release,event:string){
  this.store.put(r.id,'live_evolution',r.ownerId,r);
  if(r.state==='APPROVED'||r.state==='REVOKED')this.store.put('release:'+r.id,'live_team_release',digest([r.tenant,r.teamId]),r);
  this.store.event(r.id,this.scope(actor).actorId,event,{revision:r.revision,state:r.state,reason:r.reason,evaluationHash:r.evaluation?.hash,evaluationReason:r.evaluation?.reason,approvalReason:r.approval?.reason});return r;
 }
 list(actor:Actor){this.scope(actor);return this.store.list<Release>('live_evolution',actor.id).filter(r=>this.scope(actor).teams.some(t=>t.id===r.teamId)).map(r=>({...r,state:this.current(r,actor)?r.state:'STALE'}));}
 active(actor:Actor){const scope=this.scope(actor);return scope.teams.flatMap(t=>this.store.list<Release>('live_team_release',digest([scope.tenant,t.id])))
  .filter(r=>r.state==='APPROVED'&&this.current(r,actor)).map(r=>({id:r.id,version:r.revision,level:r.level,teamId:r.teamId,lessonId:r.lessonId,sourceRevision:r.sourceRevision,option:r.option,signature:r.signature}));}
 propose(actor:Actor,input:{level:string;teamId:string;feedbackId:string;optionIndex:number;reason:string}){
  const scope=this.scope(actor);this.team(actor,input.teamId);
  if(!['L2','L3'].includes(input.level)||input.reason.trim().length<8||input.reason.length>1000)invalid('选择 L2/L3 并填写至少 8 字的用途说明');
  const s=this.source(actor.id,input.feedbackId),option=s.source.options[input.optionIndex];
  if(!option||!s.expected.includes(input.optionIndex)||!option.question)fail('场景必须对应原文中报告的问题和原资料标准');
  if(input.level==='L3'&&s.source.forecast!.selected_ids.includes(option.id!))fail('该候选已经选中，不能把个人表达问题当成漏选策略');
  const r:Release={id:randomUUID(),revision:1,level:input.level as 'L2'|'L3',state:'DRAFT',ownerId:actor.id,authorId:scope.actorId,tenant:scope.tenant,teamId:input.teamId,lessonId:s.source.lessonId,sourceRevision:s.source.material.revision,option:{question:option.question,criteria:option.criteria},signature:optionSignature(option),dependencies:[s.dependency],reason:input.reason,createdAt:new Date().toISOString()};
  return this.store.transaction(()=>this.save(actor,r,'LIVE_EVOLUTION_PROPOSED'));
 }
 private reviewer(actor:Actor,r:Release){if(!this.scope(actor).reviewer||this.scope(actor).actorId===r.authorId)fail('须由本团队另一名授权审核人操作',403);}
 evaluate(actor:Actor,id:string,revision:number,ids:string[],reason:string){return this.store.transaction(()=>{
  const r=this.read(actor,id,revision);this.reviewer(actor,r);
  if(r.state!=='DRAFT'||reason.trim().length<8||ids.length!==2||new Set(ids).size!==2)fail('草稿需两份独立记录和至少 8 字的审核说明');
  const sources=ids.map(id=>this.source(r.ownerId,id));
  if(new Set([r.dependencies[0].visitId,...sources.map(s=>s.source.sourceTaskId)]).size!==3)fail('提案、验证和留出记录必须来自三次独立任务');
  const trials:Trial[]=sources.map((s,i)=>{
   if(s.source.lessonId!==r.lessonId||s.source.material.revision!==r.sourceRevision)fail('独立记录的课程或资料版本不同');
   const options=s.source.options,match=options.map((o,j)=>optionSignature(o)===r.signature?j:-1).filter(j=>j>=0);
   if(match.length!==1||!s.expected.includes(match[0]))fail('独立原文未支持完全相同的观察标准，不能用同课程代替可比证据');
   const baseline=s.source.forecast!.selected_ids,budget=s.source.forecast!.budget;
   const preferred=options[match[0]].id!,ordered=[preferred,...baseline,...options.map(o=>o.id!)];
   const proposed=r.level==='L3'?[...new Set(ordered)].slice(0,budget):[...baseline];
   const expected=s.expected.map(j=>options[j].id!);
   return {feedbackId:s.feedback.id,split:i===0?'validation':'holdout',baseline,proposed,expected,budget,baselineCoverage:baseline.filter(x=>expected.includes(x)).length,proposedCoverage:proposed.filter(x=>expected.includes(x)).length};
  });
  if(r.level==='L3'&&(trials.some(t=>t.proposedCoverage<t.baselineCoverage)||trials[1].proposedCoverage<=trials[1].baselineCoverage))fail('固定预算下未证明留出改善，或出现覆盖倒退');
  return this.save(actor,{...r,revision:r.revision+1,state:'VALIDATED',dependencies:[r.dependencies[0],...sources.map(s=>s.dependency)],evaluation:{cases:trials,hash:digest(trials),reviewerId:this.scope(actor).actorId,reason}},'LIVE_EVOLUTION_VALIDATED');
 });}
 approve(actor:Actor,id:string,revision:number,reason:string){return this.store.transaction(()=>{
  const r=this.read(actor,id,revision);this.reviewer(actor,r);
  if(r.state!=='VALIDATED'||!r.evaluation||reason.trim().length<8)fail('须先通过独立验证并填写共享审核理由');
  const duplicate=this.active(actor).some(p=>p.teamId===r.teamId&&p.level===r.level&&p.lessonId===r.lessonId&&p.sourceRevision===r.sourceRevision&&p.signature===r.signature);
  if(duplicate)fail('团队已有相同标准的有效版本，请先撤回旧版');
  return this.save(actor,{...r,state:'APPROVED',revision:r.revision+1,approval:{actorId:this.scope(actor).actorId,reason,at:new Date().toISOString()}},'LIVE_EVOLUTION_APPROVED');
 });}
 revoke(actor:Actor,id:string,revision:number,reason:string){return this.store.transaction(()=>{
  // Revocation remains possible after a source correction.
  const r=this.store.get<Release>(id,'live_evolution',actor.id);this.team(actor,r.teamId);this.reviewer(actor,r);
  if(r.revision!==revision||r.state!=='APPROVED'||reason.trim().length<8)fail('仅可撤回当前已发布版本，请说明原因');
  return this.save(actor,{...r,state:'REVOKED',revision:r.revision+1,reason},'LIVE_EVOLUTION_REVOKED');
 });}
}
