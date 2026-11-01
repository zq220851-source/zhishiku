import type { Analysis, Difference, Extraction, Finding, Screening, Skill, TaskInput, Unit } from './types';
import { invalid, list, object, strings, text, unique } from './errors';

const statementTypes = ['REPORTED_QUESTION', 'SELF_REPORTED_RESPONSE', 'INTERPRETATION', 'MEDICAL_CLAIM', 'CONTEXT', 'UNKNOWN'];
const enumeration = <T extends string>(value: unknown, options: readonly T[]): T => {
  if (typeof value !== 'string' || !options.includes(value as T)) return invalid('模型输出包含无效枚举。');
  return value as T;
};
export function screen(raw: string): Screening {
  const checks: [string, string, RegExp][] = [
    ['IDENTIFIER', '可能含身份或联系方式', /(?<!\d)1[3-9]\d{9}(?!\d)|(?<!\d)\d{17}[\dXx](?!\d)|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/],
    ['PATIENT', '可能含患者身份信息', /(?:患者|病人|病历|住院号).{0,15}(?:姓名|身份证|电话|张某|李某|王某|\d{4})/],
    ['SPECIAL_REPORT', '疑似安全性或质量报告线索', /不良反应|不良事件|质量投诉|药物警戒|用药后.{0,20}(?:死亡|住院|皮疹|过敏|不适)/],
    ['AUTHORIZATION', '可能涉及未授权资料', /未经授权|未获授权|偷偷录音|商业秘密|保密资料/],
  ];
  return { version: 'explicit-risk-v1', findings: checks.filter(([, , re]) => re.test(raw)).map(([code, label]) => ({ code, label })) };
}
export function validateExtraction(raw: string, value: unknown, codebook: TaskInput['codebook']): Extraction {
  const data = object(value), chars = Array.from(raw);
  const units: Unit[] = list(data.units, 200).map(v => {
    const u = object(v);
    if (!Number.isSafeInteger(u.startCp) || !Number.isSafeInteger(u.endCp) || Number(u.startCp) < 0 || Number(u.endCp) <= Number(u.startCp) || typeof u.excerpt !== 'string' || !u.excerpt.length) invalid('模型引用不是有效原文。');
    let startCp = Number(u.startCp), endCp = Number(u.endCp);
    let sourceAnchor: NonNullable<Unit['sourceAnchor']> = 'EXACT_MODEL_SPAN';
    let modelSpan: Unit['modelSpan'];
    if (endCp > chars.length || chars.slice(startCp, endCp).join('') !== u.excerpt) {
      // Never change the quoted text. Only a unique literal occurrence proves a replacement location.
      const position = raw.indexOf(u.excerpt);
      if (position < 0 || raw.indexOf(u.excerpt, position + 1) >= 0) invalid('模型引用不存在或原文位置有歧义。');
      modelSpan = { startCp, endCp };
      startCp = Array.from(raw.slice(0, position)).length; endCp = startCp + Array.from(u.excerpt).length;
      sourceAnchor = 'UNIQUE_EXACT_QUOTE';
    }
    const types = strings(u.types, 6).map(t => enumeration(t, statementTypes)) as Unit['types'];
    const skillIds = strings(u.skillIds), mapping = enumeration(u.mapping, ['CANDIDATE', 'UNMAPPED', 'UNKNOWN'] as const);
    const selfAssessment = strings(u.selfAssessment, 3).map(v => enumeration(v, ['GOOD', 'DIFFICULTY', 'UNKNOWN'] as const));
    const attribution = enumeration(u.attribution, ['OTHER_REPORTED', 'SELF', 'UNSPECIFIED'] as const);
    // Cause tags are *self-reported hypotheses*, never an objective ability score.
    // Missing fields in older extraction fixtures remain UNRESOLVED.
    const difficultyIndicators = u.difficultyIndicators === undefined ? undefined : list(u.difficultyIndicators, 6).map(value => {
      const item = object(value);
      const kind = enumeration(item.kind, ['KNOWLEDGE_UNCERTAINTY', 'BOUNDARY_OVERSTATEMENT', 'FOLLOW_UP_BLOCK'] as const);
      const quote = text(item.quote, 500), capabilityIds = strings(item.capabilityIds, 20);
      if (!String(u.excerpt).includes(quote) || !selfAssessment.includes('DIFFICULTY') ||
        !types.includes('SELF_REPORTED_RESPONSE') || attribution !== 'SELF' || u.certainty === 'INTERPRETED' ||
        (!skillIds.length && capabilityIds.length > 0) || capabilityIds.some(id => !skillIds.some(skillId =>
          codebook.skills.find(s => s.id === skillId)?.capabilityIds.includes(id)))) invalid('困难成因必须有本人困难原话及相应考点能力依据。');
      if (new Set(capabilityIds).size !== capabilityIds.length) invalid('困难成因能力标识不能重复。');
      return { kind, quote, capabilityIds };
    });
    if (difficultyIndicators && new Set(difficultyIndicators.map(i => `${i.kind}:${i.quote}`)).size !== difficultyIndicators.length) invalid('相同困难证据不能重复标注。');
    if (!types.length || skillIds.some(id => !codebook.skills.some(s => s.id === id))) invalid('模型引用了不存在的考点或类型。');
    if ((mapping === 'CANDIDATE') !== (skillIds.length > 0)) invalid('模型的映射状态与考点不一致。');
    if (selfAssessment.some(a => a !== 'UNKNOWN') && (!types.includes('SELF_REPORTED_RESPONSE') || attribution !== 'SELF')) invalid('自述表现必须引用本人回应。');
    return { id: text(u.id, 64), startCp, endCp, sourceAnchor, ...(modelSpan ? { modelSpan } : {}), excerpt: String(u.excerpt), codes: strings(u.codes, 20), types, attribution,
      certainty: enumeration(u.certainty, ['REPORTED', 'INTERPRETED', 'UNKNOWN'] as const), skillIds, mapping, selfAssessment, ...(difficultyIndicators === undefined ? {} : { difficultyIndicators }) };
  });
  unique(units);
  const relations = list(data.relations, 300).map(v => {
    const r = object(v), from = text(r.from, 64), to = text(r.to, 64);
    const source = units.find(u => u.id === from), target = units.find(u => u.id === to);
    const type = enumeration(r.type, ['RESPONSE_TO', 'REPORTED_SEQUENCE', 'SELF_CORRECTION'] as const);
    const supportUnitIds = strings(r.supportUnitIds);
    if (!source || !target || from === to || !supportUnitIds.length || supportUnitIds.some(id => !units.some(u => u.id === id))) invalid('模型关系缺有效原文引用。');
    if (type === 'RESPONSE_TO' && (!source.types.includes('REPORTED_QUESTION') || !target.types.includes('SELF_REPORTED_RESPONSE') || target.attribution !== 'SELF')) invalid('问题回应关系的对象类型不匹配。');
    if (type === 'SELF_CORRECTION' && (![source, target].every(u => u.types.includes('SELF_REPORTED_RESPONSE') && u.attribution === 'SELF') || source.startCp >= target.startCp)) invalid('改口关系必须引用前后两段本人自述。');
    if (!supportUnitIds.includes(from) || !supportUnitIds.includes(to)) invalid('关系必须引用双方原文。');
    return { from, to, type, supportUnitIds };
  });
  if (new Set(relations.map(r => `${r.from}:${r.to}:${r.type}`)).size !== relations.length) invalid('关系不能重复。');
  // Reject multiple incompatible correction parents: the consumer cannot assert one correction chain.
  const correctionTargets = relations.filter(r => r.type === 'SELF_CORRECTION').map(r => r.to);
  if (new Set(correctionTargets).size !== correctionTargets.length) invalid('改口对象不能有多个不同来源。');
  return { units, relations };
}
export function coverage(skill: Skill | undefined, input: TaskInput) {
  if (!skill || !skill.capabilityIds.length) return { coverage: 'UNKNOWN' as const, comparedSkillIds: [], missingCapabilityIds: [], reason: '问题无法确定，暂不判断覆盖。' };
  const candidates = input.plan.map(p => input.codebook.skills.find(s => s.id === p.skillId)!).filter(s => s.topic === skill.topic && s.capabilityIds.some(id => skill.capabilityIds.includes(id)));
  const covered = new Set(candidates.flatMap(s => s.capabilityIds));
  const missing = skill.capabilityIds.filter(id => !covered.has(id));
  const state = !missing.length ? 'FULL' : candidates.length ? 'PARTIAL' : 'NONE';
  return { coverage: state as 'FULL' | 'PARTIAL' | 'NONE', comparedSkillIds: candidates.map(s => s.id), missingCapabilityIds: missing,
    reason: state === 'FULL' ? '准备计划覆盖全部所需能力单元。' : state === 'PARTIAL' ? '只覆盖部分能力，缺项单独列出。' : '计划未覆盖所需能力；同主题不构成部分覆盖。' };
}
/**
 * Only explicit model-supported RESPONSE_TO / SELF_CORRECTION edges are followed.
 * This never tries adjacency, inferred skill overlap or keyword matching to invent a link.
 */
