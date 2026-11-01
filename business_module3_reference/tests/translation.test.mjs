import test from 'node:test';
import assert from 'node:assert/strict';
import {clean} from '../src/core.mjs';
import {lookupTranslation,translateItem,sourceFingerprint,validateTranslation,translationCapabilities} from '../src/translation.mjs';
const item={id:'test-translation',originalTitle:'A randomized trial',abstract:'Results: 120 patients received therapy. The response was 22.25% (95% CI: 19.57, 24.93). No survival benefit was demonstrated.'};
const value={title:'一项随机试验',abstract:'结果：120 名患者接受治疗。应答比例为 22.25%（95% CI：19.57，24.93）。未证实生存获益。',notes:''};
const env={LLM_API_URL:'https://translation.example.test/v1/chat/completions',LLM_API_KEY:'test-only',LLM_MODEL:'test-model'};
test('正文清洗保留小于、大于号及其间的研究数据',()=>{
 assert.equal(clean('<h4>Results</h4>Age < 18 years, OR = 2.99; CD4 > 200. <i>Conclusion</i>'),'Results Age < 18 years, OR = 2.99; CD4 > 200. Conclusion');
 assert.equal(clean('<p>p &lt; 0.05; <strong>n = 120</strong></p>'),'p < 0.05; n = 120');
});
test('原文任何变化使翻译指纹变化，旧译文不能用于新摘要',async()=>{
 assert.notEqual(await sourceFingerprint(item),await sourceFingerprint({...item,abstract:item.abstract+' Correction.'}));
 assert.equal(await lookupTranslation({...item,id:'doi:10.1371/journal.pone.0361185'}),null);
});
test('无模型、无缓存明确不可用，不把英文冒充中文译文',async()=>{
 let calls=0;const result=await translateItem(item,{},async()=>{calls++;throw new Error();});assert.equal(result.status,'unavailable');assert.equal(calls,0);assert.equal(result.translation,undefined);
 assert.equal(translationCapabilities({}).cachedCount,8);assert.equal(translationCapabilities({}).automatic,false);
});
test('中文内容和缺摘要无需翻译',async()=>{
 assert.equal((await translateItem({...item,originalTitle:'中国医保政策'})).status,'not_needed');
 assert.equal((await translateItem({...item,abstract:''})).status,'not_needed');
});
test('翻译验证保留数字，拒绝缺字段、未译及过度缩写',()=>{
 assert.equal(validateTranslation(value,item).reviewStatus,'not_reviewed');
 assert.throws(()=>validateTranslation({...value,abstract:value.abstract.replace('22.25','25.22')},item));
 assert.throws(()=>validateTranslation({...value,abstract:'译文'},item));
 assert.throws(()=>validateTranslation({...value,title:'English title'},item));
});
test('按需翻译去重并缓存，保留英文原文，不更改审核状态',async()=>{
 let calls=0;const original=structuredClone(item);const fetcher=async (url,options)=>{calls++;assert.equal(url,env.LLM_API_URL);const body=JSON.parse(options.body);assert.match(body.messages[0].content,/不删减/);assert.match(body.messages[1].content,/120 patients/);await new Promise(r=>setTimeout(r,20));return Response.json({choices:[{message:{content:JSON.stringify(value)}}]});};
 const [a,b]=await Promise.all([translateItem(item,env,fetcher),translateItem(item,env,fetcher)]);
 assert.equal(calls,1);assert.deepEqual(a,b);assert.equal(a.status,'ready');assert.equal(a.translation.reviewStatus,'not_reviewed');assert.deepEqual(item,original);
 assert.equal((await translateItem(item,{},fetcher)).status,'ready');assert.equal(calls,1);
});
test('服务异常和漏数字均保留原文，并允许重试',async()=>{
 const source={...item,abstract:item.abstract+' New source.'};
 assert.equal((await translateItem(source,env,async()=>new Response('bad',{status:503}))).status,'failed');
 const invalid=async()=>Response.json({choices:[{message:{content:JSON.stringify({...value,abstract:value.abstract.replace('120','100')})}}]});
 assert.equal((await translateItem(source,env,invalid)).status,'failed');assert.equal(await lookupTranslation(source),null);
});
