import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
const api=fs.readFileSync(new URL('../src/api.ts',import.meta.url),'utf8');
const ui=fs.readFileSync(new URL('../src/CoachStudio.tsx',import.meta.url),'utf8');
const app=fs.readFileSync(new URL('../src/App.tsx',import.meta.url),'utf8');
test('employee-authenticated coach routes exist',()=>{for(const p of ['/v1/mobile/coach/sheets','/v1/mobile/coach/prepare','/v1/mobile/coach/runs']) assert.ok(api.includes(p))});
test('mobile never calls old module localhost or accepts upstream owner',()=>{assert.doesNotMatch(ui,/127\.0\.0\.1|medrep_owner|localhost:\d+/);assert.doesNotMatch(api,/medrep_owner/);});
test('freeze requires actual previsit user confirmation',()=>{assert.match(ui,/previsit_confirmed:true|freezeVisit\(/);assert.match(ui,/真实拜访尚未发生/)});
test('practice retries retain request identity',()=>{assert.match(ui,/\/resume/);const engine=fs.readFileSync(new URL('../../business_module1_reference/workflow.py',import.meta.url),'utf8');assert.match(engine,/request_id.*pending\['id'\]/)});
test('coach embedded into main workspace',()=>{assert.match(app,/<CoachStudio demo=\{demo\}/)});
