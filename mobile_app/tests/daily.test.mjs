import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const api = fs.readFileSync(new URL('../src/api.ts', import.meta.url), 'utf8');
const app = fs.readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8');
const daily = fs.readFileSync(new URL('../src/DailyWorkspace.tsx', import.meta.url), 'utf8');
test('daily route is employee-Bearer API only', () => {
  assert.match(api, /\/v1\/mobile\/daily\/industry/);
  assert.match(api, /Authorization:`Bearer \$\{token\}`/);
  assert.doesNotMatch(api, /\/api\/digest\?mode=sample/);
});
test('daily screen rejects mock content, displays provenance and review warnings', () => {
  assert.match(app, /f.id==='daily'&&<DailyWorkspace demo=\{demo\}/);
  assert.match(daily, /limitations/);
  assert.match(daily, /原始来源/);
  assert.match(daily, /if\(demo\)return/);
  assert.match(daily, /rel="noopener noreferrer"/);
});
