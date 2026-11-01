import assert from 'node:assert/strict';
import { test } from 'node:test';
import { Store } from '../lib/store';
import { Service } from '../lib/service';
import { Learning, validateGrade } from '../lib/learning';
import { mainFixture } from '../lib/fixture';
import type { Actor } from '../lib/types';
import type { Exercise, Grade } from '../lib/learning-types';
const owner: Actor = { id: 'learner', role: 'EMPLOYEE' };
const other: Actor = { id: 'other', role: 'EMPLOYEE' };
const raw = '对方问亚组能否外推。我没讲清楚。';
const q = '对方问亚组能否外推。', r = '我没讲清楚。';
const answer = '亚组结果是探索性的，不能直接推广到其他人群；需要额外适用证据。';
function grade(exercise: Exercise, passed = true): Grade {
  return { criteria: exercise.criteria.map((c,i) => ({ id: c.id, result: !passed && i === 0 ? 'GAP' : 'SATISFIED', quote: answer, reason: passed ? '作答明确说明此测试要求。' : '测试评价中识别到缺项。' })), summary: passed ? '本次作答有改善证据，仍需换题和保持验证。' : '此情境还有待练习的缺项。' };
}
async function setup() {
  let time = Date.parse('2026-10-31T00:00:00Z');
  const store = new Store(':memory:'), service = new Service(store, () => time);
  const learning = service.learning;
  const task = service.createTask(owner, mainFixture(), 'task');
  const feedback = service.saveRaw(owner, task.id, { text: raw, confirmed: true, exchangeOccurred: true }, 'raw');
  await service.analyze(owner, feedback.id, 1, async () => ({ units: [
    { id: 'q', startCp: 0, endCp: Array.from(q).length, excerpt: q, codes: ['外推'], types: ['REPORTED_QUESTION'], attribution: 'OTHER_REPORTED', certainty: 'REPORTED', skillIds: ['subgroup-extrapolation'], mapping: 'CANDIDATE', selfAssessment: [] },
    { id: 'r', startCp: Array.from(q).length, endCp: Array.from(raw).length, excerpt: r, codes: ['自述困难'], types: ['SELF_REPORTED_RESPONSE'], attribution: 'SELF', certainty: 'REPORTED', skillIds: ['subgroup-extrapolation'], mapping: 'CANDIDATE', selfAssessment: ['DIFFICULTY'] },
  ], relations: [{ from: 'q', to: 'r', type: 'RESPONSE_TO', supportUnitIds: ['q','r'] }] }), 'fixture');
  learning.sync(owner);
  return { store, service, learning, task, feedback, setTime: (value: number) => { time = value; } };
}
test('self report creates a pending verification with no formal score, repeated sync does not multiply tasks or evidence', async () => {
  const { store, learning } = await setup();
  try {
    const first = learning.dashboard(owner).profiles[0];
    assert.equal(first.state, 'UNVERIFIED'); assert.equal(first.sourceCount, 1); assert.equal(first.next?.purpose, 'VERIFY');
    learning.sync(owner); learning.sync(owner);
    const after = learning.dashboard(owner).profiles[0]; assert.equal(after.next?.id, first.next?.id); assert.equal(after.sourceCount, 1);
    assert.equal(after.attempts.length, 0); assert.ok(!('score' in after));
  } finally { store.close(); }
});
test('real attempts progress through new question, delayed retention and separate context transfer, without permanent mastery', async () => {
  const { store, learning } = await setup();
  try {
    const first = learning.dashboard(owner).profiles[0].next!;
    const result = await learning.submit(owner, first.id, answer, 'one', async (_, e) => grade(e), 'test-grader');
    assert.equal(result.state, 'COMPLETED');
    const next = learning.dashboard(owner).profiles[0]; assert.equal(next.state, 'IMPROVING'); assert.equal(next.next?.purpose, 'RETEST'); assert.notEqual(next.next?.questionId, first.questionId);
    await learning.submit(owner, next.next!.id, answer, 'two', async (_, e) => grade(e), 'test-grader');
    const retention = learning.dashboard(owner).profiles[0].next!; assert.equal(retention.purpose, 'RETENTION');
    await assert.rejects(learning.submit(owner, retention.id, answer, 'early', async (_, e) => grade(e), 'test'), { code: 'EXERCISE_NOT_DUE' });
    learning.advance(owner, 7);
    assert.equal(learning.dashboard(owner).profiles[0].state, 'IMPROVING'); assert.equal(learning.dashboard(owner).profiles[0].freshness, 'DUE');
    await learning.submit(owner, retention.id, answer, 'three', async (_, e) => grade(e), 'test-grader');
    const profiles = learning.dashboard(owner).profiles;
    const normal = profiles.find(p => p.context === 'NORMAL')!, pressure = profiles.find(p => p.context === 'PRESSURE')!;
    assert.equal(normal.next?.purpose, 'RETENTION'); assert.equal(pressure.next?.purpose, 'TRANSFER');
    await learning.submit(owner, pressure.next!.id, answer, 'pressure', async (_, e) => grade(e, false), 'test-grader');
    assert.equal(learning.dashboard(owner).profiles.find(p => p.context === 'PRESSURE')?.state, 'NEEDS_PRACTICE');
    assert.equal(learning.dashboard(owner).profiles.find(p => p.context === 'NORMAL')?.state, 'IMPROVING');
    assert.ok(learning.demands(owner).some(d => d.context === 'PRESSURE' && d.due));
  } finally { store.close(); }
});
test('idempotent attempts count once; duplicate or unauthorized submissions cannot forge extra capability evidence', async () => {
  const { store, learning } = await setup(); let calls = 0;
  try {
    const e = learning.dashboard(owner).profiles[0].next!;
    const grader = async (_: string, exercise: Exercise) => { calls++; return grade(exercise); };
    const first = await learning.submit(owner, e.id, answer, 'retry', grader, 'test');
    assert.equal((await learning.submit(owner, e.id, answer, 'retry', grader, 'test')).id, first.id); assert.equal(calls, 1);
    await assert.rejects(learning.submit(owner, e.id, answer, 'different-key', grader, 'test'), { code: 'EXERCISE_COMPLETED' });
    await assert.rejects(learning.submit(other, e.id, answer, 'stolen', grader, 'test'), { code: 'NOT_FOUND' });
    await assert.rejects(learning.submit({ ...owner, role: 'PUBLISHER' }, e.id, answer, 'role', grader, 'test'), { code: 'FORBIDDEN' });
    assert.equal(learning.dashboard(owner).profiles[0].attempts.filter(a => a.state === 'COMPLETED').length, 1);
    assert.throws(() => store.db.prepare('DELETE FROM learning_grades').run(), /immutable/);
  } finally { store.close(); }
});
test('failed evaluation retains answer but supplies no success evidence; same request can recover', async () => {
  const { store, learning } = await setup();
  try {
    const e = learning.dashboard(owner).profiles[0].next!;
    const failed = await learning.submit(owner, e.id, answer, 'failed', async () => { throw new Error('private-provider-error'); }, 'test');
    assert.equal(failed.state, 'FAILED'); assert.equal(failed.answer, answer); assert.equal(learning.dashboard(owner).profiles[0].state, 'UNVERIFIED');
    const recovered = await learning.submit(owner, e.id, answer, 'failed', async (_, exercise) => grade(exercise), 'test'); assert.equal(recovered.state, 'COMPLETED');
    assert.ok(!JSON.stringify(store.db.prepare('SELECT * FROM events').all()).includes('private-provider-error'));
  } finally { store.close(); }
});
test('unsupported quotes, missing rubric criteria and self-invented criteria are rejected', async () => {
  const { store, learning } = await setup();
  try {
    const e = learning.dashboard(owner).profiles[0].next!, good = grade(e);
    assert.throws(() => validateGrade(answer, { ...good, criteria: good.criteria.slice(1) }, e));
    assert.throws(() => validateGrade(answer, { ...good, criteria: good.criteria.map(c => ({ ...c, quote: '并未说过' })) }, e));
    assert.throws(() => validateGrade(answer, { ...good, criteria: [...good.criteria, { ...good.criteria[0], id: 'invented' }] }, e));
  } finally { store.close(); }
});
test('raw revisions pause unverified demands; late model responses cannot revive obsolete source signals', async () => {
  const { store, service, learning, task, feedback } = await setup();
  try {
    const e = learning.dashboard(owner).profiles[0].next!;
    const result = await learning.submit(owner, e.id, answer, 'stale', async (_, exercise) => {
      service.saveRaw(owner, task.id, { text: '修订后不再报告该困难。', confirmed: true, exchangeOccurred: true, expectedVersion: 1 }, 'edit', feedback.id);
      return grade(exercise);
    }, 'test');
    assert.equal(result.state, 'FAILED'); assert.equal(result.errorCode, 'LEARNING_SOURCE_STALE');
    assert.equal(learning.demands(owner).length, 0);
  } finally { store.close(); }
});
test('a reviewer can retract a mistaken evaluation, preserving history and recalculating capability', async () => {
  const { store, learning } = await setup();
  try {
    const e = learning.dashboard(owner).profiles[0].next!;
    const a = await learning.submit(owner, e.id, answer, 'grade', async (_, exercise) => grade(exercise), 'test');
    assert.throws(() => learning.retract(owner, a.id, 'test correction'), { code: 'FORBIDDEN' });
    learning.retract({ ...owner, role: 'TRAINING_REVIEWER' }, a.id, '测试评价错误，撤回重核');
    const p = learning.dashboard(owner).profiles[0]; assert.equal(p.state, 'UNVERIFIED'); assert.equal(p.attempts[0].state, 'RETRACTED'); assert.ok(p.attempts[0].grade);
  } finally { store.close(); }
});

