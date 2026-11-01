/**
 * F1 experimental five-asset evidence ledger.
 * All content is TEST_ONLY; structured observations must come from a separately validated extractor.
 * Do NOT interpret these outputs as proven medical facts, expert personality or prediction accuracy.
 */
import { createHash } from 'node:crypto';
import type { Store } from './store';

export type AssetKind = 'PERSONAL_SKILL' | 'FORECAST' | 'KNOWLEDGE_COVERAGE' | 'EXPERT_OBSERVATION' | 'COHORT_EVENT';
export type ReportMode = 'REPORTED' | 'DENIED' | 'HYPOTHETICAL' | 'UNCERTAIN';
export type ObservationKind = 'EXPERT_QUESTION' | 'REP_DIFFICULTY' | 'REP_RESPONSE' | 'REP_REFLECTION';
export interface EvidenceObservation {
  id: string;
  kind: ObservationKind;
  quote: string;
  startCp: number;
  endCp: number;
  capabilityId: string | null;
  mode: ReportMode;
}
export interface KnowledgeCheck {
  observationId: string;
  capabilityId: string;
  status: 'SUPPORTED' | 'PARTIAL' | 'NOT_FOUND' | 'CONTRADICTED' | 'UNDETERMINED';
  queriedEvidenceIds: string[];
  queryAttempts: string[];
  knowledgeVersion: string;
}
export interface PracticeEvidence {
  capabilityId: string;
  trainingAttemptId: string;
  result: 'GAP' | 'SATISFIED' | 'UNKNOWN';
  criterion: string;
  /** Optional module 1 provenance; this is formative evidence, not a medical-grade score. */
  origin?: {system:'MODULE1';runId:string;attempt:number;criterionId:string;lessonId:string;sourceStatus:'fictional_test_material'|'pending_medical_review';quote:string;turnIndex:number;sourceIds:string[];observedAt:string};
}
export interface VisitEvidence {
  usage: 'TEST_ONLY' | 'INTERNAL_READING';
  sourceOrigin?: {system:'MODULE1';lessonId:string;revision:string;sourcePath:string};
  visitId: string;
  taskId: string;
  repId: string;
  expertId: string | null;
  researchId: string;
  snapshotHash: string;
  rawVersion: number;
  /** For causal replay of edited historical notes; a revision is not knowable before review time. */
  reviewedAt?: string;
  rawText: string;
  occurredAt: string;
  forecast: {
    selectedCapabilityIds: string[];
    candidateCapabilityIds: string[];
    budget: number;
    candidatePoolKnown?: boolean;
  };
  observations: EvidenceObservation[];
  knowledgeChecks: KnowledgeCheck[];
  practices: PracticeEvidence[];
}
export interface AssetEntry {
  id: string;
  visitId: string;
  rawVersion: number;
  kind: AssetKind;
  targetId: string;
  evidenceObservationIds: string[];
  status: 'OBSERVATION' | 'CANDIDATE' | 'TRAINING_EVIDENCE';
  label: string;
  note: string;
}
export interface VisitProjection { visitId: string; rawVersion: number; entries: AssetEntry[]; }

