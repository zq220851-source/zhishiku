'use strict';
const fs=require('node:fs'),path=require('node:path');
const {oldKeywordProxy,guardedQuestionProxy}=require('./methods.cjs');
const {scopedQuestionProxy}=require('./methods_v07.cjs');
const fixtures=JSON.parse(fs.readFileSync(path.join(__dirname,'cases_input.json'),'utf8'));
const observed=fixtures.map(x=>({id:x.id,split:x.split,input:x.text,baseline:oldKeywordProxy(x.text),previous:guardedQuestionProxy(x.text),candidate:scopedQuestionProxy(x.text).mode,rationale:scopedQuestionProxy(x.text).reason,evidence:scopedQuestionProxy(x.text).evidence}));
fs.writeFileSync(path.join(__dirname,'observed_v07.json'),JSON.stringify(observed,null,2));
console.log('V0.7 created',observed.length,'comparison outputs');
