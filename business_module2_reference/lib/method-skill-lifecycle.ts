/** B-side controlled Method/Skill evolution. A test result is not publication permission. */
export type PatchState='DRAFT'|'TESTED_CANDIDATE'|'REJECTED'|'APPROVED_TEST_ONLY'|'REVERTED';
export interface ComparisonSummary { split:'validation'|'holdout'|'stress'; cases:number; baselineFalseExpertClaims:number; candidateFalseExpertClaims:number; baselineMissedExpertClaims:number; candidateMissedExpertClaims:number; }
export interface MethodPatch {
  id:string; version:number; description:string; conditions:string[]; action:string; exclusions:string[]; supportingTestIds:string[]; conflictingTestIds:string[]; state:PatchState;
  comparison?:ComparisonSummary[];
}
export function evaluateMethodPatch(p:MethodPatch,results:ComparisonSummary[]): MethodPatch {
  if(p.state!=='DRAFT'||!p.id||!p.conditions.length||!p.action||!p.exclusions.length||!p.supportingTestIds.length)throw new Error('缺少可审查的条件、动作、排除项或来源');
  const holdout=results.find(x=>x.split==='holdout'),validation=results.find(x=>x.split==='validation'),stress=results.find(x=>x.split==='stress');
  if(!holdout||!validation||!stress||holdout.cases<8||validation.cases<4||stress.cases<10)throw new Error('未完成足量独立留出与验证测试');
  // A false expert observation is a high-cost error: the stress suite is an explicit veto.
  if(stress.candidateFalseExpertClaims>0||stress.candidateMissedExpertClaims>0||results.some(r=>r.candidateFalseExpertClaims>r.baselineFalseExpertClaims||r.candidateMissedExpertClaims>r.baselineMissedExpertClaims))return {...p,state:'REJECTED',comparison:results};
  const improves=results.some(r=>r.candidateFalseExpertClaims<r.baselineFalseExpertClaims||r.candidateMissedExpertClaims<r.baselineMissedExpertClaims);
  return {...p,state:improves?'TESTED_CANDIDATE':'REJECTED',comparison:results};
}
/** Deliberately never activates a production rule; requires separate, explicit authorization. */
export function approveForTestOnly(p:MethodPatch,authorized:boolean): MethodPatch {
  if(p.state!=='TESTED_CANDIDATE'||!authorized)throw new Error('未经授权或未通过对照，不能启用');
  return {...p,state:'APPROVED_TEST_ONLY'};
}
