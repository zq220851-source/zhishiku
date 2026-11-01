import assert from 'node:assert/strict';
import { test } from 'node:test';
import { derive, validateExtraction } from '../lib/analysis';
import { Store } from '../lib/store';
import { Service } from '../lib/service';
import { researchB } from './fixtures/research-b';
import type { Actor, DifficultyIndicator, Extraction, Unit } from '../lib/types';
import type { Exercise } from '../lib/learning-types';

const actor: Actor = { id: 'd3-person', role: 'EMPLOYEE' };
const q = '医生问一年以后还能保证效果吗？';
const response = '我先说肯定没问题，后来觉得自己说得太满。对方再追问长期依据，我一下子讲不清边界。';
const raw = q + response;
const skill = 'longterm-boundary-judgment';
function extraction(indicators?: DifficultyIndicator[], linked = true): Extraction {
  const unit = (id: string, excerpt: string, start: number, type: Unit['types'][number], assessment: Unit['selfAssessment']): Unit => ({
    id, excerpt, startCp: start, endCp: start + Array.from(excerpt).length, codes: [], types: [type],
    attribution: type === 'REPORTED_QUESTION' ? 'OTHER_REPORTED' : 'SELF', certainty: 'REPORTED',
    skillIds: [skill], mapping: 'CANDIDATE', selfAssessment: assessment,
  });
  return { units: [unit('q', q, 0, 'REPORTED_QUESTION', []), {
      ...unit('r', response, Array.from(q).length, 'SELF_REPORTED_RESPONSE', ['DIFFICULTY']),
      ...(indicators === undefined ? {} : { difficultyIndicators: indicators }),
    }], relations: linked ? [{ from: 'q', to: 'r', type: 'RESPONSE_TO', supportUnitIds: ['q','r'] }] : [] };
}
async function analyze(value: Extraction, input = researchB()) {
  const store = new Store(':memory:'), service = new Service(store);
  const task = service.createTask(actor, input, 'd3-task');
  const f = service.saveRaw(actor, task.id, { text: raw, confirmed: true, exchangeOccurred: true }, 'd3-raw');
  const result = await service.analyze(actor, f.id, 1, async () => value, 'fixture');
  assert.equal(result.state, 'ANALYZED', result.errorCode);
  return { store, service, task, feedback: f };
}

test('D3: an anchored mixed difficulty produces two independent hypotheses, capability-focused first exercise', async () => {
  const indicators: DifficultyIndicator[] = [
    { kind: 'BOUNDARY_OVERSTATEMENT', quote: '说得太满', capabilityIds: ['uncertainty-expression'] },
    { kind: 'FOLLOW_UP_BLOCK', quote: '讲不清边界', capabilityIds: ['long-term-limitation'] },
  ];
  const { store, service } = await analyze(extraction(indicators));
  try {
    const [need] = service.learning.needs(actor);
    assert.equal(need.hypothesis, 'MULTIPLE');
    assert.deepEqual(need.indicators, indicators);
    assert.deepEqual(need.targetCapabilityIds, ['long-term-limitation', 'uncertainty-expression']);
    const exercise = service.learning.dashboard(actor).profiles[0].next!;
    assert.deepEqual(exercise.difficultyFocus, ['BOUNDARY_OVERSTATEMENT', 'FOLLOW_UP_BLOCK']);
    assert.ok(exercise.question.includes('改成谨慎'));
    assert.ok(exercise.question.includes('继续追问'));
    assert.equal(exercise.sourceNeedId, need.needId);
    assert.ok(exercise.trainingReason.includes('说得太满'));
    assert.ok(exercise.material.includes('虚构研究 B'));
  } finally { store.close(); }
});

test('D3: knowledge uncertainty gets an evidence-explanation practice, and NO claimed objective failure', async () => {
  const { store, service } = await analyze(extraction([{ kind: 'KNOWLEDGE_UNCERTAINTY', quote: '讲不清边界', capabilityIds: ['long-term-limitation'] }]));
  try {
    const need = service.learning.needs(actor)[0], exercise = service.learning.dashboard(actor).profiles[0].next!;
    assert.equal(need.hypothesis, 'KNOWLEDGE_UNCERTAINTY');
    assert.deepEqual(exercise.targetCapabilityIds, ['long-term-limitation']);
    assert.ok(exercise.question.includes('给定资料支持什么'));
    assert.equal(need.evidenceStatus, 'SELF_REPORT_ONLY');
  } finally { store.close(); }
});

