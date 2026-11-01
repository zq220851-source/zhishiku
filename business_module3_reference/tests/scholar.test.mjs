import test from 'node:test';
import assert from 'node:assert/strict';
import {buildScholarProfile,romanizations,validateScholarInput} from '../src/scholar.mjs';

test('中文姓名转检索别名，输入只需医院和姓名',()=>{
 assert.deepEqual(romanizations('沈琳'),['Lin Shen','Shen Lin']);
 assert.deepEqual(validateScholarInput('北京大学肿瘤医院','沈琳主任'),{hospital:'北京大学肿瘤医院',name:'沈琳'});
 assert.throws(()=>validateScholarInput('医院','沈琳'));
});

test('论文必须在同一署名行出现候选作者和目标医院；网页只保留有姓名的活动线索',async()=>{
 const inst='https://openalex.org/I111',author='https://openalex.org/A222';
 const calls=[];
 const fetcher=async(raw,options)=>{
  const u=new URL(raw);let data;
  calls.push({host:u.hostname,authorization:options.headers.Authorization||null});
  if(u.hostname==='api.openalex.org'&&u.pathname==='/institutions')data={results:[{id:inst,display_name:'Huacheng Hospital',display_name_alternatives:['华城人民医院'],works_count:100}]};
  else if(u.hostname==='api.openalex.org'&&u.pathname==='/authors')data={results:[{id:author,display_name:'San Zhang',works_count:20,last_known_institutions:[{id:inst}],affiliations:[]}]};
  else if(u.hostname==='api.openalex.org'&&u.pathname==='/works')data={results:[
   {id:'https://openalex.org/W1',display_name:'Study of drug',publication_date:'2026-01-01',authorships:[{author:{id:author,display_name:'San Zhang'},institutions:[{id:inst}],raw_affiliation_strings:['Huacheng Hospital']}],doi:'https://doi.org/10.1/test'},
   {id:'https://openalex.org/W2',display_name:'Wrong attribution',publication_date:'2026-01-02',authorships:[{author:{id:author},institutions:[{id:'https://openalex.org/I999'}]},{author:{id:'https://openalex.org/A999'},institutions:[{id:inst}]}]},
   {id:'https://openalex.org/W3',display_name:'[Retracted] Unreliable work',publication_date:'2026-01-03',authorships:[{author:{id:author},institutions:[{id:inst}]}]}
  ]};
  else if(u.hostname==='api.search.brave.com')data={web:{results:[{title:'华城人民医院张三主任在学术会议作报告',description:'会议公开报道',url:'https://example.org/event'},{title:'其他医院李四的会议',description:'无关',url:'https://example.org/other'}]}};
  else if(u.hostname==='api.mymemory.translated.net')data={responseData:{translatedText:'药物研究'}};
  else throw new Error('unexpected '+u.href);
  return {ok:true,json:async()=>data};
 };
 const p=await buildScholarProfile({hospital:'华城人民医院',name:'张三'},fetcher,{OPENALEX_API_KEY:'test-openalex',BRAVE_SEARCH_API_KEY:'test'});
 assert.equal(p.papers.length,1);assert.equal(p.papers[0].id,'https://openalex.org/W1');
 assert.equal(p.papers[0].translatedTitle,'药物研究');
 assert.equal(p.events.length,1);assert.match(p.events[0].verification,/网页正文待核对/);
 assert.equal(p.webSearchStatus,'queried');
 assert.ok(calls.filter(x=>x.host==='api.openalex.org').every(x=>x.authorization==='Bearer test-openalex'));
 assert.ok(calls.filter(x=>x.host!=='api.openalex.org').every(x=>x.authorization===null));
 assert.doesNotMatch(JSON.stringify(p),/test-openalex/);
});
