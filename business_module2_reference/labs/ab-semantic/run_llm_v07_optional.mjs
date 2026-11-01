/** Explicit opt-in. Sends ONLY this repository's fictional challenge strings.
 * A model is a PROPOSER, never a verifier; outputs are not inserted into assets.
 * `node /path/to/medrep_v07_work/transpile.cjs` first to compile validation code.
 */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
const require=createRequire(import.meta.url);
const root=path.resolve(import.meta.dirname,'../../../../');
const {reanchorUniqueQuotes,validateSemanticProposal,SEMANTIC_EXTRACTION_INSTRUCTIONS}=require(path.join(root,'compiled/lib/semantic-proposal.js'));
const cfg={url:process.env.MODULE2_MODEL_BASE_URL,model:process.env.MODULE2_MODEL_NAME,key:process.env.MODULE2_MODEL_API_KEY};
if(process.env.ALLOW_SYNTHETIC_EXTERNAL_MODEL!=='YES'||!cfg.url||!cfg.model||!cfg.key){
 console.error('Not run: provide synthetic-data consent plus model endpoint/name/key. No external call made.');process.exit(2);
}
const cases=JSON.parse(fs.readFileSync(path.join(root,'review_lab/challenge_inputs.json'),'utf8'));
const max=Math.min(Number(process.env.MAX_CASES||3),cases.length);
const results=[];
for(const sample of cases.slice(0,max)){
 const p={usage:'TEST_ONLY',rawVersion:1,rawText:sample.text,events:[],links:[]};
 let result;
 try {
  const ctl=new AbortController();const timeout=setTimeout(()=>ctl.abort(),60000);
  let res;
  try{
   res=await fetch(cfg.url.replace(/\/$/,'')+'/chat/completions',{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${cfg.key}`},body:JSON.stringify({model:cfg.model,temperature:0,messages:[{role:'system',content:SEMANTIC_EXTRACTION_INSTRUCTIONS+' JSON 示例结构：'+JSON.stringify(p)+'。事件字段 action: QUESTION/RESPONSE/REFLECTION/NARRATION_CORRECTION/OTHER; agent: EXPERT/REP/OTHER/UNKNOWN; when: DURING_VISIT/AFTER_VISIT/FUTURE/UNKNOWN; factuality: REPORTED/DENIED/HYPOTHETICAL/UNCERTAIN; negationScope: TARGET_EVENT/DIFFERENT_EVENT/NO_NEGATION/UNRESOLVED; capabilityId: null。只分析原文，若没有可证实的专家现场问题允许 events=[]。'},{role:'user',content:sample.text}]}),signal:ctl.signal});
  } finally {clearTimeout(timeout);}
  if(!res.ok)throw new Error('HTTP '+res.status);
  const data=await res.json();
  const raw=String(data.choices?.[0]?.message?.content||'').trim();
  const cleaned=raw.replace(/^```(?:json)?\s*/,'').replace(/\s*```$/,'');
  const parsed=JSON.parse(cleaned);
  // Original input and version are authoritative, regardless of model echo.
  const normalized=reanchorUniqueQuotes({...parsed,usage:'TEST_ONLY',rawVersion:1,rawText:sample.text});
  const snapshot=validateSemanticProposal(normalized.proposal);
  result={id:sample.id,status:'UNVERIFIED_MODEL_PROPOSAL',events:snapshot.events,links:snapshot.links,offsetCorrections:normalized.adjustments};
 }catch(error){result={id:sample.id,status:'ERROR_UNVERIFIED',error:String(error).slice(0,180)};}
 results.push(result);
}
const output=path.join(root,'review_lab/llm_proposals_unreviewed.json');
fs.writeFileSync(output,JSON.stringify(results,null,2));
console.log('Saved',results.length,'UNVERIFIED proposals. No expert profile, knowledge, or company skill was updated.');
