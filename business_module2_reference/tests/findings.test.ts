import assert from 'node:assert/strict';
import { test } from 'node:test';
import { derive, validateExtraction } from '../lib/analysis';
import { mainFixture } from '../lib/fixture';
import { researchB } from './fixtures/research-b';
import { Store } from '../lib/store';
import { Service } from '../lib/service';
import type { Extraction, Unit } from '../lib/types';

function unit(raw: string, id: string, excerpt: string, types: Unit['types'], skillIds: string[], assessment: Unit['selfAssessment'] = []): Unit {
  const i = raw.indexOf(excerpt); if (i < 0) throw new Error('test excerpt missing');
  return { id, excerpt, startCp: Array.from(raw.slice(0, i)).length, endCp: Array.from(raw.slice(0, i + excerpt.length)).length,
    codes: [], types, attribution: types.includes('REPORTED_QUESTION') ? 'OTHER_REPORTED' : 'SELF', certainty: 'REPORTED',
    skillIds, mapping: skillIds.length ? 'CANDIDATE' : 'UNKNOWN', selfAssessment: assessment };
}

test('D1: orphan difficulty stays anchored and unlinked, without inventing a question relation or P score', () => {
  const raw = '医生问我亚组能不能外推。我当时说得不清楚，回来觉得自己还不会讲这个边界。';
  const q = unit(raw, 'q', '医生问我亚组能不能外推。', ['REPORTED_QUESTION'], ['subgroup-extrapolation']);
  const d = unit(raw, 'd', '回来觉得自己还不会讲这个边界。', ['SELF_REPORTED_RESPONSE'], ['subgroup-extrapolation'], ['DIFFICULTY']);
  const extraction = validateExtraction(raw, { units: [q, d], relations: [] }, mainFixture().codebook);
  const analysis = derive(extraction, mainFixture(), 'test', 'v0.3');
  assert.equal(analysis.differences[0].coverage, 'NONE');
  assert.equal(analysis.differences[0].personalSignal, 'UNKNOWN');
  assert.equal(analysis.findings.length, 2);
  const orphan = analysis.findings.find(f => f.kind === 'UNLINKED_SELF_REPORT')!;
  assert.equal(orphan.linkage, 'UNKNOWN');
  assert.equal(orphan.assessment.personalSignal, 'PENDING_CONFIRMATION');
  assert.deepEqual(orphan.skillIds, ['subgroup-extrapolation']);
  assert.equal(orphan.eligibleForSharedChange, false);
  assert.deepEqual(orphan.evidence.map(e => e.excerpt), [d.excerpt]);
  assert.deepEqual(analysis.relations, []);
});

test('D1: two reported questions must not absorb one ambiguous unlinked difficulty based on proximity', () => {
  const raw = '他先问了终点。又问能不能外推。我说的那个东西也没讲明白。';
  const q1 = unit(raw, 'q1', '他先问了终点。', ['REPORTED_QUESTION'], ['endpoint-explanation']);
  const q2 = unit(raw, 'q2', '又问能不能外推。', ['REPORTED_QUESTION'], ['subgroup-extrapolation']);
  const d = unit(raw, 'd', '我说的那个东西也没讲明白。', ['SELF_REPORTED_RESPONSE'], [], ['DIFFICULTY']);
  const result = derive(validateExtraction(raw, { units: [q1, q2, d], relations: [] }, mainFixture().codebook), mainFixture(), 'test', 'v0.3');
  assert.equal(result.findings.filter(f => f.kind === 'UNLINKED_SELF_REPORT').length, 1);
  assert.equal(result.differences.every(v => v.personalSignal === 'UNKNOWN'), true);
  assert.equal(result.findings.find(f => f.kind === 'UNLINKED_SELF_REPORT')?.skillIds.length, 0);
});

test('D1: explicit correction chain preserves original GOOD and later DIFFICULTY, without guessing from adjacent text', () => {
  const raw = '对方问亚组结果能外推吗。我当时说可以。哦不对，回来想想说得太满了，我还是不会解释限制。';
  const q = unit(raw, 'q', '对方问亚组结果能外推吗。', ['REPORTED_QUESTION'], ['subgroup-extrapolation']);
  const r = unit(raw, 'r', '我当时说可以。', ['SELF_REPORTED_RESPONSE'], ['subgroup-extrapolation'], ['GOOD']);
  const c = unit(raw, 'c', '哦不对，回来想想说得太满了，我还是不会解释限制。', ['SELF_REPORTED_RESPONSE'], ['subgroup-extrapolation'], ['DIFFICULTY']);
  const relations: Extraction['relations'] = [{ from: 'q', to: 'r', type: 'RESPONSE_TO', supportUnitIds: ['q', 'r'] },
    { from: 'r', to: 'c', type: 'SELF_CORRECTION', supportUnitIds: ['r', 'c'] }];
  const result = derive(validateExtraction(raw, { units: [q, r, c], relations }, mainFixture().codebook), mainFixture(), 'test', 'v0.3');
  assert.equal(result.differences[0].personalSignal, 'PENDING_VERIFY');
  assert.deepEqual(result.differences[0].performance.map(p => p.kind), ['SELF_REPORTED_GOOD', 'SELF_REPORTED_DIFFICULTY']);
  const finding = result.findings.find(f => f.kind === 'QUESTION')!;
  assert.deepEqual(finding.responseUnitIds, ['r', 'c']);
  assert.deepEqual(finding.correctionUnitIds, ['c']);
  assert.equal(finding.linkage, 'CONFIRMED');
  assert.equal(finding.evidence.length, 3);
});

