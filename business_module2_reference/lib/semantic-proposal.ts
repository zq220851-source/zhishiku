/**
 * V0.7 input boundary for a semantic model. Explicit event-level assertion, agent,
 * event time, and local negation scope avoid global regex decisions.
 * Structural validation is NOT proof the model understood the sentence.
 */
import { validateReviewEvidence, type ReviewEvidenceSnapshot, type EvidenceEvent, type EvidenceLink } from './semantic-evidence';

export type ProposedAction='QUESTION'|'RESPONSE'|'REFLECTION'|'NARRATION_CORRECTION'|'OTHER';
export type ProposedAgent='EXPERT'|'REP'|'OTHER'|'UNKNOWN';
export type ProposedTime='DURING_VISIT'|'AFTER_VISIT'|'FUTURE'|'UNKNOWN';
export type ProposedScope='TARGET_EVENT'|'DIFFERENT_EVENT'|'NO_NEGATION'|'UNRESOLVED';
export interface ProposedEvent {
  id:string;
  action:ProposedAction;
  agent:ProposedAgent;
  when:ProposedTime;
  factuality:'REPORTED'|'DENIED'|'HYPOTHETICAL'|'UNCERTAIN';
  /** exact character span including the relation-bearing clause, not a paraphrase */
  quote:string;
  startCp:number;
  endCp:number;
  negationScope:ProposedScope;
  capabilityId:string|null;
}
export interface SemanticProposal {
  usage:'TEST_ONLY';
  rawVersion:number;
  rawText:string;
  events:ProposedEvent[];
  links:EvidenceLink[];
}
const allowed={action:['QUESTION','RESPONSE','REFLECTION','NARRATION_CORRECTION','OTHER'],agent:['EXPERT','REP','OTHER','UNKNOWN'],when:['DURING_VISIT','AFTER_VISIT','FUTURE','UNKNOWN'],factuality:['REPORTED','DENIED','HYPOTHETICAL','UNCERTAIN'],negationScope:['TARGET_EVENT','DIFFERENT_EVENT','NO_NEGATION','UNRESOLVED']} as const;
export function validateSemanticProposal(p:SemanticProposal):ReviewEvidenceSnapshot {
  if(p.usage!=='TEST_ONLY'||!p.rawText||p.rawText.length>20000||!Number.isSafeInteger(p.rawVersion)||p.rawVersion<1||!Array.isArray(p.events)||!Array.isArray(p.links)||p.events.length>150)throw new Error('语义提案基础结构无效');
  const cp=Array.from(p.rawText);
  const events:EvidenceEvent[]=[];
  for (const e of p.events) {
    for(const key of Object.keys(allowed) as (keyof typeof allowed)[]){
      if(typeof e[key]!=='string'||!(allowed[key] as readonly string[]).includes(e[key] as string))throw new Error(`语义字段 ${key} 无效`);
    }
    if(!Number.isSafeInteger(e.startCp)||!Number.isSafeInteger(e.endCp)||e.startCp<0||e.endCp<=e.startCp||e.endCp>cp.length||cp.slice(e.startCp,e.endCp).join('')!==e.quote)throw new Error('模型引文未匹配原文位置');
    // Guard against self-contradictory annotations. Does NOT detect a model's semantic misreading.
    if(e.negationScope==='TARGET_EVENT' && e.factuality==='REPORTED')throw new Error('作用于该事件的否定不能同时标为已发生');
    if(e.when==='FUTURE' && e.factuality==='REPORTED')throw new Error('纯未来事件不能确认已发生');
    const kind=e.action==='QUESTION'&&e.agent==='EXPERT'&&e.when==='DURING_VISIT' ? 'EXPERT_QUESTION'
      : e.action==='RESPONSE'&&e.agent==='REP' ? 'REP_RESPONSE'
      : e.action==='REFLECTION'&&e.agent==='REP' ? 'REP_REFLECTION'
      : e.action==='NARRATION_CORRECTION'&&e.agent==='REP' ? 'NARRATION_CORRECTION'
      : null;
    if(kind)events.push({id:e.id,kind,factuality:e.factuality,quote:e.quote,startCp:e.startCp,endCp:e.endCp,capabilityId:e.capabilityId});
  }
  const ids=new Set(events.map(e=>e.id));
  const links=p.links.filter(l=>ids.has(l.from)&&ids.has(l.to));
  // Reject links to discarded events rather than silently discarding evidence links.
  if(links.length!==p.links.length)throw new Error('关系连接到未认证的主体或事件');
  const snapshot:ReviewEvidenceSnapshot={usage:p.usage,rawVersion:p.rawVersion,rawText:p.rawText,events,links};
  validateReviewEvidence(snapshot);
  return snapshot;
}
/** A transparent contract for compatible LLMs; no API is called in this module. */
export const SEMANTIC_EXTRACTION_INSTRUCTIONS=`你是医药代表拜访复盘的事件提取器，仅分析用户提供的虚构原文。
逐事件处理，不要根据整段出现「没问」「如果」「记错」就否定全部事件。
为每条独立事件给出 action、agent、when、factuality、quote、startCp、endCp、negationScope、capabilityId。
quote 必须是原文连续子串，startCp/endCp 为 Unicode code point 区间（不含 endCp），不得改写。
必须区分医生现场提问、员工主动提问、专家仅陈述、假设中的提问、员工事后反思，以及对历史说法的更正。
若「医生没有问终点，却问外推」，这是两个事件，否定只作用于终点事件；若事后修正原先叙述，列单独更正事件。
不清楚说话人、否定对象或事件发生性时使用 UNKNOWN/UNCERTAIN 与 UNRESOLVED，不要猜。
同一个专业主题出现不意味着专家现场提问。JSON 输出必须符合调用方提供的 schema；不输出未经原文证实的医学主张。`;

/** When a model miscounts Unicode characters, repair only a UNIQUE exact quote.
 * Never guess among repeated occurrences. Corrections remain an explicit audit log.
 */
export function reanchorUniqueQuotes(p:SemanticProposal):{proposal:SemanticProposal;adjustments:{eventId:string;originalStartCp:number;resolvedStartCp:number}[]} {
  if(p.usage!=='TEST_ONLY'||typeof p.rawText!=='string'||!Array.isArray(p.events))throw new Error('输入结构不合法');
  const chars=Array.from(p.rawText);
  const adjustments:{eventId:string;originalStartCp:number;resolvedStartCp:number}[]=[];
  const events=p.events.map(e=>{
    if(typeof e.quote!=='string'||!e.quote)throw new Error('缺少原文引用');
    const match=Array.from(e.quote), exact=chars.slice(e.startCp,e.endCp).join('')===e.quote;
    if(exact)return e;
    const possible:number[]=[];
    for(let i=0;i<=chars.length-match.length;i++)if(chars.slice(i,i+match.length).join('')===e.quote)possible.push(i);
    if(possible.length!==1)throw new Error('引文缺失或出现多次，必须返回模型重新定位或人工确认');
    const startCp=possible[0];adjustments.push({eventId:e.id,originalStartCp:e.startCp,resolvedStartCp:startCp});
    return {...e,startCp,endCp:startCp+match.length};
  });
  return {proposal:{...p,events},adjustments};
}
