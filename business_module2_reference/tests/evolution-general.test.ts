import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Store } from '../lib/store';
import { Service } from '../lib/service';
import { mainFixture } from '../lib/fixture';
import { researchB } from '../lib/demo-data';
import { labCases, evaluateLab } from '../lib/lab-cases';
import { compareStrategyCases, selectSkills } from '../lib/strategy';
import { demoCatalog, demoCases } from '../lib/demo-data';
import type { Actor } from '../lib/types';
import type { Reviewer } from '../lib/evolution-types';
const actor: Actor = { id: 'employee', role: 'EMPLOYEE' };
const role = (role: Actor['role']) => ({ ...actor, role });
const review: Reviewer = async p => ({ decision: 'PASS', reason: '只引用给定虚构资料', citations: [{ evidenceId: p.evidence[0].id, quote: p.evidence[0].content }] });
async function visitB(service: Service, taskKey = 'b-task') {
  const task = service.createTask(actor, researchB(), taskKey);
  const raw = '医生问一年后还能一样吗。我答不上来，回来觉得不会解释为什么不能保证。';
  const q = '医生问一年后还能一样吗。', r = raw.slice(q.length);
  const f = service.saveRaw(actor, task.id, { text: raw, confirmed: true, exchangeOccurred: true }, taskKey + '-raw');
  const analyzed = await service.analyze(actor, f.id, 1, async () => ({ units: [
    { id: 'q', startCp: 0, endCp: q.length, excerpt: q, codes: ['长期'], types: ['REPORTED_QUESTION'], attribution: 'OTHER_REPORTED', certainty: 'REPORTED', skillIds: ['longterm-boundary-judgment'], mapping: 'CANDIDATE', selfAssessment: [] },
    { id: 'r', startCp: q.length, endCp: raw.length, excerpt: r, codes: ['不会解释'], types: ['SELF_REPORTED_RESPONSE'], attribution: 'SELF', certainty: 'REPORTED', skillIds: ['longterm-boundary-judgment'], mapping: 'CANDIDATE', selfAssessment: ['DIFFICULTY'] },
  ], relations: [{ from: 'q', to: 'r', type: 'RESPONSE_TO', supportUnitIds: ['q','r'] }] }), 'mock-structured-output');
  assert.equal(analyzed.state, 'ANALYZED');
  return { task, f };
}
async function publish(e: Service['evolution'], id: string) {
  const p = e.view(role('TRAINING_REVIEWER')).proposals.find(p => p.id === id)!;
  e.training(role('TRAINING_REVIEWER'), id, p.hash, true, '虚构训练适用');
  assert.equal((await e.runAgent(role('MEDICAL_REVIEWER'), id, 'MEDICAL', review, 'test')).medical?.decision, 'PASS');
  return e.runAgent(role('PUBLISHER'), id, 'PUBLICATION', review, 'test');
}
for (const c of labCases()) test(`test lab ${c.id}: ${c.title}`, () => {
  const actual = evaluateLab(c);
  assert.equal(actual.result.kind, c.expected, actual.result.reason);
});
test('study B: real analyzed feedback makes a strategy proposal; review, same-budget next task, immutable old plan', async () => {
  const store = new Store(':memory:');
  try {
    const service = new Service(store), { task } = await visitB(service);
    const view = service.evolution.discover(actor);
    assert.equal(view.proposals.length, 1);
    assert.equal(view.proposals[0].kind, 'STRATEGY');
    assert.equal(view.proposals[0].scope?.fixtureId, 'fictional-research-b-v1');
    assert.equal((await publish(service.evolution, view.proposals[0].id)).state, 'PUBLISHED');
    const next = service.createTask(actor, service.evolution.nextInput({ focus: 'EXTRAPOLATION', budget: 1 }, task), 'b-next');
    service.evolution.recordUse(actor, next);
    assert.deepEqual(next.snapshot.plan.map(p => p.skillId), ['longterm-boundary-judgment']);
    assert.deepEqual(service.getTask(actor, task.id).snapshot.plan.map(p => p.skillId), ['window-explanation']);
    assert.equal(next.snapshot.plan.length, task.snapshot.plan.length);
  } finally { store.close(); }
});
test('study B: incomplete directory generates CONTENT; after published content can propose STRATEGY', async () => {
  const store = new Store(':memory:');
  try {
    const service = new Service(store), task = service.createTask(actor, researchB(), 'b');
    const partial = demoCatalog(researchB())!.map(c => c.skillId === 'longterm-boundary-judgment' ?
      { ...c, coveredCapabilityIds: ['long-term-limitation'] } : c);
    service.evolution.registerCatalog(actor, task, partial, demoCases(researchB()));
    const raw = '医生问一年后是不是一样。我没解释清不能保证长期结果。';
    const q = '医生问一年后是不是一样。', r = raw.slice(q.length);
    const f = service.saveRaw(actor, task.id, { text: raw, confirmed: true, exchangeOccurred: true }, 'raw');
    const analyzed = await service.analyze(actor, f.id, 1, async () => ({ units: [
      { id:'q', startCp:0, endCp:q.length, excerpt:q, types:['REPORTED_QUESTION'], attribution:'OTHER_REPORTED', certainty:'REPORTED', skillIds:['longterm-boundary-judgment'], mapping:'CANDIDATE', codes:[], selfAssessment:[] },
      { id:'r', startCp:q.length, endCp:raw.length, excerpt:r, types:['SELF_REPORTED_RESPONSE'], attribution:'SELF', certainty:'REPORTED', skillIds:['longterm-boundary-judgment'], mapping:'CANDIDATE', codes:[], selfAssessment:['DIFFICULTY'] },
    ], relations:[{ from:'q', to:'r', type:'RESPONSE_TO', supportUnitIds:['q','r'] }] }), 'mock');
    assert.equal(analyzed.state, 'ANALYZED');
    const content = service.evolution.discover(actor).proposals[0];
    assert.equal(content.kind, 'CONTENT');
    assert.equal((await publish(service.evolution, content.id)).state, 'PUBLISHED');
    const evolved = service.evolution.discover(actor);
    assert.ok(evolved.proposals.some(p => p.kind === 'STRATEGY'));
  } finally { store.close(); }
});
test('custom study without catalog keeps decision pending and never fabricates a content library', async () => {
  const store = new Store(':memory:');
  try {
    const service = new Service(store), custom = { ...researchB(), fixtureId: 'another-frozen-study' };
    const task = service.createTask(actor, custom, 'custom');
    const raw = '医生问一年后的结果，我没准备到。';
    const f = service.saveRaw(actor, task.id, { text: raw, confirmed:true, exchangeOccurred:true }, 'raw');
    await service.analyze(actor, f.id, 1, async () => ({ units:[
      { id:'q', startCp:0, endCp:raw.length, excerpt:raw, types:['REPORTED_QUESTION'], attribution:'OTHER_REPORTED', certainty:'REPORTED', skillIds:['longterm-boundary-judgment'], mapping:'CANDIDATE', codes:[], selfAssessment:[] },
    ], relations:[] }), 'mock');
    const view = service.evolution.discover(actor);
    assert.equal(view.proposals.length, 0);
    assert.equal(view.pendingDecisions?.[0]?.status, 'INSUFFICIENT_DATA');
    assert.throws(() => service.evolution.nextInput({focus:'EXTRAPOLATION',budget:1},task), { code: 'CATALOG_UNAVAILABLE' });
  } finally { store.close(); }
});
test('custom catalog cannot be overwritten or reference wrong skills and frozen evidence', () => {
  const store = new Store(':memory:');
  try {
    const service = new Service(store), task = service.createTask(actor, researchB(), 'task');
    const catalog = demoCatalog(researchB())!;
    assert.throws(() => service.evolution.registerCatalog(actor,task,[{...catalog[0],skillId:'invented'}]), {code:'INVALID_INPUT'});
    service.evolution.registerCatalog(actor,task,catalog,demoCases(researchB()));
    assert.throws(() => service.evolution.registerCatalog(actor,task,catalog), {code:'VERSION_CONFLICT'});
    assert.throws(() => service.evolution.registerCatalog({id:'other',role:'EMPLOYEE'},task,catalog), {code:'FORBIDDEN'});
  } finally { store.close(); }
});
test('strategy comparator keeps workload equal on two independent studies; unknown focus never prioritizes', () => {
  for (const fixture of [mainFixture(),researchB()]) {
    const available = [...new Set([ ...fixture.plan.map(p=>p.skillId), ...demoCatalog(fixture)!.map(c=>c.skillId), ...fixture.codebook.skills.map(s=>s.id) ])];
    const target = fixture.codebook.skills.at(-1)!.id;
    const rows = compareStrategyCases(available, demoCases(fixture)!, fixture.plan.map(p=>p.skillId),target);
    assert.ok(rows.every(r=>r.old.length === r.next.length));
    assert.deepEqual(selectSkills(available,{focus:'UNKNOWN',budget:1,prioritySkillId:target},'FOCUS'),available.slice(0,1));
  }
});
test('same fixture label with changed evidence/codebook version cannot silently reuse A or B catalog', () => {
  const b = researchB();
  assert.equal(demoCatalog({ ...b, knowledgeVersion: 'b-knowledge-v2' }), undefined);
  assert.equal(demoCases({ ...b, codebook: { ...b.codebook, version: 'b-codebook-v2' } }), undefined);
  const a = mainFixture();
  assert.equal(demoCatalog({ ...a, scenarioVersion: 'unrelated-catalog' }), undefined);
});
test('canceled task cannot be used to generate the next round', () => {
  const store = new Store(':memory:');
  try {
    const service = new Service(store), task = service.createTask(actor,researchB(),'cancelable');
    service.cancel(actor,task.id);
    assert.throws(() => service.evolution.nextInput({focus:'BASIC',budget:1},service.getTask(actor,task.id)), {code:'TASK_CANCELED'});
  } finally { store.close(); }
});
