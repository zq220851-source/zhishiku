import { randomUUID } from 'node:crypto';
import type { Actor, Feedback, RawVersion, RiskCase, RiskDetail, RiskState, RiskSummary, Screening } from './types';
import { Store, digest } from './store';
import { invalid, Module2Error, text } from './errors';

const team = 'module2-single-test-team';
const summary = (c: RiskCase): RiskSummary => ({ id: c.id, feedbackId: c.feedbackId, taskId: c.taskId, rawVersion: c.rawVersion,
  recipientRole: c.recipientRole, findingCodes: c.findingCodes, state: c.state, revision: c.revision, createdAt: c.createdAt });
/** Internal TEST receiving responsibilities, not real pharmacovigilance or enterprise reporting destinations. */
export class RiskInbox {
  constructor(readonly store: Store) {
    store.db.exec(`CREATE TABLE IF NOT EXISTS risk_routes(raw_id TEXT NOT NULL REFERENCES frozen_raw(id), recipient_role TEXT NOT NULL, case_id TEXT NOT NULL UNIQUE, PRIMARY KEY(raw_id,recipient_role));
      CREATE TRIGGER IF NOT EXISTS risk_routes_no_update BEFORE UPDATE ON risk_routes BEGIN SELECT RAISE(ABORT,'risk route is immutable'); END;
      CREATE TRIGGER IF NOT EXISTS risk_routes_no_delete BEFORE DELETE ON risk_routes BEGIN SELECT RAISE(ABORT,'risk route is immutable'); END;`);
  }
  /** Caller transaction makes isolation, raw storage and routing atomic. No raw text is copied into the inbox/audit log. */
  route(feedback: Feedback, raw: RawVersion, screening: Screening) {
    const groups = new Map<RiskCase['recipientRole'], string[]>();
    for (const finding of screening.findings) {
      const role = finding.code === 'SPECIAL_REPORT' ? 'MEDICAL_REVIEWER' : 'PUBLISHER';
      groups.set(role, [...groups.get(role) ?? [], finding.code]);
    }
    for (const [role, codes] of groups) {
      if (this.store.db.prepare('SELECT case_id FROM risk_routes WHERE raw_id=? AND recipient_role=?').get(raw.id, role)) continue;
      const id = randomUUID(), createdAt = new Date().toISOString();
      const risk: RiskCase = { id, feedbackId: feedback.id, taskId: feedback.taskId, ownerId: feedback.ownerId, rawId: raw.id,
        rawVersion: raw.version, recipientRole: role, findingCodes: [...new Set(codes)], state: 'OPEN', revision: 1, createdAt, routingPolicy: 'test-routing-v1',
        history: [{ type: 'ROUTED', actorId: 'SYSTEM', role, createdAt }] };
      this.store.put(id, 'risk-case', team, risk);
      this.store.db.prepare('INSERT INTO risk_routes VALUES(?,?,?)').run(raw.id, role, id);
      this.store.event(id, 'SYSTEM', 'RISK_ROUTED', { feedbackId: feedback.id, rawId: raw.id, recipientRole: role, findingCodes: codes, policy: risk.routingPolicy });
    }
  }
  private record(id: string): RiskCase { return this.store.get<RiskCase>(id, 'risk-case', team); }
  private receive(actor: Actor, risk: RiskCase) {
    if (actor.role !== risk.recipientRole) throw new Module2Error('FORBIDDEN', '当前职责不是该事项的接收职责。', 403);
  }
  list(actor: Actor): RiskSummary[] {
    return this.store.list<RiskCase>('risk-case', team)
      .filter(c => actor.role === 'EMPLOYEE' ? c.ownerId === actor.id : c.recipientRole === actor.role).map(summary);
  }
  detail(actor: Actor, id: string): RiskDetail {
    const risk = this.record(id); this.receive(actor, risk);
    const raw = this.store.db.prepare('SELECT payload FROM frozen_raw WHERE id=? AND owner=? AND feedback_id=?').get(risk.rawId, risk.ownerId, risk.feedbackId) as { payload: string } | undefined;
    if (!raw) throw new Module2Error('NOT_FOUND', '隔离原文不存在。', 404);
    const feedback = this.store.get<Feedback>(risk.feedbackId, 'feedback', risk.ownerId);
    return { ...risk, rawText: (JSON.parse(raw.payload) as RawVersion).text, superseded: feedback.versions.at(-1)?.id !== risk.rawId };
  }
  update(actor: Actor, id: string, state: unknown, expectedRevision: unknown, note: unknown, key: string): RiskSummary {
    const original = this.record(id); this.receive(actor, original);
    if (!Number.isSafeInteger(expectedRevision) || Number(expectedRevision) < 1) invalid('请提供事项当前版本。');
    if (!['RECEIVED', 'IN_PROGRESS', 'RESOLVED'].includes(String(state))) invalid('不支持的处理状态。');
    const target = state as RiskState;
    const reason = note === undefined || note === '' ? undefined : text(note, 2000);
    if (target === 'RESOLVED' && !reason) invalid('结束处理需要记录结果说明。');
    return this.store.idempotent(`risk:${actor.id}:${actor.role}:${id}`, key, { target, expectedRevision, reason }, () => {
      const current = this.record(id); this.receive(actor, current);
      if (current.revision !== expectedRevision) throw new Module2Error('VERSION_CONFLICT', '事项已更新，请刷新后处理。', 409);
      const next: Partial<Record<RiskState, RiskState>> = { OPEN: 'RECEIVED', RECEIVED: 'IN_PROGRESS', IN_PROGRESS: 'RESOLVED' };
      if (next[current.state] !== target) throw new Module2Error('INVALID_TRANSITION', '请先确认接收，再开始和结束处理。', 409);
      current.state = target; current.revision++;
      current.history.push({ type: target as 'RECEIVED' | 'IN_PROGRESS' | 'RESOLVED', actorId: actor.id, role: actor.role, createdAt: new Date().toISOString(), ...(reason ? { note: reason } : {}) });
      this.store.put(id, 'risk-case', team, current);
      this.store.event(id, actor.id, `RISK_${target}`, { role: actor.role, revision: current.revision, ...(reason ? { noteHash: digest(reason) } : {}) });
      return { id, value: summary(current) };
    }, replayId => { const current = this.record(replayId); this.receive(actor, current); return summary(current); });
  }
}
