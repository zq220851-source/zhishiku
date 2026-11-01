import { loadEnvConfig } from '@next/env';
import { writeFileSync } from 'node:fs';
import assert from 'node:assert/strict';
import { Store } from '../lib/store';
import { Service } from '../lib/service';
import { mainFixture } from '../lib/fixture';
import { settings, modelProvider } from '../lib/provider';
import { evolutionReviewer } from '../lib/evolution-provider';
async function main() {
  loadEnvConfig(process.cwd()); const config = settings(), store = new Store(':memory:'), s = new Service(store);
  const actor = { id: 'fictional-full-loop', role: 'EMPLOYEE' as const }; const report: unknown[] = [];
  try {
    const t = s.createTask(actor, mainFixture(), 'initial');
    const f = s.saveRaw(actor, t.id, { text: '今天主任看着亚组那张图问，换一类病人是不是也差不多？我没敢往下说，就答应回去查一下。说实话这块我还真不太会讲。', confirmed: true, exchangeOccurred: true }, 'raw');
    const analyzed = await s.analyze(actor, f.id, 1, modelProvider(config), config.model); assert.equal(analyzed.state, 'ANALYZED');
    for (const kind of ['CONTENT','STRATEGY']) {
      s.evolution.discover(actor); const p = s.evolution.view(actor).proposals.find(p => p.kind === kind)!; assert.ok(p);
      s.evolution.training({ ...actor, role: 'TRAINING_REVIEWER' }, p.id, p.hash, true, '虚构测试：目标与资料边界一致，同意此用途，非正式评分批准。');
      const done = await s.evolution.continueAgents(actor, p.id, evolutionReviewer(config), config.model);
      report.push(done); console.log(JSON.stringify({ kind, state: done.state, error: done.error, checks: done.checks })); assert.equal(done.state, 'PUBLISHED');
    }
    const next = s.createTask(actor, s.evolution.nextInput({ focus: 'EXTRAPOLATION', budget: 2 }), 'next'); s.evolution.recordUse(actor, next);
    assert.ok(next.snapshot.plan.some(p => p.skillId === 'subgroup-extrapolation'));
    assert.ok(!s.getTask(actor, t.id).snapshot.plan.some(p => p.skillId === 'subgroup-extrapolation'));
    report.push({ oldPlan: t.snapshot.plan, nextPlan: next.snapshot.plan, observation: s.evolution.view(actor).releases });
    console.log('虚构口述→医学Agent→培训测试审核→发布Agent→内容/策略版本→下一次实际选用：通过');
  } finally { writeFileSync('docs/整模块主流程实测.json', JSON.stringify({ at: new Date().toISOString(), model: config.model, report }, null, 2)); store.close(); }
}
main().catch(e => { console.error(e instanceof assert.AssertionError ? e.message : '主流程实测未完成'); process.exitCode = 1; });
