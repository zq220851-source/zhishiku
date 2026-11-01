/** A-side typed evidence contract. It validates sources & links; it DOES NOT infer semantics. */
export type EventKind = 'EXPERT_QUESTION' | 'REP_RESPONSE' | 'REP_REFLECTION' | 'NARRATION_CORRECTION';
export type EventFactuality = 'REPORTED' | 'DENIED' | 'HYPOTHETICAL' | 'UNCERTAIN';
export type EventRelation = 'ANSWER_TO' | 'REFLECTS_ON' | 'REVISES_DESCRIPTION';
export interface EvidenceEvent {
  id: string;
  kind: EventKind;
  factuality: EventFactuality;
  quote: string;
  startCp: number;
  endCp: number;
  capabilityId: string | null;
}
export interface EvidenceLink {
  from: string;
  to: string;
  type: EventRelation;
  evidenceEventIds: string[];
}
export interface ReviewEvidenceSnapshot {
  usage: 'TEST_ONLY';
  rawVersion: number;
  rawText: string;
  events: EvidenceEvent[];
  links: EvidenceLink[];
}
const kinds:EventKind[]=['EXPERT_QUESTION','REP_RESPONSE','REP_REFLECTION','NARRATION_CORRECTION'];
const factualities:EventFactuality[]=['REPORTED','DENIED','HYPOTHETICAL','UNCERTAIN'];
const relations:EventRelation[]=['ANSWER_TO','REFLECTS_ON','REVISES_DESCRIPTION'];
export function validateReviewEvidence(s:ReviewEvidenceSnapshot):void {
  if(s.usage!=='TEST_ONLY'||!Number.isSafeInteger(s.rawVersion)||s.rawVersion<1||!s.rawText||s.rawText.length>20000)throw new Error('目前仅支持有版本的虚构测试原文');
  const cp=Array.from(s.rawText), events=new Map<string,EvidenceEvent>();
  for(const e of s.events){
    if(!/^[\w:-]{1,80}$/.test(e.id)||events.has(e.id)||!kinds.includes(e.kind)||!factualities.includes(e.factuality))throw new Error('事件ID、类别或状态无效');
    if(!Number.isSafeInteger(e.startCp)||!Number.isSafeInteger(e.endCp)||e.startCp<0||e.endCp<=e.startCp||e.endCp>cp.length||cp.slice(e.startCp,e.endCp).join('')!==e.quote)throw new Error('事件必须有精确原文位置');
    events.set(e.id,e);
  }
  const seenLinks=new Set<string>();
  for(const link of s.links){
    const f=events.get(link.from),t=events.get(link.to);
    if(!f||!t||f.id===t.id||!relations.includes(link.type)||!link.evidenceEventIds.includes(f.id)||!link.evidenceEventIds.includes(t.id)||link.evidenceEventIds.some(id=>!events.has(id)))throw new Error('关系缺少有来源的两端事件');
    const code=`${link.from}|${link.to}|${link.type}`;
    if(seenLinks.has(code))throw new Error('重复关系');seenLinks.add(code);
    if(link.type==='ANSWER_TO'&&(f.kind!=='REP_RESPONSE'||t.kind!=='EXPERT_QUESTION'))throw new Error('回答关系要求回应指向提问');
    if(link.type==='REFLECTS_ON'&&(f.kind!=='REP_REFLECTION'||t.kind!=='REP_RESPONSE'))throw new Error('反思不能冒充对历史叙述的更正');
    if(link.type==='REVISES_DESCRIPTION'&&(f.kind!=='NARRATION_CORRECTION'||f.startCp<=t.startCp))throw new Error('历史叙述更正必须发生在被更正的叙述之后');
  }
}
/** Only verified reported claims can be projected as expert observations. All others stay evidence candidates. */
export function reportedExpertQuestions(s:ReviewEvidenceSnapshot): EvidenceEvent[] {
  validateReviewEvidence(s);
  return s.events.filter(e=>e.kind==='EXPERT_QUESTION'&&e.factuality==='REPORTED');
}
