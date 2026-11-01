import test from 'node:test';
import assert from 'node:assert/strict';
import {assemble,SEEDS,parseFDA,parsePapers,collect,refreshFeed,validateSummary,day,TOPICS,SOURCES,PRODUCTS,parsePipeline,parseReports,parseChinaList,extractNHSAContent,matchChinaTopics,selectIndustry} from '../src/core.mjs';
import app from '../worker/index.js';
const now=new Date('2026-10-31T04:00:00Z');
const fixture={items:SEEDS,date:null,mode:'sample'};
test('全员内容不随个人负责领域变化；个人内容按领域隔离',()=>{
 const a=assemble(fixture,['cervical']),b=assemble(fixture,['lung']);
 assert.deepEqual(a.industry,b.industry);
 assert.ok(a.learning.every(x=>x.topics.includes('cervical')));
 assert.ok(b.learning.every(x=>x.topics.includes('lung')));
 assert.notDeepEqual(a.learning.map(x=>x.id),b.learning.map(x=>x.id));
});
test('无负责领域仍有行业动态，学习板块为空',()=>{const x=assemble(fixture,[]);assert.equal(x.industry.length,2);assert.equal(x.learning.length,0);});
test('相同 DOI 大小写合并，多方向匹配保留，跨板块正文只出现一次',()=>{
 const base={...SEEDS[2],doi:'10.123/ABC',id:'a',industry:true};
 const result=assemble({items:[base,{...base,doi:'10.123/abc',id:'b',topics:['lung'],industry:false}]},['lung']);
 assert.equal(result.industry.length,1);assert.equal(result.learning.length,0);assert.deepEqual(result.crossReferences,['a']);assert.deepEqual(result.industry[0].topics,['cervical','lung']);
});
test('多方向阅读预算不被单一方向占满',()=>{
 const items=Array.from({length:12},(_,n)=>({...SEEDS[2],id:'c'+n})).concat({...SEEDS[5],id:'l'});
 const x=assemble({items},['cervical','lung'],'brief');assert.equal(x.learning.length,3);assert.ok(x.learning.some(x=>x.id==='l'));
});
test('历史样例日期不被改成当日，审核状态保持未审核',()=>{
 for(const x of [...assemble(fixture).industry,...assemble(fixture).learning]){assert.ok(x.publishedAt<'2026');assert.equal(x.reviewStatus,'not_reviewed');}
});
test('FDA 过滤旧闻、未来日期、非医药内容与无效链接',()=>{
 const item=(title,date,link='https://www.fda.gov/x')=>`<item><title>${title}</title><link>${link}</link><pubDate>${date}</pubDate><description>Announcement</description></item>`;
 const xml='<rss><channel>'+item('Drug approval','Fri, 30 Oct 2026 16:00:00 EDT')+item('Drug old','Thu, 1 Jan 2026 16:00:00 GMT')+item('Drug future','Fri, 1 Jan 2027 16:00:00 GMT')+item('Food contamination','Fri, 30 Oct 2026 16:00:00 GMT')+item('Drug unsafe','Fri, 30 Oct 2026 16:00:00 GMT','javascript:alert(1)')+'</channel></rss>';
 const x=parseFDA(xml,now);assert.equal(x.length,1);assert.equal(x[0].publishedAt,'2026-10-30');assert.equal(x[0].summaryMode,'original_excerpt');
});
test('排除撤稿、更正和未来文献；缺摘要不编造结果',()=>{
 const base={source:'MED',id:'123',title:'Cervical cancer',firstPublicationDate:'2026-10-25'};
 const data={resultList:{result:[base,{...base,id:'124',pubTypeList:{pubType:['Retracted Publication']}},{...base,id:'125',firstPublicationDate:'2027-01-01'}]}};
 const x=parsePapers(data,TOPICS[0],now);assert.equal(x.length,1);assert.equal(x[0].summaryMode,'metadata_only');assert.match(x[0].summary,/未提供摘要/);
});
test('单一来源失败时仍返回其他领域，不回填历史样例',async()=>{
 const fetcher=async u=>{if(String(u).includes('/col/col104/'))return new Response('failed',{status:503});return emptySource(u);};
 const f=await collect(now,fetcher);assert.equal(f.status,'partial');assert.equal(f.sources.find(s=>s.id==='nhsa-policy').status,'failed');assert.deepEqual(f.items,[]);
});
test('所有来源失败与真实无新增保持不同状态',async()=>{
 const failed=await collect(now,async()=>new Response('fail',{status:500}));assert.equal(failed.status,'failed');
 const empty=await collect(now,async u=>emptySource(u));assert.equal(empty.status,'ok');assert.equal(empty.items.length,0);
});
test('AI 摘要必须返回可定位的原文证据，且不能自动获批',()=>{
 const item={originalTitle:'Study',abstract:'The trial enrolled patients with cervical cancer.'};const value={title:'标题',summary:'摘要',limitations:'限制',question:'问题',evidence:['The trial enrolled patients with cervical cancer.']};
 assert.equal(validateSummary(value,item).reviewStatus,'not_reviewed');assert.throws(()=>validateSummary({...value,evidence:['An invented statement absent from source.']},item));
});
test('API 输入验证与服务端边界',async()=>{
 for(const route of ['/api/digest?mode=bad','/api/digest?topics=unknown','/api/digest?length=huge'])assert.equal((await app.fetch(new Request('https://test.local'+route))).status,400);
 const r=await app.fetch(new Request('https://test.local/api/digest?topics=cervical&mode=sample'));assert.equal(r.status,200);const d=await r.json();assert.equal(d.learning.length,2);
 assert.equal((await app.fetch(new Request('https://test.local/api/digest',{method:'POST'}))).status,405);
});
test('日刊日期使用上海时区',()=>{assert.equal(day(new Date('2026-10-30T18:00:00Z')),'2026-10-31');});
function emptySource(u){return new Response(String(u).includes('/api/products/')?JSON.stringify({success:true,data:{肿瘤:PRODUCTS.map(p=>({id:+p.id,title:p.name,status:p.status==='marketed'?14:8,target:p.target,domain:''}))}}):String(u).includes('/api/reports')?JSON.stringify({success:true,data:[]}):String(u).includes('nhsa.gov.cn')?'<recordset></recordset>':String(u).includes('cdr-adr.org.cn')?'<table><tr><td class="liS2"></td></tr></table>':JSON.stringify({resultList:{result:[]}}));}
test('官网管线仅把状态 14 作为负责产品；在研不能被选择',async()=>{
 const parsed=parsePipeline({success:true,data:{肿瘤:PRODUCTS.map(p=>({id:+p.id,title:p.name,status:p.status==='marketed'?14:8,target:p.target,domain:''}))}});
 assert.equal(parsed.length,PRODUCTS.length);assert.ok(parsed.some(p=>p.status==='investigational'));
 assert.equal((await app.fetch(new Request('https://test.local/api/digest?mode=sample&products=86'))).status,400);
});
test('公司新闻稿区分在研与上市申请受理，按已上市产品过滤',()=>{
 const reports={success:true,data:[{id:1,title:'IBI363 临床研究结果',published_at:'2026-10-26 00:00:00',content:'<p>研究仍在进行。</p>'},{id:2,title:'信迪利单抗新增适应症上市申请获受理',published_at:'2026-10-26 00:00:00',content:'<p>申请获受理。</p>'}]};
 const items=parseReports(reports,PRODUCTS,now);assert.equal(items.length,2);assert.equal(items[0].approvalStatus,'在研项目，尚未获批');assert.equal(items[1].approvalStatus,'上市申请获受理，尚未获批');
 const digest=assemble({mode:'live',items,pipeline:{products:PRODUCTS}},[],'standard',['1']);assert.equal(digest.learning.length,2);assert.equal(digest.industry.length,0);
});
test('每日采集写入持久快照；全来源失败不覆盖上一期',async()=>{
 const files=new Map(),bucket={put:async(k,v)=>files.set(k,v),get:async k=>files.has(k)?{json:async()=>JSON.parse(files.get(k))}:null};
 const good=await refreshFeed({BUCKET:bucket},now,async u=>emptySource(u));
 assert.equal(good.status,'ok');assert.equal(JSON.parse(files.get('daily/latest.json')).date,day(now));
 const before=files.get('daily/latest.json');await refreshFeed({BUCKET:bucket},now,async()=>new Response('fail',{status:503}));assert.equal(files.get('daily/latest.json'),before);
});
const nhsa=SOURCES.find(s=>s.id==='nhsa-news'),cdr=SOURCES.find(s=>s.id==='cdr');
function row(title,date='2026-10-20',url='/art/2026/10/20/art_14_1.html'){return `<record><![CDATA[<li><a href="${url}" title="${title}">${title}</a><span>${date}</span></li>]]></record>`;}
test('国内列表保留中文标题和真实日期，排除过期、未来、无关和站外链接',()=>{
 const html='<recordset>'+row('医保药品目录调整')+row('药品旧闻','2026-01-01')+row('药品未来','2027-01-01')+row('药品无效日期','2026-02-30')+row('医保影像大赛公告')+row('药品外链','2026-10-20','https://evil.test/x')+row('药品危险链接','2026-10-20','javascript:alert(1)')+'</recordset>';
 const items=parseChinaList(html,nhsa,now);assert.equal(items.length,1);assert.equal(items[0].region,'CN');assert.equal(items[0].publishedAt,'2026-10-20');assert.equal(items[0].summaryMode,'metadata_only');assert.equal(items[0].abstract,'');
 assert.throws(()=>parseChinaList('<html>请完成验证</html>',nhsa,now));
});
test('药监索引日期不冒充原文发布日期，允许指向官方药监主站',()=>{
 const html='<table><tr><td><a href="https://www.nmpa.gov.cn/a.html" title="国家药监局批准某药上市">某药</a><div class="liS2">2026-10-27</div></td></tr></table>';
 const [item]=parseChinaList(html,cdr,now);assert.equal(item.publishedAt,null);assert.equal(item.listedAt,'2026-10-27');assert.equal(item.summaryMode,'metadata_only');assert.equal(item.sourceListURL,cdr.url);
});
test('医保正文按内容边界提取，不混入导航、脚本或举报页脚',()=>{
 const body=extractNHSAContent('<header>导航假消息</header><!--ZJEG_RSS.content.begin--><p>国家医保药品目录调整工作已开展，具体条件请核对官方原始文件。</p><script>evil()</script><p>中国医保，一生守护！页脚</p><!--ZJEG_RSS.content.end-->');
 assert.match(body,/目录调整/);assert.doesNotMatch(body,/导航|evil|页脚/);assert.throws(()=>extractNHSAContent('<html>没有正文</html>'));
});
test('中国主题按疾病匹配，不从药物名臆测适应证',()=>{
 assert.deepEqual(matchChinaTopics('宫颈癌与乳腺癌诊疗'),['cervical','breast']);assert.deepEqual(matchChinaTopics('某单抗注射液获批'),[]);
});
test('实时全员行业板块只收国内内容，兼顾药监和医保，不以 FDA 填空',()=>{
 const base={...SEEDS[0],mode:'live',region:'CN',sourceId:'cdr',publishedAt:'2026-10-25'};
 const items=[{...base,id:'a',title:'药监局批准某药上市'},{...base,id:'b',title:'修订药品说明书'},{...base,id:'c',sourceId:'nhsa-news',title:'重要提醒',abstract:'国家医保药品目录谈判签约'},{...base,id:'us',region:'US',title:'FDA approval',publishedAt:'2026-10-31'}];
 const selected=selectIndustry(items,2,true);assert.equal(selected.length,2);assert.ok(selected.some(x=>x.id==='c'));assert.ok(selected.every(x=>x.region==='CN'));assert.deepEqual(selectIndustry([items[3]],4,true),[]);
});
test('国内疾病学习优先，全员动态不因方向改变',()=>{
 const china={...SEEDS[2],id:'cn-cervical',region:'CN',sourceId:'nhsa-news',publishedAt:'2026-10-20',mode:'live'};
 const feed={mode:'live',items:[china,{...SEEDS[2],id:'international'},{...SEEDS[0],region:'CN',sourceId:'nhsa-policy'}]};
 const a=assemble(feed,['cervical']),b=assemble(feed,['lung']);assert.equal(a.learning[0].id,'cn-cervical');assert.deepEqual(a.industry,b.industry);assert.ok(b.learning.every(x=>x.topics.includes('lung')));
});
test('国内正文不可用时保留可核实标题，不编造政策摘要',async()=>{
 const fetcher=async u=>String(u).includes('/col/col14/')?new Response('<recordset>'+row('药品目录调整通知')+'</recordset>'):String(u).includes('/art/')?new Response('访问受限',{status:412}):emptySource(u);
 const f=await collect(now,fetcher);const item=f.items[0];assert.equal(item.summaryMode,'metadata_only');assert.equal(item.abstract,'');assert.match(item.summaryNotice,/未获取/);assert.equal(f.sources.find(s=>s.id==='nhsa-news').metadataOnly,1);
});
