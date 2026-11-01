import {test} from 'node:test';
import assert from 'node:assert/strict';
import {connectedConfig,readModule1} from '../src/live-knowledge.mjs';
test('module3 uses module1 products and preserves source state, without demo employee',async()=>{
 const cfg=await connectedConfig({MODULE1_BASE_URL:'http://127.0.0.1:8892'},[{id:'1',name:'达伯舒®'}],[],[],async u=>{
  assert.equal(u,'http://127.0.0.1:8892/api/knowledge/catalog');
  return Response.json({system:'MODULE1',mode:'SOURCE_CORPUS',version:'v1',products:[{brand:'达伯舒',product_id:'daboshu',review_status:'pending_medical_review'}],courses:[],questions:[],claims:[],sources:[]});
 });
 assert.equal(cfg.products[0].module1ProductId,'daboshu');assert.equal(cfg.products[0].sourceStatus,'pending_medical_review');assert.equal(cfg.profile,null);
});
test('source failure and non-loopback source never fall back to seed data',async()=>{
 await assert.rejects(readModule1({MODULE1_BASE_URL:'http://example.com'},'/api/knowledge/catalog'));
 await assert.rejects(readModule1({MODULE1_BASE_URL:'http://127.0.0.1:8892'},'/api/knowledge/catalog',async()=>new Response('',{status:503})));
});
