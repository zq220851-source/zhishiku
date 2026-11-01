/**
 * D0 TEST-ONLY contracts for eventual module 1 handoff. These are local, synchronous-in-memory
 * fixtures behind async interfaces; no module 1 business code is imported or simulated.
 */
import type { Evidence, TaskInput } from './types';
import { validateTaskInput } from './fixture';
import { createHash } from 'node:crypto';
const digest = (value: unknown) => createHash('sha256').update(JSON.stringify(value)).digest('hex');

export type SourceStatus = 'NOT_FOUND' | 'VERSION_MISMATCH' | 'NOT_AVAILABLE' | 'UNAUTHORIZED';
export type SourceResult<T> = { status: 'OK'; value: T; usedVersions: Record<string, string> } |
  { status: SourceStatus; reason: string };
export interface SnapshotRequest { taskId: string; snapshotHash?: string; }
export interface TaskSnapshotContract { taskId: string; snapshotHash: string; usage: 'TEST_ONLY'; input: TaskInput; }
export interface EvidenceRequest extends SnapshotRequest { knowledgeVersion: string; evidenceIds: string[]; }
export interface CatalogRequest extends SnapshotRequest { scenarioVersion: string; }
export interface TrainingCatalogEntry {
  contentId: string; version: string; skillId: string; coveredCapabilityIds: string[]; evidenceIds: string[];
  status: 'ELIGIBLE_TEST_ONLY';
}
export interface TrainingRequest extends SnapshotRequest { requestId: string; skillId: string; }
export interface NextPreparationRequest extends SnapshotRequest { requestId: string; }
export interface TaskSnapshotSource { readTask(request: SnapshotRequest): Promise<SourceResult<TaskSnapshotContract>>; }
export interface KnowledgeEvidenceSource { readEvidence(request: EvidenceRequest): Promise<SourceResult<Evidence[]>>; }
export interface TrainingCatalogSource { readCatalog(request: CatalogRequest): Promise<SourceResult<TrainingCatalogEntry[]>>; }
export interface TrainingExecutionPort { execute(request: TrainingRequest): Promise<SourceResult<{ executionId: string }>>; }
export interface NextPreparationPort { prepare(request: NextPreparationRequest): Promise<SourceResult<{ preparedTaskId: string }>>; }

const unavailable = <T>(reason: string): SourceResult<T> => ({ status: 'NOT_AVAILABLE', reason });
/** Explicitly unavailable: an offline fixture must not fabricate practice grades or next-round task consumption. */
export const unavailableTrainingExecution: TrainingExecutionPort = { async execute() { return unavailable('模块 1 训练执行器尚未接入。'); } };
export const unavailableNextPreparation: NextPreparationPort = { async prepare() { return unavailable('模块 1 下一轮准备器尚未接入。'); } };

const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;
type FixtureRecord = { taskId: string; input: TaskInput; catalog?: TrainingCatalogEntry[] };
/** Test data stand-in only; catalog existence is not inferred from a codebook or a selected plan. */
export class FixtureModule1Sources implements TaskSnapshotSource, KnowledgeEvidenceSource, TrainingCatalogSource {
  private records = new Map<string, { snapshot: TaskSnapshotContract; catalog?: TrainingCatalogEntry[] }>();
  constructor(records: FixtureRecord[]) {
    for (const record of records) {
      if (!record.taskId || this.records.has(record.taskId)) throw new Error('测试任务 ID 缺失或重复。');
      const input = validateTaskInput(record.input), snapshotHash = digest(input);
      if (record.catalog) {
        const ids = new Set<string>();
        for (const content of record.catalog) {
          const skill = input.codebook.skills.find(s => s.id === content.skillId);
          if (!content.contentId || !content.version || ids.has(content.contentId) || !skill || content.status !== 'ELIGIBLE_TEST_ONLY' ||
            !content.coveredCapabilityIds.length || content.coveredCapabilityIds.some(id => !skill.capabilityIds.includes(id)) ||
            content.evidenceIds.some(id => !input.evidence.some(e => e.id === id))) {
            throw new Error('测试训练目录引用了不存在的能力或证据。');
          }
          ids.add(content.contentId);
        }
      }
      this.records.set(record.taskId, { snapshot: { taskId: record.taskId, snapshotHash, usage: 'TEST_ONLY', input: copy(input) },
        ...(record.catalog ? { catalog: copy(record.catalog) } : {}) });
    }
  }
  private lookup(request: SnapshotRequest): SourceResult<{ snapshot: TaskSnapshotContract; catalog?: TrainingCatalogEntry[] }> {
    const found = this.records.get(request.taskId);
    if (!found) return { status: 'NOT_FOUND', reason: '不存在对应测试任务。' };
    if (request.snapshotHash !== undefined && request.snapshotHash !== found.snapshot.snapshotHash) return { status: 'VERSION_MISMATCH', reason: '冻结任务快照版本不匹配。' };
    return { status: 'OK', value: found, usedVersions: { snapshotHash: found.snapshot.snapshotHash } };
  }
  async readTask(request: SnapshotRequest): Promise<SourceResult<TaskSnapshotContract>> {
    const result = this.lookup(request);
    return result.status === 'OK' ? { status: 'OK', value: copy(result.value.snapshot), usedVersions: result.usedVersions } : result;
  }
  async readEvidence(request: EvidenceRequest): Promise<SourceResult<Evidence[]>> {
    if (!request.snapshotHash) return { status: 'VERSION_MISMATCH', reason: '读取资料必须提供冻结任务快照版本。' };
    const result = this.lookup(request); if (result.status !== 'OK') return result;
    const input = result.value.snapshot.input;
    if (request.knowledgeVersion !== input.knowledgeVersion) return { status: 'VERSION_MISMATCH', reason: '测试知识版本不匹配。' };
    const evidence = request.evidenceIds.map(id => input.evidence.find(e => e.id === id));
    if (evidence.some(e => !e)) return { status: 'NOT_FOUND', reason: '请求的资料在冻结版本中不存在。' };
    return { status: 'OK', value: copy(evidence as Evidence[]), usedVersions: { ...result.usedVersions, knowledgeVersion: input.knowledgeVersion } };
  }
  async readCatalog(request: CatalogRequest): Promise<SourceResult<TrainingCatalogEntry[]>> {
    if (!request.snapshotHash) return { status: 'VERSION_MISMATCH', reason: '读取训练目录必须提供冻结任务快照版本。' };
    const result = this.lookup(request); if (result.status !== 'OK') return result;
    const input = result.value.snapshot.input;
    if (request.scenarioVersion !== input.scenarioVersion) return { status: 'VERSION_MISMATCH', reason: '训练目录版本不匹配。' };
    if (!result.value.catalog) return unavailable('该冻结任务没有可核验的训练内容目录；不能据此判断 L2/L3。');
    return { status: 'OK', value: copy(result.value.catalog), usedVersions: { ...result.usedVersions, scenarioVersion: input.scenarioVersion } };
  }
}
