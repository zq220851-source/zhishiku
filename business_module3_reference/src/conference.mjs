// Public conference evidence. An agenda proves a listing, not attendance or delivery.
const CSCO_AGENDA='https://meeting.csco.org.cn/home/program/39';
let agendaCache=null;
const conferenceDecode=value=>String(value||'').replace(/&(?:nbsp|amp|lt|gt|quot|#39|#x27);/gi,m=>({'&nbsp;':' ','&amp;':'&','&lt;':'<','&gt;':'>','&quot;':'"','&#39;':"'",'&#x27;':"'"}[m.toLowerCase()]||m));
const conferencePlain=value=>conferenceDecode(value.replace(/<[^>]*>/g,' ')).replace(/\s+/g,' ').trim();
const conferenceNorm=value=>conferencePlain(value).replace(/\s+/g,'');

export function parseCscoAgenda(html,name,hospital){
 if(typeof html!=='string'||html.length>6_000_000)return [];
 const dates=[...html.matchAll(/<span>\s*(20\d\d-\d\d-\d\d)\s*(上午|下午)\s*<\/span>/gi)].map(m=>({at:m.index,date:m[1],session:m[2]}));
 const events=[];
 for(const match of html.matchAll(/<tr\b[^>]*>[\s\S]*?<\/tr>/gi)){
  if(!match[0].includes(name)||!match[0].includes(hospital))continue;
  const cells=[...match[0].matchAll(/<td\b[^>]*>([\s\S]*?)<\/td>/gi)].map(m=>conferencePlain(m[1]));
  if(cells.length<5||conferenceNorm(cells.at(-2))!==conferenceNorm(name)||conferenceNorm(cells.at(-1))!==conferenceNorm(hospital))continue;
  const role=cells.find(x=>/^(专家讨论|专题发言|口头报告|会议总结|病例讨论|主持|开幕致辞|大会发言)$/.test(x));
  const time=cells.find(x=>/^\d\d:\d\d-\d\d:\d\d$/.test(x));
  const topic=cells.at(-3);
  if(!role||!time||!topic)continue;
  const date=[...dates].reverse().find(d=>d.at<match.index);
  if(!date)continue;
  const section=[...html.slice(Math.max(0,match.index-18000),match.index).matchAll(/<b>([^<]*(?:专场|论坛)[^<]*)<\/b>/gi)].at(-1);
  const sectionName=section?conferencePlain(section[1]):'';
  const kind=/发言|报告|致辞/.test(role)?'演讲':'会议';
  events.push({kind,role,title:topic==='专家讨论'?`${date.date} 中国临床肿瘤学会年会 · ${sectionName||'专题'} · 专家讨论`:`${date.date} 中国临床肿瘤学会年会 · ${topic}`,snippet:`官方日程列示：${name}（${hospital}），${sectionName?sectionName+'，':''}${date.session} ${time}，角色：${role}。`,date:date.date,url:CSCO_AGENDA,domain:'meeting.csco.org.cn',sourceName:'中国临床肿瘤学会官方日程',confidence:'official_agenda',verification:'官方日程同时列出姓名、医院与角色；日程不能证明实际到场或完成发言。'});
 }
 return events.slice(0,12);
}

// These two reviewed public records give the demo case evidence across source types.
// They are explicitly labelled as a reviewed snapshot, not a fresh web search.
const reviewedTaoEvents=[
 {kind:'会议',role:'开场致辞',title:'2025 消化道肿瘤规范化诊治专题学习班（苏州站）',snippet:'中国临床肿瘤学会会后简讯记载陶敏教授代表承办方致辞；未记载他在此会的专题报告。',date:'2025-04-26',url:'https://www.csco.org.cn/cn/ncontent.aspx?oid=9192',domain:'csco.org.cn',sourceName:'中国临床肿瘤学会会后简讯',confidence:'reviewed_report',verification:'会后官方简讯写明姓名与活动角色；内容为已报道的致辞，不推断专题演讲。'},
 {kind:'演讲',role:'讲座',title:'MSI-H 肿瘤的免疫治疗及相关问题的思考',snippet:'2021 年江苏省肿瘤化疗与生物治疗学术会议报道记载陶敏教授作该主题讲座，并讨论双免联合的研究方向。历史记录，不是近期演讲；报道没有证明使用达伯欣®。',date:'2021-05-29',url:'https://www-search.liangyihui.net/doc/73959',domain:'www-search.liangyihui.net',sourceName:'良医汇会议报道（转载南京鼓楼医院肿瘤中心）',confidence:'reviewed_report',verification:'公开会后报道写明医院、姓名和讲座主题；为历史记录，未核对会议视频。'}
];
export function reviewedPublicEvents(name,hospital){return conferenceNorm(name)==='陶敏'&&conferenceNorm(hospital)==='苏州大学附属第一医院'?reviewedTaoEvents.map(x=>({...x})):[];}
export async function findOfficialConferenceEvents(name,hospital,fetcher=fetch){
 try{
  if(!agendaCache||Date.now()-agendaCache.at>6*60*60_000){
   const response=await fetcher(CSCO_AGENDA,{headers:{Accept:'text/html'},signal:AbortSignal.timeout(18000)});
   if(!response.ok)throw new Error('HTTP '+response.status);
   const html=await response.text();if(html.length<1000||html.length>6_000_000)throw new Error('日程页大小异常');
   agendaCache={html,at:Date.now()};
  }
  return {items:parseCscoAgenda(agendaCache.html,name,hospital),status:'queried'};
 }catch{return {items:[],status:'failed'};}
}
