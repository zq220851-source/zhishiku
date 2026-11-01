import { Discovery } from '../../../lib/discovery';
import { Store } from '../../../lib/store';
import { Service } from '../../../lib/service';
import { actor, body, gate, json, route, session } from '../../../lib/http';
import { mainFixture, sampleReflection } from '../../../lib/fixture';
import { researchB } from '../../../lib/demo-data';
import type { TrainingCatalogEntry } from '../../../lib/module1-contracts';
import type { StrategyCase } from '../../../lib/decision-engine';
import { configured, modelProvider, settings } from '../../../lib/provider';
import { evolutionReviewer } from '../../../lib/evolution-provider';
import { learningGrader } from '../../../lib/learning-provider';
import { invalid, object, text, Module2Error } from '../../../lib/errors';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
const singleton = globalThis as typeof globalThis & { module2Service?: Service };
function service() { return singleton.module2Service ??= new Service(new Store()); }
export function GET(request: Request) {
  return route(() => {
    gate(request); if (process.env.MODULE2_LIVE_MODE === 'true') throw new Module2Error('FIXTURE_MODE_DISABLED','旧测试接口已停用，请使用原知识库联动入口 /api/live',410); const user = actor(request), config = settings();
    const taskId = new URL(request.url).searchParams.get('taskId');
    const riskId = new URL(request.url).searchParams.get('riskId');
    if (riskId) return json(service().risks.detail(user, riskId));
    return json({ discovery: new Discovery(service().store).list(user), evolution: service().evolution.view(user), learning: service().learning.dashboard(user), nextTrainingDemands: service().learning.demands(user), actor: user, risks: service().risks.list(user), tasks: service().tasks(user), ...(taskId ? { task: service().getTask(user, taskId), feedback: service().feedback(user, taskId) } : {}),
      model: { configured: configured(config), authorized: config.authorized, name: config.model || null },
      fixture: mainFixture(), fixtures: { A: mainFixture(), B: researchB() }, sampleReflection });
  });
}
export function POST(request: Request) {
  return route(async () => {
    gate(request); if (process.env.MODULE2_LIVE_MODE === 'true') throw new Module2Error('FIXTURE_MODE_DISABLED','旧测试接口已停用，请使用原知识库联动入口 /api/live',410); const input = object(await body(request));
    if (input.action === 'session') return session(request);
    if (input.action === 'switchRole') {
      const before = actor(request);
      const response = session(request, input.role);
      service().store.event(`session:${before.id}`, before.id, 'TEST_ROLE_SWITCHED', { from: before.role, to: input.role });
      return response;
    }
    const user = actor(request), key = request.headers.get('idempotency-key') ?? '';
    if (input.action === 'discoverPatterns') return json(await new Discovery(service().store).run(user, settings()));
    if (input.action === 'continueAgents') { const config = settings(); return json(await service().evolution.continueAgents(user, text(input.id), evolutionReviewer(config), config.model)); }
    if (input.action === 'discover') return json(service().evolution.discover(user));
    if (input.action === 'trainingReview') return json(service().evolution.training(user, text(input.id), text(input.hash), input.approved === true, input.reason));
    if (input.action === 'reviseProposal') return json(service().evolution.revise(user, text(input.id), text(input.hash), input.question, input.answer));
    if (input.action === 'runMedicalAgent' || input.action === 'runPublicationAgent') {
      const config = settings(); return json(await service().evolution.runAgent(user, text(input.id), input.action === 'runMedicalAgent' ? 'MEDICAL' : 'PUBLICATION', evolutionReviewer(config), config.model));
    }
    if (input.action === 'restoreRelease') { service().evolution.restoreRelease(user, text(input.id), input.reason); return json(service().evolution.view(user)); }
    if (input.action === 'recallRelease') { service().evolution.recall(user, text(input.id), input.reason); return json(service().evolution.view(user)); }
    if (input.action === 'withdrawKnowledge') { service().evolution.withdrawKnowledge(user, text(input.id), text(input.version), input.reason); return json(service().evolution.view(user)); }
    if (input.action === 'nextTask') {
      const focus = text(input.focus) as 'BASIC' | 'EXTRAPOLATION' | 'UNKNOWN';
      const source = input.taskId === undefined ? undefined : service().getTask(user, text(input.taskId));
      const budget = input.budget === undefined ? (source?.snapshot.plan.length ?? 2) : Number(input.budget);
      const task = service().createTask(user, service().evolution.nextInput({ focus, budget }, source), key);
      service().evolution.recordUse(user, task); return json(task, 201);
    }
    if (input.action === 'registerTestCatalog') {
      const task = service().getTask(user, text(input.taskId));
      service().evolution.registerCatalog(user, task, input.catalog as TrainingCatalogEntry[], input.cases as StrategyCase[] | undefined);
      return json({ registered: true, taskId: task.id });
    }
    if (input.action === 'syncLearning') return json(service().learning.sync(user));
    if (input.action === 'advanceLearningClock') return json(service().learning.advance(user, input.days));
    if (input.action === 'retractLearningAttempt') { service().learning.retract(user, text(input.attemptId), input.reason); return json(service().learning.dashboard(user)); }
    if (input.action === 'submitLearningAnswer') {
      const config = settings();
      return json(await service().learning.submit(user, text(input.exerciseId), input.answer, key, learningGrader(config), config.model || 'UNCONFIGURED'));
    }
    if (input.action === 'updateRisk') return json(service().risks.update(user, text(input.riskId), input.state, input.expectedRevision, input.note, key));
    if (input.action === 'createTask') {
      const task = service().createTask(user, input.fixture ?? mainFixture(), key);
      return json(task, 201);
    }
    if (input.action === 'cancelTask') return json(service().cancel(user, text(input.taskId)));
    if (input.action === 'saveRaw') return json(service().saveRaw(user, text(input.taskId), input.raw, key, input.feedbackId === undefined ? undefined : text(input.feedbackId)));
    if (input.action === 'analyze') {
      if (!Number.isSafeInteger(input.expectedVersion) || Number(input.expectedVersion) < 1) invalid('请提供原文版本。');
      const config = settings();
      return json(await service().analyze(user, text(input.feedbackId), Number(input.expectedVersion), modelProvider(config), config.model || 'UNCONFIGURED'));
    }
    return invalid('未知操作。');
  });
}