test('D3: no model-supported cause => UNRESOLVED and checks whole skill, not coverage missing capabilities', async () => {
  const input = researchB();
  // The plan covers only the first capability. This is about plan coverage, not proven personal failure.
  input.plan.push({ skillId: skill, question: '一年后的结果？', rationale: '测试已预备该题', evidenceIds: ['B-E1'] });
  const { store, service } = await analyze(extraction(), input);
  try {
    const need = service.learning.needs(actor)[0], exercise = service.learning.dashboard(actor).profiles[0].next!;
    assert.equal(need.hypothesis, 'UNRESOLVED');
    assert.deepEqual(need.indicators, []);
    assert.deepEqual(exercise.targetCapabilityIds, ['long-term-limitation', 'uncertainty-expression']);
    assert.deepEqual(exercise.difficultyFocus, []);
  } finally { store.close(); }
});

test('D3: model cannot attach unsupported kind to GOOD, another skill or a fabricated quotation', () => {
  const base = extraction([{ kind: 'BOUNDARY_OVERSTATEMENT', quote: '说得太满', capabilityIds: ['uncertainty-expression'] }]);
  const update = (indicators: unknown, selfAssessment: string[] = ['DIFFICULTY']) => ({ ...base, units: [base.units[0], { ...base.units[1], difficultyIndicators: indicators, selfAssessment }] });
  assert.throws(() => validateExtraction(raw, update([{ kind: 'BOUNDARY_OVERSTATEMENT', quote: '我从没说过', capabilityIds: ['uncertainty-expression'] }]), researchB().codebook));
  assert.throws(() => validateExtraction(raw, update([{ kind: 'BOUNDARY_OVERSTATEMENT', quote: '说得太满', capabilityIds: ['observation-window'] }]), researchB().codebook));
  assert.throws(() => validateExtraction(raw, update([{ kind: 'BOUNDARY_OVERSTATEMENT', quote: '说得太满', capabilityIds: ['uncertainty-expression'] }], ['GOOD']), researchB().codebook));
  assert.throws(() => validateExtraction(raw, update([{ kind: 'UNKNOWN_FAILURE', quote: '说得太满', capabilityIds: [] }]), researchB().codebook));
  assert.throws(() => validateExtraction(raw, update([{ kind: 'FOLLOW_UP_BLOCK', quote: '讲不清边界', capabilityIds: ['long-term-limitation'] }, { kind: 'FOLLOW_UP_BLOCK', quote: '讲不清边界', capabilityIds: [] }]), researchB().codebook));
});

test('D3: unlinked subtype remains a sourced need but cannot create practice', async () => {
  const { store, service } = await analyze(extraction([{ kind: 'FOLLOW_UP_BLOCK', quote: '讲不清边界', capabilityIds: ['long-term-limitation'] }], false));
  try {
    const [need] = service.learning.needs(actor);
    assert.equal(need.hypothesis, 'FOLLOW_UP_BLOCK');
    assert.equal(need.status, 'AWAITING_CONFIRMATION');
    assert.deepEqual(need.indicators[0].capabilityIds, ['long-term-limitation']);
    assert.equal(service.learning.dashboard(actor).profiles.length, 0);
  } finally { store.close(); }
});

test('D3: actual graded gap outranks initial cause, and later practice evidence remains separate', async () => {
  const { store, service } = await analyze(extraction([{ kind: 'BOUNDARY_OVERSTATEMENT', quote: '说得太满', capabilityIds: ['uncertainty-expression'] }]));
  try {
    const first = service.learning.dashboard(actor).profiles[0].next!;
    const answer = '此资料只是虚构的三个月观察，不支持长期保证。';
    const outcome = await service.learning.submit(actor, first.id, answer, 'd3-answer', async (a, ex: Exercise) => ({
      criteria: ex.criteria.map(c => ({ id: c.id, result: c.id === 'evidence-boundary' ? 'SATISFIED' : 'GAP', quote: a, reason: '测试：待补练' })), summary: '测试逐项输出',
    }), 'fixture');
    assert.equal(outcome.passed, false);
    const next = service.learning.dashboard(actor).profiles[0].next!;
    assert.deepEqual(next.targetCapabilityIds, ['uncertainty-expression']);
    assert.equal(service.learning.needs(actor)[0].evidenceStatus, 'PRACTICE_GAP');
  } finally { store.close(); }
});


