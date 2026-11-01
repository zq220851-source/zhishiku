import assert from 'node:assert/strict';
import { test } from 'node:test';
import { Store } from '../lib/store';
import { Service } from '../lib/service';
import { researchB } from './fixtures/research-b';
import type { Actor, Extraction, Unit } from '../lib/types';
import type { Exercise, Grade } from '../lib/learning-types';

const owner: Actor = { id: 'employee-b', role: 'EMPLOYEE' };
const raw = '医生追问一年以后也能保证吗？我当时说得太满了，回来想想不对，我其实不会解释一年后没数据这个限制。';
const q = '医生追问一年以后也能保证吗？';
const r = '我当时说得太满了，回来想想不对，我其实不会解释一年后没数据这个限制。';
const attemptAnswer = '这项虚构研究只观察三个月，没有一年后数据，不能保证长期效果。';
function unit(id: string, excerpt: string, start: number, type: Unit['types'][number], skills: string[], assessment: Unit['selfAssessment'] = []): Unit {
  return { id, excerpt, startCp: start, endCp: start + Array.from(excerpt).length, codes: ['自然口述'], types: [type],
    attribution: type === 'REPORTED_QUESTION' ? 'OTHER_REPORTED' : 'SELF', certainty: 'REPORTED', skillIds: skills,
    mapping: skills.length ? 'CANDIDATE' : 'UNMAPPED', selfAssessment: assessment };
}
function extraction(linked: boolean): Extraction {
  return { units: [unit('q', q, 0, 'REPORTED_QUESTION', ['longterm-boundary-judgment']),
    unit('r', r, Array.from(q).length, 'SELF_REPORTED_RESPONSE', ['longterm-boundary-judgment'], ['DIFFICULTY'])],
    relations: linked ? [{ from: 'q', to: 'r', type: 'RESPONSE_TO', supportUnitIds: ['q', 'r'] }] : [] };
}
async function setup(linked: boolean) {
  const store = new Store(':memory:');
  const service = new Service(store);
  const task = service.createTask(owner, researchB(), 'research-b-task');
  const feedback = service.saveRaw(owner, task.id, { text: raw, confirmed: true, exchangeOccurred: true }, 'spoken');
  await service.analyze(owner, feedback.id, 1, async () => extraction(linked), 'test-provider');
  return { store, service, task, feedback, learning: service.learning };
}
function grade(exercise: Exercise, gaps: string[] = []): Grade {
  return { criteria: exercise.criteria.map(c => ({ id: c.id, result: gaps.includes(c.id) ? 'GAP' as const : 'SATISFIED' as const,
    quote: attemptAnswer, reason: gaps.includes(c.id) ? '没有解释这个目标' : '已展示该目标' })), summary: '本次独立测试作答的逐项判断。' };
}

test('D2: unrelated research B turns an anchored difficulty into an individualized, versioned training need', async () => {
  const { store, learning, task, feedback } = await setup(true);
  try {
    const needs = learning.needs(owner);
    assert.equal(needs.length, 1);
    assert.equal(needs[0].source.taskId, task.id);
    assert.equal(needs[0].source.feedbackId, feedback.id);
    assert.equal(needs[0].source.findingId, 'question:q:longterm-boundary-judgment');
    assert.equal(needs[0].observedProblem, r);
    assert.equal(needs[0].status, 'READY_FOR_PRACTICE');
    assert.equal(needs[0].evidenceStatus, 'SELF_REPORT_ONLY');
    assert.deepEqual(needs[0].targetCapabilityIds, ['long-term-limitation', 'uncertainty-expression']);
    assert.equal(needs[0].targetCapabilities[0].description, '说明资料不包含一年后结果');
    const first = learning.dashboard(owner).profiles[0].next!;
    assert.ok(first.question.includes('一年后'));
    assert.ok(first.question.includes('长期效果未知'));
    assert.deepEqual(first.targetCapabilityIds, needs[0].targetCapabilityIds);
    assert.equal(first.material.includes('虚构研究 B'), true);
    assert.equal(first.material.includes('虚构研究 A'), false);
    learning.sync(owner);
    assert.equal(learning.needs(owner).length, 1);
    assert.equal(learning.dashboard(owner).profiles[0].next?.id, first.id);
  } finally { store.close(); }
});

test('D2: unlinked self-report remains a pending confirmation, never becoming an invented question or practice grade', async () => {
  const { store, learning } = await setup(false);
  try {
    const needs = learning.needs(owner);
    assert.equal(needs.length, 1);
    assert.equal(needs[0].status, 'AWAITING_CONFIRMATION');
    assert.equal(needs[0].source.findingId, 'unlinked:r');
    assert.equal(needs[0].observedProblem, r);
    assert.equal(learning.dashboard(owner).profiles.length, 0);
    assert.equal(learning.demands(owner).length, 0);
  } finally { store.close(); }
});

