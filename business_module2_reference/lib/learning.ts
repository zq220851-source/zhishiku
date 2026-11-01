import { randomUUID } from 'node:crypto';
import { Store, digest } from './store';
import { Module2Error, invalid, object, list, text } from './errors';
import { screen } from './analysis';
import { MODEL_REQUEST_TIMEOUT_MS } from './provider';
import type { Actor, Feedback, Task, DifficultyIndicator } from './types';
import type { Attempt, Context, Exercise, ExercisePurpose, Grade, Grader, LearningDashboard, LearningProfile, LearningSignal, LearningView, PersonalTrainingNeed } from './learning-types';

// This is a declared fictional-test policy, never a calibrated production mastery or spacing rule.
export const testLearningPolicy = { id: 'test-longitudinal-policy-v1', usage: 'TEST_ONLY' as const, reviewDays: 7 };
const day = 86400000;
const employee = (a: Actor) => { if (a.role !== 'EMPLOYEE') throw new Module2Error('FORBIDDEN', '此操作需要员工测试职责。', 403); };
type NeedSourceRecord = Omit<PersonalTrainingNeed, 'status' | 'evidenceStatus' | 'reason'> & { linked: boolean; selfReport: 'DIFFICULTY' | 'GOOD'; priorAttemptIds: string[] };