function responsesForQuestion(extraction: Extraction, questionId: string) {
  const direct = extraction.relations.filter(r => r.type === 'RESPONSE_TO' && r.from === questionId).map(r => r.to);
  const all = new Set(direct);
  const corrections = new Set<string>();
  // A correction is inherited only from a response that belongs uniquely to this question.
  // Otherwise it remains an unlinked finding for clarification, rather than a false pairing.
  let changed = true;
  while (changed) {
    changed = false;
    for (const edge of extraction.relations.filter(r => r.type === 'SELF_CORRECTION')) {
      const linkedQuestions = extraction.relations.filter(r => r.type === 'RESPONSE_TO' && r.to === edge.from).map(r => r.from);
      if (all.has(edge.from) && !all.has(edge.to) && (!linkedQuestions.length || (linkedQuestions.length === 1 && linkedQuestions[0] === questionId))) {
        all.add(edge.to); corrections.add(edge.to); changed = true;
      }
    }
  }
  return { responseIds: [...all].sort((a,b) => extraction.units.find(u => u.id === a)!.startCp - extraction.units.find(u => u.id === b)!.startCp), correctionIds: [...corrections] };
}

const reportSignal = (units: Unit[]): Difference['personalSignal'] => units.some(u => u.selfAssessment.includes('DIFFICULTY')) ? 'PENDING_VERIFY' :
  units.some(u => u.selfAssessment.includes('GOOD')) ? 'SELF_REPORTED_SUCCESS' : 'UNKNOWN';

