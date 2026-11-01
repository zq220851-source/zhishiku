/**
 * Optional, real-model qualitative check. Uses only invented study A/B utterances.
 * Does not run in `npm test`, does not claim a clinically validated accuracy rate.
 * Run via `npm run test:live:difficulty` after explicitly authorizing test data.
 */
import { modelProvider, settings, configured, promptVersion } from '../lib/provider';
import { mainFixture } from '../lib/fixture';
import { researchB } from './fixtures/research-b';
import { derive, validateExtraction } from '../lib/analysis';
import type { DifficultyIndicator, TaskInput } from '../lib/types';

type Cause = DifficultyIndicator['kind'];
const cases: { title: string; input: TaskInput; raw: string; expected: Cause[]; excluded: Cause[] }[] = [
  { title: 'B: 自述知识不理解', input: researchB(),
    raw: '嗯，他问一年后效果还能不能一样。我那个三个月观察期跟一年后有没有数据，老实说我自己没弄懂，当时回答得也糊涂。',
    expected: ['KNOWLEDGE_UNCERTAINTY'], excluded: [] },
  { title: 'B: 自述保证过头', input: researchB(),
    raw: '医生问长期会不会一直有效。我当时说肯定可以，回来想想，说得太绝对了，资料根本没有一年后的东西。',
    expected: ['BOUNDARY_OVERSTATEMENT'], excluded: [] },
  { title: 'B: 对方追加追问时卡住', input: researchB(),
    raw: '他说三个月我懂，然后又追了一句一年后呢，我一下卡住，根本不知道怎么接那个追问。',
    expected: ['FOLLOW_UP_BLOCK'], excluded: [] },
  { title: 'B: 具体成因不清', input: researchB(),
    raw: '对方问一年后呢，我感觉这次讲得不太好，回来也有点别扭。',
    expected: [], excluded: ['KNOWLEDGE_UNCERTAINTY','BOUNDARY_OVERSTATEMENT','FOLLOW_UP_BLOCK'] },
  { title: 'A: 改口加追问', input: mainFixture(),
    raw: '医生问亚组能不能用到别的人群。我当时答应得太满了。后来他又问为什么能外推，我没解释出来。',
    expected: ['BOUNDARY_OVERSTATEMENT','FOLLOW_UP_BLOCK'], excluded: [] },
];

async function main() {
  const config = settings();
  if (!configured(config) || !config.authorized) throw new Error('需要服务端模型凭证和明确的虚构测试资料授权；本脚本不读取真实复盘。');
  const provider = modelProvider(config);
  let passes = 0;
  for (const sample of cases) {
    try {
      const result = validateExtraction(sample.raw, await provider(sample.raw, sample.input.codebook,
        { title: sample.input.title, knowledgeVersion: sample.input.knowledgeVersion }), sample.input.codebook);
      const kinds = [...new Set(result.units.flatMap(u => u.difficultyIndicators ?? []).map(i => i.kind))];
      const analysis = derive(result, sample.input, config.model, promptVersion);
      const pass = sample.expected.every(kind => kinds.includes(kind)) && sample.excluded.every(kind => !kinds.includes(kind));
      if (pass) passes++;
      console.log(JSON.stringify({ title: sample.title, pass, kinds, expected: sample.expected,
        excerpts: result.units.filter(u => u.selfAssessment.includes('DIFFICULTY')).map(u => u.excerpt),
        personalSignals: analysis.differences.map(d => d.personalSignal) }, null, 2));
    } catch (error) {
      console.error(JSON.stringify({ title: sample.title, pass: false,
        error: error instanceof Error ? error.message : String(error) }, null, 2));
    }
  }
  console.log(`真实模型虚构口语样例：${passes}/${cases.length} 场通过；仅是定性回归，不是准确率估计。`);
  if (passes !== cases.length) process.exitCode = 1;
}
main().catch(error => { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; });
