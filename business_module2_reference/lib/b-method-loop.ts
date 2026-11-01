/** Skill/method lifecycle for test-only selection heuristics. No automatic publishing. */
import type { VisitEvidence } from './five-assets';
import { proposeNextPreparation, evaluateNextPreparation, type PreparationContext, type BlindTrial, type BPriorityWeights, type PlanDelta } from './b-evolution';
export interface MethodExperiment {
  id:string;version:number;why:string;conditions:string[];action:string;exclusions:string[];
  evidenceVisitIds:string[];weights:BPriorityWeights;
  state:'DRAFT'|'REJECTED'|'TESTED_CANDIDATE'|'APPROVED_TEST_ONLY';
}
export interface MethodTrial {id:string;split:'validation'|'holdout'; context:PreparationContext; holdout:BlindTrial;}
export interface MethodTrialScore {id:string;split:'validation'|'holdout';oldCovered:number;newCovered:number;oldMisses:string[];newMisses:string[];displaced:string[];}
export interface MethodVerdict {method:MethodExperiment;results:MethodTrialScore[];why:string;}
/** Test splits are authored by the reviewer and never sent to the selector. */
export function testMethodCandidate(candidate:MethodExperiment,trials:MethodTrial[],history:VisitEvidence[]):MethodVerdict{
  if(candidate.state!=='DRAFT'||!candidate.id||candidate.version<1||!candidate.why||candidate.conditions.length===0||!candidate.action||candidate.exclusions.length===0||candidate.evidenceVisitIds.length===0)
    throw new Error('候选方法缺少经验来源、条件、动作或例外');
  if(!trials.some(x=>x.split==='validation')||!trials.some(x=>x.split==='holdout')||new Set(trials.map(x=>x.id)).size!==trials.length)throw new Error('必须有独立验证与留出案例');
  if(new Set(trials.map(x=>x.holdout.observedVisitId)).size!==trials.length)throw new Error('不同案例不得复用同一留出拜访');
  for(const ref of candidate.evidenceVisitIds)if(!history.some(v=>v.visitId===ref))throw new Error('方法来源不存在');
  const scores:MethodTrialScore[]=[];
  for(const trial of trials){
    if(candidate.evidenceVisitIds.includes(trial.holdout.observedVisitId))throw new Error('经验来源泄露到留出测试');
    const baseline=proposeNextPreparation(trial.context,history);
    const next=proposeNextPreparation(trial.context,history,candidate.weights,`B_METHOD:${candidate.id}:v${candidate.version}`);
    const b=evaluateNextPreparation(baseline,trial.context,trial.holdout,history);
    const r=evaluateNextPreparation(next,trial.context,trial.holdout,history);
    if(!b.passedBudget||!r.passedBudget)throw new Error('选题成本不一致');
    scores.push({id:trial.id,split:trial.split,oldCovered:b.newCovered,newCovered:r.newCovered,oldMisses:b.newMisses,newMisses:r.newMisses,displaced:r.lost});
  }
  const holdout=scores.filter(x=>x.split==='holdout');
  const losses=scores.filter(x=>x.newCovered<x.oldCovered);
  const gains=holdout.filter(x=>x.newCovered>x.oldCovered);
  const accepted=losses.length===0&&gains.length>0;
  return {method:{...candidate,state:accepted?'TESTED_CANDIDATE':'REJECTED'},results:scores,
    why:accepted?'留出案例出现覆盖改善，未观察到测试回归；仍只允许申请测试环境使用':
      losses.length?`发现 ${losses.length} 个覆盖倒退案例，拒绝`: '未证明在独立留出数据上改善，拒绝'};
}
export function authorizeTestMethod(verdict:MethodVerdict,approval:{actor:string;reason:string;allow:boolean}):MethodExperiment{
  if(verdict.method.state!=='TESTED_CANDIDATE'||!approval.allow||!/^[A-Za-z0-9_.:-]{2,100}$/.test(approval.actor)||approval.reason.trim().length<8)
    throw new Error('方法未经独立对照或显式测试授权，不能启用');
  return {...verdict.method,state:'APPROVED_TEST_ONLY'};
}
/** Only an explicitly approved TEST_ONLY method may alter the comparison proposal. */
export function testPreparationWithApprovedMethod(context:PreparationContext,history:VisitEvidence[],method:MethodExperiment):PlanDelta{
  if(method.state!=='APPROVED_TEST_ONLY')throw new Error('候选方法未经批准测试');
  return proposeNextPreparation(context,history,method.weights,`B_METHOD:${method.id}:v${method.version}`);
}
