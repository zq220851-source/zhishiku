import assert from 'node:assert/strict';
import { test } from 'node:test';
import { Service } from '../lib/service';
import { Store } from '../lib/store';
import { mainFixture } from '../lib/fixture';
import { coverage, derive, validateExtraction } from '../lib/analysis';
import type { Actor, Extraction } from '../lib/types';
const employee: Actor = { id: 'employee-a', role: 'EMPLOYEE' };
const other: Actor = { id: 'employee-b', role: 'EMPLOYEE' };
function setup() { const store = new Store(':memory:'); return { store, service: new Service(store) }; }
const rawInput = (text = '对方问亚组外推。我没讲清楚。') => ({ text, confirmed: true, exchangeOccurred: true });
function extraction(raw = rawInput().text): Extraction {
  const question = raw.split('。')[0] + '。';
  const response = raw.slice(question.length);
  return { units: [
    { id: 'q', startCp: 0, endCp: Array.from(question).length, excerpt: question, types: ['REPORTED_QUESTION'], codes: ['亚组外推'], attribution: 'OTHER_REPORTED', certainty: 'REPORTED', skillIds: ['subgroup-extrapolation'], mapping: 'CANDIDATE', selfAssessment: [] },
    { id: 'r', startCp: Array.from(question).length, endCp: Array.from(raw).length, excerpt: response, types: ['SELF_REPORTED_RESPONSE'], codes: ['自述困难'], attribution: 'SELF', certainty: 'REPORTED', skillIds: ['subgroup-extrapolation'], mapping: 'CANDIDATE', selfAssessment: ['DIFFICULTY'] },
  ], relations: [{ from: 'q', to: 'r', type: 'RESPONSE_TO', supportUnitIds: ['q', 'r'] }] };
}
test('replaceable task input, immutable snapshot, idempotent creation, and owner isolation', () => {
  const { service, store } = setup();
  try {
    const input = mainFixture(), task = service.createTask(employee, input, 'create');
    assert.equal(service.createTask(employee, input, 'create').id, task.id);
    assert.throws(() => service.createTask(employee, { ...input, title: 'changed' }, 'create'), { code: 'IDEMPOTENCY_CONFLICT' });
    input.evidence[0].content = 'changed';
    assert.notEqual(service.getTask(employee, task.id).snapshot.evidence[0].content, 'changed');
    assert.throws(() => store.db.prepare('UPDATE frozen_plans SET payload=? WHERE id=?').run('{}', task.snapshot.id), /immutable/);
    assert.throws(() => service.getTask(other, task.id), { code: 'NOT_FOUND' });
    assert.throws(() => service.createTask({ ...employee, role: 'PUBLISHER' }, input, 'publish'), { code: 'FORBIDDEN' });
  } finally { store.close(); }
});
test('invalid evidence and fabricated training are rejected without partially creating a task', () => {
  const { service, store } = setup();
  try {
    const f = mainFixture(); f.plan[0].evidenceIds = ['missing'];
    assert.throws(() => service.createTask(employee, f, 'missing'), { code: 'INVALID_INPUT' });
    const p = mainFixture(); Object.assign(p.plan[0], { practiced: true });
    assert.throws(() => service.createTask(employee, p, 'fake'), { code: 'INVALID_INPUT' });
    assert.equal(service.tasks(employee).length, 0);
  } finally { store.close(); }
});
test('whole original text preserved; confirmation, revision conflict, no-op and retries checked', () => {
  const { service, store } = setup();
  try {
    const task = service.createTask(employee, mainFixture(), 'task');
    const body = rawInput('  🙂原话\n保留。 '), f = service.saveRaw(employee, task.id, body, 'submit');
    assert.equal(f.versions[0].text, body.text);
    assert.equal(service.saveRaw(employee, task.id, body, 'submit').id, f.id);
    assert.throws(() => service.saveRaw(employee, task.id, { ...body, confirmed: false }, 'bad'), { code: 'INVALID_INPUT' });
    assert.throws(() => service.saveRaw(other, task.id, body, 'other'), { code: 'NOT_FOUND' });
    const next = service.saveRaw(employee, task.id, { ...rawInput('修正后。'), expectedVersion: 1 }, 'edit', f.id);
    assert.equal(next.versions.length, 2); assert.equal(next.versions[0].text, body.text);
    assert.throws(() => service.saveRaw(employee, task.id, { ...body, expectedVersion: 1 }, 'conflict', f.id), { code: 'VERSION_CONFLICT' });
    assert.equal(service.saveRaw(employee, task.id, { ...rawInput('修正后。'), expectedVersion: 2 }, 'noop', f.id).versions.length, 2);
    service.cancel(employee, task.id);
    assert.throws(() => service.saveRaw(employee, task.id, body, 'cancel'), { code: 'TASK_CANCELED' });
  } finally { store.close(); }
});
test('four confirmed coverage cases; canonical mapping supports paraphrase and explicit partial missing units', () => {
  const input = mainFixture(), target = input.codebook.skills.find(s => s.id === 'subgroup-extrapolation')!;
  assert.equal(coverage(input.codebook.skills[0], input).coverage, 'FULL');
  assert.equal(coverage(target, input).coverage, 'NONE');
  assert.equal(coverage(undefined, input).coverage, 'UNKNOWN');
  input.plan = [{ skillId: 'subgroup-explanation', question: '换一种问法', rationale: '测试解释而未准备外推', evidenceIds: ['E1'] }];
  assert.equal(coverage(target, input).coverage, 'PARTIAL');
  assert.deepEqual(coverage(target, input).missingCapabilityIds, ['extrapolation']);
  input.plan.push({ ...input.plan[0], skillId: target.id });
  assert.equal(coverage(target, input).coverage, 'FULL');
});
test('semantic validation uses supplied codebook and rejects fabricated spans, ids, relationships and self-grading', () => {
  const input = mainFixture(); const valid = extraction();
  assert.equal(validateExtraction(rawInput().text, valid, input.codebook).units.length, 2);
  for (const edit of [{ excerpt: '伪造' }, { skillIds: ['fake'] }, { attribution: 'SELF', selfAssessment: ['GOOD'] }, { startCp: -1 }]) {
    assert.throws(() => validateExtraction(rawInput().text, { ...valid, units: [{ ...valid.units[0], ...edit }, valid.units[1]] }, input.codebook));
  }
  assert.throws(() => validateExtraction(rawInput().text, { ...valid, relations: [{ ...valid.relations[0], supportUnitIds: ['fake'] }] }, input.codebook));
  const analysis = derive(valid, input, 'test-provider', 'test-prompt');
  assert.equal(analysis.differences[0].coverage, 'NONE');
  assert.equal(analysis.differences[0].personalSignal, 'PENDING_VERIFY');
  assert.ok(!('score' in analysis)); assert.ok(!('accuracy' in analysis));
});
test('risk screening stops provider calls and failures keep original text without fabricated fallback', async () => {
  const { service, store } = setup(); let calls = 0;
  try {
    const task = service.createTask(employee, mainFixture(), 'task');
    const blocked = service.saveRaw(employee, task.id, rawInput('用药后疑似不良反应。'), 'risk');
    const result = await service.analyze(employee, blocked.id, 1, async () => { calls++; return extraction(); }, 'test-provider');
    assert.equal(result.state, 'RESTRICTED'); assert.equal(calls, 0);
    const normal = service.saveRaw(employee, task.id, rawInput(), 'normal');
    const failure = await service.analyze(employee, normal.id, 1, async () => { throw new Error('secret provider details'); }, 'test-provider');
    assert.equal(failure.state, 'FAILED'); assert.equal(failure.errorCode, 'MODEL_REQUEST_FAILED'); assert.equal(failure.analysis, undefined);
    assert.equal(failure.versions[0].text, rawInput().text);
    assert.ok(!JSON.stringify(store.db.prepare('SELECT * FROM events').all()).includes('secret provider details'));
    const recovered = await service.analyze(employee, normal.id, 1, async () => extraction(), 'test-provider');
    assert.equal(recovered.state, 'ANALYZED');
  } finally { store.close(); }
});
test('raw edit and task cancellation during model call prevent late analysis writeback', async () => {
  const { service, store } = setup();
  try {
    const task = service.createTask(employee, mainFixture(), 'task');
    const f = service.saveRaw(employee, task.id, rawInput(), 'submit');
    const result = await service.analyze(employee, f.id, 1, async () => { service.saveRaw(employee, task.id, { ...rawInput('修订后的原话。'), expectedVersion: 1 }, 'edit', f.id); return extraction(); }, 'test-provider');
    assert.equal(result.state, 'SAVED'); assert.equal(result.versions.length, 2); assert.equal(result.analysis, undefined);
    const second = service.saveRaw(employee, task.id, rawInput(), 'second');
    const canceled = await service.analyze(employee, second.id, 1, async () => { service.cancel(employee, task.id); return extraction(); }, 'test-provider');
    assert.equal(canceled.analysis, undefined);
    assert.equal(canceled.state, 'CANCELED');
  } finally { store.close(); }
});

