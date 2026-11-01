/** Explicit live acceptance: invented representative speech, no real patient or doctor data. */
import { loadEnvConfig } from '@next/env';
import { writeFileSync } from 'node:fs';
import { Store } from '../lib/store';
import { Service } from '../lib/service';
import { mainFixture } from '../lib/fixture';
import { modelProvider, settings } from '../lib/provider';
import { learningGrader } from '../lib/learning-provider';

const cases = [
  { name: '讲不清，先带回问题', text: '今天去拜访，主任时间挺紧的。我刚讲完研究，他就指着亚组那张图问，说那换成没入组的那类病人，是不是也一样？我当时有点卡住，只说这个我回去再核实一下，没往下解释。出来以后想想，这块我确实没讲明白。前面那个主要终点，他也问了一句，我按准备的讲了，感觉还行吧，但他没表态。', expectDifficulty: true },
  { name: '不知道对方是否听懂', text: '今天这个拜访特别短，我就把研究那几页过了一下。主任一直点头，最后说行，资料放这儿。我也不知道他是听明白了还是赶时间，反正没怎么问。不能说我讲得有多好，具体他关心啥我也没摸出来。', expectDifficulty: false },
  { name: '改口，否定自己最初的印象', text: '我一开始觉得今天答得还不错。哦不对，后来主任问，那个亚组看着挺好，换一类人是不是也能这么理解？我顺嘴就说应该差不多。回来翻了一下材料才发现自己说满了，那张图不能这么往外套。下次再被追问，我还真不太会把这个边界讲清楚。', expectDifficulty: true },
];
async function main() {
  loadEnvConfig(process.cwd()); const config = settings(); const store = new Store(':memory:'); const service = new Service(store);
  const results: any[] = [];
  const originalFetch = globalThis.fetch; let wireCount = 0;
  globalThis.fetch = async (input, init) => { const r = await originalFetch(input, init); if (process.argv.includes('--trace')) { const wire = await r.clone().text(); writeFileSync(`.data/rep-wire-${++wireCount}.json`, wire.replaceAll(config.apiKey, '[REDACTED]'), {mode: 0o600}); } return r; };
  try {
    for (const [index, c] of cases.entries()) {
      if (process.argv.includes('--correction-only') && index !== 2) continue;
      const actor = { id: `fictional-rep-${index}`, role: 'EMPLOYEE' as const };
      const task = service.createTask(actor, mainFixture(), 'task');
      const f = service.saveRaw(actor, task.id, { text: c.text, confirmed: true, exchangeOccurred: true }, 'raw');
      const analyzed = await service.analyze(actor, f.id, 1, modelProvider(config), config.model);
      const profiles = service.learning.dashboard(actor).profiles;
      const differences = analyzed.analysis?.differences ?? [];
      const checks = {
        analysisCompleted: analyzed.state === 'ANALYZED',
        originalPreserved: analyzed.versions.at(-1)?.text === c.text,
        noInstantAbilityJudgment: profiles.every(p => p.state === 'UNVERIFIED'),
        expectedSignal: c.expectDifficulty ? differences.some(d => d.skillId === 'subgroup-extrapolation' && d.personalSignal === 'PENDING_VERIFY') : profiles.length === 0,
      };
      const result: any = { name: c.name, spokenReflection: c.text, analysisState: analyzed.state, errorCode: analyzed.errorCode, checks, differences, practice: [] };
      if (index === 0) {
        const p = profiles.find(p => p.label === '亚组结果及外推限制');
        if (p?.next) {
          for (const [n, answer] of [
            '我可能会说，主任，图上这个趋势看着还行，换一类人应该也差不太多吧。不过具体我也不太确定，得回去问问。',
            '主任，我刚才那句说得太满了。这张亚组图只能当个继续研究的线索，不能就按这个说换一类人也一样。那类人到底适不适用，还得另外找证据，这份材料我现在给不了您这个结论。',
          ].entries()) {
            const current = service.learning.dashboard(actor).profiles.find(x => x.id === p.id)!;
            const attempt = await service.learning.submit(actor, current.next!.id, answer, `answer-${n}`, learningGrader(config), config.model);
            result.practice.push({ answer, state: attempt.state, passed: attempt.passed, feedback: attempt.grade, error: attempt.errorCode, next: service.learning.dashboard(actor).profiles.find(x => x.id === p.id)?.next?.purpose });
          }
        }
        result.checks.overclaimCaught = result.practice[0]?.state === 'COMPLETED' && result.practice[0]?.passed === false;
        result.checks.naturalCorrectAnswerAccepted = result.practice[1]?.state === 'COMPLETED' && result.practice[1]?.passed === true;
      }
      results.push(result);
      console.log(JSON.stringify({ case: c.name, checks: result.checks }));
    }
    writeFileSync((process.argv.includes('--correction-only') ? 'docs/药代改口复测.json' : 'docs/药代自然口述实测.json'), JSON.stringify({ at: new Date().toISOString(), model: config.model, fictional: true, results }, null, 2));
    if (results.some(r => Object.values(r.checks).some(v => !v))) process.exitCode = 1;
  } finally { globalThis.fetch = originalFetch; store.close(); }
}
main().catch(() => { console.error('实测未完成，未输出密钥或请求详情。'); process.exitCode = 1; });
