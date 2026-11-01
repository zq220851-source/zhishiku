/** Review and persisted snapshots for test-only B learning, independent of semantic extraction. */
import { createHash } from 'node:crypto';
import type { Store } from './store';
import { analyzeFiveAssets, type FiveAssetLearning, type PreparationContext, type PlanDelta, proposeNextPreparation } from './b-evolution';
import type { VisitEvidence } from './five-assets';

const hash=(value:unknown)=>createHash('sha256').update(JSON.stringify(value)).digest('hex');
export type CandidateType='PERSONAL_TRAINING'|'KNOWLEDGE_REVIEW'|'EXPERT_NOTE'|'COHORT_HYPOTHESIS'|'PREDICTION_EXPERIMENT'|'METHOD_PATCH';
export interface BProposal { id:string;kind:CandidateType;scope:string;why:string;sourceDigest:string;sourceRefs:string[];state:'CANDIDATE'; }
export interface BReviewDecision {id:string;candidateId:string;actor:string;reviewedDigest:string;decision:'APPROVE_TEST_ONLY'|'REJECT'|'NEEDS_MORE_EVIDENCE';reason:string;at:string; }
export interface NextRoundArtifact {context:PreparationContext;delta:PlanDelta;status:'COMPARISON_ONLY';}
export function buildCandidates(a:FiveAssetLearning):BProposal[]{
  if(a.source!=='HUMAN_VERIFIED_SYNTHETIC')throw new Error('只接受核验的虚构输入');
  const out:BProposal[]=[];
  const add=(kind:CandidateType,scope:string,why:string,refs:string[])=>{
    const id=hash([a.sourceDigest,kind,scope,why]).slice(0,24);
    out.push({id,kind,scope,why,sourceDigest:a.sourceDigest,sourceRefs:refs,state:'CANDIDATE'});
  };
  const ref=(arr:{visitId:string}[])=>[...new Set(arr.map(x=>x.visitId))];
  for(const x of a.personal) if(x.status!=='INSUFFICIENT_EVIDENCE')add('PERSONAL_TRAINING',`${x.repId}:${x.capabilityId}`,x.reason,ref(x.evidence));
  for(const x of a.knowledge) if(x.status==='CANDIDATE')add('KNOWLEDGE_REVIEW',`${x.researchId}:${x.capabilityId}:${x.knowledgeVersion}`,`需核对：${x.recommendation}。不可直接新增医学知识`,ref(x.evidence));
  for(const x of a.experts)add('EXPERT_NOTE',`${x.expertId}:${x.researchId}:${x.capabilityId}`,x.description,ref(x.evidence));
  for(const x of a.cohort) if(x.status==='PATTERN_FOR_REVIEW')add('COHORT_HYPOTHESIS',`${x.researchId}:${x.capabilityId}`,x.reason,ref(x.evidence));
  for(const x of a.forecast)if(x.diagnosis!=='SOMETIMES_SELECTED')add('PREDICTION_EXPERIMENT',`${x.researchId}:${x.capabilityId}`,`候选原因：${x.diagnosis}；需要用未来留出样例同预算比较`,ref(x.evidence));
  return out.sort((a,b)=>a.id.localeCompare(b.id));
}
/** No clinical / production release API exists here. Only explicit test reviews can be persisted. */
export class BReviewLedger {
  constructor(private store:Store){store.db.exec(`CREATE TABLE IF NOT EXISTS b_runs (
    run_id TEXT PRIMARY KEY,source_digest TEXT NOT NULL,payload_hash TEXT NOT NULL,payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS b_decisions (decision_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,candidate_id TEXT NOT NULL,reviewer TEXT NOT NULL,payload TEXT NOT NULL,FOREIGN KEY(run_id) REFERENCES b_runs(run_id));
    CREATE TRIGGER IF NOT EXISTS b_runs_immutable_update BEFORE UPDATE ON b_runs BEGIN SELECT RAISE(ABORT,'immutable'); END;
    CREATE TRIGGER IF NOT EXISTS b_runs_immutable_delete BEFORE DELETE ON b_runs BEGIN SELECT RAISE(ABORT,'immutable'); END;
    CREATE TRIGGER IF NOT EXISTS b_decisions_immutable_update BEFORE UPDATE ON b_decisions BEGIN SELECT RAISE(ABORT,'immutable'); END;
    CREATE TRIGGER IF NOT EXISTS b_decisions_immutable_delete BEFORE DELETE ON b_decisions BEGIN SELECT RAISE(ABORT,'immutable'); END;`);}
  execute(args:{runId:string;visits:VisitEvidence[];asOf:string;preparation?:PreparationContext}):{assets:FiveAssetLearning;candidates:BProposal[];next?:NextRoundArtifact}{
    if(!/^[A-Za-z0-9_.:-]{2,100}$/.test(args.runId))throw new Error('审查运行 ID 无效');
    const assets=analyzeFiveAssets({source:'HUMAN_VERIFIED_SYNTHETIC',visits:args.visits,asOf:args.asOf});
    if(args.preparation&&Date.parse(args.preparation.startsAt)<Date.parse(args.asOf))throw new Error('下一准备时间不得早于分析时点');
    const candidates=buildCandidates(assets);
    const next=args.preparation?{context:args.preparation,delta:proposeNextPreparation(args.preparation,args.visits),status:'COMPARISON_ONLY' as const}:undefined;
    const payload={assets,candidates,...(next?{next}:{})};const serialized=JSON.stringify(payload),payloadHash=hash(payload);
    this.store.transaction(()=>{
      const prior=this.store.db.prepare('SELECT payload_hash FROM b_runs WHERE run_id=?').get(args.runId) as {payload_hash:string}|undefined;
      if(prior){if(prior.payload_hash!==payloadHash)throw new Error('同一运行 ID 不允许覆盖内容');return;}
      this.store.db.prepare('INSERT INTO b_runs VALUES (?,?,?,?)').run(args.runId,assets.sourceDigest,payloadHash,serialized);
    });
    return payload;
  }
  read(runId:string):{assets:FiveAssetLearning;candidates:BProposal[];next?:NextRoundArtifact}{
    const row=this.store.db.prepare('SELECT payload FROM b_runs WHERE run_id=?').get(runId) as {payload:string}|undefined;
    if(!row)throw new Error('运行记录不存在');return JSON.parse(row.payload);
  }
  review(runId:string,input:BReviewDecision){
    if(!/^[A-Za-z0-9_.:-]{2,100}$/.test(input.id)||!/^[A-Za-z0-9_.:-]{2,100}$/.test(input.actor)||input.reason.trim().length<8||!Number.isFinite(Date.parse(input.at)))throw new Error('独立审核信息不完整');
    if(!['APPROVE_TEST_ONLY','REJECT','NEEDS_MORE_EVIDENCE'].includes(input.decision))throw new Error('审核结果无效');
    const run=this.read(runId),candidate=run.candidates.find(x=>x.id===input.candidateId);
    if(!candidate||candidate.sourceDigest!==input.reviewedDigest)throw new Error('候选或当前证据指纹无效');
    this.store.transaction(()=>{
      if(this.store.db.prepare('SELECT 1 FROM b_decisions WHERE decision_id=?').get(input.id))throw new Error('重复审核编号');
      this.store.db.prepare('INSERT INTO b_decisions VALUES (?,?,?,?,?)').run(input.id,runId,input.candidateId,input.actor,JSON.stringify(input));
    });
  }
  decisions(runId:string):BReviewDecision[]{
    return (this.store.db.prepare('SELECT payload FROM b_decisions WHERE run_id=? ORDER BY rowid').all(runId) as {payload:string}[]).map(x=>JSON.parse(x.payload) as BReviewDecision);
  }
}
