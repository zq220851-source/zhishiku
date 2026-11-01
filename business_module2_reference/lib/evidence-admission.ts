/**
 * V0.7: separate a language model's span-grounded interpretation from permission
 * to update the five long-lived assets. A valid substring is NOT proof of semantics.
 * This module only operates on fictional TEST_ONLY material pending a formal policy.
 */
import { validateReviewEvidence, type ReviewEvidenceSnapshot, type EvidenceEvent } from './semantic-evidence';
import type { VisitEvidence, EvidenceObservation } from './five-assets';

export type AdmissionVerdict = 'APPROVE_TEST_ONLY' | 'REJECT' | 'NEEDS_CLARIFICATION';
export interface EventReview {
  eventId: string;
  verdict: AdmissionVerdict;
  reviewerId: string;
  reason: string;
  checkedRawVersion: number;
  /** Specifically asserts question identity, negation scope and later corrections were checked. */
  verifiedFactuality: 'REPORTED' | 'DENIED' | 'HYPOTHETICAL' | 'UNCERTAIN';
}
export interface AdmissionResult {
  accepted: EvidenceEvent[];
  withheld: { eventId: string; reason: string }[];
}

export function admitReviewedEvents(snapshot: ReviewEvidenceSnapshot, reviews: EventReview[]): AdmissionResult {
  validateReviewEvidence(snapshot);
  const byEvent = new Map<string, EventReview>();
  for (const r of reviews) {
    if (!snapshot.events.some(e => e.id === r.eventId)) throw new Error(`审查对象不存在: ${r.eventId}`);
    if (byEvent.has(r.eventId) || !/^[a-zA-Z0-9_.:-]{2,80}$/.test(r.reviewerId) || r.reason.trim().length < 8 || r.checkedRawVersion !== snapshot.rawVersion)
      throw new Error('审查重复、审查人无效、理由不足或原文版本不一致');
    if (!['APPROVE_TEST_ONLY','REJECT','NEEDS_CLARIFICATION'].includes(r.verdict) || !['REPORTED','DENIED','HYPOTHETICAL','UNCERTAIN'].includes(r.verifiedFactuality))
      throw new Error('审查状态非法');
    byEvent.set(r.eventId,r);
  }
  const accepted: EvidenceEvent[] = [], withheld: AdmissionResult['withheld'] = [];
  for(const e of snapshot.events) {
    const r = byEvent.get(e.id);
    if(!r) { withheld.push({eventId:e.id,reason:'缺少独立语义审核'}); continue; }
    if(r.verdict !== 'APPROVE_TEST_ONLY') {withheld.push({eventId:e.id,reason:r.reason});continue;}
    if(r.verifiedFactuality !== e.factuality) {withheld.push({eventId:e.id,reason:'审核确认的事实状态与模型输出冲突'});continue;}
    if(e.kind==='EXPERT_QUESTION' && e.factuality!=='REPORTED') {withheld.push({eventId:e.id,reason:'未确认的现场专家提问不得投射到五资产'});continue;}
    accepted.push(e);
  }
  return {accepted,withheld};
}

/** Only positive, independently reviewed expert questions are allowed to update
 * forecast/expert/cohort records; missing or ambiguous items remain withheld.
 * Everything is TEST_ONLY; never call this as a production approval pathway.
 */
export function reviewedQuestionObservations(snapshot: ReviewEvidenceSnapshot, reviews: EventReview[]): {
  observations: EvidenceObservation[];
  withheld: AdmissionResult['withheld'];
} {
  const result = admitReviewedEvents(snapshot, reviews);
  const observations: EvidenceObservation[] = result.accepted
    .filter(e=>e.kind==='EXPERT_QUESTION' && e.factuality==='REPORTED')
    .map(e=>({id:e.id,kind:'EXPERT_QUESTION',quote:e.quote,startCp:e.startCp,endCp:e.endCp,capabilityId:e.capabilityId,mode:'REPORTED'}));
  return {observations,withheld:result.withheld};
}

/** Pure optional adapter. The caller supplies the frozen task and knowledge checks;
 * NOT a new model-generated task. Review provenance must be recorded separately.
 */
export function withReviewedQuestions(base: VisitEvidence, snapshot: ReviewEvidenceSnapshot, reviews: EventReview[]): VisitEvidence {
  if(base.usage!=='TEST_ONLY'||snapshot.usage!=='TEST_ONLY'||base.rawText!==snapshot.rawText||base.rawVersion!==snapshot.rawVersion)
    throw new Error('源原文或版本不一致，拒绝注入长期资产');
  if (base.observations.length || base.practices.length) throw new Error('专用专家提问接口只接受未投射的测试任务；其他能力证据必须通过独立流程处理');
  const {observations} = reviewedQuestionObservations(snapshot,reviews);
  const allowed = new Set(observations.map(o=>o.id));
  return { ...base, observations, knowledgeChecks:base.knowledgeChecks.filter(k=>allowed.has(k.observationId)), practices:[] };
}
