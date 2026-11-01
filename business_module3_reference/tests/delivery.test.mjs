import test from 'node:test';
import assert from 'node:assert/strict';
import {formatDailyMessage,sendFeishuDigest,validateAssignments,dispatchFeishuDaily,deliveryCapabilities} from '../src/delivery.mjs';
import {assemble,PRODUCTS} from '../src/core.mjs';

const item={id:'news-1',title:'信迪利单抗新增适应症上市申请获受理',url:'https://www.innoventbio.com/#/news/715',publishedAt:'2026-10-26',topics:[],productIds:['1'],industry:false,approvalStatus:'上市申请获受理，尚未获批'};
const feed={date:'2026-10-31',mode:'live',status:'ok',items:[{...item,id:'industry',title:'医保目录调整',industry:true,region:'CN',sourceId:'nhsa-news',productIds:[]},item],pipeline:{products:PRODUCTS}};
const digest=assemble(feed,[],'standard',['1']);

test('同一条个人日报消息保留全员与产品两部分、来源和审批边界',()=>{
 const message=formatDailyMessage(digest);
 assert.match(message,/行业动态 · 全员共读/);assert.match(message,/产品与在研学习 · 按负责产品/);
 assert.match(message,/上市申请获受理，尚未获批/);assert.match(message,/https:\/\/www\.innoventbio\.com/);
 assert.match(message,/未经医学审核/);
});
test('飞书未配置时不伪称已连接；分配表只接受已上市产品',()=>{
 assert.equal(deliveryCapabilities({}).feishu.status,'unconfigured');
 assert.deepEqual(validateAssignments([{employee_id:'E1',feishu_open_id:'ou_123456789',product_ids:['1'],active:true}],PRODUCTS)[0].productIds,['1']);
 assert.throws(()=>validateAssignments([{employee_id:'E1',feishu_open_id:'ou_123456789',product_ids:['86'],active:true}],PRODUCTS),/在研/);
 assert.throws(()=>validateAssignments([{employee_id:'E1',feishu_open_id:'not-open-id',product_ids:['1'],active:true}],PRODUCTS),/open_id/);
});
test('飞书消息使用企业应用 token、个人 open_id 与同日报稳定去重 ID',async()=>{
 const calls=[],fetcher=async(url,options)=>{
  calls.push({url:String(url),options});
  return new Response(JSON.stringify(String(url).includes('/oauth/v3/token')?{code:0,access_token:'test-token',expires_in:7200}:{code:0,data:{message_id:'om_test'}}),{headers:{'Content-Type':'application/json'}});
 };
 const env={FEISHU_APP_ID:'cli_test1',FEISHU_APP_SECRET:'secret-for-test'};
 const result=await sendFeishuDigest(digest,'ou_123456789',env,fetcher);
 assert.equal(result.messageId,'om_test');assert.equal(calls.length,2);
 const tokenBody=JSON.parse(calls[0].options.body);assert.equal(tokenBody.grant_type,'client_credentials');
 assert.equal(tokenBody.client_id,'cli_test1');
 assert.match(calls[1].url,/receive_id_type=open_id/);
 const body=JSON.parse(calls[1].options.body);assert.equal(body.receive_id,'ou_123456789');assert.equal(body.msg_type,'text');
 assert.match(JSON.parse(body.content).text,/行业动态/);assert.equal(body.uuid,result.requestId);
 assert.equal(calls[1].options.headers.Authorization,'Bearer test-token');
});
test('定时飞书投递默认关闭；开启后按员工去重且不重复发同日报',async()=>{
 const files=new Map([['delivery/assignments.json',JSON.stringify([{employee_id:'E1',feishu_open_id:'ou_123456789',product_ids:['1'],active:true}])]]);
 const bucket={get:async key=>files.has(key)?{json:async()=>JSON.parse(files.get(key))}:null,put:async(key,value)=>files.set(key,value)};
 let sends=0;const fetcher=async url=>{if(String(url).includes('/oauth/v3/token'))return new Response(JSON.stringify({code:0,access_token:'token',expires_in:7200}));sends++;return new Response(JSON.stringify({code:0,data:{message_id:'om_one'}}));};
 const env={BUCKET:bucket,FEISHU_DELIVERY_ENABLED:'true',FEISHU_APP_ID:'cli_test2',FEISHU_APP_SECRET:'secret-for-test'};
 assert.equal((await dispatchFeishuDaily(feed,{...env,FEISHU_DELIVERY_ENABLED:'false'},assemble,fetcher)).status,'disabled');
 const first=await dispatchFeishuDaily(feed,env,assemble,fetcher),second=await dispatchFeishuDaily(feed,env,assemble,fetcher);
 assert.equal(first.sent,1);assert.equal(second.skipped,1);assert.equal(sends,1);
});
