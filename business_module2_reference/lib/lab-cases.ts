/** Transparent synthetic structured-analysis cases, NOT a claim of real model accuracy. */
import { mainFixture } from './fixture';
import { researchB, demoCatalog, demoCases } from './demo-data';
import { decideSharedChange } from './decision-engine';
import type { SharedDecisionKind } from './decision-engine';
import { compareStrategyCases } from './strategy';
import type { Difference, TaskInput } from './types';
import type { TrainingCatalogEntry } from './module1-contracts';
import type { StrategyCase } from './decision-engine';
export interface LabCase {
  id: string; study: 'A' | 'B'; title: string; utterance: string; skillId: string;
  coverage: Difference['coverage']; usable?: boolean; gap: boolean;
  catalog: 'DEFAULT' | 'MISSING' | 'PARTIAL'; released: string[];
  expected: SharedDecisionKind; why: string;
}
const CASES: LabCase[] = [
  { id: 'A1', study: 'A', title: '缺少共享训练内容', utterance: '医生后来问，这个亚组能不能推到别的人群。我那会儿没准备到这块，解释不清。', skillId: 'subgroup-extrapolation', coverage: 'NONE', gap: true, catalog: 'DEFAULT', released: [], expected: 'CONTENT', why: '准备未覆盖，场景目录中也没有完整亚组外推练习' },
  { id: 'A2', study: 'A', title: '补内容后仍没选到', utterance: '我这回准备终点和人群，医生却追问亚组外推，还是没练到。', skillId: 'subgroup-extrapolation', coverage: 'NONE', gap: true, catalog: 'DEFAULT', released: ['subgroup-extrapolation'], expected: 'STRATEGY', why: '模拟存在已审核的共享内容，但冻结计划仍未选择' },
  { id: 'A3', study: 'A', title: '只是个人解释不清', utterance: '这题我练过了，可真问起来，我把外推限制说得太绝对。', skillId: 'endpoint-explanation', coverage: 'FULL', gap: false, catalog: 'DEFAULT', released: [], expected: 'PERSONAL_ONLY', why: '该题已有准备覆盖，不以自述困难推定团队内容缺项' },
  { id: 'A4', study: 'A', title: '问题归属还不明确', utterance: '反正有个问题，我不记得具体问的是什么了。', skillId: 'subgroup-extrapolation', coverage: 'UNKNOWN', usable: false, gap: false, catalog: 'DEFAULT', released: [], expected: 'INSUFFICIENT_DATA', why: '问题不可用，不能强行归因' },
  { id: 'B1', study: 'B', title: '内容存在、选题未命中', utterance: '医生问一年之后呢？这个我们有训练材料，但这次没选，我当时卡住了。', skillId: 'longterm-boundary-judgment', coverage: 'NONE', gap: true, catalog: 'DEFAULT', released: [], expected: 'STRATEGY', why: '研究 B 有边界训练目录，但原计划只选观察窗口' },
  { id: 'B2', study: 'B', title: '目录缺失，不装作知道', utterance: '一年后是不是一样？我记得没准备这题。', skillId: 'longterm-boundary-judgment', coverage: 'NONE', gap: true, catalog: 'MISSING', released: [], expected: 'INSUFFICIENT_DATA', why: '缺少真实可验证的目录，不能把准备计划当目录' },
  { id: 'B3', study: 'B', title: '只覆盖了部分能力', utterance: '我知道只有三个月，但不知道怎么解释不能保证一年后的结果。', skillId: 'longterm-boundary-judgment', coverage: 'PARTIAL', gap: true, catalog: 'PARTIAL', released: [], expected: 'CONTENT', why: '目录仅有长期限制，没有不作保证的表达能力训练' },
  { id: 'B4', study: 'B', title: '已覆盖且本人自述顺利', utterance: '医生问观察多久，我说三个月，对方没有再问。', skillId: 'window-explanation', coverage: 'FULL', gap: false, catalog: 'DEFAULT', released: [], expected: 'PERSONAL_ONLY', why: '不能因有复盘就强行产生进化' },
  { id: 'B5', study: 'B', title: '考点映射仍未知', utterance: '医生突然问了个我不确定的问题，具体忘了。', skillId: 'non-existent', coverage: 'UNKNOWN', gap: true, catalog: 'DEFAULT', released: [], expected: 'INSUFFICIENT_DATA', why: '未映射到真实冻结考点' },
];
export function labCases(): LabCase[] { return CASES; }
export function labInput(c: LabCase): TaskInput { return c.study === 'A' ? mainFixture() : researchB(); }
export function labCatalog(c: LabCase): TrainingCatalogEntry[] | undefined {
  if (c.catalog === 'MISSING') return undefined;
  const catalog = demoCatalog(labInput(c))!;
  return c.catalog === 'PARTIAL' ? catalog.map(x => x.skillId === 'longterm-boundary-judgment' ?
    { ...x, coveredCapabilityIds: ['long-term-limitation'] } : x) : catalog;
}
export function labDifference(c: LabCase): Difference {
  return { questionUnitId: 'model-extracted-question', skillId: c.skillId, usability: c.usable === false ? 'AMBIGUOUS' : 'USABLE',
    coverage: c.coverage, comparedSkillIds: [], missingCapabilityIds: [], reason: '测试用的结构化分析输出',
    performance: [], personalSignal: 'PENDING_VERIFY', gapCandidate: c.gap };
}
export function evaluateLab(c: LabCase) {
  const input = labInput(c);
  const result = decideSharedChange(input, labDifference(c), labCatalog(c), c.released);
  const catalog = labCatalog(c);
  const available = [...new Set([...input.plan.map(p => p.skillId), ...(catalog ?? []).map(x => x.skillId), ...c.released])];
  const cases = demoCases(input) as StrategyCase[];
  const comparisons = compareStrategyCases(available, cases, input.plan.map(p => p.skillId), c.skillId);
  const preview = comparisons.find(r => r.partition === 'HOLDOUT' && r.added.length > 0);
  return { input, result, passed: result.kind === c.expected, preview, comparisons };
}
