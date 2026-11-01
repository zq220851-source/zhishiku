import type { TaskInput } from '../../lib/types';
/** Entirely fictional and independent of Research A. No pre-seeded analysis or decisions. */
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
    evidence: [{ id: 'B-E1', version: '1', title: '虚构研究 B 测试资料（非医学事实）', usage: 'TEST_ONLY',
      content: '此资料纯属虚构，观察窗口仅为三个月，不包含一年后的结果，不支持保证长期效果。没有真实药物、疾病或疗效数据。' }],
    plan: [{ skillId: 'window-explanation', question: '研究观察了多长时间？', rationale: '练习解释观察窗口。', evidenceIds: ['B-E1'] }],
  };
}
export const researchBRaw = '医生先问观察了多久，我说是三个月。后来问一年后也一样吗，我当时答不上来。回来觉得自己不会讲清长期边界。';
