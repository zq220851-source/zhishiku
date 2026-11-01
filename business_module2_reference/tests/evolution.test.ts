import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Store } from '../lib/store';
import { Service } from '../lib/service';
import { mainFixture } from '../lib/fixture';
import { compareStrategies, selectSkills } from '../lib/strategy';
import type { Actor } from '../lib/types';
import type { Reviewer } from '../lib/evolution-types';
const a: Actor = { id: 'one', role: 'EMPLOYEE' };
const role = (r: Actor['role']) => ({ ...a, role: r });
const review: Reviewer = async p => ({ decision: 'PASS', reason: '限定在测试资料内。', citations: [{ evidenceId: p.evidence[0].id, quote: p.evidence[0].content }] });
async function setup() {
  const store = new Store(':memory:'), service = new Service(store); const task = service.createTask(a, mainFixture(), 't');
  const raw = '主任问亚组结果能不能用到其他人群。我还不太会讲这个边界。';
  const f = service.saveRaw(a, task.id, { text: raw, confirmed: true, exchangeOccurred: true }, 'f');
  const q = raw.split('。')[0] + '。', response = raw.slice(q.length);
  await service.analyze(a, f.id, 1, async () => ({ units: [
    { id: 'q', startCp: 0, endCp: q.length, excerpt: q, codes: ['外推'], types: ['REPORTED_QUESTION'], attribution: 'OTHER_REPORTED', certainty: 'REPORTED', skillIds: ['subgroup-extrapolation'], mapping: 'CANDIDATE', selfAssessment: [] },
    { id: 'r', startCp: q.length, endCp: raw.length, excerpt: response, codes: ['困难'], types: ['SELF_REPORTED_RESPONSE'], attribution: 'SELF', certainty: 'REPORTED', skillIds: ['subgroup-extrapolation'], mapping: 'CANDIDATE', selfAssessment: ['DIFFICULTY'] },
  ], relations: [{ from: 'q', to: 'r', type: 'RESPONSE_TO', supportUnitIds: ['q','r'] }] }), 'test');
  service.evolution.discover(a); return { store, service, task, f, e: service.evolution };
}
async function publish(e: Service['evolution'], id: string) {
  const p = e.view(role('TRAINING_REVIEWER')).proposals.find(x => x.id === id)!;
  e.training(role('TRAINING_REVIEWER'), id, p.hash, true, '确认训练目标与边界。');
  await e.runAgent(role('MEDICAL_REVIEWER'), id, 'MEDICAL', review, 'test');
  return e.runAgent(role('PUBLISHER'), id, 'PUBLICATION', review, 'test');
}
test('content and strategy progress through distinct reviews, real tests and actual next selection, preserving old snapshot', async () => {
  const { store, service, e, task } = await setup();
  try {
    const p = e.view(a).proposals[0]; assert.equal(p.kind, 'CONTENT');
    e.discover(a); assert.equal(e.view(a).proposals.length, 1);
    const blocked = await e.runAgent(role('PUBLISHER'), p.id, 'PUBLICATION', review, 'test'); assert.equal(blocked.state, 'BLOCKED');
    const released = await publish(e, p.id); assert.equal(released.state, 'PUBLISHED');
    assert.equal(e.view(a).releases.length, 1);
    await e.runAgent(role('PUBLISHER'), p.id, 'PUBLICATION', review, 'test'); assert.equal(e.view(a).releases.length, 1);
    e.discover(a); const strategy = e.view(a).proposals.find(x => x.kind === 'STRATEGY')!; assert.ok(strategy);
    assert.equal((await publish(e, strategy.id)).state, 'PUBLISHED');
    const next = service.createTask(a, e.nextInput({ focus: 'EXTRAPOLATION', budget: 2 }), 'next'); e.recordUse(a, next);
    assert.deepEqual(next.snapshot.plan.map(x => x.skillId), ['endpoint-explanation','subgroup-extrapolation']);
    assert.deepEqual(service.getTask(a, task.id).snapshot.plan.map(x => x.skillId), ['endpoint-explanation','population-explanation']);
    assert.ok(e.view(a).releases.every(r => r.uses === 1));
    e.recall(role('PUBLISHER'), released.releaseId!, '测试召回');
    assert.ok(!e.nextInput({ focus: 'EXTRAPOLATION', budget: 2 }).plan.some(p => p.skillId === 'subgroup-extrapolation'));
  } finally { store.close(); }
});
test('role boundaries, revised draft invalidates reviews, stale agent cannot publish changed draft', async () => {
  const { store, e } = await setup();
  try {
    const p = e.view(a).proposals[0];
    assert.throws(() => e.training(a, p.id, p.hash, true, 'wrong role'), { code: 'FORBIDDEN' });
    e.training(role('TRAINING_REVIEWER'), p.id, p.hash, true, '合适');
    const result = await e.runAgent(role('MEDICAL_REVIEWER'), p.id, 'MEDICAL', async proposal => {
      e.revise(role('TRAINING_REVIEWER'), p.id, p.hash, p.question + ' 请解释原因。', p.answer); return review(proposal, [], 'MEDICAL');
    }, 'test');
    assert.equal(result.medical, undefined); assert.equal(result.training, undefined);
    assert.equal((await e.runAgent(role('PUBLISHER'), p.id, 'PUBLICATION', review, 'test')).state, 'BLOCKED');
    assert.equal(e.view(a).releases.length, 0);
  } finally { store.close(); }
});
test('fabricated citation, changed source, unsupported answer and withdrawn knowledge stop publication and practice', async () => {
  const { store, e, service, task, f } = await setup();
  try {
    const p = e.view(a).proposals[0];
    assert.equal((await e.runAgent(role('MEDICAL_REVIEWER'), p.id, 'MEDICAL', async () => ({ decision: 'PASS', reason: 'invented', citations: [{ evidenceId: 'E1', quote: '假的引文' }] }), 'test')).state, 'BLOCKED');
    const edited = e.revise(role('TRAINING_REVIEWER'), p.id, p.hash, p.question, '保证所有人都有效。');
    assert.equal((await publish(e, edited.id)).state, 'BLOCKED');
    service.saveRaw(a, task.id, { text: '原报告有误。', confirmed: true, exchangeOccurred: true, expectedVersion: 1 }, 'revise', f.id);
    assert.equal((await publish(e, edited.id)).state, 'BLOCKED');
    e.withdrawKnowledge(role('MEDICAL_REVIEWER'), 'E1', '1', '测试撤回来源');
    assert.throws(() => e.nextInput({ focus: 'BASIC', budget: 2 }), { code: 'KNOWLEDGE_UNAVAILABLE' });
    assert.ok(service.learning.dashboard(a).profiles.every(p => !p.active));
  } finally { store.close(); }
});
test('selection has the same budget and content, held-out comparison exposes added coverage and omissions', () => {
  const available = ['endpoint-explanation','population-explanation','subgroup-extrapolation'];
  const rows = compareStrategies(available); assert.ok(rows.every(r => r.valid && !r.lost.length)); assert.ok(rows.some(r => r.partition === 'HOLDOUT' && r.added.length));
  assert.deepEqual(selectSkills(available, { focus: 'UNKNOWN', budget: 2 }, 'FOCUS'), available.slice(0,2));
  assert.ok(compareStrategies(available.slice(0,2)).some(r => !r.valid));
});

test('restoring a recalled version rechecks current evidence; withdrawn shared evidence never silently returns', async () => {
  const { store, e } = await setup();
  try {
    const p = e.view(a).proposals[0]; const release = await publish(e, p.id);
    e.recall(role('PUBLISHER'), release.releaseId!, '测试撤回');
    e.restoreRelease(role('PUBLISHER'), release.releaseId!, '重新核查有效');
    assert.equal(e.view(a).releases[0].active, true);
    e.withdrawKnowledge(role('MEDICAL_REVIEWER'), 'E1', '1', '来源已失效');
    assert.throws(() => e.restoreRelease(role('PUBLISHER'), release.releaseId!, '不能强行恢复'), { code: 'RESTORE_BLOCKED' });
  } finally { store.close(); }
});