test('retracting the only successful evaluation replaces its downstream retest with verification', async () => {
  const { store, learning } = await setup();
  try {
    const first = learning.dashboard(owner).profiles[0].next!;
    const a = await learning.submit(owner, first.id, answer, 'initial', async (_, e) => grade(e), 'test');
    const oldNext = learning.dashboard(owner).profiles[0].next!;
    learning.retract({ ...owner, role: 'TRAINING_REVIEWER' }, a.id, '撤回不可靠评价');
    const next = learning.dashboard(owner).profiles[0].next!;
    assert.equal(next.purpose, 'VERIFY'); assert.notEqual(next.id, oldNext.id);
  } finally { store.close(); }
});
test('correcting the originating self report does not erase independent valid practice evidence', async () => {
  const { store, learning, service, task, feedback } = await setup();
  try {
    const exercise = learning.dashboard(owner).profiles[0].next!;
    await learning.submit(owner, exercise.id, answer, 'actual', async (_, e) => grade(e), 'test');
    service.saveRaw(owner, task.id, { text: '原自述需要更正。', confirmed: true, exchangeOccurred: true, expectedVersion: 1 }, 'new-text', feedback.id);
    assert.equal(learning.dashboard(owner).profiles[0].state, 'IMPROVING');
    assert.equal(learning.dashboard(owner).profiles[0].attempts.filter(a => a.state === 'COMPLETED').length, 1);
  } finally { store.close(); }
});