export function derive(extraction: Extraction, input: TaskInput, model: string, promptVersion: string): Analysis {
  const differences: Difference[] = [];
  const findings: Finding[] = [];
  const linkedResponseIds = new Set<string>();
  for (const unit of extraction.units.filter(u => u.types.includes('REPORTED_QUESTION') && !u.types.includes('INTERPRETATION') && u.certainty !== 'INTERPRETED')) {
    const linked = responsesForQuestion(extraction, unit.id);
    const evidenceResponses = linked.responseIds.map(id => extraction.units.find(u => u.id === id)!).filter(u => u.attribution === 'SELF' && u.certainty !== 'INTERPRETED');
    const ids: (string | null)[] = unit.skillIds.length ? unit.skillIds : [null];
    for (const skillId of ids) {
      const skill = input.codebook.skills.find(s => s.id === skillId);
      const comparison = coverage(skill, input);
      const responses = evidenceResponses.filter(u => unit.skillIds.length === 1 ? !u.skillIds.length || u.skillIds.includes(skillId!) : u.skillIds.length === 1 && u.skillIds[0] === skillId);
      const performance: Difference['performance'] = responses.flatMap(u => u.selfAssessment.filter(a => a !== 'UNKNOWN').map(a => ({ unitId: u.id, kind: a === 'GOOD' ? 'SELF_REPORTED_GOOD' as const : 'SELF_REPORTED_DIFFICULTY' as const, excerpt: u.excerpt })));
      // Keep the *whole* history in performance, but an explicitly superseded
      // statement cannot overrule the employee's later correction. No inferred
      // temporal or semantic links: only validated SELF_CORRECTION edges apply.
      const superseded = new Set(extraction.relations.filter(r => r.type === 'SELF_CORRECTION' &&
        responses.some(u => u.id === r.from) && responses.some(u => u.id === r.to)).map(r => r.from));
      const currentResponses = responses.filter(u => !superseded.has(u.id));
      const personalSignal = reportSignal(currentResponses) === 'PENDING_VERIFY' ? 'PENDING_VERIFY' :
        reportSignal(currentResponses) === 'SELF_REPORTED_SUCCESS' ? 'SELF_REPORTED_SUCCESS' : 'UNKNOWN';
      differences.push({ questionUnitId: unit.id, skillId, usability: skill ? 'USABLE' : 'AMBIGUOUS', ...comparison, performance,
        personalSignal, gapCandidate: comparison.coverage === 'PARTIAL' || comparison.coverage === 'NONE' });
      responses.forEach(u => linkedResponseIds.add(u.id));
      const relevant = [unit, ...responses];
      findings.push({ id: `question:${unit.id}:${skillId ?? 'unknown'}`, kind: 'QUESTION', questionUnitId: unit.id,
        responseUnitIds: responses.map(u => u.id), correctionUnitIds: linked.correctionIds.filter(id => responses.some(u => u.id === id)),
        linkage: responses.length ? 'CONFIRMED' : 'UNKNOWN', linkageEvidenceUnitIds: responses.length ? relevant.map(u => u.id) : [],
        skillIds: skillId ? [skillId] : [], evidence: relevant.map(u => ({ id: u.id, startCp: u.startCp, endCp: u.endCp, excerpt: u.excerpt, sourceAnchor: u.sourceAnchor })),
        assessment: { coverage: comparison.coverage, personalSignal },
        // D1 has no verified historical catalog. A coverage gap is NOT permission to alter shared content.
        eligibleForSharedChange: false,
        limitations: ['依据员工复盘形成问题候选，不证明现场事实。', ...(responses.length ? [] : ['没有可靠的问答对应关系，不推断员工表现。'])] });
    }
  }
  // Even a correctly extracted difficulty without RESPONSE_TO must survive as an orphan finding.
  // Do not attach it to the nearest question or allow it to trigger shared-content changes.
  for (const unit of extraction.units.filter(u => u.types.includes('SELF_REPORTED_RESPONSE') && u.attribution === 'SELF' &&
    u.certainty !== 'INTERPRETED' && u.selfAssessment.some(a => a === 'DIFFICULTY' || a === 'GOOD') && !linkedResponseIds.has(u.id))) {
    findings.push({ id: `unlinked:${unit.id}`, kind: 'UNLINKED_SELF_REPORT', responseUnitIds: [unit.id], correctionUnitIds: [],
      linkage: 'UNKNOWN', linkageEvidenceUnitIds: [unit.id], skillIds: [...unit.skillIds],
      evidence: [{ id: unit.id, startCp: unit.startCp, endCp: unit.endCp, excerpt: unit.excerpt, sourceAnchor: unit.sourceAnchor }],
      assessment: { coverage: 'UNKNOWN', personalSignal: reportSignal([unit]) === 'PENDING_VERIFY' ? 'PENDING_CONFIRMATION' : reportSignal([unit]) },
      eligibleForSharedChange: false,
      limitations: ['该本人自述有原文依据，但未确认与哪个现场问题对应；只能等待澄清或自检，不能直接改变共享场景或选题。'] });
  }
  return { ...extraction, codebookVersion: input.codebook.version, model, promptVersion, differences, findings,
    limitations: ['依据员工复盘形成候选，不证明现场事实或医学结论。', '没有提及的问题保持未知，不据此计算真实医生提问准确率。', '自述表现与模拟评价独立，不生成正式能力扣分。', '未命中显式风险规则不代表完整安全审查通过。', '共享审核、发布和三条进化路径尚待接入。'] };
}
