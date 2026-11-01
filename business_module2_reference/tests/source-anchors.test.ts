import assert from 'node:assert/strict';
import { test } from 'node:test';
import { validateExtraction } from '../lib/analysis';
import { mainFixture } from '../lib/fixture';
const unit = (excerpt: string, startCp: number, endCp: number) => ({ id: 'u', excerpt, startCp, endCp,
  codes: ['原话'], types: ['REPORTED_QUESTION'], attribution: 'OTHER_REPORTED', certainty: 'REPORTED', skillIds: [], mapping: 'UNKNOWN', selfAssessment: [] });
const validate = (raw: string, excerpt: string, start: number, end: number) => validateExtraction(raw, { units: [unit(excerpt, start, end)], relations: [] }, mainFixture().codebook).units[0];
test('program locates a unique exact quote when a model miscounts Unicode offsets, preserving both proven source and proposed location', () => {
  const raw = '前文🙂他说问题。后文。';
  const result = validate(raw, '他说问题。', 4, 9);
  assert.equal(result.startCp, 3); assert.equal(result.endCp, 8);
  assert.equal(Array.from(raw).slice(result.startCp, result.endCp).join(''), result.excerpt);
  assert.equal(result.sourceAnchor, 'UNIQUE_EXACT_QUOTE');
  assert.deepEqual(result.modelSpan, { startCp: 4, endCp: 9 });
});
test('duplicate quotes without a correct model location, invented excerpts and invalid indices are never guessed', () => {
  assert.throws(() => validate('问题。问题。', '问题。', 1, 4), { code: 'INVALID_INPUT' });
  assert.throws(() => validate('他说问题。', '他没说过。', 0, 5), { code: 'INVALID_INPUT' });
  assert.throws(() => validate('他说问题。', '他说问题。', -1, 4), { code: 'INVALID_INPUT' });
  assert.equal(validate('问题。问题。', '问题。', 3, 6).sourceAnchor, 'EXACT_MODEL_SPAN');
});
