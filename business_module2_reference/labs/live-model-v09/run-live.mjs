/**
 * Actual-model runner. Reads ONLY input prompts, never the frozen answer key.
 * Calls the V0.8 project's compatibleSemanticExtractor and stageSemanticEvidence.
 * Outputs unreviewed proposals; does NOT update the five long-term assets.
 * No key is ever written to file or terminal.
 */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const dir=path.dirname(fileURLToPath(import.meta.url));
const module2=path.resolve(dir,'../..');
const {compatibleSemanticExtractor,stageSemanticEvidence}=require(path.join(module2,'.bench-compiled/lib/semantic-pipeline.js'));
const {settings}=require(path.join(module2,'.bench-compiled/lib/provider.js'));
const inputFile=path.join(dir,'inputs.json');
const outputFile=process.env.V09_OUTPUT_PATH || path.join(dir,'unreviewed-results.json');
const maxArg=(process.argv.find(a=>a.startsWith('--max='))||'--max=3').split('=')[1];
const max=Number(maxArg);
if(!Number.isSafeInteger(max)||max<1||max>25){console.error('Use --max=1 through --max=25.');process.exit(2);}
if(process.env.MODULE2_MODEL_DATA_AUTHORIZED!=='true'){
 console.error('Only synthetic inputs are eligible. Set MODULE2_MODEL_DATA_AUTHORIZED=true explicitly.');process.exit(2);
}
const config=settings();
if(!config.baseUrl||!config.model||!config.apiKey){
 console.error('Model endpoint/name/key are missing from server-side environment. No request made.');process.exit(2);
}
if(!/^https:\/\//i.test(config.baseUrl)){console.error('HTTPS model endpoint required.');process.exit(2);}
const samples=JSON.parse(fs.readFileSync(inputFile,'utf8'));
if(!Array.isArray(samples)||samples.some(x=>x.source && x.source!=='SYNTHETIC_TEST_ONLY')){
 console.error('Input set is not exclusively synthetic.');process.exit(2);
}
// Ensure a fixed, nonempty, unique sample roster, without loading answer key.
if(new Set(samples.map(x=>x.id)).size!==samples.length||samples.some(x=>!x.text||!x.id)){
 console.error('Input samples invalid.');process.exit(2);
}
const sourceHash=createHash('sha256').update(fs.readFileSync(inputFile)).digest('hex');
const records=[];
const extractor=compatibleSemanticExtractor(config);
// Simulated module-1 capability dictionary. It is independent of expected labels.
const capabilityCatalog={
  endpoint:'解释主要研究终点与其定义',
  extrapolation:'解释亚组或研究结果能否用于其他人群、推广适用范围及证据外推边界',
  subgroup:'描述亚组研究结果本身（不自动等于外推）'
};
console.log(`Running ${Math.min(max,samples.length)} synthetic examples through actual model adapter. Model responses remain UNREVIEWED.`);
for(const [index,sample] of samples.slice(0,max).entries()){
 const rawText=sample.text;
 const started=Date.now();
 try{
  const staged=await stageSemanticEvidence({usage:'TEST_ONLY',rawText,rawVersion:1,capabilityCatalog},extractor);
  records.push({id:sample.id,inputHash:createHash('sha256').update(rawText).digest('hex'),status:'UNREVIEWED_PROPOSAL',
   events:staged.proposal.events,links:staged.proposal.links,offsetFixes:staged.reanchored,
   proposalHash:staged.proposalHash,elapsedMs:Date.now()-started});
  console.log(`${index+1}/${Math.min(max,samples.length)} ${sample.id}: proposal obtained (${staged.proposal.events.length} events)`);
 }catch(err){
  // Error class/code only. Never print raw transport error messages, response bodies, or auth headers.
  const message=String(err?.code||err?.name||'MODEL_REQUEST_FAILED');
  records.push({id:sample.id,inputHash:createHash('sha256').update(rawText).digest('hex'),status:'ERROR',code:message,elapsedMs:Date.now()-started});
  console.log(`${index+1}/${Math.min(max,samples.length)} ${sample.id}: ${message}`);
 }
}
const doc={version:'V09',sourceHash,modelName:config.model,actualModelRequested:true,
 unreviewed:true,reviewed:false,assetUpdates:0,
 generatedAt:new Date().toISOString(),records};
fs.mkdirSync(path.dirname(outputFile),{recursive:true});
fs.writeFileSync(outputFile,JSON.stringify(doc,null,2),'utf8');
console.log(`Unreviewed results saved. No credential or raw response body saved. Score separately: python3 labs/live-model-v09/score.py <results_file>`);
if(records.every(x=>x.status==='ERROR'))process.exitCode=1;
