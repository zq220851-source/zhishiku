import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mainFixture } from '../lib/fixture';
import { researchB } from './fixtures/research-b';
import { FixtureModule1Sources, unavailableTrainingExecution, unavailableNextPreparation } from '../lib/module1-contracts';

test('D0: two independent, replaceable task snapshots are returned frozen and keyed by hash', async () => {
  const a = mainFixture(), b = researchB();
  const source = new FixtureModule1Sources([{ taskId: 'task-a', input: a }, { taskId: 'task-b', input: b }]);
  const first = await source.readTask({ taskId: 'task-b' });
  assert.equal(first.status, 'OK'); if (first.status !== 'OK') return;
  const snapshot = first.value;
  assert.equal(snapshot.input.codebook.version, 'b-codebook-v1');
  assert.equal(snapshot.input.plan[0].skillId, 'window-explanation');
  assert.ok(snapshot.snapshotHash);
  assert.ok(!JSON.stringify(snapshot).includes('subgroup-extrapolation'));
  b.evidence[0].content = 'MUTATED'; snapshot.input.plan[0].question = 'MUTATED';
  const reread = await source.readTask({ taskId: 'task-b', snapshotHash: snapshot.snapshotHash });
  assert.equal(reread.status, 'OK');
  if (reread.status === 'OK') assert.notEqual(reread.value.input.evidence[0].content, 'MUTATED');
  const aRead = await source.readTask({ taskId: 'task-a' });
  assert.equal(aRead.status, 'OK'); if (aRead.status === 'OK') assert.equal(aRead.value.input.fixtureId, 'research-a-main-v1');
});

test('D0: missing task, hash mismatch and evidence version mismatch never fall back to latest', async () => {
  const source = new FixtureModule1Sources([{ taskId: 'task-b', input: researchB() }]);
  assert.equal((await source.readTask({ taskId: 'missing' })).status, 'NOT_FOUND');
  assert.equal((await source.readTask({ taskId: 'task-b', snapshotHash: 'old-hash' })).status, 'VERSION_MISMATCH');
  const saved = await source.readTask({ taskId: 'task-b' });
  assert.equal(saved.status, 'OK'); if (saved.status !== 'OK') return;
  const common = { taskId: 'task-b', snapshotHash: saved.value.snapshotHash };
  assert.equal((await source.readEvidence({ taskId: 'task-b', knowledgeVersion: 'b-knowledge-v1', evidenceIds: ['B-E1'] })).status, 'VERSION_MISMATCH');
  assert.equal((await source.readCatalog({ taskId: 'task-b', scenarioVersion: 'b-catalog-v1' })).status, 'VERSION_MISMATCH');
  assert.equal((await source.readEvidence({ ...common, knowledgeVersion: 'wrong', evidenceIds: ['B-E1'] })).status, 'VERSION_MISMATCH');
  assert.equal((await source.readEvidence({ ...common, knowledgeVersion: 'b-knowledge-v1', evidenceIds: ['E1'] })).status, 'NOT_FOUND');
  const good = await source.readEvidence({ ...common, knowledgeVersion: 'b-knowledge-v1', evidenceIds: ['B-E1'] });
  assert.equal(good.status, 'OK'); if (good.status === 'OK') assert.equal(good.value[0].id, 'B-E1');
  assert.equal((await source.readCatalog({ ...common, scenarioVersion: 'b-catalog-v1' })).status, 'NOT_AVAILABLE');
  assert.equal((await source.readCatalog({ ...common, scenarioVersion: 'new-version' })).status, 'VERSION_MISMATCH');
});

test('D0: test catalog is separate from the codebook and plan; unsupported module 1 execution is explicit', async () => {
  const source = new FixtureModule1Sources([{ taskId: 'task-b', input: researchB(), catalog: [
    { contentId: 'b-longterm-01', version: '1', skillId: 'longterm-boundary-judgment', coveredCapabilityIds: ['long-term-limitation', 'uncertainty-expression'], evidenceIds: ['B-E1'], status: 'ELIGIBLE_TEST_ONLY' },
  ] }]);
  const saved = await source.readTask({ taskId: 'task-b' });
  assert.equal(saved.status, 'OK'); if (saved.status !== 'OK') return;
  const found = await source.readCatalog({ taskId: 'task-b', snapshotHash: saved.value.snapshotHash, scenarioVersion: 'b-catalog-v1' });
  assert.equal(found.status, 'OK'); if (found.status === 'OK') {
    assert.equal(found.value[0].skillId, 'longterm-boundary-judgment');
    assert.ok(saved.value.input.plan.every(p => p.skillId !== found.value[0].skillId));
  }
  assert.equal((await unavailableTrainingExecution.execute({ requestId: 'd0', taskId: 'task-b', snapshotHash: saved.value.snapshotHash, skillId: 'longterm-boundary-judgment' })).status, 'NOT_AVAILABLE');
  assert.equal((await unavailableNextPreparation.prepare({ requestId: 'd0', taskId: 'task-b', snapshotHash: saved.value.snapshotHash })).status, 'NOT_AVAILABLE');
  assert.throws(() => new FixtureModule1Sources([{ taskId: 'task-b', input: researchB(), catalog: [
    { contentId: 'bad', version: '1', skillId: 'subgroup-extrapolation', coveredCapabilityIds: ['subgroup'], evidenceIds: ['E1'], status: 'ELIGIBLE_TEST_ONLY' },
  ] }]));
});
