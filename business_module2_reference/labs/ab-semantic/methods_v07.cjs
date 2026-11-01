'use strict';
/** V0.7 experimental scoped-clause baseline, not production language understanding.
 * Distinguishes target of negation, direct questioning vs discussion, speaker role,
 * reported vs hypothetical event and a subsequent retraction.
 * Produces an auditable reason and abstains on ambiguous referents.
 */
const TOPIC=/(外推|推到|推广|适用|其他人群|别的人群|其他患者|另一组病人|更多人群|适用范围|证据边界|边界|这事)/;
const ASK=/(追问|提问|问|问过|问了|是否|是不是|有无|能否|可否|想知道)/;
const EXPERT=/(医生|专家|教授|主任|那位专家|他|对方)/;
const UNCERTAIN=/(不确定|不敢确定|记不(?:清|得)|不知道是谁|好像|不清楚是谁|不确定.*(?:问|提)|是谁说的)/;
const FUTURE=/(假如|如果|万一|下次|明天|准备时|会不会有|担心如果|可能会|计划|预想)/;
const REVOKE=/(记错|听错|把(?:培训老师|同事|同行).{0,12}记成(?:医生|专家)|其实(?:并没|没有)|先前说.*(?:不对|记错))/;
const SELF=/(我自己(?:又)?想到|我回来自己想到|是我自己提|是我先问|我自己问(?:医生|专家)|外推是我自己想|培训时想到|我没有说专家问|不是专家问|不是医生问|我自己提的)/;
const OTHER_SPEAKER=/(同行代表|培训老师|专家的同事|同事问)/;
const DENIAL=/(?:没有|没|并未|根本没|压根没|未)(?:明确)?(?:问|提|追问)|(?:问|提)的不是|没有直接提问|没提出问题|没有反问|没有问过/;
const REVERSAL=/(不是没问|并不是没问|不是没有问|并没有说他没问|确实问|真的问|明确问|当面问|确实提过)/;
const TARGET_DENIAL=/(没(?:有)?问.{0,16}(?:外推|推广|其他人群|适用|这事)|没(?:有)?提.{0,16}(?:外推|推广|其他人群|这事)|(?:问|提)的不是.{0,12}(?:外推|推广|适用)|(?:外推|推广).{0,12}(?:没有问|没问))/;
function units(text){
 return text.split(/(?<=[。！？；;，,])|(?=却)|(?=但是)|(?=但)|(?=不过)|(?=反而)|(?=而是)|(?=后来)/).map(s=>s.trim()).filter(Boolean);
}
function scopedQuestionProxy(text){
 const clauses=units(text), topicIndices=clauses.map((s,i)=>TOPIC.test(s)?i:-1).filter(i=>i>=0);
 const explain=(mode,why,evidence)=>({mode,reason:why,evidence:evidence||'',units:clauses});
 if(!topicIndices.length)return explain('UNCERTAIN','未检测到研究目标主题','');
 // Role disambiguation applies to attribution of the same event, not merely any word in the utterance.
 if(OTHER_SPEAKER.test(text)&&/(不是专家|不是医生|专家本人没有问|培训老师的话记成医生|但他是同行代表)/.test(text))return explain('DENIED','提问者不是目标专家或后续纠正说话人',text);
 if(REVOKE.test(text)&&/(记错|听错|记成|其实并没有|其实没有)/.test(text))return explain('DENIED','后续明确修正了原先现场提问的描述',text);
 if(/医生不是没问|医生并不是没问|并没有说他没问/.test(text))return explain('REPORTED','双重否定表示实际发生提问',text);
 if(/(?:我自己问(?:医生|专家)|是我先问|是我自己先问|是我自己提的|是我自己提|外推是我自己想)/.test(text))return explain('DENIED','目标问题由员工主动提出或想到',text);
 let hasDenied=false,hasHyp=false,hasUncertain=false,hasPositive=false,positiveEvidence='',negativeEvidence='';
 const topicIn=(s)=>TOPIC.test(s);
 for(let i=0;i<clauses.length;i++){
  const s=clauses[i], hasTopic=topicIn(s), previous=clauses.slice(Math.max(i-2,0),i).join('');
  const related=hasTopic || (/(确实提过|真的问了|当面问的|确实问了|其中一个是|追问了)/.test(s)&&TOPIC.test(previous));
  if(!related)continue;
  const context=clauses.slice(Math.max(0,i-2),i+1).join('');
  if(UNCERTAIN.test(s)||(/他/.test(s)&&/(记不|不确定|不清楚)/.test(context))){hasUncertain=true;continue;}
  // A hypothetical quote can itself be the real question, so factual framing wins.
  if(/(?:这是|确实是|就是).{0,8}(?:他|医生|专家).{0,5}(?:当面问|问的)/.test(context) || /(?:他|医生|专家).{0,4}(?:确实|真的)(?:提过|问了)/.test(context)){
   hasPositive=true;positiveEvidence=s;continue;
  }
  if(SELF.test(s)||(/(?:回来|复盘).{0,8}(?:自己|才)?(?:想到|想起)/.test(s)&&!/(?:医生|专家).{0,10}(?:问|追问)/.test(s))){hasDenied=true;negativeEvidence=s;continue;}
  if(DENIAL.test(s) && !REVERSAL.test(s)){
   if(hasTopic && (TARGET_DENIAL.test(s)||!/(终点|样本量|换方案)/.test(s))){hasDenied=true;negativeEvidence=s;continue;}
  }
  // A topic clause with future/modal without a same-clause actual speaker+question is hypothetical.
  if(FUTURE.test(s)&&!/(?:今天|当场|当面|确实|真的).{0,10}(?:问|追问|提)/.test(s)){
   hasHyp=true;continue;
  }
  if(/(?:不确定|似乎|好像|不敢确定)/.test(context)){hasUncertain=true;continue;}
  if(OTHER_SPEAKER.test(s)) {hasDenied=true;negativeEvidence=s;continue;}
  const expertInContext=EXPERT.test(s)||(/^(?:追问|却追问|但追问|又追问|问了|其中一个)/.test(s)&&/(?:医生|专家|教授|主任)/.test(previous));
  const expertDirect=/(?:医生|专家|教授|主任|对方|那位专家).{0,18}(?:问|追问|提问|关心)/.test(s);
  const targetAndQuestion=ASK.test(s)||/(?:追问了|问了)/.test(s)||/(其中一个是)/.test(s);
  if((expertDirect&&targetAndQuestion)||(expertInContext&&targetAndQuestion)) {hasPositive=true;positiveEvidence=s;continue;}
  if(/(?:我回答|我说|我当时)/.test(s) && /他.{0,6}(?:问|提)/.test(previous)) {hasPositive=true;positiveEvidence=s;continue;}
  // reported direct speech + answer implies prior questioning, but unknown speaker is NOT promoted
  if(/(?:他|对方).{0,12}(?:说|问)/.test(s)){hasUncertain=true;continue;}
 }
 if(hasPositive)return explain('REPORTED','至少一条含目标主题的现场提问有明确归属',positiveEvidence);
 if(hasUncertain)return explain('UNCERTAIN','提问发生或主体身份存在不可解决的不确定性',text);
 if(hasDenied)return explain('DENIED','目标提问被明确否认或说明只是员工自问',negativeEvidence);
 if(hasHyp)return explain('HYPOTHETICAL','仅为假设或未来准备',text);
 if(/(?:回来|复盘|自己|培训)/.test(text) && !/(?:医生|专家).{0,10}(?:问|追问)/.test(text)) return explain('DENIED','只有员工自发主题，没有现场专家提问',text);
 return explain('UNCERTAIN','缺少可确证的专家现场提问证据',text);
}
module.exports={scopedQuestionProxy,units};