test('D1: invalid self-correction relationship is rejected, as is invented excerpt', () => {
  const raw = '问长期效果。我没说清楚。'; const q = unit(raw, 'q', '问长期效果。', ['REPORTED_QUESTION'], ['longterm-boundary-judgment']);
  const r = unit(raw, 'r', '我没说清楚。', ['SELF_REPORTED_RESPONSE'], ['longterm-boundary-judgment'], ['DIFFICULTY']);
  assert.throws(() => validateExtraction(raw, { units: [q, r], relations: [{ from: 'q', to: 'r', type: 'SELF_CORRECTION', supportUnitIds: ['q', 'r'] }] }, researchB().codebook));
  assert.throws(() => validateExtraction(raw, { units: [q, { ...r, excerpt: '我没说过。' }], relations: [] }, researchB().codebook));
});

test('D1: research B uses its own skill IDs and missing capability; unlinked difficulty remains a candidate', () => {
  const input = researchB(), raw = '他说一年后是不是也保证有效。我真的不知道怎么解释长期资料的限制。';
  const q = unit(raw, 'q', '他说一年后是不是也保证有效。', ['REPORTED_QUESTION'], ['longterm-boundary-judgment']);
  const d = unit(raw, 'd', '我真的不知道怎么解释长期资料的限制。', ['SELF_REPORTED_RESPONSE'], ['longterm-boundary-judgment'], ['DIFFICULTY']);
  const result = derive(validateExtraction(raw, { units: [q, d], relations: [] }, input.codebook), input, 'test', 'v0.3');
  assert.equal(result.differences[0].coverage, 'NONE');
  assert.deepEqual(result.differences[0].missingCapabilityIds, ['long-term-limitation','uncertainty-expression']);
  assert.equal(result.findings.find(f => f.kind === 'UNLINKED_SELF_REPORT')?.linkage, 'UNKNOWN');
  assert.equal(result.findings.some(f => f.skillIds.includes('subgroup-extrapolation')), false);
});


test('D1: service persists the unlinked finding with the current raw revision; no fake relation is recorded', async () => {
  const store = new Store(':memory:');
  try {
    const service = new Service(store), actor = { id: 'test-rep-b', role: 'EMPLOYEE' as const };
    const task = service.createTask(actor, researchB(), 'b-task');
    const raw = '对方问一年以后呢。我觉得我还是没解释清楚这个边界。';
    const q = unit(raw, 'q', '对方问一年以后呢。', ['REPORTED_QUESTION'], ['longterm-boundary-judgment']);
    const d = unit(raw, 'd', '我觉得我还是没解释清楚这个边界。', ['SELF_REPORTED_RESPONSE'], ['longterm-boundary-judgment'], ['DIFFICULTY']);
    const feedback = service.saveRaw(actor, task.id, { text: raw, confirmed: true, exchangeOccurred: true }, 'b-raw');
    const analyzed = await service.analyze(actor, feedback.id, 1, async () => ({ units: [q,d], relations: [] }), 'offline-fixture');
    assert.equal(analyzed.state, 'ANALYZED');
    const stored = service.getFeedback(actor, feedback.id);
    assert.equal(stored.analysisRawId, stored.versions[0].id);
    assert.equal(stored.analysis?.findings.find(f => f.kind === 'UNLINKED_SELF_REPORT')?.evidence[0].excerpt, d.excerpt);
    assert.equal(stored.analysis?.differences[0].personalSignal, 'UNKNOWN');
    assert.equal(stored.analysis?.relations.length, 0);
  } finally { store.close(); }
});

test('D1: unclear question does not map to a B skill without explicit evidence, even if task context is known', () => {
  const raw = '那个结果以后也一样吗，我也不太懂指哪个结果。';
  const q = unit(raw, 'q', '那个结果以后也一样吗', ['REPORTED_QUESTION'], []);
  const result = derive(validateExtraction(raw, { units: [q], relations: [] }, researchB().codebook), researchB(), 'test', 'v0.3');
  assert.equal(result.differences[0].coverage, 'UNKNOWN');
  assert.equal(result.findings[0].skillIds.length, 0);
  assert.equal(result.findings[0].eligibleForSharedChange, false);
});
