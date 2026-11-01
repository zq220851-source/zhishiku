import type { TaskInput } from './types';
import { invalid, list, object, strings, text, unique } from './errors';

export function validateTaskInput(value: unknown): TaskInput {
  const input = object(value), cb = object(input.codebook);
  const capabilities = list(cb.capabilities).map(v => { const a = object(v); return { id: text(a.id), description: text(a.description, 1000) }; });
  unique(capabilities);
  const skills = list(cb.skills).map(v => {
    const a = object(v), capabilityIds = strings(a.capabilityIds);
    if (!capabilityIds.length || capabilityIds.some(id => !capabilities.some(c => c.id === id))) invalid('考点引用了不存在的能力单元。');
    return { id: text(a.id), topic: text(a.topic), cognitiveTask: text(a.cognitiveTask), evidenceBoundary: text(a.evidenceBoundary, 1000), capabilityIds };
  });
  unique(skills);
  const evidence = list(input.evidence, 30).map(v => {
    const e = object(v);
    if (e.usage !== 'TEST_ONLY' && !(e.usage === 'INTERNAL_READING' && input.origin)) invalid('输入不能自行声明正式医学批准。');
    return { id: text(e.id), version: text(e.version), title: text(e.title), content: text(e.content, 20000), usage: e.usage as 'TEST_ONLY' | 'INTERNAL_READING' };
  });
  unique(evidence);
  const plan = list(input.plan).map(v => {
    const a = object(v), skillId = text(a.skillId), evidenceIds = strings(a.evidenceIds);
    if (!skills.some(s => s.id === skillId) || evidenceIds.some(id => !evidence.some(e => e.id === id))) invalid('准备计划引用不存在的考点或资料。');
    if ('practiced' in a || 'evaluated' in a || 'score' in a) invalid('演练和评分必须来自实际记录，不能通过输入标记伪造。');
    return { skillId, question: text(a.question, 2000), rationale: text(a.rationale, 2000), evidenceIds };
  });
  if (!capabilities.length || !skills.length || !plan.length || new Set(plan.map(p => p.skillId)).size !== plan.length) invalid('代码本和准备计划不能为空或重复。');
  let origin: TaskInput['origin'];
  if (input.origin !== undefined) {
    const o = object(input.origin);
    if (o.system !== 'MODULE1' || !['sheets','runs'].includes(String(o.sourceKind)) || typeof o.candidatePoolKnown !== 'boolean') invalid('模块一来源无效。');
    origin = { system: 'MODULE1', sourceKind: o.sourceKind as 'sheets'|'runs', sourceTaskId: text(o.sourceTaskId), lessonId: text(o.lessonId), revision: text(o.revision), sourcePath: text(o.sourcePath, 1000), sourceHash: text(o.sourceHash), candidatePoolKnown: o.candidatePoolKnown as boolean };
  }
  let forecastSnapshot: TaskInput['forecastSnapshot'];
  if (input.forecastSnapshot !== undefined) {
    if (!origin || !origin.candidatePoolKnown || origin.sourceKind !== 'sheets') invalid('不能为非访前冻结任务补造预测。');
    const f = object(input.forecastSnapshot), candidateSkillIds = strings(f.candidateSkillIds), selectedSkillIds = strings(f.selectedSkillIds);
    if (!candidateSkillIds.length || !selectedSkillIds.length || new Set(candidateSkillIds).size!==candidateSkillIds.length ||
        new Set(selectedSkillIds).size!==selectedSkillIds.length || candidateSkillIds.some(id=>!skills.some(s=>s.id===id)) ||
        selectedSkillIds.some(id=>!candidateSkillIds.includes(id)) || plan.some(p=>!selectedSkillIds.includes(p.skillId)) ||
        plan.length!==selectedSkillIds.length || !Number.isSafeInteger(f.budget) || f.budget!==selectedSkillIds.length) invalid('预测候选、选中重点与原计划不一致。');
    const generatedAt=text(f.generatedAt),frozenAt=text(f.frozenAt);
    if (!Number.isFinite(Date.parse(generatedAt)) || !Number.isFinite(Date.parse(frozenAt)) || Date.parse(frozenAt)<Date.parse(generatedAt) || Date.parse(frozenAt)>Date.now()+60_000) invalid('先验预测冻结时间无效。');
    forecastSnapshot={candidateSkillIds,selectedSkillIds,generatedAt,frozenAt,budget:f.budget as number,note:text(f.note,500)};
  } else if (origin?.candidatePoolKnown) invalid('已声明候选池存在，但缺少冻结先验预测。');
  return { ...(origin ? { origin } : {}), ...(forecastSnapshot?{forecastSnapshot}:{}), fixtureId: text(input.fixtureId), title: text(input.title), knowledgeVersion: text(input.knowledgeVersion),
    scenarioVersion: text(input.scenarioVersion), strategyVersion: text(input.strategyVersion),
    codebook: { version: text(cb.version), capabilities, skills }, evidence, plan };
}

/** Fictional input data only. No analysis, review decision or predicted output is seeded. */
export function mainFixture(): TaskInput {
  return {
    fixtureId: 'research-a-main-v1', title: '虚构研究 A · 学术交流准备', knowledgeVersion: 'test-evidence-v1', scenarioVersion: 'SC1', strategyVersion: 'ST1',
    codebook: { version: 'test-codebook-v1', capabilities: [
      { id: 'endpoint', description: '解释主要终点的定义' }, { id: 'population', description: '解释入组条件与人群范围' },
      { id: 'subgroup', description: '解释亚组结果及其探索性性质' }, { id: 'extrapolation', description: '说明亚组结果的外推限制' },
    ], skills: [
      { id: 'endpoint-explanation', topic: '虚构研究 A', cognitiveTask: '解释', evidenceBoundary: '主要终点定义', capabilityIds: ['endpoint'] },
      { id: 'population-explanation', topic: '虚构研究 A', cognitiveTask: '解释', evidenceBoundary: '入组与排除条件', capabilityIds: ['population'] },
      { id: 'subgroup-explanation', topic: '虚构研究 A', cognitiveTask: '解释', evidenceBoundary: '亚组结果及探索性性质', capabilityIds: ['subgroup'] },
      { id: 'subgroup-extrapolation', topic: '虚构研究 A', cognitiveTask: '解释并评价', evidenceBoundary: '亚组结果及外推限制', capabilityIds: ['subgroup', 'extrapolation'] },
    ] },
    evidence: [{ id: 'E1', version: '1', title: '虚构研究 A 测试资料（非医学事实）', usage: 'TEST_ONLY',
      content: '本材料完全虚构，仅验证软件流程。主要终点为预先定义的测试终点。研究有指定入组和排除条件。亚组结果为探索性结果，不支持直接推广到其他人群。不包含真实药物、疗效数值或治疗建议。' }],
    plan: [
      { skillId: 'endpoint-explanation', question: '如何解释主要终点？', rationale: '本次准备覆盖研究基本终点。', evidenceIds: ['E1'] },
      { skillId: 'population-explanation', question: '研究的入组人群是什么？', rationale: '本次准备覆盖研究入组范围。', evidenceIds: ['E1'] },
    ],
  };
}
export const sampleReflection = '这次讨论的是虚构研究 A。对方先问主要终点是什么意思，我觉得这部分解释清楚了。后来又问亚组结果能不能推广到其他人群，我不太确定，没能讲清楚。我觉得可能是之前没有准备到这部分。对方最后是否认可，我不知道。';