export function validateGrade(answer: string, value: unknown, exercise: Exercise): Grade {
  const data = object(value), seen = new Set<string>();
  const criteria = list(data.criteria, 100).map(value => {
    const c = object(value), id = text(c.id);
    if (!exercise.criteria.some(r => r.id === id) || seen.has(id) || !['SATISFIED', 'GAP', 'UNKNOWN'].includes(String(c.result))) invalid('评价项与固定标准不一致。');
    seen.add(id);
    if (typeof c.quote !== 'string' || (c.quote && !answer.includes(c.quote)) || (c.result === 'SATISFIED' && !c.quote.trim())) invalid('评价引用必须是作答原文；满足标准时需给出原话。');
    return { id, result: c.result as 'SATISFIED' | 'GAP' | 'UNKNOWN', quote: c.quote, reason: text(c.reason, 2000) };
  });
  if (seen.size !== exercise.criteria.length) invalid('评价未覆盖全部固定标准。');
  return { criteria, summary: text(data.summary, 3000) };
}
export class Learning {
  constructor(readonly store: Store, readonly clock = () => Date.now(), readonly knowledgeUsable: (snapshot: Task['snapshot']) => boolean = () => true) {
    store.db.exec(`CREATE TABLE IF NOT EXISTS learning_signals(id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, owner TEXT NOT NULL, feedback_id TEXT NOT NULL, raw_id TEXT NOT NULL, skill_id TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(owner,feedback_id,raw_id,skill_id));
      CREATE TABLE IF NOT EXISTS learning_need_sources(id TEXT PRIMARY KEY, owner TEXT NOT NULL, feedback_id TEXT NOT NULL, payload TEXT NOT NULL);
      CREATE TRIGGER IF NOT EXISTS learning_need_sources_immutable_update BEFORE UPDATE ON learning_need_sources BEGIN SELECT RAISE(ABORT,'need source is immutable'); END;
      CREATE TRIGGER IF NOT EXISTS learning_need_sources_immutable_delete BEFORE DELETE ON learning_need_sources BEGIN SELECT RAISE(ABORT,'need source is immutable'); END;
      CREATE TABLE IF NOT EXISTS learning_grades(attempt_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS learning_retractions(attempt_id TEXT PRIMARY KEY, payload TEXT NOT NULL);
      CREATE TRIGGER IF NOT EXISTS learning_grades_immutable_update BEFORE UPDATE ON learning_grades BEGIN SELECT RAISE(ABORT,'grade is immutable'); END;
      CREATE TRIGGER IF NOT EXISTS learning_grades_immutable_delete BEFORE DELETE ON learning_grades BEGIN SELECT RAISE(ABORT,'grade is immutable'); END;
      CREATE TRIGGER IF NOT EXISTS learning_signals_immutable_update BEFORE UPDATE ON learning_signals BEGIN SELECT RAISE(ABORT,'signal is immutable'); END;
      CREATE TRIGGER IF NOT EXISTS learning_signals_immutable_delete BEFORE DELETE ON learning_signals BEGIN SELECT RAISE(ABORT,'signal is immutable'); END;
      CREATE TRIGGER IF NOT EXISTS learning_retractions_immutable_update BEFORE UPDATE ON learning_retractions BEGIN SELECT RAISE(ABORT,'retraction is immutable'); END;
      CREATE TRIGGER IF NOT EXISTS learning_retractions_immutable_delete BEFORE DELETE ON learning_retractions BEGIN SELECT RAISE(ABORT,'retraction is immutable'); END;`);
  }
  now(actor: Actor) { const saved = this.store.list<{ days: number }>('learning-clock', actor.id)[0]; return this.clock() + (saved?.days ?? 0) * day; }
  private signals(profile: LearningProfile): LearningSignal[] {
    const rows = this.store.db.prepare('SELECT payload FROM learning_signals WHERE profile_id=? AND owner=?').all(profile.id, profile.ownerId) as { payload: string }[];
    return rows.map(r => JSON.parse(r.payload) as LearningSignal).filter(s => {
      const f = this.store.get<Feedback>(s.feedbackId, 'feedback', profile.ownerId);
      const t = this.store.get<Task>(f.taskId, 'task', profile.ownerId);
      return t.status === 'READY' && f.state === 'ANALYZED' && f.analysisRawId === s.rawId && f.versions.at(-1)?.id === s.rawId;
    });
  }
  private active(profile: LearningProfile): boolean {
    if (!this.knowledgeUsable(profile.snapshot)) return false;
    const independentPractice = this.attempts(profile).some(a => a.state === 'COMPLETED' && a.grade && !a.grade.criteria.some(c => c.result === 'UNKNOWN'));
    if (independentPractice) return true;
    if (profile.sourceProfileId) {
      if (profile.sourceAttemptId && this.store.db.prepare('SELECT attempt_id FROM learning_retractions WHERE attempt_id=?').get(profile.sourceAttemptId)) return false;
      return this.active(this.store.get<LearningProfile>(profile.sourceProfileId, 'learning-profile', profile.ownerId));
    }
    return this.signals(profile).length > 0;
  }
  /** Called inside the analysis transaction, or via an explicit sync for already analyzed records. */
  capture(actor: Actor, feedback: Feedback, task: Task) {
    if (actor.role !== 'EMPLOYEE' || feedback.ownerId !== actor.id || feedback.state !== 'ANALYZED' || task.status !== 'READY' || feedback.analysisRawId !== feedback.versions.at(-1)?.id) return;
    // The practice here is TEST_ONLY for *any* supplied and validated frozen task.
    if (task.snapshot.evidence.some(e => e.usage !== 'TEST_ONLY')) return;
    // Capture *both* linked and unlinked findings immutably. A raw revision clears the
    // mutable analysis cache but must not erase source evidence or historical decisions.
    for (const finding of feedback.analysis?.findings ?? []) {
      if (!['PENDING_VERIFY', 'PENDING_CONFIRMATION', 'SELF_REPORTED_SUCCESS'].includes(finding.assessment.personalSignal)) continue;
      const linked = finding.kind === 'QUESTION' && finding.linkage === 'CONFIRMED' && finding.responseUnitIds.length > 0;
      if (finding.kind === 'QUESTION' && !linked) continue;
      const reported = finding.evidence.filter(e => finding.responseUnitIds.includes(e.id));
      if (!reported.length) continue;
      const skillId = finding.skillIds.length === 1 ? finding.skillIds[0] : null;
      const skill = task.snapshot.codebook.skills.find(s => s.id === skillId);
      const indicators: DifficultyIndicator[] = finding.assessment.personalSignal === 'SELF_REPORTED_SUCCESS' ? [] :
        reported.filter(e => feedback.analysis?.units.some(u => u.id === e.id && u.selfAssessment.includes('DIFFICULTY')))
          .flatMap(e => feedback.analysis?.units.find(u => u.id === e.id)?.difficultyIndicators ?? []);
      const supported = [...new Set(indicators.flatMap(i => i.capabilityIds))];
      // C (prediction coverage) and P (personal ability) are independent. Never turn
      // missing planned capabilities into an unsupported claim of personal weakness.
      const target = skill ? (supported.length ? skill.capabilityIds.filter(id => supported.includes(id)) : [...skill.capabilityIds]) : [];
      const profileId = linked && skill ? `learning-${digest({ owner: actor.id, definition: skill, knowledge: task.snapshot.knowledgeVersion, codebook: task.snapshot.codebook.version, context: 'NORMAL' })}` : undefined;
      const needId = `need-${digest({ owner: actor.id, feedback: feedback.id, raw: feedback.analysisRawId, finding: finding.id })}`;
      const record: NeedSourceRecord = { needId, ownerId: actor.id, source: { taskId: task.id, feedbackId: feedback.id,
        rawId: feedback.analysisRawId!, findingId: finding.id, evidenceUnitIds: finding.evidence.map(e => e.id) },
        skillId, ...(profileId ? { profileId } : {}), knowledgeVersion: task.snapshot.knowledgeVersion,
        codebookVersion: task.snapshot.codebook.version, targetCapabilityIds: target,
        targetCapabilities: target.map(id => ({ id, description: task.snapshot.codebook.capabilities.find(c => c.id === id)!.description })),
        observedProblem: reported.map(e => e.excerpt).join(' ').slice(0, 2000),
        hypothesis: !indicators.length ? 'UNRESOLVED' : new Set(indicators.map(i => i.kind)).size === 1 ? indicators[0].kind : 'MULTIPLE',
        indicators,
        linked: linked && Boolean(skill), selfReport: finding.assessment.personalSignal === 'SELF_REPORTED_SUCCESS' ? 'GOOD' : 'DIFFICULTY',
        priorAttemptIds: profileId ? this.store.list<Attempt>('learning-attempt', actor.id).filter(a => a.profileId === profileId).map(a => a.id) : [] };
      const savedNeed = this.store.db.prepare('INSERT OR IGNORE INTO learning_need_sources VALUES(?,?,?,?)').run(needId, actor.id, feedback.id, JSON.stringify(record));
      if (savedNeed.changes) this.store.event(needId, actor.id, 'PERSONAL_TRAINING_NEED_CAPTURED', { feedbackId: feedback.id, rawId: feedback.analysisRawId, findingId: finding.id, linked });
    }
    // Only reliably linked findings may create an active practice profile.
    for (const difference of feedback.analysis?.differences ?? []) {
      const linkedFinding = feedback.analysis?.findings?.find(f => f.kind === 'QUESTION' && f.questionUnitId === difference.questionUnitId &&
        f.skillIds.includes(difference.skillId ?? '') && f.linkage === 'CONFIRMED' && f.responseUnitIds.length > 0);
      if (!linkedFinding || !difference.skillId || difference.personalSignal === 'UNKNOWN') continue;
      const skill = task.snapshot.codebook.skills.find(s => s.id === difference.skillId); if (!skill) continue;
      const id = `learning-${digest({ owner: actor.id, definition: skill, knowledge: task.snapshot.knowledgeVersion, codebook: task.snapshot.codebook.version, context: 'NORMAL' })}`;
      let profile = this.store.list<LearningProfile>('learning-profile', actor.id).find(p => p.id === id);
      if (!profile) {
        profile = { id, ownerId: actor.id, skillId: skill.id, label: skill.evidenceBoundary, context: 'NORMAL', snapshot: task.snapshot, createdAt: new Date().toISOString() };
        this.store.put(id, 'learning-profile', actor.id, profile);
      }
      const signal: LearningSignal = { id: randomUUID(), profileId: id, feedbackId: feedback.id, rawId: feedback.analysisRawId!, kind: difference.personalSignal === 'PENDING_VERIFY' ? 'DIFFICULTY' : 'GOOD', createdAt: new Date().toISOString() };
      const result = this.store.db.prepare('INSERT OR IGNORE INTO learning_signals VALUES(?,?,?,?,?,?,?)').run(signal.id, id, actor.id, feedback.id, signal.rawId, skill.id, JSON.stringify(signal));
      if (result.changes) this.store.event(id, actor.id, 'LEARNING_SIGNAL_LINKED', { feedbackId: feedback.id, rawId: signal.rawId, kind: signal.kind, policy: testLearningPolicy.id });
      const newDifficulty = Boolean(result.changes) && signal.kind === 'DIFFICULTY';
      if (newDifficulty) for (const pending of this.store.list<Exercise>('learning-exercise', actor.id).filter(e => e.profileId === profile!.id && e.state === 'PENDING')) {
        pending.state = 'PAUSED'; this.store.put(pending.id, 'learning-exercise', actor.id, pending);
      }
      this.ensureExercise(actor, profile, newDifficulty);
    }
  }
  /** Personal requests, including inactive historical sources. Evaluation is derived from the immutable grade ledger. */
  needs(actor: Actor): PersonalTrainingNeed[] {
    const rows = this.store.db.prepare('SELECT payload FROM learning_need_sources WHERE owner=? ORDER BY rowid ASC').all(actor.id) as { payload: string }[];
    const records = rows.map(r => JSON.parse(r.payload) as NeedSourceRecord);
    return records.map(record => {
      const f = this.store.get<Feedback>(record.source.feedbackId, 'feedback', actor.id);
      const t = this.store.get<Task>(record.source.taskId, 'task', actor.id);
      const currentSource = t.status === 'READY' && f.state === 'ANALYZED' && f.analysisRawId === record.source.rawId &&
        f.versions.at(-1)?.id === record.source.rawId && this.knowledgeUsable(t.snapshot);
      const valid = record.profileId ? this.store.list<LearningProfile>('learning-profile', actor.id).filter(p => p.id === record.profileId)
        .flatMap(profile => this.attempts(profile)).filter(a => a.state === 'COMPLETED' && !record.priorAttemptIds.includes(a.id)) : [];
      const last = valid[0];
      const evidenceStatus: PersonalTrainingNeed['evidenceStatus'] = last?.passed ? 'PRACTICE_IMPROVEMENT' : last?.grade?.criteria.some(c => c.result === 'GAP') ? 'PRACTICE_GAP' : 'SELF_REPORT_ONLY';
      const status: PersonalTrainingNeed['status'] = !currentSource ? 'SOURCE_STALE' : !record.linked ? 'AWAITING_CONFIRMATION' : last?.passed ? 'FOLLOW_UP' : 'READY_FOR_PRACTICE';
      return { needId: record.needId, ownerId: record.ownerId, source: record.source,
        skillId: record.skillId, ...(record.profileId ? { profileId: record.profileId } : {}),
        knowledgeVersion: record.knowledgeVersion, codebookVersion: record.codebookVersion,
        targetCapabilityIds: record.targetCapabilityIds, targetCapabilities: record.targetCapabilities, observedProblem: record.observedProblem,
        hypothesis: record.hypothesis, indicators: record.indicators ?? [], evidenceStatus, status,
        reason: !currentSource ? '原文、任务或知识版本已失效，暂不使用旧线索发起新训练。' : !record.linked ? '尚无可靠的问答关系或唯一考点，需澄清；不自动安排练习。' :
          last?.passed ? '练习出现改善证据；仍需复测、保持或迁移。' : record.selfReport === 'GOOD' ?
          '仅有自述成功，还没有独立练习证据；可做确认性练习。' : record.indicators?.length ? '有原话支持的困难类型线索，先针对该线索验证；不视为已证实能力不足。' : '有自述困难但成因尚不明确，先做验证练习；不视为已证实能力不足。' };
    });
  }
  sync(actor: Actor) {
    employee(actor);
    this.store.transaction(() => {
      for (const f of this.store.list<Feedback>('feedback', actor.id)) {
        const task = this.store.get<Task>(f.taskId, 'task', actor.id);
        const row = this.store.db.prepare('SELECT payload FROM frozen_plans WHERE id=?').get(task.snapshot.id) as { payload: string };
        this.capture(actor, f, { ...task, snapshot: JSON.parse(row.payload) });
      }
    });
    return this.dashboard(actor);
  }
  private attempts(profile: LearningProfile): Attempt[] {
    return this.store.list<Attempt>('learning-attempt', profile.ownerId).filter(a => a.profileId === profile.id).map(a => {
      const saved = this.store.db.prepare('SELECT payload FROM learning_grades WHERE attempt_id=?').get(a.id) as { payload: string } | undefined;
      const withdrawn = this.store.db.prepare('SELECT payload FROM learning_retractions WHERE attempt_id=?').get(a.id) as { payload: string } | undefined;
      return { ...a, ...(saved ? JSON.parse(saved.payload) : {}), ...(withdrawn ? { state: 'RETRACTED', retractionReason: JSON.parse(withdrawn.payload).reason } : {}) } as Attempt;
    }).sort((a,b) => b.submittedAt - a.submittedAt || b.recordedAt.localeCompare(a.recordedAt));
  }
  private view(actor: Actor, profile: LearningProfile): LearningView {
    const active = this.active(profile), attempts = this.attempts(profile);
    const latest = attempts.find(a => a.state === 'COMPLETED' && a.grade && !a.grade.criteria.some(c => c.result === 'UNKNOWN'));
    const current = this.now(actor);
    const state = !latest || !active ? 'UNVERIFIED' : latest.passed ? 'IMPROVING' : 'NEEDS_PRACTICE';
    const freshness = !latest ? 'NO_PRACTICE' : current >= latest.submittedAt + testLearningPolicy.reviewDays * day ? 'DUE' : 'CURRENT';
    const next = this.store.list<Exercise>('learning-exercise', actor.id).find(e => e.profileId === profile.id && e.state === 'PENDING');
    const newDifficulty = this.needs(actor).some(n => n.profileId === profile.id && n.status === 'READY_FOR_PRACTICE' && n.evidenceStatus === 'SELF_REPORT_ONLY');
    return { id: profile.id, label: profile.label, context: profile.context, state, freshness, active, sourceCount: this.signals(profile).length, attempts, next,
      reason: !active ? '来源复盘已变化或资料已停用，暂停相关训练；已有作答仍保留。' : newDifficulty ? '有新的本人困难待验证；过去改善证据保留，但不能抵消新的训练需求。' : !latest ? '当前只有自述或尚无明确评价，需要实际练习验证。' : latest.passed ? '已有改善证据，仍需换题、保持或迁移验证；不代表永久掌握。' : '在此能力和情境下观察到具体缺项，需要针对练习。' };
  }
  dashboard(actor: Actor): LearningDashboard {
    const simulatedDays = this.store.list<{ days: number }>('learning-clock', actor.id)[0]?.days ?? 0;
    return { policy: testLearningPolicy, now: this.now(actor), simulatedDays, profiles: this.store.list<LearningProfile>('learning-profile', actor.id).map(p => this.view(actor, p)), needs: this.needs(actor) };
  }
  private ensureExercise(actor: Actor, profile: LearningProfile, forceVerify = false) {
    if (!this.active(profile)) return;
    if (this.store.list<Exercise>('learning-exercise', actor.id).some(e => e.profileId === profile.id && e.state === 'PENDING')) return;
    const attempts = this.attempts(profile), valid = attempts.filter(a => a.state === 'COMPLETED');
    const last = valid[0], lastExercise = last ? this.store.get<Exercise>(last.exerciseId, 'learning-exercise', actor.id) : undefined;
    let purpose: ExercisePurpose = forceVerify ? 'VERIFY' : !last ? (profile.sourceProfileId ? 'TRANSFER' : 'VERIFY') : !last.passed ? 'VERIFY' : lastExercise?.purpose === 'VERIFY' || lastExercise?.purpose === 'TRANSFER' ? 'RETEST' : 'RETENTION';
    const current = this.now(actor);
    const dueAt = purpose === 'RETENTION' && last ? last.submittedAt + testLearningPolicy.reviewDays * day : current;
    const variant = this.store.list<Exercise>('learning-exercise', actor.id).filter(e => e.profileId === profile.id).length + 1;
    const frames = purpose === 'RETEST' ? '换一个问法：请向未参与前次交流的同事解释' : purpose === 'RETENTION' ? '间隔后重新作答，不查看之前的答案：请说明' : purpose === 'TRANSFER' ? '对方要求快速给出结论，请用简短但保留边界的回答说明' : '先做一次确认性练习：请说明';
    const skill = profile.snapshot.codebook.skills.find(s => s.id === profile.skillId)!;
    const currentNeeds = this.needs(actor).filter(n => n.profileId === profile.id && n.status !== 'SOURCE_STALE');
    const difficulty = [...currentNeeds].reverse().find(n => n.status === 'READY_FOR_PRACTICE') ?? currentNeeds.at(-1);
    // A failed graded answer narrows the next exercise to its exact missing capabilities;
    // a passing answer restores the whole skill for an independent retest.
    const gaps = last?.grade?.criteria.filter(c => c.result === 'GAP' && skill.capabilityIds.includes(c.id)).map(c => c.id) ?? [];
    const unknown = last?.grade?.criteria.filter(c => c.result === 'UNKNOWN' && skill.capabilityIds.includes(c.id)).map(c => c.id) ?? [];
    const targetCapabilityIds = !forceVerify && !last?.passed && gaps.length ? gaps : !forceVerify && !last?.passed && unknown.length ? unknown :
      [...new Set(difficulty?.targetCapabilityIds.length ? difficulty.targetCapabilityIds : skill.capabilityIds)];
    const targetDescriptions = targetCapabilityIds.map(id => profile.snapshot.codebook.capabilities.find(c => c.id === id)!.description);
    const observed = (!last || forceVerify) && difficulty?.observedProblem ? `复盘中的本人自述为“${difficulty.observedProblem.slice(0, 220)}”（仅作待验证线索，不认定现场事实）。` : '';
    const label: Record<DifficultyIndicator['kind'], string> = {
      KNOWLEDGE_UNCERTAINTY: '自述对知识或证据理解不确定', BOUNDARY_OVERSTATEMENT: '自述表达超过证据边界',
      FOLLOW_UP_BLOCK: '自述现场追问时解释卡住',
    };
    const focus = difficulty?.indicators ?? [];
    const cause = focus.length ? `原文线索：${focus.map(i => `${label[i.kind]}（“${i.quote}”）`).join('；')}；仅待验证，不等于评价结论。` : '';
    const causePrompts: Record<DifficultyIndicator['kind'], string> = {
      KNOWLEDGE_UNCERTAINTY: '请先说明给定资料支持什么、哪些信息无法确定，再解释相应能力目标。',
      BOUNDARY_OVERSTATEMENT: '请把原先说得过满的说法改成谨慎、符合资料边界的表达，并解释为什么这样改。',
      FOLLOW_UP_BLOCK: '模拟对方继续追问适用范围：请正面回应，再说明资料能够和不能支持什么。',
    };
    const subtypeQuestion = !last || forceVerify ? [...new Set(focus.map(i => i.kind))].map(kind => causePrompts[kind]).join('') : '';
    const trainingReason = !forceVerify && gaps.length && !last?.passed ? `上次作答仍缺少：${targetDescriptions.join('；')}。` :
      !forceVerify && unknown.length && !last?.passed ? `上次作答有尚无法确定的部分：${targetDescriptions.join('；')}。` :
      !last || forceVerify ? `${cause}根据本人复盘线索验证：${targetDescriptions.join('；')}。` : `采用新的问法再次验证：${targetDescriptions.join('；')}。`;
    const exercise: Exercise = { id: randomUUID(), ownerId: actor.id, profileId: profile.id, purpose, questionId: `${purpose.toLowerCase()}-${profile.context.toLowerCase()}-${variant}`,
      question: `${frames}“${profile.label}”。${observed}${trainingReason}${profile.context === 'PRESSURE' ? '情境：时间紧，对方催促直接下结论。' : '情境：常规学术讨论。'}${subtypeQuestion || '请解释结论及适用范围，不只罗列关键词。'}`,
      targetCapabilityIds, trainingReason, difficultyFocus: [...new Set(focus.map(i => i.kind))], ...(difficulty?.needId ? { sourceNeedId: difficulty.needId } : {}),
      material: profile.snapshot.evidence.map(e => `${e.title}（${e.id}@${e.version}）：${e.content}`).join('\n'), materialHash: digest(profile.snapshot.evidence), rubricVersion: 'test-capability-rubric-v1',
      criteria: [...targetCapabilityIds.map(id => ({ id, description: profile.snapshot.codebook.capabilities.find(c => c.id === id)!.description })), { id: 'evidence-boundary', description: '回答不超出虚构资料支持的范围，明确不确定性，不补造真实疗效或保证' }],
      dueAt, createdAt: new Date().toISOString(), ...(last ? { basedOnAttemptId: last.id } : {}), state: 'PENDING' };
    this.store.put(exercise.id, 'learning-exercise', actor.id, exercise);
    this.store.event(profile.id, actor.id, 'LEARNING_EXERCISE_CREATED', { exerciseId: exercise.id, purpose, dueAt, policy: testLearningPolicy.id });
  }
  advance(actor: Actor, days: unknown) {
    employee(actor); if (!Number.isSafeInteger(days) || Number(days) < 1 || Number(days) > 30) invalid('测试时间每次可推进 1～30 天。');
    this.store.transaction(() => {
      const prior = this.store.list<{ days: number }>('learning-clock', actor.id)[0]?.days ?? 0;
      this.store.put(`clock-${actor.id}`, 'learning-clock', actor.id, { days: prior + Number(days) });
      this.store.event(`clock-${actor.id}`, actor.id, 'TEST_LEARNING_CLOCK_ADVANCED', { days });
    });
    return this.dashboard(actor);
  }
  demands(actor: Actor) { return this.dashboard(actor).profiles.filter(p => p.active && p.next).map(p => ({ profileId: p.id, skill: p.label, context: p.context, purpose: p.next!.purpose, dueAt: p.next!.dueAt, due: p.next!.dueAt <= this.now(actor), reason: p.reason, exerciseId: p.next!.id, targetCapabilityIds: p.next!.targetCapabilityIds ?? [], sourceNeedId: p.next!.sourceNeedId ?? null })); }
  async submit(actor: Actor, exerciseId: string, answerValue: unknown, key: string, grader: Grader, model: string): Promise<Attempt> {
    employee(actor); const answer = text(answerValue, 12000);
    if (screen(answer).findings.length) throw new Module2Error('LEARNING_INPUT_RESTRICTED', '作答含需隔离的线索，已停止向模型发送，请先核对。', 409);
    const attempt = this.store.idempotent(`learning-answer:${actor.id}:${exerciseId}`, key, { answer }, () => {
      const exercise = this.store.get<Exercise>(exerciseId, 'learning-exercise', actor.id), profile = this.store.get<LearningProfile>(exercise.profileId, 'learning-profile', actor.id);
      if (!this.active(profile)) throw new Module2Error('LEARNING_SOURCE_STALE', '来源已更新，当前练习暂停。', 409);
      if (exercise.state !== 'PENDING') throw new Module2Error('EXERCISE_COMPLETED', '此题已有作答记录，请进入下一题。', 409);
      if (exercise.dueAt > this.now(actor)) throw new Module2Error('EXERCISE_NOT_DUE', '这项保持验证尚未到期；测试中可推进时间。', 409);
      const a: Attempt = { id: randomUUID(), ownerId: actor.id, profileId: exercise.profileId, exerciseId, answer, state: 'FAILED', submittedAt: this.now(actor), recordedAt: new Date().toISOString() };
      this.store.put(a.id, 'learning-attempt', actor.id, a); return { id: a.id, value: a };
    }, id => this.store.get<Attempt>(id, 'learning-attempt', actor.id));
    const token = randomUUID();
    const exercise = this.store.transaction(() => {
      const latest = this.store.get<Attempt>(attempt.id, 'learning-attempt', actor.id);
      const exercise = this.store.get<Exercise>(exerciseId, 'learning-exercise', actor.id);
      if (latest.state === 'COMPLETED' || latest.state === 'RETRACTED') return undefined;
      if (exercise.attemptId) {
        const processing = this.store.get<Attempt>(exercise.attemptId, 'learning-attempt', actor.id);
        if (processing.state === 'PROCESSING' && (processing.lease?.expiresAt ?? 0) > this.clock()) throw new Module2Error('ALREADY_PROCESSING', '本题正在评价，请稍候。', 409);
      }
      if (exercise.state !== 'PENDING') throw new Module2Error('EXERCISE_COMPLETED', '本题已经完成。', 409);
      latest.state = 'PROCESSING'; latest.lease = { token, expiresAt: this.clock() + MODEL_REQUEST_TIMEOUT_MS + 15000 }; exercise.attemptId = latest.id;
      this.store.put(latest.id, 'learning-attempt', actor.id, latest); this.store.put(exerciseId, 'learning-exercise', actor.id, exercise);
      return exercise;
    });
    if (!exercise) return this.store.get<Attempt>(attempt.id, 'learning-attempt', actor.id);
    try {
      const grade = validateGrade(answer, await grader(answer, exercise), exercise);
      return this.store.transaction(() => {
        const latest = this.store.get<Attempt>(attempt.id, 'learning-attempt', actor.id), liveExercise = this.store.get<Exercise>(exerciseId, 'learning-exercise', actor.id);
        const profile = this.store.get<LearningProfile>(attempt.profileId, 'learning-profile', actor.id);
        if (latest.lease?.token !== token || liveExercise.attemptId !== latest.id) return latest;
        if (liveExercise.state !== 'PENDING' || !this.active(profile)) { latest.state = 'FAILED'; latest.errorCode = 'LEARNING_SOURCE_STALE'; delete latest.lease; this.store.put(latest.id, 'learning-attempt', actor.id, latest); return latest; }
        latest.state = 'COMPLETED'; latest.grade = grade; latest.model = model; latest.passed = grade.criteria.every(c => c.result === 'SATISFIED'); delete latest.lease; delete latest.errorCode;
        this.store.db.prepare('INSERT INTO learning_grades VALUES(?,?)').run(latest.id, JSON.stringify({ grade, model, passed: latest.passed }));
        liveExercise.state = 'COMPLETED'; this.store.put(exerciseId, 'learning-exercise', actor.id, liveExercise); this.store.put(latest.id, 'learning-attempt', actor.id, latest);
        this.store.event(profile.id, actor.id, 'LEARNING_ATTEMPT_EVALUATED', { attemptId: latest.id, exerciseId, rubric: exercise.rubricVersion, model, passed: latest.passed, policy: testLearningPolicy.id });
        if (latest.passed && exercise.purpose === 'RETENTION' && profile.context === 'NORMAL') {
          const transferId = `${profile.id}-pressure`;
          const exists = this.store.list<LearningProfile>('learning-profile', actor.id).find(p => p.id === transferId);
          if (!exists) this.store.put(transferId, 'learning-profile', actor.id, { ...profile, id: transferId, context: 'PRESSURE', sourceProfileId: profile.id, sourceAttemptId: latest.id });
          this.ensureExercise(actor, this.store.get<LearningProfile>(transferId, 'learning-profile', actor.id));
        }
        this.ensureExercise(actor, profile); return latest;
      });
    } catch (error) {
      return this.store.transaction(() => {
        const latest = this.store.get<Attempt>(attempt.id, 'learning-attempt', actor.id);
        if (latest.lease?.token !== token) return latest;
        latest.state = 'FAILED'; latest.errorCode = error instanceof Module2Error ? error.code : 'EVALUATION_FAILED'; delete latest.lease;
        this.store.put(latest.id, 'learning-attempt', actor.id, latest); this.store.event(latest.profileId, actor.id, 'LEARNING_EVALUATION_FAILED', { attemptId: latest.id, code: latest.errorCode }); return latest;
      });
    }
  }
  retract(actor: Actor, id: string, reasonValue: unknown) {
    if (actor.role !== 'TRAINING_REVIEWER') throw new Module2Error('FORBIDDEN', '撤回评价需要培训审核职责。', 403);
    const reason = text(reasonValue, 2000);
    return this.store.transaction(() => {
      const attempt = this.store.get<Attempt>(id, 'learning-attempt', actor.id);
      if (attempt.state !== 'COMPLETED' && attempt.state !== 'RETRACTED') invalid('只能撤回已经完成的评价。');
      if (this.store.db.prepare('SELECT attempt_id FROM learning_retractions WHERE attempt_id=?').get(id)) return;
      this.store.db.prepare('INSERT INTO learning_retractions VALUES(?,?)').run(id, JSON.stringify({ reason, actorId: actor.id, role: actor.role, at: new Date().toISOString() }));
      attempt.state = 'RETRACTED'; this.store.put(id, 'learning-attempt', actor.id, attempt);
      for (const exercise of this.store.list<Exercise>('learning-exercise', actor.id)) {
        if (exercise.state === 'PENDING' && exercise.basedOnAttemptId === id) { exercise.state = 'PAUSED'; this.store.put(exercise.id, 'learning-exercise', actor.id, exercise); }
      }
      this.ensureExercise({ ...actor, role: 'EMPLOYEE' }, this.store.get<LearningProfile>(attempt.profileId, 'learning-profile', actor.id));
      this.store.event(attempt.profileId, actor.id, 'LEARNING_EVALUATION_RETRACTED', { attemptId: id, reasonHash: digest(reason), role: actor.role });
    });
  }
}
