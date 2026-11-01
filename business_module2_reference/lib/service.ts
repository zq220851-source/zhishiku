import { randomUUID } from 'node:crypto';
import type { Actor, Feedback, Provider, RawVersion, Task } from './types';
import { Store, digest } from './store';
import { Module2Error, invalid, object, text } from './errors';
import { validateTaskInput } from './fixture';
import { derive, screen, validateExtraction } from './analysis';
import { Evolution } from './evolution';
import { Learning } from './learning';
import { RiskInbox } from './risk-inbox';
import { MODEL_REQUEST_TIMEOUT_MS, promptVersion } from './provider';

const now = () => new Date().toISOString();
const employee = (actor: Actor) => { if (actor.role !== 'EMPLOYEE') throw new Module2Error('FORBIDDEN', '当前操作需要员工测试职责。', 403); };
export class Service {
  readonly learning: Learning;
  readonly evolution: Evolution;
  readonly risks: RiskInbox;
  constructor(readonly store: Store, learningClock?: () => number) { this.risks = new RiskInbox(store); this.evolution = new Evolution(store); this.learning = new Learning(store, learningClock, snapshot => this.evolution.knowledgeUsable(snapshot)); }
  createTask(actor: Actor, input: unknown, key: string): Task {
    employee(actor); const data = validateTaskInput(input);
    return this.store.idempotent(`task:${actor.id}`, key, data, () => {
      const id = randomUUID(), timestamp = now();
      const snapshot = { ...data, id: randomUUID(), hash: digest(data), frozenAt: timestamp, kind: data.origin ? 'MODULE1_SNAPSHOT' as const : 'TEST_FIXTURE' as const };
      const task: Task = { id, ownerId: actor.id, title: data.title, status: 'READY', createdAt: timestamp, snapshot };
      this.store.db.prepare('INSERT INTO frozen_plans VALUES(?,?)').run(snapshot.id, JSON.stringify(snapshot));
      this.store.put(id, 'task', actor.id, task); this.store.event(id, actor.id, 'TASK_CREATED', { snapshotId: snapshot.id, hash: snapshot.hash });
      return { id, value: task };
    }, id => this.getTask(actor, id));
  }
  getTask(actor: Actor, id: string): Task {
    const task = this.store.get<Task>(id, 'task', actor.id);
    // Frozen data is read from the immutable record, not from the mutable entity cache.
    const row = this.store.db.prepare('SELECT payload FROM frozen_plans WHERE id=?').get(task.snapshot.id) as { payload: string };
    return { ...task, snapshot: JSON.parse(row.payload) };
  }
  tasks(actor: Actor): Task[] { return this.store.list<Task>('task', actor.id).map(t => this.getTask(actor, t.id)); }
  feedback(actor: Actor, taskId: string): Feedback[] { this.getTask(actor, taskId); return this.store.list<Feedback>('feedback', actor.id).filter(f => f.taskId === taskId).map(f => this.getFeedback(actor, f.id)); }
  getFeedback(actor: Actor, id: string): Feedback {
    const feedback = this.store.get<Feedback>(id, 'feedback', actor.id);
    const rows = this.store.db.prepare('SELECT payload FROM frozen_raw WHERE feedback_id=? AND owner=? ORDER BY version').all(id, actor.id) as { payload: string }[];
    return { ...feedback, versions: rows.map(r => JSON.parse(r.payload)) };
  }
  cancel(actor: Actor, id: string): Task {
    employee(actor);
    return this.store.transaction(() => {
      const task = this.getTask(actor, id); task.status = 'CANCELED';
      this.store.put(id, 'task', actor.id, task);
      for (const feedback of this.feedback(actor, id)) {
        if (feedback.state !== 'PROCESSING') continue;
        feedback.state = 'CANCELED'; delete feedback.processingLease;
        this.store.put(feedback.id, 'feedback', actor.id, feedback);
        this.store.event(feedback.id, actor.id, 'ANALYSIS_CANCELED');
      }
      this.store.event(id, actor.id, 'TASK_CANCELED'); return task;
    });
  }
  saveRaw(actor: Actor, taskId: string, value: unknown, key: string, feedbackId?: string): Feedback {
    employee(actor); const input = object(value), raw = text(input.text, 20000);
    if (input.confirmed !== true || input.exchangeOccurred !== true) invalid('请确认原文并确认交流已发生。');
    if (input.source !== undefined && !['TEXT','VOICE_TRANSCRIPT'].includes(String(input.source))) invalid('不支持的原文来源。');
    const expectedVersion = input.expectedVersion;
    if (feedbackId && (!Number.isSafeInteger(expectedVersion) || Number(expectedVersion) < 1)) invalid('请提供当前原文版本。');
    const scope = feedbackId ? `revise:${actor.id}:${feedbackId}` : `submit:${actor.id}:${taskId}`;
    return this.store.idempotent(scope, key, { taskId, raw, expectedVersion, source: input.source ?? 'TEXT' }, () => {
      const task = this.getTask(actor, taskId);
      if (task.status !== 'READY') throw new Module2Error('TASK_CANCELED', '交流已取消，不能提交或分析复盘。', 409);
      const previous = feedbackId ? this.getFeedback(actor, feedbackId) : undefined;
      if (previous && previous.taskId !== taskId) throw new Module2Error('NOT_FOUND', '该复盘不属于此任务。', 404);
      if (previous && previous.versions.at(-1)!.version !== expectedVersion) throw new Module2Error('VERSION_CONFLICT', '原文已被修改，请刷新核对。', 409);
      if (previous?.versions.at(-1)!.text === raw) return { id: previous.id, value: previous };
      const version: RawVersion = { id: randomUUID(), version: (previous?.versions.at(-1)?.version ?? 0) + 1, text: raw, hash: digest(raw), createdAt: now(), source: input.source === 'VOICE_TRANSCRIPT' ? 'VOICE_TRANSCRIPT' : 'TEXT' };
      const result: Feedback = { id: previous?.id ?? randomUUID(), ownerId: actor.id, taskId, createdAt: previous?.createdAt ?? now(), versions: [...previous?.versions ?? [], version], state: 'SAVED' };
      this.store.db.prepare('INSERT INTO frozen_raw VALUES(?,?,?,?,?)').run(version.id, result.id, actor.id, version.version, JSON.stringify(version));
      const screening = screen(raw);
      if (screening.findings.length) { result.state = 'RESTRICTED'; result.screening = screening; }
      this.store.put(result.id, 'feedback', actor.id, result);
      if (screening.findings.length) {
        this.store.event(result.id, actor.id, 'RISK_ISOLATED', { rawId: version.id, screeningVersion: screening.version });
        this.risks.route(result, version, screening);
      }
      this.store.event(result.id, actor.id, previous ? 'RAW_REVISED' : 'RAW_CONFIRMED', { rawId: version.id, version: version.version, hash: version.hash });
      return { id: result.id, value: result };
    }, id => this.getFeedback(actor, id));
  }
  async analyze(actor: Actor, id: string, expectedVersion: number, provider: Provider, model: string): Promise<Feedback> {
    employee(actor);
    const claimed = this.store.transaction(() => {
      const feedback = this.getFeedback(actor, id), task = this.getTask(actor, feedback.taskId), raw = feedback.versions.at(-1)!;
      if (task.status !== 'READY') throw new Module2Error('TASK_CANCELED', '交流已取消，不分析覆盖。', 409);
      if (raw.version !== expectedVersion) throw new Module2Error('VERSION_CONFLICT', '原文已更新，请刷新。', 409);
      if (feedback.state === 'ANALYZED' && feedback.analysisRawId === raw.id) return { cached: true as const, feedback, task, raw };
      if (feedback.state === 'PROCESSING' && (feedback.processingLease?.expiresAt ?? 0) > Date.now()) throw new Module2Error('ALREADY_PROCESSING', '当前原文正在分析。', 409);
      const screening = screen(raw.text); feedback.screening = screening;
      feedback.state = screening.findings.length ? 'RESTRICTED' : 'PROCESSING';
      delete feedback.errorCode;
      if (screening.findings.length) { delete feedback.processingLease; this.risks.route(feedback, raw, screening); }
      else feedback.processingLease = { token: randomUUID(), expiresAt: Date.now() + MODEL_REQUEST_TIMEOUT_MS + 15000 };
      this.store.put(id, 'feedback', actor.id, feedback);
      this.store.event(id, actor.id, feedback.state === 'RESTRICTED' ? 'RISK_ISOLATED' : 'ANALYSIS_STARTED', { rawId: raw.id, screeningVersion: screening.version });
      return { cached: false as const, feedback, task, raw };
    });
    if (claimed.cached || claimed.feedback.state === 'RESTRICTED') return claimed.feedback;
    try {
      const extraction = validateExtraction(claimed.raw.text, await provider(claimed.raw.text, claimed.task.snapshot.codebook, { title: claimed.task.title, knowledgeVersion: claimed.task.snapshot.knowledgeVersion, ...(claimed.task.snapshot.origin ? {evidence: claimed.task.snapshot.evidence} : {}) }), claimed.task.snapshot.codebook);
      const analysis = derive(extraction, claimed.task.snapshot, model, promptVersion);
      return this.finish(actor, id, claimed.raw.id, claimed.feedback.processingLease!.token, feedback => ({ ...feedback, state: 'ANALYZED', analysis, analysisRawId: claimed.raw.id }));
    } catch (error) {
      const code = error instanceof Module2Error ? error.code : 'MODEL_REQUEST_FAILED';
      return this.finish(actor, id, claimed.raw.id, claimed.feedback.processingLease!.token, feedback => ({ ...feedback, state: 'FAILED', errorCode: code }));
    }
  }
  private finish(actor: Actor, id: string, rawId: string, token: string, update: (f: Feedback) => Feedback): Feedback {
    return this.store.transaction(() => {
      const feedback = this.getFeedback(actor, id);
      if (feedback.versions.at(-1)!.id !== rawId || feedback.processingLease?.token !== token || this.getTask(actor, feedback.taskId).status !== 'READY') { this.store.event(id, actor.id, 'STALE_RESULT_DISCARDED', { rawId }); return feedback; }
      const result = update(feedback); delete result.processingLease; this.store.put(id, 'feedback', actor.id, result);
      if (result.state === 'ANALYZED' && !this.getTask(actor, result.taskId).snapshot.origin) this.learning.capture(actor, result, this.getTask(actor, result.taskId));
      this.store.event(id, actor.id, result.state === 'ANALYZED' ? 'ANALYSIS_COMPLETED' : 'ANALYSIS_FAILED', { rawId, code: result.errorCode });
      return result;
    });
  }
}
