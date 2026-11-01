/** Two unrelated fictional studies. Neither embeds extracted analyses nor desired decisions. */
import type { TaskInput } from './types';
import type { TrainingCatalogEntry } from './module1-contracts';
import type { StrategyCase } from './decision-engine';
import { mainFixture } from './fixture';
export function researchB(): TaskInput {
  return {
    fixtureId: 'fictional-research-b-v1', title: '虚构研究 B · 三个月观察窗口', knowledgeVersion: 'b-knowledge-v1', scenarioVersion: 'b-catalog-v1', strategyVersion: 'b-strategy-v1',
    codebook: { version: 'b-codebook-v1', capabilities: [
      { id: 'observation-window', description: '准确描述三个月观察窗口' },
      { id: 'long-term-limitation', description: '说明资料不包含一年后结果' },
      { id: 'uncertainty-expression', description: '解释未知信息时不作长期效果保证' },
    ], skills: [
      { id: 'window-explanation', topic: '虚构研究 B', cognitiveTask: '解释', evidenceBoundary: '观察窗口', capabilityIds: ['observation-window'] },
      { id: 'longterm-boundary-judgment', topic: '虚构研究 B', cognitiveTask: '评价证据边界', evidenceBoundary: '长期效果未知', capabilityIds: ['long-term-limitation', 'uncertainty-expression'] },
    ] },
    evidence: [{ id: 'B-E1', version: '1', title: '虚构研究 B 测试资料（非医学事实）', usage: 'TEST_ONLY', content: '此资料纯属虚构，观察窗口仅为三个月，不包含一年后的结果，不支持保证长期效果。没有真实药物、疾病或疗效数据。' }],
    plan: [{ skillId: 'window-explanation', question: '研究观察了多长时间？', rationale: '练习解释观察窗口。', evidenceIds: ['B-E1'] }],
  };
}
export function demoCatalog(input: TaskInput): TrainingCatalogEntry[] | undefined {
  if (input.fixtureId === 'research-a-main-v1' && input.knowledgeVersion === 'test-evidence-v1' && input.codebook.version === 'test-codebook-v1' && input.scenarioVersion.startsWith('SC1')) return [
    { contentId: 'A-content-endpoint', version: '1', skillId: 'endpoint-explanation', coveredCapabilityIds: ['endpoint'], evidenceIds: ['E1'], status: 'ELIGIBLE_TEST_ONLY' },
    { contentId: 'A-content-population', version: '1', skillId: 'population-explanation', coveredCapabilityIds: ['population'], evidenceIds: ['E1'], status: 'ELIGIBLE_TEST_ONLY' },
  ];
  if (input.fixtureId === 'fictional-research-b-v1' && input.knowledgeVersion === 'b-knowledge-v1' && input.codebook.version === 'b-codebook-v1' && input.scenarioVersion.startsWith('b-catalog-v1')) return [
    { contentId: 'B-content-window', version: '1', skillId: 'window-explanation', coveredCapabilityIds: ['observation-window'], evidenceIds: ['B-E1'], status: 'ELIGIBLE_TEST_ONLY' },
    { contentId: 'B-content-longterm', version: '1', skillId: 'longterm-boundary-judgment', coveredCapabilityIds: ['long-term-limitation','uncertainty-expression'], evidenceIds: ['B-E1'], status: 'ELIGIBLE_TEST_ONLY' },
  ];
  return undefined;
}
export function demoCases(input: TaskInput): StrategyCase[] | undefined {
  if (input.fixtureId === 'research-a-main-v1' && input.knowledgeVersion === 'test-evidence-v1' && input.codebook.version === 'test-codebook-v1' && input.scenarioVersion.startsWith('SC1')) return [
    { id: 'A-dev-routine', partition: 'DEVELOPMENT', focus: 'BASIC', expectedSkillIds: ['endpoint-explanation', 'population-explanation'], budget: 2 },
    { id: 'A-dev-boundary', partition: 'DEVELOPMENT', focus: 'EXTRAPOLATION', expectedSkillIds: ['endpoint-explanation', 'subgroup-extrapolation'], budget: 2 },
    { id: 'A-holdout-routine', partition: 'HOLDOUT', focus: 'BASIC', expectedSkillIds: ['endpoint-explanation','population-explanation'], budget: 2 },
    { id: 'A-holdout-boundary', partition: 'HOLDOUT', focus: 'EXTRAPOLATION', expectedSkillIds: ['endpoint-explanation','subgroup-extrapolation'], budget: 2 },
  ];
  if (input.fixtureId === 'fictional-research-b-v1' && input.knowledgeVersion === 'b-knowledge-v1' && input.codebook.version === 'b-codebook-v1' && input.scenarioVersion.startsWith('b-catalog-v1')) return [
    { id: 'B-dev-window', partition: 'DEVELOPMENT', focus: 'BASIC', expectedSkillIds: ['window-explanation'], budget: 1 },
    { id: 'B-dev-longterm', partition: 'DEVELOPMENT', focus: 'EXTRAPOLATION', expectedSkillIds: ['longterm-boundary-judgment'], budget: 1 },
    { id: 'B-holdout-window', partition: 'HOLDOUT', focus: 'BASIC', expectedSkillIds: ['window-explanation'], budget: 1 },
    { id: 'B-holdout-longterm', partition: 'HOLDOUT', focus: 'EXTRAPOLATION', expectedSkillIds: ['longterm-boundary-judgment'], budget: 1 },
  ];
  return undefined;
}
export const demoTasks = { A: mainFixture, B: researchB };
