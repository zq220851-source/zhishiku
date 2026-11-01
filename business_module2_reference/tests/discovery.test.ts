import { test } from 'node:test';
import assert from 'node:assert/strict';
import { validatePatterns } from '../lib/discovery';
const observations = [0,1].map(i => ({ feedbackId: `f${i}`, rawId: `r${i}`, taskId: `t${i}`, excerpt: i ? '这次我说不清' : '这次我说明白了', codes: [], skillIds: [] }));
const pattern = { label: '同类问题表现不同', kind: 'CONTRADICTION', reason: '两次自述不同，不能归因于能力变化。', alternatives: '可能是提问范围不同。', supports: [0], counters: [1] };
test('pattern evidence must exist and retain counters; one feedback cannot masquerade as independent recurring observations', () => {
  assert.equal(validatePatterns({ patterns: [pattern] }, observations).length, 1);
  assert.throws(() => validatePatterns({ patterns: [{ ...pattern, counters: [8] }] }, observations));
  assert.throws(() => validatePatterns({ patterns: [{ ...pattern, counters: [] }] }, observations));
  assert.throws(() => validatePatterns({ patterns: [{ ...pattern, kind: 'COMMON', supports: [0], counters: [] }] }, observations));
  assert.throws(() => validatePatterns({ patterns: [{ ...pattern, kind: 'COMMON', supports: [0,1], counters: [] }] }, observations.map(o => ({ ...o, feedbackId: 'same' }))));
  assert.deepEqual(validatePatterns({ patterns: [] }, observations), []);
});
