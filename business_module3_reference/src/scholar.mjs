import {PINYIN_MAP} from './pinyin-map.mjs';
import {findOfficialConferenceEvents,reviewedPublicEvents} from './conference.mjs';

const scholarCache=new Map();
const pageSize=12;
const cleanText=value=>String(value||'').replace(/<[^>]+>/g,' ').replace(/&(?:amp|lt|gt|quot|apos);/g,m=>({'&amp;':'&','&lt;':'<','&gt;':'>','&quot;':'"','&apos;':"'"}[m])).replace(/\s+/g,' ').trim();
const cleanAffiliation=value=>cleanText(value).replace(/\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b/g,'').replace(/\bElectronic address:\s*/gi,'').trim();
const norm=value=>String(value||'').toLowerCase().replace(/[^a-z\u3400-\u9fff]/g,'');
const personName=value=>String(value||'').trim().replace(/(?:主任|教授|医生|医师|博士)$/,'');
const pinyin=value=>[...value].map(c=>PINYIN_MAP[c]||c).filter(Boolean);
function requestURL(base,params){const u=new URL(base);u.search=new URLSearchParams(params);return u.href;}
async function getJSON(url,fetcher,headers={}){const r=await fetcher(url,{headers:{Accept:'application/json',...headers},signal:AbortSignal.timeout(12000)});if(!r.ok)throw new Error('HTTP '+r.status);return r.json();}
export function validateScholarInput(hospital,name){
 hospital=String(hospital||'').trim();name=personName(name);
 if(hospital.length<3||hospital.length>80||name.length<2||name.length>30||/[<>\x00-\x1f]/.test(hospital+name))throw new Error('请输入完整医院名称和主任姓名');
 return {hospital,name};
}
export function romanizations(name){
 const parts=pinyin(name);if(parts.length<2||parts.some(x=>!/^[a-z]+$/.test(x)))return [];
 const surname=parts[0][0].toUpperCase()+parts[0].slice(1),given=parts.slice(1).join('');
 const givenTitle=given[0].toUpperCase()+given.slice(1);
 return [...new Set([givenTitle+' '+surname,surname+' '+givenTitle])];
}
function institutionScore(x,query){const target=norm(query),names=[x.display_name,...(x.display_name_alternatives||[])].map(norm);return names.includes(target)?4:names.some(n=>n.length>=6&&(n.includes(target)||target.includes(n)))?2:0;}
async function findInstitution(hospital,fetcher,apiKey){
 const d=await getJSON(requestURL('https://api.openalex.org/institutions',{search:hospital,per_page:5}),fetcher,apiKey?{Authorization:'Bearer '+apiKey}:{});
 const list=(d.results||[]).filter(x=>x.id&&x.display_name);
 const sorted=list.map(x=>({...x,score:institutionScore(x,hospital)})).sort((a,b)=>b.score-a.score||Number(b.works_count||0)-Number(a.works_count||0));
 return sorted[0]?.score>=2?sorted[0]:null;
}
function candidateScore(x,aliases,institution){
 const same=aliases.some(n=>norm(n)===norm(x.display_name)||norm(n)===norm(x.display_name.replace(/\b[A-Z]\b/g,'')));
 if(!same)return -1;
 const institutionHit=[...(x.affiliations||[]).map(a=>a.institution),...(x.last_known_institutions||[])].some(i=>i?.id===institution.id);
 return institutionHit?10:1;
}
async function findAuthors(name,institution,fetcher,apiKey){
 const aliases=romanizations(name);const tasks=[name,...aliases].map(search=>getJSON(requestURL('https://api.openalex.org/authors',{search,per_page:20}),fetcher,apiKey?{Authorization:'Bearer '+apiKey}:{}).catch(()=>({results:[]})));
 const data=await Promise.all(tasks),map=new Map();for(const d of data)for(const x of d.results||[])if(x.id&&!map.has(x.id))map.set(x.id,x);
 return [...map.values()].map(x=>({...x,matchScore:candidateScore(x,aliases,institution)})).filter(x=>x.matchScore>=10).sort((a,b)=>b.matchScore-a.matchScore||Number(b.works_count||0)-Number(a.works_count||0)).slice(0,3);
}
function paperEvidence(work,author,institution){
 if(/\b(correction|erratum|retract(?:ed|ion)|withdrawn|expression of concern)\b|更正|撤稿|撤回|收回/i.test(work.display_name||''))return null;
 const line=(work.authorships||[]).find(x=>x.author?.id===author.id&&x.institutions?.some(i=>i.id===institution.id));
 if(!line)return null;
 return {id:work.id,title:cleanText(work.display_name),date:work.publication_date||null,sourceUrl:work.doi||work.id,source:'OpenAlex',publicationType:work.type==='preprint'?'预印本':'文献记录',affiliation:cleanAffiliation(line.raw_affiliation_strings?.find(s=>s)||institution.display_name),authorName:line.raw_author_name||author.display_name,authorId:author.id,institutionId:institution.id,pmid:work.ids?.pmid?.split('/').pop()||null,medicalIndexStatus:'not_checked',verification:'同一署名行出现作者与目标医院',translationStatus:'pending',translatedTitle:null};
}
async function findPapers(authors,institution,fetcher,apiKey){
 const all=await Promise.all(authors.map(async author=>{
  try{const d=await getJSON(requestURL('https://api.openalex.org/works',{filter:'author.id:'+author.id.split('/').pop(),per_page:50,sort:'publication_date:desc'}),fetcher,apiKey?{Authorization:'Bearer '+apiKey}:{});return (d.results||[]).map(w=>paperEvidence(w,author,institution)).filter(Boolean);}catch{return [];}
 }));
 const map=new Map();for(const p of all.flat())if(!map.has(p.id))map.set(p.id,p);
 const papers=[...map.values()].sort((a,b)=>String(b.date||'').localeCompare(String(a.date||''))).slice(0,pageSize);
 const pmids=papers.map(x=>x.pmid).filter(x=>/^\d+$/.test(x));
 if(pmids.length)try{
  const query='('+pmids.map(x=>'EXT_ID:'+x).join(' OR ')+') AND SRC:MED';
  const d=await getJSON(requestURL('https://www.ebi.ac.uk/europepmc/webservices/rest/search',{query,format:'json',pageSize:25}),fetcher);
  const indexed=new Set((d.resultList?.result||[]).map(x=>x.pmid));
  for(const p of papers)if(p.pmid)p.medicalIndexStatus=indexed.has(p.pmid)?'pubmed_indexed':'not_found';
 }catch{for(const p of papers)if(p.pmid)p.medicalIndexStatus='source_unavailable';}
 return papers;
}
function parseWebResults(data,name,hospital,kind){
 return (data.web?.results||[]).map(x=>{
  const title=cleanText(x.title),snippet=cleanText(x.description),evidence=title+' '+snippet;
  let u;try{u=new URL(x.url);if(u.protocol!=='https:')return null;}catch{return null;}
  if(!evidence.includes(name)||!/(会议|大会|论坛|年会|演讲|报告|发言|讲座|学术)/.test(evidence))return null;
  const sameHospital=evidence.includes(hospital),confirmed=sameHospital&&/(主讲|发表.*报告|作.*报告|演讲|发言|主持)/.test(evidence);
  return {title,snippet,url:u.href,domain:u.hostname,kind,date:null,verification:confirmed?'搜索摘要写明医院、姓名及活动角色；网页正文待核对':sameHospital?'搜索摘要同时出现姓名与医院；活动角色待核对':'仅姓名命中；同名风险高',confidence:confirmed?'role_in_snippet':sameHospital?'matched_snippet':'name_only'};
 }).filter(Boolean);
}
async function findEvents(name,hospital,fetcher,apiKey){
 if(!apiKey)return {items:[],status:'not_configured'};
 const kinds=[['会议',`"${hospital}" "${name}" 会议 大会 论坛`],['演讲',`"${hospital}" "${name}" 演讲 报告 发言 讲座`]];
 const results=await Promise.all(kinds.map(async([kind,q])=>{try{return {items:parseWebResults(await getJSON(requestURL('https://api.search.brave.com/res/v1/web/search',{q,count:10}),fetcher,{'X-Subscription-Token':apiKey}),name,hospital,kind),failed:false};}catch{return {items:[],failed:true};}}));
 const map=new Map();for(const x of results.flatMap(r=>r.items))if(!map.has(x.url))map.set(x.url,x);
 return {items:[...map.values()].sort((a,b)=>(b.confidence==='role_in_snippet')-(a.confidence==='role_in_snippet')||(b.confidence==='matched_snippet')-(a.confidence==='matched_snippet')).slice(0,12),status:results.every(r=>r.failed)?'failed':results.some(r=>r.failed)?'partial':'queried'};
}
async function collectEvents(name,hospital,fetcher,env){
 const [official,web]=await Promise.all([findOfficialConferenceEvents(name,hospital,fetcher),findEvents(name,hospital,fetcher,env.BRAVE_SEARCH_API_KEY)]);
 const map=new Map();for(const e of [...official.items,...reviewedPublicEvents(name,hospital),...web.items]){
  const key=e.url+'|'+e.title;if(!map.has(key))map.set(key,e);
 }
 return {items:[...map.values()].sort((a,b)=>String(b.date||'').localeCompare(String(a.date||''))),officialStatus:official.status,webStatus:web.status};
}
async function translateTitle(title,fetcher){
 if(/[\u3400-\u9fff]/.test(title))return title;
 try{const d=await getJSON(requestURL('https://api.mymemory.translated.net/get',{q:title.slice(0,490),langpair:'en|zh-CN'}),fetcher);const value=cleanText(d.responseData?.translatedText);return /[\u3400-\u9fff]/.test(value)&&!d.quotaFinished?value:null;}catch{return null;}
}
export async function buildScholarProfile(input,fetcher=fetch,env={}){
 const {hospital,name}=validateScholarInput(input.hospital,input.name),key=hospital+'|'+name,prior=scholarCache.get(key);
 if(prior&&Date.now()-prior.at<10*60_000)return prior.value;
 const checkedAt=new Date().toISOString(),institution=await findInstitution(hospital,fetcher,env.OPENALEX_API_KEY);
 if(!institution){const eventSearch=await collectEvents(name,hospital,fetcher,env),events=eventSearch.items;await Promise.all(events.map(async e=>{e.translatedTitle=await translateTitle(e.title,fetcher);e.translatedSnippet=await translateTitle(e.snippet,fetcher);}));const value={hospital,name,checkedAt,status:'institution_unmatched',papers:[],events,candidates:[],webSearchStatus:eventSearch.webStatus,officialAgendaStatus:eventSearch.officialStatus,sources:[{name:'OpenAlex 机构索引',status:'未匹配'},{name:'中国临床肿瘤学会公开日程',status:eventSearch.officialStatus},{name:'Brave Search 公开网页索引',status:eventSearch.webStatus}],note:'未能在学术索引中可靠匹配该医院。请使用医院全称；系统没有据此推断任何作者或论文。',coverage:'公开索引结果，非完整履历；不对学术能力评分。'};scholarCache.set(key,{at:Date.now(),value});return value;}
 const [authors,eventSearch]=await Promise.all([findAuthors(name,institution,fetcher,env.OPENALEX_API_KEY),collectEvents(name,hospital,fetcher,env)]),events=eventSearch.items;
 const papers=await findPapers(authors,institution,fetcher,env.OPENALEX_API_KEY);
 await Promise.all([...papers.map(async p=>{p.translatedTitle=await translateTitle(p.title,fetcher);p.translationStatus=p.translatedTitle?'machine_translated':'unavailable';}),...events.map(async e=>{e.translatedTitle=await translateTitle(e.title,fetcher);e.translatedSnippet=await translateTitle(e.snippet,fetcher);})]);
 const value={hospital,name,checkedAt,status:authors.length?'candidate_found':'author_unmatched',institution:{id:institution.id,name:institution.display_name,officialName:hospital},candidates:authors.map(a=>({id:a.id,displayName:a.display_name,orcid:a.orcid||null,worksCount:a.works_count||0})),papers,events,webSearchStatus:eventSearch.webStatus,officialAgendaStatus:eventSearch.officialStatus,sources:[{name:'OpenAlex 机构、作者与论文索引',status:'已查询',url:'https://openalex.org/'},{name:'PubMed · Europe PMC 医学文献索引',status:'有 PubMed 编号的论文已核对',url:'https://europepmc.org/'},{name:'中国临床肿瘤学会公开日程',status:eventSearch.officialStatus,url:'https://meeting.csco.org.cn/home/program/39'},{name:'Brave Search 公开网页索引',status:eventSearch.webStatus,url:'https://search.brave.com/'}],note:authors.length>1?'同名候选作者不止一位；论文只显示同一署名行同时出现候选作者和目标医院的记录，仍需人工核实具体身份。':'论文按同一署名行的作者与医院筛选；公开会议记录按来源标明角色和核验程度。',coverage:'公开索引结果，非完整履历；不对学术能力评分。'};
 scholarCache.set(key,{at:Date.now(),value});return value;
}
