import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const ui=fs.readFileSync(new URL('../src/CoachStudio.tsx',import.meta.url),'utf8');
const api=fs.readFileSync(new URL('../src/api.ts',import.meta.url),'utf8');

test('course expression and visit simulation are separate visible tabs',()=>{
  assert.match(ui,/学课表达练习/);
  assert.match(ui,/访前模拟实战/);
  assert.match(ui,/tab==='visit-practice'/);
  assert.match(ui,/tab==='learn-practice'/);
});
test('visit simulation follows materials and previsit prediction freeze',()=>{
  assert.match(ui,/第一节 · 资料与依据/);
  assert.match(ui,/第二节 · 访前预测与重点/);
  assert.match(ui,/第三节 · 模拟实战对话/);
  assert.match(ui,/frozen&&<div className="studio-next-stage"/);
  assert.match(ui,/进入访前模拟实战/);
});
test('the two distinct real module1 modes are used',()=>{
  assert.match(ui,/startVisitPractice\(sheet\.id,optionId\)/);
  assert.match(ui,/startLesson\(lesson\)/);
  assert.match(ui,/r\.mode==='visit'\?'visit-practice':'learn-practice'/);
  assert.match(api,/\/v1\/mobile\/coach\/runs\/visit/);
  assert.match(api,/\/v1\/mobile\/coach\/runs\/learn/);
});
test('multi-turn answer, finish, feedback, help and retry retained',()=>{
  assert.match(ui,/<RealtimeVoice kind="coach"/);
  assert.doesNotMatch(ui,/<textarea[^>]*value=\{answer\}/);
  assert.match(ui,/finishCoachRun\(/);
  assert.match(ui,/supportCoachRun\(/);
  assert.match(ui,/retryCoachRun\(/);
  assert.match(ui,/r\.review/);
});
test('no direct old localhost or API secret on mobile',()=>{
  assert.doesNotMatch(ui,/127\.0\.0\.1|medrep_owner|OPENAI_API_KEY|sk-[A-Za-z0-9]/);
  assert.doesNotMatch(api,/medrep_owner/);
});
