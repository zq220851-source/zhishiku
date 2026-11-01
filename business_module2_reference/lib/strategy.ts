import type { Comparison, StrategyInput } from './evolution-types';
import type { StrategyCase } from './decision-engine';
import { demoCases } from './demo-data';
import { mainFixture } from './fixture';
/** Capacity is fixed between baseline and proposed selection; no outcome labels are passed to the selector. */
export function selectSkills(available: string[], input: StrategyInput, strategy: 'BASELINE' | 'FOCUS'): string[] {
  const capacity = Math.max(0, Math.min(10, Math.floor(input.budget)));
  const base = [...new Set([...(input.baselineSkillIds ?? available), ...available])].filter(s => available.includes(s));
  if (strategy === 'BASELINE' || input.focus !== 'EXTRAPOLATION' || !input.prioritySkillId || !available.includes(input.prioritySkillId)) return base.slice(0, capacity);
  // Keep the first baseline anchor only when capacity >1; re-rank the remaining slot without increasing work.
  const anchor = capacity > 1 ? base.slice(0, 1) : [];
  const order = [...new Set([...anchor, input.prioritySkillId, ...base])];
  return order.slice(0, capacity);
}
/** Authored independent test cases: evaluate two selectors against the same content and budget. */
export function compareStrategyCases(available: string[], cases: StrategyCase[], baseline: string[], prioritySkillId: string): Comparison[] {
  return cases.map(c => {
    const args: StrategyInput = { focus: c.focus, budget: c.budget, prioritySkillId, baselineSkillIds: baseline };
    const old = selectSkills(available, args, 'BASELINE'), next = selectSkills(available, args, 'FOCUS');
    return { partition: c.partition, caseId: c.id, old, next,
      added: next.filter(id => c.expectedSkillIds.includes(id) && !old.includes(id)),
      lost: old.filter(id => c.expectedSkillIds.includes(id) && !next.includes(id)),
      valid: old.length === next.length && old.length <= c.budget && c.expectedSkillIds.every(id => available.includes(id)) };
  });
}
/** Legacy A demo preview; production/generic decisions call compareStrategyCases with their own fixtures. */
export function compareStrategies(available: string[]): Comparison[] {
  const input = mainFixture();
  return compareStrategyCases(available, demoCases(input)!, input.plan.map(p => p.skillId), 'subgroup-extrapolation');
}
