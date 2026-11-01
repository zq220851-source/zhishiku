'use strict';
/** Loads INDEPENDENT reviewer aggregates, not raw gold; domain gate never activates patch. */
const fs=require('fs'),path=require('path');
const {evaluateMethodPatch}=require('../../../../compiled/lib/method-skill-lifecycle.js');
const review=JSON.parse(fs.readFileSync(path.join(__dirname,'../../../../review_lab/audit_result.json'),'utf8'));
const draft={id:'expert-question-factuality-guard',version:1,description:'对现场专家提问先判断否定、假设、更正，再决定是否允许进入五资产',conditions:['候选事件属于专家现场问询'],action:'检查句法中的否定、假设与更正范围，证据不足则弃权',exclusions:['不会改变正式医学知识','不自动建立稳定专家倾向','不允许未经审查上线'],supportingTestIds:['D02','V06'],conflictingTestIds:review.counts.stress.failures.map(x=>x.id),state:'DRAFT'};
const evaluated=evaluateMethodPatch(draft,review.comparisonSummaries);
fs.writeFileSync(path.join(__dirname,'method_patch_result.json'),JSON.stringify(evaluated,null,2));
console.log('Method patch:',evaluated.state,'; failures in stress:',draft.conflictingTestIds.length);
