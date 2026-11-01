import test from 'node:test';
import assert from 'node:assert/strict';
import {DEMO_PROFILE,demoProfileSummary} from '../src/demo-profile.mjs';
import {assemble,PRODUCTS} from '../src/core.mjs';
import app from '../worker/index.js';

test('单一虚构档案的数量一致，负责产品与在研学习分开',()=>{
 const p=demoProfileSummary(PRODUCTS);
 assert.equal(p.id,'demo-me');assert.equal(p.fictional,true);
 assert.deepEqual(p.territory,['姑苏区','虎丘区']);
 assert.equal(p.hospitalCount,7);assert.equal(p.doctorCount,22);assert.equal(p.keyCount,14);
 assert.deepEqual(p.productIds,['1','2']);assert.deepEqual(p.learning.map(x=>x.id),['85']);
 assert.ok(p.marketed.every(x=>PRODUCTS.some(y=>y.id===x.id&&y.status==='marketed')));
 assert.ok(p.learning.every(x=>PRODUCTS.some(y=>y.id===x.id&&y.status==='investigational')));
 assert.ok(DEMO_PROFILE.hospitals.every(h=>h.sourceUrl.startsWith('https://hrss.suzhou.gov.cn/')));
});

test('全员动态保持共享，个人学习只匹配档案负责的已上市产品',()=>{
 const p=demoProfileSummary(PRODUCTS);
 const base={id:'industry',industry:true,region:'CN',sourceId:'nhsa-news',topics:[],productIds:[],title:'医保政策',publishedAt:'2026-10-30',mode:'live'};
 const product=(id,productId)=>({...base,id,industry:false,sourceId:'innovent-reports',productIds:[productId],title:id});
 const feed={mode:'live',date:'2026-10-31',items:[base,product('io','1'),product('other','83')],pipeline:{products:PRODUCTS}};
 const digest=assemble(feed,[],'standard',p.productIds);
 assert.deepEqual(digest.industry.map(x=>x.id),['industry']);
 assert.deepEqual(digest.learning.map(x=>x.id),['io']);
});

test('个人日报由服务端档案决定产品，忽略客户端伪造参数',async()=>{
 const response=await app.fetch(new Request('https://test.local/api/digest?mode=sample&profile=me&products=83'));
 const digest=await response.json();
 assert.equal(response.status,200);
 assert.deepEqual(digest.productIds,['1','2']);
 assert.equal(digest.profile.name,'林知安');
 assert.ok(digest.learning.some(x=>x.id==='example-io-pd1'));
 assert.ok(!digest.learning.some(x=>x.productIds?.includes('83')));
 const config=await (await app.fetch(new Request('https://test.local/api/config'))).json();
 assert.equal(config.profile.hospitalCount,7);
 assert.equal((await app.fetch(new Request('https://test.local/api/digest?mode=sample&profile=unknown'))).status,400);
});
