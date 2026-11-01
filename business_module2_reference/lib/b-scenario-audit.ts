/** Test-only L2 scenario audit: knowledge evidence, scenario content and selected training are separate. */
export type TrainingDimension='CONCEPT'|'EVIDENCE_BOUNDARY'|'FOLLOW_UP'|'SELF_EXPLANATION';
export interface CapabilityRequirement {researchId:string;capabilityId:string;requiredDimensions:TrainingDimension[];sourceEvidenceIds:string[]; }
export interface ScenarioSnapshot {id:string;version:string;researchId:string;capabilityId:string;dimensions:TrainingDimension[];status:'ELIGIBLE_TEST_ONLY'|'DRAFT';}
export interface ScenarioDiagnostic {capabilityId:string;state:'NO_ELIGIBLE_CONTENT'|'PARTIAL_CAPABILITY'|'FULL_CAPABILITY'|'UNKNOWN_REQUIREMENT';
  coveredDimensions:TrainingDimension[]; missingDimensions:TrainingDimension[]; sourceScenarioIds:string[];
  action:'CREATE_CANDIDATE'|'REVISE_CANDIDATE'|'REUSE_CONTENT'|'ASK_FOR_KNOWLEDGE';
  proposedTestOnlyEdit:string; sourceEvidenceIds:string[];}
const validDimension=(x:string):x is TrainingDimension=>['CONCEPT','EVIDENCE_BOUNDARY','FOLLOW_UP','SELF_EXPLANATION'].includes(x);
export function auditScenarioCoverage(requirement:CapabilityRequirement,catalog:ScenarioSnapshot[],knowledge:'SUPPORTED'|'PARTIAL'|'NOT_FOUND'|'CONTRADICTED'|'UNDETERMINED'):ScenarioDiagnostic {
  if(!requirement.researchId||!requirement.capabilityId||new Set(requirement.requiredDimensions).size!==requirement.requiredDimensions.length||requirement.requiredDimensions.some(x=>!validDimension(x))||
    requirement.sourceEvidenceIds.some(x=>!x)||new Set(catalog.map(x=>x.id)).size!==catalog.length||
    catalog.some(x=>!x.id||!x.version||x.dimensions.some(d=>!validDimension(d))))throw new Error('冻结能力要求或训练目录无效');
  const matched=catalog.filter(c=>c.researchId===requirement.researchId&&c.capabilityId===requirement.capabilityId&&c.status==='ELIGIBLE_TEST_ONLY');
  const covered=[...new Set(matched.flatMap(x=>x.dimensions))];const missing=requirement.requiredDimensions.filter(d=>!covered.includes(d));
  const common={capabilityId:requirement.capabilityId,coveredDimensions:covered,missingDimensions:missing,sourceScenarioIds:matched.map(x=>x.id),sourceEvidenceIds:requirement.sourceEvidenceIds};
  if(!requirement.requiredDimensions.length)return {...common,state:'UNKNOWN_REQUIREMENT',action:'ASK_FOR_KNOWLEDGE',proposedTestOnlyEdit:'能力要求尚未定义，不自动造题'};
  if(knowledge==='NOT_FOUND'||knowledge==='CONTRADICTED'||knowledge==='UNDETERMINED')
    return {...common,state:'UNKNOWN_REQUIREMENT',action:'ASK_FOR_KNOWLEDGE',proposedTestOnlyEdit:'先核验医学依据；不得生成缺乏依据的标准答案'};
  if(knowledge==='PARTIAL'&&missing.includes('EVIDENCE_BOUNDARY'))
    return {...common,state:'UNKNOWN_REQUIREMENT',action:'ASK_FOR_KNOWLEDGE',proposedTestOnlyEdit:'边界依据仍不充分，暂不生成医学参考答案'};
  if(!matched.length)return {...common,state:'NO_ELIGIBLE_CONTENT',action:'CREATE_CANDIDATE',proposedTestOnlyEdit:`仅创建训练任务候选：需实际练到 ${missing.join(' / ')}；医学参考答案待核验`};
  if(missing.length)return {...common,state:'PARTIAL_CAPABILITY',action:'REVISE_CANDIDATE',proposedTestOnlyEdit:`建议修订 ${matched.map(x=>x.id).join(',')}，补充 ${missing.join(' / ')} 的追问及逐项评价；医学参考答案待核验`};
  return {...common,state:'FULL_CAPABILITY',action:'REUSE_CONTENT',proposedTestOnlyEdit:'现有场景覆盖已定义的训练动作，不因一次漏选而重复造题'};
}