const digest = (v: unknown) => createHash('sha256').update(JSON.stringify(v)).digest('hex');
const unique = (xs: string[], name: string) => {
  if (new Set(xs).size !== xs.length || xs.some(x => !x || x.length > 160)) throw new Error(`${name} 无效或重复`);
};
const identifier = (x: unknown, name: string) => {
  if (typeof x !== 'string' || !/^[A-Za-z0-9_.:-]{1,160}$/.test(x)) throw new Error(`${name} 不能为空或含无效字符`);
};
export function validateVisitEvidence(input: VisitEvidence): void {
  if (input.usage !== 'TEST_ONLY' && !(input.usage === 'INTERNAL_READING' && input.sourceOrigin?.system === 'MODULE1' && input.sourceOrigin.lessonId && input.sourceOrigin.revision && input.sourceOrigin.sourcePath)) throw new Error('缺少模块一原知识库来源，或用途无效');
  for (const key of ['visitId','taskId','repId','researchId','snapshotHash'] as const) identifier(input[key], key);
  if (input.expertId !== null) identifier(input.expertId, 'expertId');
  if (!Number.isSafeInteger(input.rawVersion) || input.rawVersion < 1 || !Number.isFinite(Date.parse(input.occurredAt)) || (input.reviewedAt !== undefined && !Number.isFinite(Date.parse(input.reviewedAt)))) throw new Error('原文版本或时间无效');
  if (!input.rawText || input.rawText.length > 20000) throw new Error('原文为空或过长');
  unique(input.forecast.selectedCapabilityIds, 'selected'); unique(input.forecast.candidateCapabilityIds, 'candidate');
  if (!Number.isSafeInteger(input.forecast.budget) || input.forecast.budget < 0 || input.forecast.selectedCapabilityIds.length > input.forecast.budget ||
    input.forecast.selectedCapabilityIds.some(c => !input.forecast.candidateCapabilityIds.includes(c))) throw new Error('冻结预测池和选题不一致');
  const chars = Array.from(input.rawText), seen = new Set<string>();
  for (const o of input.observations) {
    identifier(o.id, 'observationId'); if (seen.has(o.id)) throw new Error('重复观察编号'); seen.add(o.id);
    if (!['EXPERT_QUESTION','REP_DIFFICULTY','REP_RESPONSE','REP_REFLECTION'].includes(o.kind) || !['REPORTED','DENIED','HYPOTHETICAL','UNCERTAIN'].includes(o.mode)) throw new Error('观察类型或语义模式无效');
    if (!Number.isSafeInteger(o.startCp) || !Number.isSafeInteger(o.endCp) || o.startCp < 0 || o.endCp <= o.startCp || chars.slice(o.startCp,o.endCp).join('') !== o.quote) throw new Error(`观察 ${o.id} 未指向准确原文`);
    if (o.capabilityId !== null) identifier(o.capabilityId, 'capabilityId');
  }
  for (const k of input.knowledgeChecks) {
    if (!seen.has(k.observationId) || !input.observations.some(o => o.id === k.observationId && o.kind === 'EXPERT_QUESTION' && o.capabilityId === k.capabilityId && o.mode === 'REPORTED')) throw new Error('知识检查没有有效的现场问题依据');
    if (!['SUPPORTED','PARTIAL','NOT_FOUND','CONTRADICTED','UNDETERMINED'].includes(k.status)) throw new Error('知识检查状态非法');
    identifier(k.knowledgeVersion,'knowledgeVersion'); unique(k.queriedEvidenceIds,'queriedEvidenceIds');
    if (!Array.isArray(k.queryAttempts) || k.queryAttempts.some(q => !q || q.length > 300)) throw new Error('检索尝试格式无效');
  }
  const attemptIds = new Set<string>();
  for (const p of input.practices) {
    identifier(p.trainingAttemptId,'trainingAttemptId'); identifier(p.capabilityId,'capabilityId');
    if (attemptIds.has(p.trainingAttemptId) || !['GAP','SATISFIED','UNKNOWN'].includes(p.result) || !p.criterion || p.criterion.length > 300) throw new Error('训练证据重复或不完整');
    if(p.origin){
      const a=p.origin;
      if(a.system!=='MODULE1'||!['fictional_test_material','pending_medical_review'].includes(a.sourceStatus)||!a.runId||!a.criterionId||!a.lessonId||
        !Number.isInteger(a.attempt)||a.attempt<1||!Number.isInteger(a.turnIndex)||a.turnIndex<0||
        !a.quote?.trim()||!Number.isFinite(Date.parse(a.observedAt))||!Array.isArray(a.sourceIds)||
        a.sourceIds.some(x=>!x))throw new Error('模块1练习来源不可追溯');
    }
    attemptIds.add(p.trainingAttemptId);
  }
}
export function projectVisit(v: VisitEvidence): VisitProjection {
  validateVisitEvidence(v);
  const entries: AssetEntry[] = [];
  const add = (kind: AssetKind, targetId: string, sourceIds: string[], status: AssetEntry['status'], label: string, note: string) => {
    entries.push({ id: digest([v.visitId,v.rawVersion,kind,targetId,sourceIds,label]).slice(0,20), visitId:v.visitId, rawVersion:v.rawVersion, kind, targetId, evidenceObservationIds:sourceIds, status, label, note });
  };
  for (const o of v.observations) {
    if (o.kind === 'REP_DIFFICULTY' && o.mode === 'REPORTED') add('PERSONAL_SKILL', `${v.repId}:${o.capabilityId ?? 'UNMAPPED'}`, [o.id], 'OBSERVATION', 'SELF_REPORTED_DIFFICULTY', '只是员工自述，需练习验证，不代表真实能力评分');
    if (o.kind !== 'EXPERT_QUESTION' || o.mode !== 'REPORTED' || !o.capabilityId) continue;
    const selected = v.forecast.selectedCapabilityIds.includes(o.capabilityId);
    const inPool = v.forecast.candidateCapabilityIds.includes(o.capabilityId);
    add('FORECAST', `${v.researchId}:${o.capabilityId}`, [o.id], 'OBSERVATION', selected ? 'REPORTED_COVERED' : 'REPORTED_UNCOVERED', selected ? '只表示报告的问题与冻结选题能力有交集；不代表真实命中率' : inPool ? '候选存在但未选，需再核对预算/优先级' : '候选池未包含，需再核对召回或适用性');
    const k = v.knowledgeChecks.find(k => k.observationId === o.id && k.capabilityId === o.capabilityId);
    if (k) add('KNOWLEDGE_COVERAGE', `${v.researchId}:${o.capabilityId}:${k.knowledgeVersion}`, [o.id], 'CANDIDATE', k.status === 'NOT_FOUND' ? 'RETRIEVAL_NOT_FOUND' : k.status, k.status === 'NOT_FOUND' ? '仅为未检索到的候选，不得认定医学知识不存在' : '只记录检索层测试结果，不替代医学审核');
    if (v.expertId) add('EXPERT_OBSERVATION', `${v.expertId}:${o.capabilityId}`, [o.id], 'OBSERVATION', 'REPORTED_EXPERT_QUESTION', '单次员工转述，不形成专家稳定偏好');
    add('COHORT_EVENT', `${v.researchId}:${o.capabilityId}`, [o.id], 'OBSERVATION', 'REPORTED_TOPIC_OCCURRENCE', '保留拜访、员工和专家的独立去重维度');
  }
  for (const p of v.practices) add('PERSONAL_SKILL', `${v.repId}:${p.capabilityId}`, [], 'TRAINING_EVIDENCE', `PRACTICE_${p.result}`, `练习 ${p.trainingAttemptId} · ${p.criterion}；不等于永久掌握`);
  return { visitId:v.visitId, rawVersion:v.rawVersion, entries };
}
/** Immutable revisions. Same visit/version with changed content is an explicit conflict. */
export class FiveAssetLedger {
  constructor(private store: Store) {
    store.db.exec(`CREATE TABLE IF NOT EXISTS five_asset_submissions (
      visit_id TEXT NOT NULL, raw_version INTEGER NOT NULL, payload_hash TEXT NOT NULL, payload TEXT NOT NULL,
      PRIMARY KEY(visit_id,raw_version));
      CREATE TRIGGER IF NOT EXISTS five_asset_no_update BEFORE UPDATE ON five_asset_submissions BEGIN SELECT RAISE(ABORT,'immutable'); END;
      CREATE TRIGGER IF NOT EXISTS five_asset_no_delete BEFORE DELETE ON five_asset_submissions BEGIN SELECT RAISE(ABORT,'immutable'); END;`);
  }
  record(input: VisitEvidence): VisitProjection {
    const projection = projectVisit(input); const hash = digest(input);
    return this.store.transaction(() => {
      const existing = this.store.db.prepare('SELECT payload_hash FROM five_asset_submissions WHERE visit_id=? AND raw_version=?').get(input.visitId,input.rawVersion) as {payload_hash:string}|undefined;
      if (existing) { if(existing.payload_hash!==hash) throw new Error('同一拜访原文版本已冻结，不能覆盖'); return projection; }
      const rows = this.store.db.prepare('SELECT payload FROM five_asset_submissions WHERE visit_id=? ORDER BY raw_version DESC LIMIT 1').all(input.visitId) as {payload:string}[];
      if (rows.length) {
        const previous = JSON.parse(rows[0].payload) as VisitEvidence;
        if (input.rawVersion <= previous.rawVersion || input.repId !== previous.repId || input.taskId !== previous.taskId || input.snapshotHash !== previous.snapshotHash || input.researchId !== previous.researchId || input.expertId !== previous.expertId) throw new Error('原文修订必须保留冻结任务身份和单调版本');
      }
      this.store.db.prepare('INSERT INTO five_asset_submissions VALUES(?,?,?,?)').run(input.visitId,input.rawVersion,hash,JSON.stringify(input));
      return projection;
    });
  }
  history(visitId: string): VisitEvidence[] {
    return (this.store.db.prepare('SELECT payload FROM five_asset_submissions WHERE visit_id=? ORDER BY raw_version').all(visitId) as {payload:string}[]).map(r=>JSON.parse(r.payload) as VisitEvidence);
  }
  current(): VisitEvidence[] {
    const rows = this.store.db.prepare(`SELECT x.payload FROM five_asset_submissions x WHERE x.raw_version=(SELECT MAX(raw_version) FROM five_asset_submissions y WHERE y.visit_id=x.visit_id) ORDER BY x.visit_id`).all() as {payload:string}[];
    return rows.map(r=>JSON.parse(r.payload) as VisitEvidence);
  }
  currentEntries(): AssetEntry[] { return this.current().flatMap(v=>projectVisit(v).entries); }
  cohortSummary() {
    const visits=this.current(), totalVisits=visits.length, totalReps=new Set(visits.map(v=>v.repId)).size;
    const keyToVisits=new Map<string,Set<string>>(), keyToReps=new Map<string,Set<string>>(), keyToExperts=new Map<string,Set<string>>();
    for(const v of visits) for(const cap of new Set(v.observations.filter(o=>o.kind==='EXPERT_QUESTION'&&o.mode==='REPORTED'&&o.capabilityId).map(o=>o.capabilityId!))) {
      const key=`${v.researchId}:${cap}`;
      if(!keyToVisits.has(key)){keyToVisits.set(key,new Set());keyToReps.set(key,new Set());keyToExperts.set(key,new Set());}
      keyToVisits.get(key)!.add(v.visitId); keyToReps.get(key)!.add(v.repId); if(v.expertId)keyToExperts.get(key)!.add(v.expertId);
    }
    return [...keyToVisits].map(([key,ids])=>({key, reportedVisits:ids.size, reportedReps:keyToReps.get(key)!.size, reportedExperts:keyToExperts.get(key)!.size, denominatorVisits:totalVisits, denominatorReps:totalReps, type:'DESCRIPTIVE_PATTERN_CANDIDATE' as const})).sort((a,b)=>a.key.localeCompare(b.key));
  }
}
