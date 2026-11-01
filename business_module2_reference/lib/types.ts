export type Coverage = 'FULL' | 'PARTIAL' | 'NONE' | 'UNKNOWN';
export type Role = 'EMPLOYEE' | 'TRAINING_REVIEWER' | 'MEDICAL_REVIEWER' | 'PUBLISHER';
export interface LiveScope { tenant:string; actorId:string; reviewer:boolean; teams:{id:string;name:string;owners:string[]}[] }
export interface Actor { id: string; role: Role; scope?:LiveScope; }
export interface Evidence { id: string; version: string; title: string; content: string; usage: 'TEST_ONLY' | 'INTERNAL_READING'; }
export interface Capability { id: string; description: string; }
export interface Skill {
  id: string; topic: string; cognitiveTask: string; evidenceBoundary: string;
  capabilityIds: string[];
}
export interface PlanItem {
  skillId: string; question: string; rationale: string; evidenceIds: string[];
}
export interface TaskInput {
  origin?: { system: 'MODULE1'; sourceTaskId: string; sourceKind: 'sheets' | 'runs'; lessonId: string; revision: string; sourcePath: string; sourceHash: string; candidatePoolKnown: boolean };
  /** Frozen before the reported visit. The candidate set means generated candidates, not all possible questions. */
  forecastSnapshot?: {candidateSkillIds:string[];selectedSkillIds:string[];generatedAt:string;frozenAt:string;budget:number;note:string};
  fixtureId: string; title: string; knowledgeVersion: string; scenarioVersion: string; strategyVersion: string;
  codebook: { version: string; capabilities: Capability[]; skills: Skill[] };
  evidence: Evidence[]; plan: PlanItem[];
}
export interface Task {
  id: string; ownerId: string; title: string; status: 'READY' | 'CANCELED'; createdAt: string;
  snapshot: TaskInput & { id: string; hash: string; frozenAt: string; kind: 'TEST_FIXTURE' | 'MODULE1_SNAPSHOT' };
}
export interface RawVersion { id: string; version: number; text: string; hash: string; createdAt: string; source: 'TEXT' | 'VOICE_TRANSCRIPT'; }
export type StatementType = 'REPORTED_QUESTION' | 'SELF_REPORTED_RESPONSE' | 'INTERPRETATION' | 'MEDICAL_CLAIM' | 'CONTEXT' | 'UNKNOWN';
export interface DifficultyIndicator {
  kind: 'KNOWLEDGE_UNCERTAINTY' | 'BOUNDARY_OVERSTATEMENT' | 'FOLLOW_UP_BLOCK';
  quote: string; // verbatim substring of the containing SELF_REPORTED_RESPONSE unit
  capabilityIds: string[]; // model-proposed, codebook-constrained; [] when unclear
}
export interface Unit {
  id: string; startCp: number; endCp: number; excerpt: string; codes: string[];
  sourceAnchor?: 'EXACT_MODEL_SPAN' | 'UNIQUE_EXACT_QUOTE';
  modelSpan?: { startCp: number; endCp: number };
  types: StatementType[]; attribution: 'OTHER_REPORTED' | 'SELF' | 'UNSPECIFIED';
  certainty: 'REPORTED' | 'INTERPRETED' | 'UNKNOWN';
  skillIds: string[]; mapping: 'CANDIDATE' | 'UNMAPPED' | 'UNKNOWN';
  selfAssessment: ('GOOD' | 'DIFFICULTY' | 'UNKNOWN')[];
  difficultyIndicators?: DifficultyIndicator[];
}
export interface Relation { from: string; to: string; type: 'RESPONSE_TO' | 'REPORTED_SEQUENCE' | 'SELF_CORRECTION'; supportUnitIds: string[]; }
export interface Extraction { units: Unit[]; relations: Relation[]; }
export interface Difference {
  questionUnitId: string; skillId: string | null; usability: 'USABLE' | 'AMBIGUOUS';
  coverage: Coverage; comparedSkillIds: string[]; missingCapabilityIds: string[]; reason: string;
  performance: { unitId: string; kind: 'SELF_REPORTED_GOOD' | 'SELF_REPORTED_DIFFICULTY'; excerpt: string }[];
  personalSignal: 'PENDING_VERIFY' | 'SELF_REPORTED_SUCCESS' | 'UNKNOWN';
  gapCandidate: boolean;
}
/** D1: source-anchored observation, not a verified conversation fact or an L1/L2/L3 action. */
export interface Finding {
  id: string;
  kind: 'QUESTION' | 'UNLINKED_SELF_REPORT';
  questionUnitId?: string;
  responseUnitIds: string[];
  correctionUnitIds: string[];
  linkage: 'CONFIRMED' | 'CANDIDATE' | 'UNKNOWN';
  linkageEvidenceUnitIds: string[];
  skillIds: string[];
  evidence: Pick<Unit, 'id' | 'startCp' | 'endCp' | 'excerpt' | 'sourceAnchor'>[];
  assessment: { coverage: Coverage; personalSignal: 'PENDING_VERIFY' | 'SELF_REPORTED_SUCCESS' | 'PENDING_CONFIRMATION' | 'UNKNOWN' };
  eligibleForSharedChange: boolean;
  limitations: string[];
}
export interface Analysis extends Extraction {
  findings: Finding[];
  codebookVersion: string; model: string; promptVersion: string; differences: Difference[];
  limitations: string[];
}
export interface Screening { findings: { code: string; label: string }[]; version: string; }
export interface Feedback {
  id: string; taskId: string; ownerId: string; createdAt: string; versions: RawVersion[];
  state: 'SAVED' | 'PROCESSING' | 'FAILED' | 'ANALYZED' | 'RESTRICTED' | 'CANCELED';
  processingLease?: { token: string; expiresAt: number };
  analysis?: Analysis; analysisRawId?: string; errorCode?: string; screening?: Screening;
}
export interface ModelSettings { baseUrl: string; model: string; apiKey: string; authorized: boolean; thinking?: 'enabled' | 'disabled'; }
export type Provider = (text: string, codebook: TaskInput['codebook'], context?: Pick<TaskInput, 'title' | 'knowledgeVersion'> & { evidence?: Evidence[] }) => Promise<unknown>;

export type RiskState = 'OPEN' | 'RECEIVED' | 'IN_PROGRESS' | 'RESOLVED';
export interface RiskAction {
  type: 'ROUTED' | 'RECEIVED' | 'IN_PROGRESS' | 'RESOLVED'; actorId: string; role: Role;
  createdAt: string; note?: string;
}
export interface RiskCase {
  id: string; feedbackId: string; taskId: string; ownerId: string; rawId: string; rawVersion: number;
  recipientRole: 'MEDICAL_REVIEWER' | 'PUBLISHER'; findingCodes: string[];
  state: RiskState; revision: number; createdAt: string; history: RiskAction[];
  routingPolicy: 'test-routing-v1';
}
export type RiskSummary = Pick<RiskCase, 'id' | 'feedbackId' | 'taskId' | 'rawVersion' | 'recipientRole' | 'findingCodes' | 'state' | 'revision' | 'createdAt'>;
export interface RiskDetail extends RiskCase { rawText: string; superseded: boolean; }