test('D2: a real grade gap narrows the next exercise; improvement redirects to a different retest and retains evidence', async () => {
  const { store, learning } = await setup(true);
  try {
    const first = learning.dashboard(owner).profiles[0].next!;
    const a = await learning.submit(owner, first.id, attemptAnswer, 'b-answer-1', async e => grade(first, ['uncertainty-expression']), 'test');
    assert.equal(a.state, 'COMPLETED');
    const afterGap = learning.dashboard(owner).profiles[0].next!;
    assert.notEqual(afterGap.id, first.id);
    assert.deepEqual(afterGap.targetCapabilityIds, ['uncertainty-expression']);
    assert.ok(afterGap.question.includes('解释未知信息时不作长期效果保证'));
    assert.ok(!afterGap.question.includes('准确描述三个月观察窗口'));
    assert.equal(learning.needs(owner)[0].evidenceStatus, 'PRACTICE_GAP');
    assert.equal(learning.needs(owner)[0].status, 'READY_FOR_PRACTICE');
    await learning.submit(owner, afterGap.id, attemptAnswer, 'b-answer-2', async () => grade(afterGap), 'test');
    const afterImprovement = learning.dashboard(owner).profiles[0].next!;
    assert.equal(afterImprovement.purpose, 'RETEST');
    assert.deepEqual(afterImprovement.targetCapabilityIds, ['long-term-limitation', 'uncertainty-expression']);
    assert.equal(learning.needs(owner)[0].evidenceStatus, 'PRACTICE_IMPROVEMENT');
    assert.equal(learning.needs(owner)[0].status, 'FOLLOW_UP');
    assert.equal(learning.dashboard(owner).profiles[0].attempts.length, 2);
  } finally { store.close(); }
});

test('D2: raw correction suspends unpractised needs; failed grader never forges improvement', async () => {
  const { store, learning, service, task, feedback } = await setup(true);
  try {
    const first = learning.dashboard(owner).profiles[0].next!;
    const failure = await learning.submit(owner, first.id, attemptAnswer, 'fail-once', async () => { throw Error('external failure'); }, 'test');
    assert.equal(failure.state, 'FAILED');
    assert.equal(learning.needs(owner)[0].evidenceStatus, 'SELF_REPORT_ONLY');
    service.saveRaw(owner, task.id, { text: '改正：刚才不确定的那段不是实际交流。', confirmed: true, exchangeOccurred: true, expectedVersion: 1 }, 'correct', feedback.id);
    assert.equal(learning.needs(owner)[0].status, 'SOURCE_STALE');
    assert.equal(learning.demands(owner).length, 0);
    assert.equal(learning.dashboard(owner).profiles[0].active, false);
  } finally { store.close(); }
});

test('D2: retracted grades do not count as improvement; only same owner sees their source needs', async () => {
  const { store, learning } = await setup(true);
  try {
    const first = learning.dashboard(owner).profiles[0].next!;
    const attempt = await learning.submit(owner, first.id, attemptAnswer, 'b-grading', async () => grade(first), 'test');
    assert.equal(learning.needs(owner)[0].evidenceStatus, 'PRACTICE_IMPROVEMENT');
    learning.retract({ ...owner, role: 'TRAINING_REVIEWER' }, attempt.id, '模拟测试纠正评分');
    assert.equal(learning.needs(owner)[0].evidenceStatus, 'SELF_REPORT_ONLY');
    assert.equal(learning.needs(owner)[0].status, 'READY_FOR_PRACTICE');
    assert.equal(learning.needs({ id: 'not-this-employee', role: 'EMPLOYEE' }).length, 0);
    assert.equal(learning.dashboard({ ...owner, role: 'TRAINING_REVIEWER' }).needs.length, 1);
    assert.throws(() => store.db.prepare('DELETE FROM learning_need_sources').run(), /immutable/);
  } finally { store.close(); }
});

test('D2: withdrawn study B evidence stops practice without losing its quoted history', async () => {
  const { store, learning } = await setup(true);
  try {
    assert.equal(learning.dashboard(owner).profiles[0].active, true);
    store.put('withdraw-b-evidence', 'knowledge-withdrawal', 'single-test-team', { id: 'B-E1', version: '1' });
    assert.equal(learning.dashboard(owner).profiles[0].active, false);
    assert.equal(learning.needs(owner)[0].status, 'SOURCE_STALE');
    assert.equal(learning.demands(owner).length, 0);
    assert.equal(learning.needs(owner)[0].observedProblem, r);
  } finally { store.close(); }
});


test('D2: later self-reported difficulty is not dismissed by an earlier passing answer', async () => {
  const { store, learning, service, task } = await setup(true);
  try {
    const first = learning.dashboard(owner).profiles[0].next!;
    await learning.submit(owner, first.id, attemptAnswer, 'initial-improvement', async () => grade(first), 'test');
    assert.equal(learning.needs(owner).length, 1);
    assert.equal(learning.needs(owner)[0].status, 'FOLLOW_UP');
    const second = service.saveRaw(owner, task.id, { text: raw, confirmed: true, exchangeOccurred: true }, 'new-visit');
    await service.analyze(owner, second.id, 1, async () => extraction(true), 'test-provider');
    const needs = learning.needs(owner);
    assert.equal(needs.length, 2);
    assert.equal(needs[0].status, 'FOLLOW_UP');
    assert.equal(needs[1].status, 'READY_FOR_PRACTICE');
    assert.equal(needs[1].evidenceStatus, 'SELF_REPORT_ONLY');
    const latest = learning.dashboard(owner).profiles[0];
    assert.equal(latest.attempts.length, 1);
    assert.equal(latest.next?.purpose, 'VERIFY');
    assert.ok(latest.next?.question.includes('本人自述'));
    assert.ok(latest.reason.includes('新的本人困难'));
  } finally { store.close(); }
});
