'use strict';
const fs=require('fs'),path=require('path');
const {oldKeywordProxy,guardedQuestionProxy}=require('./methods.cjs');
const samples=JSON.parse(fs.readFileSync(path.join(__dirname,'cases_input.json'),'utf8'));
const output=samples.map(({id,split,text})=>({id,split,baseline:oldKeywordProxy(text),candidate:guardedQuestionProxy(text),input:text}));
const out=path.join(__dirname,'observed.json');fs.writeFileSync(out,JSON.stringify(output,null,2));
console.log('wrote',out,'cases:',output.length);
