'use strict';
// Separate process consumes ONLY the independent audit's aggregate scores.
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../../../../');
const {evaluateMethodPatch}=require(path.join(root,'compiled/lib/method-skill-lifecycle.js'));
const report=JSON.parse(fs.readFileSync(path.join(root,'review_lab/audit_v07_result.json'),'utf8'));
const comparisons=['validation','holdout','stress'].map(split=>({
  split,cases:report.splits[split].candidate.total,
  baselineFalseExpertClaims:report.splits[split].previous.false_report_ids.length,
  candidateFalseExpertClaims:report.splits[split].candidate.false_report_ids.length,
  baselineMissedExpertClaims:report.splits[split].previous.missed_report_ids.length,
  candidateMissedExpertClaims:report.splits[split].candidate.missed_report_ids.length
}));
const draft={id:'scoped-question-factuality-v07',version:1,state:'DRAFT',
 description:'将句子级否定拆为事件级作用域并保留说话人身份；纯规则实验，不用于生产',
 conditions:['虚构复盘中有外推相关的专家问题候选'],
 action:'按子句局部判断事实性，无法确认时弃权；正式语义使用模型事件提案和独立审核',
 exclusions:['未经审核不写入专家画像和群体账本','不能声明真实 LLM 语义能力','不得自动修改医学事实'],
 supportingTestIds:report.splits.stress.candidate.wrong.map(x=>x.id).length?['S01','S02']:['S01'],
 conflictingTestIds:[...report.splits.stress.candidate.wrong.map(x=>x.id),...report.splits.challenge.candidate.wrong.map(x=>x.id)]};
const evaluated=evaluateMethodPatch(draft,comparisons);
// Additional new challenge suite is a veto, not eligible for automatic approval.
if(report.gate==='REJECTED' && evaluated.state!=='REJECTED') throw new Error('Independent challenge verdict overrides legacy gate');
fs.writeFileSync(path.join(root,'review_lab/method_patch_v07.json'),JSON.stringify({...evaluated,extraChallengeGate:report.gate},null,2));
console.log('Skill candidate status:',evaluated.state,'new challenge gate:',report.gate);
