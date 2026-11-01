'use strict';
/** Uses the actual TypeScript five-asset domain code after local transpilation. */
const fs=require('fs'),path=require('path');
const {projectVisit}=require('../../../../compiled/lib/five-assets.js');
const {oldKeywordProxy,guardedQuestionProxy}=require('./methods.cjs');
const input=JSON.parse(fs.readFileSync(path.join(__dirname,'cases_input.json'),'utf8'));
function trial(id,fn){
  const v=input.find(x=>x.id===id);if(!v)throw new Error(id);
  const mode=fn(v.text);
  const span={quote:v.text,startCp:0,endCp:Array.from(v.text).length};
  const out=projectVisit({usage:'TEST_ONLY',visitId:v.id,taskId:'task-'+v.id,repId:'rep-test',expertId:'expert-test',researchId:'study-test',snapshotHash:'fixed-task-snapshot',rawVersion:1,rawText:v.text,occurredAt:'2026-10-01T10:00:00Z',forecast:{candidateCapabilityIds:['subgroup','extrapolation'],selectedCapabilityIds:['subgroup'],budget:1},observations:[{id:'e1',kind:'EXPERT_QUESTION',capabilityId:'extrapolation',mode,...span}],knowledgeChecks:[],practices:[]});
  return {method:fn.name,mode,entries:out.entries.map(x=>({kind:x.kind,label:x.label,targetId:x.targetId}))};
}
const results=['D02','S01','S09','H01','H12'].map(id=>({id,text:input.find(x=>x.id===id).text,baseline:trial(id,oldKeywordProxy),candidate:trial(id,guardedQuestionProxy)}));
fs.writeFileSync(path.join(__dirname,'asset_trace.json'),JSON.stringify(results,null,2));
console.log(results.map(x=>`${x.id} baseline:${x.baseline.mode} assets:${x.baseline.entries.length} candidate:${x.candidate.mode} assets:${x.candidate.entries.length}`).join('\n'));