test('concurrent submissions cannot run a second evaluator and risky answers never reach the provider', async () => {
  const { store, learning } = await setup();
  try {
    const e = learning.dashboard(owner).profiles[0].next!;
    let finish!: (value: Grade) => void, calls = 0;
    const pending = learning.submit(owner, e.id, answer, 'first-concurrent', async () => { calls++; return new Promise<Grade>(resolve => { finish = resolve; }); }, 'test');
    await assert.rejects(learning.submit(owner, e.id, answer, 'second-concurrent', async () => { calls++; return grade(e); }, 'test'), { code: 'ALREADY_PROCESSING' });
    finish(grade(e)); assert.equal((await pending).state, 'COMPLETED'); assert.equal(calls, 1);
    const next = learning.dashboard(owner).profiles[0].next!;
    await assert.rejects(learning.submit(owner, next.id, '患者手机号13800138000', 'restricted', async () => { calls++; return grade(next); }, 'test'), { code: 'LEARNING_INPUT_RESTRICTED' });
    assert.equal(calls, 1);
  } finally { store.close(); }
});

test('a newly reported difficulty brings forward verification without deleting earlier practice evidence', async () => {
  const { store, learning, service, task, feedback } = await setup();
  try {
    for (const key of ['verify', 'retest']) { const e = learning.dashboard(owner).profiles[0].next!; await learning.submit(owner, e.id, answer, key, async (_, e) => grade(e), 'test'); }
    assert.equal(learning.dashboard(owner).profiles[0].next?.purpose, 'RETENTION');
    const second = service.saveRaw(owner, task.id, { text: raw, confirmed: true, exchangeOccurred: true }, 'another-report');
    const original = service.getFeedback(owner, feedback.id).analysis!;
    await service.analyze(owner, second.id, 1, async () => ({ units: original.units, relations: original.relations }), 'test');
    const p = learning.dashboard(owner).profiles[0]; assert.equal(p.next?.purpose, 'VERIFY'); assert.equal(p.state, 'IMPROVING'); assert.equal(p.attempts.length, 2);
  } finally { store.close(); }
});
