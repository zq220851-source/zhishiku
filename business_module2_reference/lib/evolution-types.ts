import type { TaskInput, Evidence } from './types';
export interface SourceRef { ownerId: string; feedbackId: string; rawId: string; taskId: string; excerpt: string; signal: string; coverage: string; }
export interface Proposal {
  scope?: { fixtureId: string; knowledgeVersion: string; codebookVersion: string; scenarioVersion: string };
  id: string; version: number; kind: 'CONTENT' | 'STRATEGY'; skillId: string; label: string; question: string; answer: string;
  reason: string; alternatives: string[]; sources: SourceRef[]; evidence: Evidence[]; hash: string;
  state: 'DRAFT' | 'REVIEWING' | 'BLOCKED' | 'READY' | 'PUBLISHED' | 'RECALLED';
  medical?: AgentReview; training?: { approved: boolean; reason: string; actor: string; hash: string };
  publication?: AgentReview; checks?: { name: string; passed: boolean }[];
  lease?: { token: string; until: number }; error?: string; releaseId?: string;
}
export interface AgentReview { agent: 'MEDICAL' | 'PUBLICATION'; decision: 'PASS' | 'BLOCK'; reason: string; citations: { evidenceId: string; quote: string }[]; hash: string; at: string; model: string; }
export interface Release { scope?: Proposal['scope']; id: string; proposalId: string; proposalHash: string; kind: 'CONTENT' | 'STRATEGY'; skillId: string; label: string; question: string; answer: string; evidence: Evidence[]; createdAt: string; }
export interface Use { id: string; ownerId: string; taskId: string; releaseIds: string[]; strategyId: string; selectedSkills: string[]; at: string; }
export interface StrategyInput { focus: 'BASIC' | 'EXTRAPOLATION' | 'UNKNOWN'; budget: number; prioritySkillId?: string; baselineSkillIds?: string[]; }
export interface Comparison { partition: 'DEVELOPMENT' | 'HOLDOUT'; caseId: string; old: string[]; next: string[]; added: string[]; lost: string[]; valid: boolean; }
export type Reviewer = (proposal: Proposal, checks: { name: string; passed: boolean }[], role: 'MEDICAL' | 'PUBLICATION') => Promise<Omit<AgentReview, 'hash' | 'at' | 'model' | 'agent'>>;
export interface EvolutionView { proposalComparisons?: Record<string, Comparison[]>; pendingDecisions?: { study: string; skillId: string | null; status: 'INSUFFICIENT_DATA' | 'PERSONAL_ONLY'; reason: string }[]; proposals: Proposal[]; releases: (Release & { active: boolean; uses: number; feedback: number; difficulties: number })[]; comparisons: Comparison[]; knowledgeAvailable: boolean; }
export interface KnowledgePort { read(): Evidence[]; }
export type NextInput = TaskInput;
