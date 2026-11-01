/** Pure L2/L3 decision logic. The catalog is explicit; a selected plan is NOT a content catalog. */
import type { Difference, TaskInput } from './types';
import type { TrainingCatalogEntry } from './module1-contracts';
export type SharedDecisionKind = 'CONTENT' | 'STRATEGY' | 'PERSONAL_ONLY' | 'INSUFFICIENT_DATA';
export interface SharedDecision {
  kind: SharedDecisionKind; skillId: string | null; reason: string;
  missingCapabilities: string[]; catalogContentIds: string[];
}
export function decideSharedChange(input: TaskInput, difference: Difference,
  catalog: TrainingCatalogEntry[] | undefined, releasedContentSkills: string[] = []): SharedDecision {
  const skill = input.codebook.skills.find(s => s.id === difference.skillId);
  const base = { skillId: skill?.id ?? null, missingCapabilities: difference.missingCapabilityIds, catalogContentIds: [] as string[] };
  if (!skill || difference.usability !== 'USABLE' || difference.coverage === 'UNKNOWN')
    return { ...base, kind: 'INSUFFICIENT_DATA', reason: '问题或考点映射仍不明确，暂不改变共享内容和策略。' };
  if (!difference.gapCandidate) return { ...base, kind: 'PERSONAL_ONLY', reason: '没有可证实的准备覆盖缺口，不因此修改共享内容或选题。' };
  if (!catalog) return { ...base, kind: 'INSUFFICIENT_DATA', reason: '缺少可核验的训练内容目录，无法判断缺内容还是没有选到。' };
  const matching = catalog.filter(c => c.skillId === skill.id && c.status === 'ELIGIBLE_TEST_ONLY');
  const covered = new Set(matching.flatMap(c => c.coveredCapabilityIds));
  const fullContent = releasedContentSkills.includes(skill.id) || skill.capabilityIds.every(id => covered.has(id));
  const resultBase = { ...base, catalogContentIds: matching.map(c => c.contentId) };
  if (!fullContent) return { ...resultBase, kind: 'CONTENT', reason: `现有训练内容未覆盖「${skill.evidenceBoundary}」的全部能力单元，需要补充或修订共享场景。` };
  if (!input.plan.some(p => p.skillId === skill.id)) return { ...resultBase, kind: 'STRATEGY', reason: `「${skill.evidenceBoundary}」已有可用训练内容，但本次冻结计划没有选中；应在同等题量下比较选题方案。` };
  return { ...resultBase, kind: 'PERSONAL_ONLY', reason: '内容和选题都已覆盖该能力，先优先验证个人表现，不机械修改团队资产。' };
}

export interface StrategyCase {
  id: string; partition: 'DEVELOPMENT' | 'HOLDOUT'; focus: 'BASIC' | 'EXTRAPOLATION' | 'UNKNOWN';
  expectedSkillIds: string[]; budget: number;
}
export function validateCatalog(input: TaskInput, entries: TrainingCatalogEntry[]) {
  const seen = new Set<string>();
  if (!Array.isArray(entries) || entries.length > 100) throw new Error('训练内容目录无效。');
  for (const item of entries) {
    const skill = input.codebook.skills.find(s => s.id === item.skillId);
    if (!item.contentId || !item.version || seen.has(item.contentId) || !skill || item.status !== 'ELIGIBLE_TEST_ONLY' ||
      !Array.isArray(item.coveredCapabilityIds) || !item.coveredCapabilityIds.length ||
      item.coveredCapabilityIds.some(id => !skill.capabilityIds.includes(id)) ||
      !Array.isArray(item.evidenceIds) || item.evidenceIds.some(id => !input.evidence.some(e => e.id === id))) throw new Error('训练内容目录引用了不存在的能力或资料。');
    seen.add(item.contentId);
  }
}
export function validateStrategyCases(input: TaskInput, cases: StrategyCase[]) {
  if (!Array.isArray(cases) || cases.length > 30 || cases.some(c => !c.id ||
    !['DEVELOPMENT', 'HOLDOUT'].includes(c.partition) || !['BASIC','EXTRAPOLATION','UNKNOWN'].includes(c.focus) ||
    !Number.isInteger(c.budget) || c.budget < 1 || c.budget > 10 || !Array.isArray(c.expectedSkillIds) ||
    c.expectedSkillIds.some(s => !input.codebook.skills.some(x => x.id === s)))) throw new Error('选题对照样例无效。');
}
