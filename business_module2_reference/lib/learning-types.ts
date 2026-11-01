import type { Task, DifficultyIndicator } from './types';
export type Context = 'NORMAL' | 'PRESSURE';
export type ExercisePurpose = 'VERIFY' | 'RETEST' | 'RETENTION' | 'TRANSFER';
export interface LearningProfile {
  id: string; ownerId: string; skillId: string; label: string; context: Context;
  snapshot: Task['snapshot']; createdAt: string; sourceProfileId?: string; sourceAttemptId?: string;
}
export interface LearningSignal { id: string; profileId: string; feedbackId: string; rawId: string; kind: 'DIFFICULTY' | 'GOOD'; createdAt: string; }
export interface Criterion { id: string; description: string; }
export interface Exercise {
  id: string; ownerId: string; profileId: string; purpose: ExercisePurpose; questionId: string; question: string;
  targetCapabilityIds: string[]; trainingReason: string; sourceNeedId?: string; difficultyFocus?: DifficultyIndicator['kind'][];
  material: string; materialHash: string; rubricVersion: 'test-capability-rubric-v1'; criteria: Criterion[];
  dueAt: number; createdAt: string; basedOnAttemptId?: string; state: 'PENDING' | 'COMPLETED' | 'PAUSED'; attemptId?: string;
}
export interface Grade {
  criteria: { id: string; result: 'SATISFIED' | 'GAP' | 'UNKNOWN'; quote: string; reason: string }[];
  summary: string;
}
export interface Attempt {
  id: string; ownerId: string; profileId: string; exerciseId: string; answer: string;
  submittedAt: number; recordedAt: string; state: 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'RETRACTED';
  lease?: { token: string; expiresAt: number }; errorCode?: string;
  grade?: Grade; model?: string; passed?: boolean; retractionReason?: string;
}
export type Grader = (answer: string, exercise: Exercise) => Promise<unknown>;
/** D2: a source-backed request for future module 1 training; neither a diagnosis nor a score. */
export interface PersonalTrainingNeed {
  needId: string; ownerId: string;
  source: { taskId: string; feedbackId: string; rawId: string; findingId: string; evidenceUnitIds: string[] };
  skillId: string | null; profileId?: string; knowledgeVersion: string; codebookVersion: string;
  targetCapabilityIds: string[]; targetCapabilities: { id: string; description: string }[]; observedProblem: string;
  /** Anchored self-reported possibilities, never an objective diagnosis or graded ability. */
  hypothesis: DifficultyIndicator['kind'] | 'UNRESOLVED' | 'MULTIPLE';
  indicators: DifficultyIndicator[];
  evidenceStatus: 'SELF_REPORT_ONLY' | 'PRACTICE_GAP' | 'PRACTICE_IMPROVEMENT';
  status: 'AWAITING_CONFIRMATION' | 'READY_FOR_PRACTICE' | 'FOLLOW_UP' | 'SOURCE_STALE';
  reason: string;
}
export interface LearningView {
  id: string; label: string; context: Context; state: 'UNVERIFIED' | 'NEEDS_PRACTICE' | 'IMPROVING';
  freshness: 'NO_PRACTICE' | 'CURRENT' | 'DUE'; reason: string; sourceCount: number;
  attempts: Attempt[]; next?: Exercise; active: boolean;
}
export interface LearningDashboard { policy: { id: string; usage: 'TEST_ONLY'; reviewDays: number }; now: number; simulatedDays: number; profiles: LearningView[]; needs: PersonalTrainingNeed[]; }