test('D3: an explicit later GOOD correction supersedes earlier DIFFICULTY without erasing either quote', () => {
  const text = '医生问一年后也有效吗？我最初觉得自己没解释清楚。哦不对，我当时解释了没有一年后的资料。';
  const snippets = ['医生问一年后也有效吗？', '我最初觉得自己没解释清楚。', '哦不对，我当时解释了没有一年后的资料。'];
  const units = snippets.map((excerpt, index) => {
    const startCp = Array.from(text.slice(0, text.indexOf(excerpt))).length;
    return { id: `u${index}`, excerpt, startCp, endCp: startCp + Array.from(excerpt).length, codes: [],
      types: [index === 0 ? 'REPORTED_QUESTION' : 'SELF_REPORTED_RESPONSE'],
      attribution: index === 0 ? 'OTHER_REPORTED' : 'SELF', certainty: 'REPORTED',
      skillIds: [skill], mapping: 'CANDIDATE', selfAssessment: index === 1 ? ['DIFFICULTY'] : index === 2 ? ['GOOD'] : [],
      ...(index === 1 ? { difficultyIndicators: [{ kind: 'KNOWLEDGE_UNCERTAINTY', quote: '没解释清楚', capabilityIds: [] }] } : {}),
    };
  });
  const valid = validateExtraction(text, { units, relations: [
    { from: 'u0', to: 'u1', type: 'RESPONSE_TO', supportUnitIds: ['u0', 'u1'] },
    { from: 'u1', to: 'u2', type: 'SELF_CORRECTION', supportUnitIds: ['u1', 'u2'] },
  ] }, researchB().codebook);
  const result = derive(valid, researchB(), 'fixture', 'v5');
  assert.deepEqual(result.differences[0].performance.map(p => p.kind), ['SELF_REPORTED_DIFFICULTY', 'SELF_REPORTED_GOOD']);
  assert.equal(result.differences[0].personalSignal, 'SELF_REPORTED_SUCCESS');
  assert.deepEqual(result.findings[0].correctionUnitIds, ['u2']);
});

test('D3: a cause without skill mapping can survive as an unlinked source signal with no invented capability', () => {
  const value = extraction([{ kind: 'FOLLOW_UP_BLOCK', quote: '讲不清边界', capabilityIds: [] }], false);
  value.units[1].skillIds = []; value.units[1].mapping = 'UNKNOWN';
  const checked = validateExtraction(raw, value, researchB().codebook);
  const result = derive(checked, researchB(), 'fixture', 'v5');
  assert.equal(result.findings.find(f => f.kind === 'UNLINKED_SELF_REPORT')?.linkage, 'UNKNOWN');
  assert.deepEqual(checked.units[1].difficultyIndicators?.[0].capabilityIds, []);
});

test('D3: reverse correction keeps the earlier negative historical wording but does not schedule it as an active cause', async () => {
  const correctedRaw = '医生问一年后也有效吗？我最初觉得自己没解释清楚。哦不对，我当时解释了没有一年后的资料。';
  const parts = ['医生问一年后也有效吗？', '我最初觉得自己没解释清楚。', '哦不对，我当时解释了没有一年后的资料。'];
  const units: Unit[] = parts.map((excerpt, index) => {
    const cp = Array.from(correctedRaw.slice(0, correctedRaw.indexOf(excerpt))).length;
    return { id: `part-${index}`, excerpt, startCp: cp, endCp: cp + Array.from(excerpt).length, codes: [],
      types: [index === 0 ? 'REPORTED_QUESTION' : 'SELF_REPORTED_RESPONSE'], attribution: index === 0 ? 'OTHER_REPORTED' : 'SELF',
      certainty: 'REPORTED', skillIds: [skill], mapping: 'CANDIDATE',
      selfAssessment: index === 1 ? ['DIFFICULTY'] : index === 2 ? ['GOOD'] : [],
      ...(index === 1 ? { difficultyIndicators: [{ kind: 'KNOWLEDGE_UNCERTAINTY' as const, quote: '没解释清楚', capabilityIds: [] }] } : {}),
    };
  });
  const store = new Store(':memory:');
  try {
    const service = new Service(store);
    const task = service.createTask(actor, researchB(), 'd3-correction-task');
    const f = service.saveRaw(actor, task.id, { text: correctedRaw, confirmed: true, exchangeOccurred: true }, 'd3-correction-raw');
    await service.analyze(actor, f.id, 1, async () => ({ units, relations: [
      { from: 'part-0', to: 'part-1', type: 'RESPONSE_TO', supportUnitIds: ['part-0','part-1'] },
      { from: 'part-1', to: 'part-2', type: 'SELF_CORRECTION', supportUnitIds: ['part-1','part-2'] },
    ] }), 'fixture');
    const [need] = service.learning.needs(actor);
    assert.equal(need.hypothesis, 'UNRESOLVED');
    assert.deepEqual(need.indicators, []);
    assert.ok(need.observedProblem.includes('没解释清楚'));
    assert.ok(need.observedProblem.includes('哦不对'));
    assert.equal(service.learning.dashboard(actor).profiles.length, 1); // GOOD still gets a confirmatory test
    assert.ok(!service.learning.dashboard(actor).profiles[0].next!.trainingReason.includes('知识或证据理解不确定'));
  } finally { store.close(); }
});
