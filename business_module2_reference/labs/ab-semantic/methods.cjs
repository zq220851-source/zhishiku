'use strict';
/** TEST PROTOTYPE ONLY. No LLM, no claim of general Chinese semantics. */
function oldKeywordProxy(text) {
  const topic=/(外推|推广|推到|适用|其他人群|别的人群|其他患者|另一组病人|更多人群|适用范围)/.test(text);
  const speaker=/(医生|专家|教授|主任|对方)/.test(text);
  const question=/(问|追问|提|关心)/.test(text);
  return topic && speaker && question ? 'REPORTED' : 'UNCERTAIN';
}
/** Candidate method patch: specific question-event factuality guard, NOT full event extraction.
 *  Preserve uncertainty if the speaker cannot be established; examine explicit negation,
 *  counterfactual, and subsequent narration corrections before promoting observations.
 */
function guardedQuestionProxy(text) {
  const topic=/(外推|推广|推到|适用|其他人群|别的人群|其他患者|另一组病人|更多人群|适用范围|这事)/.test(text);
  if (!topic) return 'UNCERTAIN';
  const corrected=/(记错了|听错了|是我先问的|其实并没有|其实是我|根本没问|压根没问)/.test(text);
  const denied=/(没有问|没问|没提|没有提|并未问|并没有追问|没人问|谁也没明确问|不是.{0,6}(?:专家|医生).{0,3}问|不是专家问的|问的不是外推|现场只聊了终点)/.test(text);
  const selfOnly=/(我自己(?:又)?想到|我回来自己想到|是我自己提的|是我(?:自己)?先问的)/.test(text);
  if (corrected || denied || selfOnly) return 'DENIED';
  if (/(不确定|不敢确定|记不(?:得|清)是谁|不记得是谁|不知道是谁|好像)/.test(text)) return 'UNCERTAIN';
  if (/(如果|假如|要是|万一|下次如果|会不会有|准备时想过|下次.*(?:问我|追问))/.test(text)) return 'HYPOTHETICAL';
  const speaker=/(医生|专家|教授|主任|对方|老师)/.test(text);
  const question=/(问|追问|提|关心|是不是|是否)/.test(text);
  if (speaker && question) return 'REPORTED';
  return 'UNCERTAIN';
}
module.exports={oldKeywordProxy,guardedQuestionProxy};