test('interrupted model calls expire their lease and recover without accepting superseded results', async () => {
  const { service, store } = setup();
  try {
    const task = service.createTask(employee, mainFixture(), 'lease-task');
    const f = service.saveRaw(employee, task.id, rawInput(), 'lease-raw');
    let release!: () => void;
    const waiting = new Promise<void>(resolve => { release = resolve; });
    let entered!: () => void;
    const started = new Promise<void>(resolve => { entered = resolve; });
    const pending = service.analyze(employee, f.id, 1, async () => { entered(); await waiting; return extraction(); }, 'first-provider');
    await started;
    const processing = service.getFeedback(employee, f.id) as ReturnType<Service['getFeedback']> & { processingLease?: { token: string; expiresAt: number } };
    assert.ok(processing.processingLease, 'persist a recoverable lease, not a permanent PROCESSING flag');
    processing.processingLease.expiresAt = 0;
    store.put(f.id, 'feedback', employee.id, processing);
    const recovered = await service.analyze(employee, f.id, 1, async () => extraction(), 'recovered-provider');
    assert.equal(recovered.analysis?.model, 'recovered-provider');
    release(); await pending;
    assert.equal(service.getFeedback(employee, f.id).analysis?.model, 'recovered-provider');
  } finally { store.close(); }
});
test('raw historical records are immutable in the database', () => {
  const { service, store } = setup();
  try {
    const task = service.createTask(employee, mainFixture(), 'frozen-task');
    const f = service.saveRaw(employee, task.id, rawInput(), 'frozen-raw');
    assert.throws(() => store.db.prepare('UPDATE frozen_raw SET payload=? WHERE id=?').run('{}', f.versions[0].id), /immutable/);
  } finally { store.close(); }
});
