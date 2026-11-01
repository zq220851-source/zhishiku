'use strict';
// Test runner must never read `expected`; it reads test INPUT only.
const fs=require('node:fs'),path=require('node:path');
const root=path.join(__dirname,'../../../../review_lab');
const raw=JSON.parse(fs.readFileSync(path.join(root,'challenge_inputs.json'),'utf8'));
const {oldKeywordProxy,guardedQuestionProxy}=require('./methods.cjs');
const {scopedQuestionProxy}=require('./methods_v07.cjs');
const out=raw.map(c=>({id:c.id,input:c.text,baseline:oldKeywordProxy(c.text),previous:guardedQuestionProxy(c.text),candidate:scopedQuestionProxy(c.text).mode,rationale:scopedQuestionProxy(c.text).reason}));
fs.writeFileSync(path.join(root,'challenge_observed.json'),JSON.stringify(out,null,2));
console.log('Challenge output',out.length);
