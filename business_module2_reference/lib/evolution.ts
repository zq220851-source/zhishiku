import { randomUUID } from 'node:crypto';
import { Store, digest } from './store';
import { Module2Error, text } from './errors';
import { mainFixture } from './fixture';
import { demoCatalog, demoCases } from './demo-data';
import { decideSharedChange, validateCatalog, validateStrategyCases } from './decision-engine';
import type { TrainingCatalogEntry } from './module1-contracts';
import type { StrategyCase } from './decision-engine';
import { screen } from './analysis';
import { compareStrategies, compareStrategyCases, selectSkills } from './strategy';
import type { Actor, Feedback, Task, TaskInput } from './types';
import type { AgentReview, EvolutionView, KnowledgePort, Proposal, Release, Reviewer, SourceRef, StrategyInput, Use } from './evolution-types';
const TEAM = 'single-test-team';
const stamp = () => new Date().toISOString();
function requireRole(actor: Actor, role: Actor['role']) { if (actor.role !== role) throw new Module2Error('FORBIDDEN', '当前职责不能执行此操作。', 403); }
export class Evolution {
  constructor(readonly store: Store, readonly knowledge: KnowledgePort = { read: () => mainFixture().evidence }) {
    store.db.exec(`CREATE TABLE IF NOT EXISTS evolution_archive(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
      CREATE TRIGGER IF NOT EXISTS evolution_archive_no_update BEFORE UPDATE ON evolution_archive BEGIN SELECT RAISE(ABORT,'immutable evolution version'); END;
      CREATE TRIGGER IF NOT EXISTS evolution_archive_no_delete BEFORE DELETE ON evolution_archive BEGIN SELECT RAISE(ABORT,'immutable evolution version'); END;`);
  }
  private proposals() { return this.store.list<Proposal>('proposal', TEAM); }
  private releaseRecords() { return (this.store.db.prepare("SELECT payload FROM evolution_archive WHERE id LIKE 'release-%'").all() as { payload: string }[]).map(r => JSON.parse(r.payload) as Release); }
  private evidence() { const withdrawn = this.store.list<{ id: string; version: string }>('knowledge-withdrawal', TEAM); return this.knowledge.read().filter(e => e.usage === 'TEST_ONLY' && !withdrawn.some(w => w.id === e.id && w.version === e.version)); }
  private evidenceValid(p: { evidence: Proposal['evidence']; scope?: Proposal['scope']; sources?: SourceRef[] }) {
    if (!p.evidence.length) return false;
    let allowed = this.evidence();
    if (p.scope && p.sources?.length) {
      try { allowed = this.store.get<Task>(p.sources[0].taskId, 'task', p.sources[0].ownerId).snapshot.evidence; }
      catch { return false; }
    }
    const withdrawn = this.store.list<{ id: string; version: string }>('knowledge-withdrawal', TEAM);
    return p.evidence.every(e => e.usage === 'TEST_ONLY' && allowed.some(k => k.id === e.id && k.version === e.version && k.content === e.content && k.usage === e.usage) &&
      !withdrawn.some(w => w.id === e.id && w.version === e.version));
  }
  /** Optional explicit catalog+cases for an arbitrary frozen task; absence remains UNKNOWN. */
  registerCatalog(actor: Actor, task: Task, entries: TrainingCatalogEntry[], cases?: StrategyCase[]) {
    requireRole(actor, 'EMPLOYEE');
    if (task.ownerId !== actor.id) throw new Module2Error('FORBIDDEN', '不能注册其他员工的目录。', 403);
    try { validateCatalog(task.snapshot, entries); if (cases) validateStrategyCases(task.snapshot, cases); }
    catch (e) { throw new Module2Error('INVALID_INPUT', e instanceof Error ? e.message : '无效目录。'); }
    const id = `catalog-${task.id}`;
    const existing = this.store.list<{ id: string }>('test-catalog', actor.id).find(c => c.id === id);
    if (existing) throw new Module2Error('VERSION_CONFLICT', '任务目录已冻结，不可覆盖。', 409);
    this.store.put(id, 'test-catalog', actor.id, { id, snapshotHash: task.snapshot.hash, entries, cases });
    this.store.event(task.id, actor.id, 'TEST_CATALOG_FROZEN', { catalogCount: entries.length, caseCount: cases?.length ?? 0 });
  }
  private catalog(task: Task): TrainingCatalogEntry[] | undefined {
    const row = this.store.list<{ id: string; snapshotHash: string; entries: TrainingCatalogEntry[] }>('test-catalog', task.ownerId).find(x => x.id === `catalog-${task.id}`);
    return row ? row.snapshotHash === task.snapshot.hash ? row.entries : undefined : demoCatalog(task.snapshot);
  }
  private cases(task: Task): StrategyCase[] | undefined {
    const row = this.store.list<{ id: string; snapshotHash: string; cases?: StrategyCase[] }>('test-catalog', task.ownerId).find(x => x.id === `catalog-${task.id}`);
    return row ? row.snapshotHash === task.snapshot.hash ? row.cases : undefined : demoCases(task.snapshot);
  }
  private matchingReleases(task: Task) {
    return this.releaseRecords().filter(r => this.active(r) && r.scope?.fixtureId === task.snapshot.fixtureId && r.scope.knowledgeVersion === task.snapshot.knowledgeVersion && r.scope.codebookVersion === task.snapshot.codebook.version);
  }
  private available(task: Task) {
    const entries = this.catalog(task);
    if (!entries) return undefined;
    const releases = this.matchingReleases(task).filter(r => r.kind === 'CONTENT');
    return [...new Set([...task.snapshot.plan.map(p => p.skillId), ...entries.map(e => e.skillId), ...releases.map(r => r.skillId)])];
  }
  private sourceValid(ref: SourceRef) {
    const f = this.store.get<Feedback>(ref.feedbackId, 'feedback', ref.ownerId), t = this.store.get<Task>(ref.taskId, 'task', ref.ownerId);
    return t.status === 'READY' && f.state === 'ANALYZED' && f.analysisRawId === ref.rawId && f.versions.at(-1)?.id === ref.rawId;
  }
  private active(r: Release) { const original = this.proposals().find(p => p.id === r.proposalId); return !!original && this.evidenceValid(original) && original.sources.some(s => this.sourceValid(s)) && !this.store.list<{ releaseId: string; recalled?: boolean }>('release-recall', TEAM).some(x => x.releaseId === r.id && x.recalled !== false); }
  private hash(p: Pick<Proposal, 'kind' | 'skillId' | 'question' | 'answer' | 'evidence' | 'version'>) { return digest({ kind: p.kind, skillId: p.skillId, question: p.question, answer: p.answer, evidence: p.evidence, version: p.version }); }
  /** All changes come from real analysis + explicit catalog; no study-specific business branches. */
  discover(actor: Actor) {
    requireRole(actor, 'EMPLOYEE');
    return this.store.transaction(() => {
      for (const f of this.store.list<Feedback>('feedback', actor.id)) {
        if (f.state !== 'ANALYZED' || !f.analysis || !f.analysisRawId) continue;
        const task = this.store.get<Task>(f.taskId, 'task', actor.id);
        if (task.status !== 'READY' || f.versions.at(-1)?.id !== f.analysisRawId) continue;
        for (const d of f.analysis.differences) {
          const unit = f.analysis.units.find(u => u.id === d.questionUnitId);
          if (!unit || !d.skillId) continue;
          const skill = task.snapshot.codebook.skills.find(s => s.id === d.skillId);
          if (!skill) continue;
          const source: SourceRef = { ownerId: actor.id, feedbackId: f.id, rawId: f.analysisRawId,
            taskId: task.id, excerpt: unit.excerpt, signal: d.personalSignal, coverage: d.coverage };
          const scope = { fixtureId: task.snapshot.fixtureId, knowledgeVersion: task.snapshot.knowledgeVersion,
            codebookVersion: task.snapshot.codebook.version, scenarioVersion: task.snapshot.scenarioVersion };
          for (const existing of this.proposals().filter(p => p.skillId === skill.id && p.scope?.fixtureId === scope.fixtureId)) {
            if (!existing.sources.some(s => s.rawId === source.rawId && s.excerpt === source.excerpt)) {
              existing.sources.push(source); this.save(existing, actor, 'SOURCE_LINKED');
            }
          }
          const releases = this.matchingReleases(task);
          const decision = decideSharedChange(task.snapshot, d, this.catalog(task), releases.filter(r => r.kind === 'CONTENT').map(r => r.skillId));
          const noteId = `decision-${f.analysisRawId}-${d.questionUnitId}-${skill.id}`;
          this.store.put(noteId, 'evolution-decision', actor.id, { id: noteId, rawId: f.analysisRawId,
            study: task.title, skillId: skill.id, status: decision.kind, reason: decision.reason });
          if (decision.kind !== 'CONTENT' && decision.kind !== 'STRATEGY') continue;
          if (this.proposals().some(p => p.kind === decision.kind && p.skillId === skill.id && p.scope?.fixtureId === scope.fixtureId && p.state !== 'RECALLED')) continue;
          const evidence = task.snapshot.evidence;
          const p: Proposal = { id: randomUUID(), version: 1, scope, kind: decision.kind, skillId: skill.id, label: skill.evidenceBoundary,
            question: `请${skill.cognitiveTask}「${skill.evidenceBoundary}」，并说明资料的适用边界。`,
            answer: evidence.map(e => e.content).join('\n'), evidence, sources: [source],
            reason: decision.reason,
            alternatives: ['保留现状并继续收集复盘，避免根据个别线索过度调整。',
              decision.kind === 'CONTENT' ? '先进行个人训练；不能替代缺少的共享场景。' : '增加题量；会改变训练负担，不能作为同条件策略对照。'],
            hash: '', state: 'DRAFT' };
          p.hash = this.hash(p); this.save(p, actor, 'PROPOSAL_CREATED');
        }
      }
      return this.view(actor);
    });
  }
  private save(p: Proposal, actor: Actor, event: string) { this.store.put(p.id, 'proposal', TEAM, p); this.store.event(p.id, actor.id, event, { hash: p.hash, version: p.version, state: p.state }); }
  private get(id: string) { return this.store.get<Proposal>(id, 'proposal', TEAM); }
  private check(p: Proposal) {
    const source = p.sources.find(s => this.sourceValid(s));
    const task = source ? this.store.get<Task>(source.taskId, 'task', source.ownerId) : undefined;
    const available = task && this.available(task);
    const cases = task && this.cases(task);
    const comparisons = task && available && cases ? compareStrategyCases(available, cases, task.snapshot.plan.map(x => x.skillId), p.skillId) : [];
    const contentFromFrozenSource = !!task && p.evidence.every(e => task.snapshot.evidence.some(k =>
      k.id === e.id && k.version === e.version && k.content === e.content));
    return [
      { name: '资料版本有效，且只用于虚构测试', passed: this.evidenceValid(p) && contentFromFrozenSource },
      { name: '至少一条来源复盘仍有效', passed: !!source },
      { name: '内容未混入风险资料', passed: !screen(p.question + p.answer).findings.length },
      { name: '考点属于来源冻结代码本', passed: !!task?.snapshot.codebook.skills.some(s => s.id === p.skillId) },
      { name: '存在本次任务对应的有效训练目录', passed: available !== undefined },
      ...(p.kind === 'CONTENT' ? [
        { name: '答案只引用冻结测试资料，不添加医学结论', passed: p.answer.trim().length > 0 && p.answer.split('\n').filter(Boolean).every(line => p.evidence.some(e => e.content.includes(line))) },
        { name: '保留冻结计划中的原考点', passed: !!task && task.snapshot.plan.every(x => available?.includes(x.skillId)) },
      ] : [
        { name: '存在独立开发和留出测试样例', passed: !!cases && cases.some(c => c.partition === 'DEVELOPMENT') && cases.some(c => c.partition === 'HOLDOUT') },
        { name: '同题量对照不存在新增遗漏', passed: comparisons.length > 0 && comparisons.every(c => c.valid && c.lost.length === 0) },
        { name: '留出样例有新增有效覆盖', passed: comparisons.some(c => c.partition === 'HOLDOUT' && c.added.length > 0) },
      ]),
    ];
  }
  training(actor: Actor, id: string, expectedHash: string, approved: boolean, reason: unknown) {
    requireRole(actor, 'TRAINING_REVIEWER'); const note = text(reason, 2000);
    return this.store.transaction(() => { const p = this.get(id); if (p.hash !== expectedHash || p.state === 'PUBLISHED' || p.state === 'RECALLED') throw new Module2Error('VERSION_CONFLICT', '请刷新后审核当前草稿。', 409);
      p.training = { approved, reason: note, actor: actor.id, hash: p.hash }; p.state = 'DRAFT'; delete p.lease; this.save(p, actor, 'TRAINING_REVIEWED'); return p; });
  }
  revise(actor: Actor, id: string, hash: string, question: unknown, answer: unknown) {
    requireRole(actor, 'TRAINING_REVIEWER'); return this.store.transaction(() => { const old = this.get(id);
      if (old.hash !== hash || old.state === 'PUBLISHED' || old.state === 'RECALLED') throw new Module2Error('VERSION_CONFLICT', '只能修改当前未发布草稿。', 409);
      this.store.db.prepare('INSERT OR IGNORE INTO evolution_archive VALUES(?,?)').run(`draft-${id}-${old.version}`, JSON.stringify(old));
      const p: Proposal = { ...old, version: old.version + 1, question: text(question, 5000), answer: text(answer, 20000), state: 'DRAFT', medical: undefined, training: undefined, publication: undefined, checks: undefined, lease: undefined, error: undefined };
      p.hash = this.hash(p); this.save(p, actor, 'DRAFT_REVISED'); return p; });
  }
  async runAgent(actor: Actor, id: string, role: 'MEDICAL' | 'PUBLICATION', reviewer: Reviewer, model: string) {
    requireRole(actor, role === 'MEDICAL' ? 'MEDICAL_REVIEWER' : 'PUBLISHER');
    const token = randomUUID();
    const p = this.store.transaction(() => { const p = this.get(id);
      if (p.state === 'PUBLISHED' || p.state === 'RECALLED') return p;
      if (p.lease && p.lease.until > Date.now()) throw new Module2Error('ALREADY_PROCESSING', 'Agent 正在处理。', 409);
      p.lease = { token, until: Date.now() + 105000 }; p.state = 'REVIEWING'; delete p.error;
      this.save(p, actor, `${role}_AGENT_STARTED`); return p; });
    if (p.state === 'PUBLISHED' || p.state === 'RECALLED') return p;
    const checks = this.check(p);
    if (role === 'PUBLICATION') checks.push({ name: '当前稿件已获医学 Agent 通过', passed: p.medical?.decision === 'PASS' && p.medical.hash === p.hash }, { name: '当前稿件培训审核通过', passed: p.training?.approved === true && p.training.hash === p.hash });
    try {
      const result = checks.every(c => c.passed) ? await reviewer(p, checks, role) : { decision: 'BLOCK' as const, reason: checks.filter(c => !c.passed).map(c => c.name).join('；'), citations: [] };
      if (!['PASS', 'BLOCK'].includes(result.decision) || !result.reason.trim() || !Array.isArray(result.citations) || result.citations.some(c => !p.evidence.some(e => e.id === c.evidenceId && c.quote.trim() && e.content.includes(c.quote))) || (result.decision === 'PASS' && !result.citations.length)) throw new Module2Error('MODEL_INVALID_RESPONSE', 'Agent 引用或结论格式不符合要求。', 502);
      return this.store.transaction(() => { const live = this.get(id); if (live.hash !== p.hash || live.lease?.token !== token) return live;
        delete live.lease; live.checks = this.check(live);
        const review: AgentReview = { ...result, agent: role, hash: p.hash, at: stamp(), model };
        if (role === 'MEDICAL') live.medical = review; else live.publication = review;
        live.state = result.decision === 'PASS' && live.checks.every(c => c.passed) ? 'READY' : 'BLOCKED';
        if (role === 'PUBLICATION' && live.state === 'READY') {
          if (live.medical?.hash !== live.hash || live.medical.decision !== 'PASS' || live.training?.hash !== live.hash || !live.training.approved) { live.state = 'BLOCKED'; live.error = 'REVIEW_CHANGED'; }
          else {
            const release: Release = { id: `release-${digest({ id, hash: live.hash })}`, proposalId: id, proposalHash: live.hash, scope: live.scope, kind: live.kind, skillId: live.skillId, label: live.label, question: live.question, answer: live.answer, evidence: live.evidence, createdAt: stamp() };
            this.store.db.prepare('INSERT OR IGNORE INTO evolution_archive VALUES(?,?)').run(release.id, JSON.stringify(release)); live.releaseId = release.id; live.state = 'PUBLISHED';
          }
        }
        this.save(live, actor, `${role}_AGENT_COMPLETED`); return live; });
    } catch (error) {
      return this.store.transaction(() => { const live = this.get(id); if (live.lease?.token !== token) return live;
        delete live.lease; live.state = 'BLOCKED'; live.error = error instanceof Module2Error ? error.code : 'AGENT_FAILED'; this.save(live, actor, `${role}_AGENT_FAILED`); return live; });
    }
  }
  async continueAgents(actor: Actor, id: string, reviewer: Reviewer, model: string) {
    const p = this.get(id);
    if (actor.role === 'EMPLOYEE' && !p.sources.some(s => s.ownerId === actor.id)) throw new Module2Error('FORBIDDEN', '不能操作其他人的候选。', 403);
    if (!['EMPLOYEE','TRAINING_REVIEWER','MEDICAL_REVIEWER','PUBLISHER'].includes(actor.role)) throw new Module2Error('FORBIDDEN', '无权运行。', 403);
    let current = p;
    if (!p.medical || p.medical.hash !== p.hash || p.medical.decision !== 'PASS') current = await this.runAgent({ id: 'medical-agent', role: 'MEDICAL_REVIEWER' }, id, 'MEDICAL', reviewer, model);
    if (current.medical?.decision === 'PASS' && current.training?.approved && current.training.hash === current.hash) return this.runAgent({ id: 'publication-agent', role: 'PUBLISHER' }, id, 'PUBLICATION', reviewer, model);
    return current;
  }
  recall(actor: Actor, id: string, reason: unknown) {
    requireRole(actor, 'PUBLISHER'); const note = text(reason, 2000);
    return this.store.transaction(() => { const release = this.releaseRecords().find(r => r.id === id); if (!release) throw new Module2Error('NOT_FOUND', '版本不存在。', 404);
      this.store.put(`recall-${id}`, 'release-recall', TEAM, { releaseId: id, recalled: true, reason: note, at: stamp() }); const p = this.get(release.proposalId); p.state = 'RECALLED'; this.save(p, actor, 'RELEASE_RECALLED'); });
  }
  restoreRelease(actor: Actor, id: string, reason: unknown) {
    requireRole(actor, 'PUBLISHER'); const note = text(reason, 2000);
    return this.store.transaction(() => { const release = this.releaseRecords().find(r => r.id === id); if (!release) throw new Module2Error('NOT_FOUND', '版本不存在。', 404);
      const p = this.get(release.proposalId);
      if (!this.evidenceValid(release) || p.hash !== release.proposalHash || p.medical?.decision !== 'PASS' || !p.training?.approved || !this.check(p).every(c => c.passed)) throw new Module2Error('RESTORE_BLOCKED', '旧版本的资料、审核或测试条件不再有效，不能恢复。', 409);
      this.store.put(`recall-${id}`, 'release-recall', TEAM, { releaseId: id, recalled: false, reason: note, at: stamp() }); p.state = 'PUBLISHED'; this.save(p, actor, 'RELEASE_RESTORED');
    });
  }
  withdrawKnowledge(actor: Actor, evidenceId: string, version: string, reason: unknown) {
    requireRole(actor, 'MEDICAL_REVIEWER'); const note = text(reason, 2000);
    if (!this.knowledge.read().some(e => e.id === evidenceId && e.version === version)) throw new Module2Error('NOT_FOUND', '资料不存在。', 404);
    this.store.transaction(() => { this.store.put(`withdraw-${evidenceId}-${version}`, 'knowledge-withdrawal', TEAM, { id: evidenceId, version, reason: note, at: stamp() }); this.store.event(evidenceId, actor.id, 'KNOWLEDGE_WITHDRAWN', { version, reason: note }); });
  }
  knowledgeUsable(snapshot: TaskInput) {
    // D2 L1 can use a validated, frozen TEST_ONLY snapshot from any fictional study.
    // Keep the original A evidence port check for its existing withdrawal and review tests;
    // a new study is *not* silently replaced with research A's evidence.
    if (snapshot.fixtureId === 'research-a-main-v1') return this.evidenceValid(snapshot);
    const withdrawn = this.store.list<{ id: string; version: string }>('knowledge-withdrawal', TEAM);
    return snapshot.evidence.length > 0 && snapshot.evidence.every(e => e.usage === 'TEST_ONLY' &&
      !withdrawn.some(w => w.id === e.id && w.version === e.version));
  }
  nextInput(input: StrategyInput, sourceTask?: Task): TaskInput {
    if (!['BASIC','EXTRAPOLATION','UNKNOWN'].includes(input.focus) || !Number.isInteger(input.budget) || input.budget < 1 || input.budget > 10)
      throw new Module2Error('INVALID_INPUT', '请选择测试场景和有效的训练题量。');
    if (sourceTask?.status === 'CANCELED') throw new Module2Error('TASK_CANCELED', '已取消的任务不能作为下一次准备依据。', 409);
    const base = sourceTask?.snapshot ?? mainFixture();
    if (!this.knowledgeUsable(base)) throw new Module2Error('KNOWLEDGE_UNAVAILABLE', '冻结测试资料已停用，等待有效替代。', 409);
    const task = sourceTask ?? { snapshot: { ...base, hash: '' }, ownerId: '', id: '' } as Task;
    const available = this.available(task);
    if (!available) throw new Module2Error('CATALOG_UNAVAILABLE', '此任务没有可核验的训练目录，不能生成下一轮准备。', 409);
    const releases = this.matchingReleases(task);
    const content = releases.filter(r => r.kind === 'CONTENT');
    const strategy = releases.filter(r => r.kind === 'STRATEGY').at(-1);
    const baselineSkillIds = base.plan.map(p => p.skillId);
    const selected = selectSkills(available, { ...input, baselineSkillIds, prioritySkillId: strategy?.skillId }, strategy ? 'FOCUS' : 'BASELINE');
    const catalog = this.catalog(task) ?? [];
    return { ...base,
      scenarioVersion: content.length ? `${base.scenarioVersion}+${content.map(r => r.id).join('+')}` : base.scenarioVersion,
      strategyVersion: strategy?.id ?? base.strategyVersion,
      plan: selected.map(skillId => {
        const published = content.find(r => r.skillId === skillId);
        if (published) return { skillId, question: published.question, rationale: '经测试审核发布的共享场景候选。', evidenceIds: published.evidence.map(e => e.id) };
        const planned = base.plan.find(p => p.skillId === skillId);
        if (planned) return planned;
        const item = catalog.find(c => c.skillId === skillId);
        const skill = base.codebook.skills.find(s => s.id === skillId)!;
        if (!item) throw new Module2Error('CATALOG_UNAVAILABLE', '目录缺少所选能力训练题。', 409);
        return { skillId, question: `请${skill.cognitiveTask}：${skill.evidenceBoundary}`, rationale: '从已登记的测试训练目录选择；正式训练由模块 1 执行。', evidenceIds: item.evidenceIds };
      }) };
  }
  recordUse(actor: Actor, task: Task) {
    const releaseIds = this.releaseRecords().filter(r => task.snapshot.scenarioVersion.split('+').includes(r.id) && task.snapshot.plan.some(p => p.skillId === r.skillId)).map(r => r.id);
    const use: Use = { id: `use-${task.id}`, ownerId: actor.id, taskId: task.id, releaseIds, strategyId: task.snapshot.strategyVersion, selectedSkills: task.snapshot.plan.map(p => p.skillId), at: stamp() };
    this.store.put(use.id, 'release-use', TEAM, use);
  }
  view(actor: Actor): EvolutionView {
    const uses = this.store.list<Use>('release-use', TEAM), all = this.releaseRecords();
    const proposals = this.proposals().filter(p => actor.role !== 'EMPLOYEE' || p.sources.some(s => s.ownerId === actor.id)).map(p => ({ ...p, sources: p.sources.filter(s => actor.role !== 'EMPLOYEE' || s.ownerId === actor.id) }));
    const pendingDecisions = this.store.list<{ id: string; rawId: string; study: string; skillId: string | null; status: string; reason: string }>('evolution-decision', actor.id)
      .filter(d => d.status === 'PERSONAL_ONLY' || d.status === 'INSUFFICIENT_DATA')
      .filter(d => this.store.list<Feedback>('feedback', actor.id).some(f => f.analysisRawId === d.rawId && f.versions.at(-1)?.id === d.rawId))
      .map(d => ({ study: d.study, skillId: d.skillId, status: d.status as 'PERSONAL_ONLY' | 'INSUFFICIENT_DATA', reason: d.reason }));
    const available = [...new Set([...mainFixture().plan.map(p => p.skillId), ...all.filter(r => r.kind === 'CONTENT' && this.active(r) && r.scope?.fixtureId === 'research-a-main-v1').map(r => r.skillId)])];
    const proposalComparisons: Record<string, ReturnType<typeof compareStrategyCases>> = {};
    for (const proposal of proposals.filter(p => p.kind === 'STRATEGY')) {
      const source = proposal.sources.find(s => this.sourceValid(s));
      if (!source) continue;
      const task = this.store.get<Task>(source.taskId, 'task', source.ownerId);
      const skills = this.available(task), samples = this.cases(task);
      if (skills && samples) proposalComparisons[proposal.id] = compareStrategyCases(skills, samples, task.snapshot.plan.map(p => p.skillId), proposal.skillId);
    }
    return { proposals, pendingDecisions, proposalComparisons, knowledgeAvailable: this.evidence().length > 0, comparisons: compareStrategies(available), releases: all.map(r => {
      const relevant = uses.filter(u => u.releaseIds.includes(r.id) || u.strategyId === r.id);
      const feedback = relevant.flatMap(u => this.store.list<Feedback>('feedback', u.ownerId).filter(f => f.taskId === u.taskId && f.state === 'ANALYZED'));
      return { ...r, active: this.active(r), uses: relevant.length, feedback: feedback.length, difficulties: feedback.filter(f => f.analysis?.differences.some(d => d.skillId === r.skillId && d.personalSignal === 'PENDING_VERIFY')).length };
    }) };
  }
}
