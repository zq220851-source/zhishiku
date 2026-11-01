/** Optional LIVE model comparator. Never runs automatically. Sends ONLY synthetic fixture text. */
import fs from 'node:fs';
const cfg={url:process.env.MODULE2_MODEL_BASE_URL,model:process.env.MODULE2_MODEL_NAME,key:process.env.MODULE2_MODEL_API_KEY};
if(process.env.ALLOW_SYNTHETIC_EXTERNAL_MODEL!=='YES'||!cfg.url||!cfg.key||!cfg.model){
 console.error('No live model executed: set ALLOW_SYNTHETIC_EXTERNAL_MODEL=YES and MODULE2_MODEL_BASE_URL / MODULE2_MODEL_NAME / MODULE2_MODEL_API_KEY.');process.exit(2);
}
const input=JSON.parse(fs.readFileSync(new URL('./cases_input.json',import.meta.url)));
const out=[];
for(const c of input){
 const prompt='你是医药代表复盘的事实性标注器。仅根据这段虚构测试口述，判断是否“员工报告专家/医生在现场提出外推或跨人群适用问题”。四种状态只选一个：REPORTED（明确现场提问）、DENIED（明确未发生或事后改口否认）、HYPOTHETICAL（假设/未来准备）、UNCERTAIN（不能确认专家是谁或是否问过）。不能用词面出现“外推”推定专家问过。只返回 JSON，如 {"mode":"UNCERTAIN","evidence":"原文对应短语","reason":"..."}。';
 let response;
 try{
  const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),60000);
  try{response=await fetch(cfg.url.replace(/\/$/,'')+'/chat/completions',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+cfg.key},body:JSON.stringify({model:cfg.model,messages:[{role:'system',content:prompt},{role:'user',content:c.text}],temperature:0}),signal:ctl.signal});}finally{clearTimeout(timer);}
  if(!response.ok)throw new Error('HTTP '+response.status);
  const data=await response.json();const str=data.choices?.[0]?.message?.content||'';
  const match=str.match(/\{[\s\S]*\}/);const v=match?JSON.parse(match[0]):null;
  const mode=['REPORTED','DENIED','HYPOTHETICAL','UNCERTAIN'].includes(v?.mode)?v.mode:'UNCERTAIN';
  out.push({id:c.id,split:c.split,input:c.text,predicted:mode,evidence:typeof v?.evidence==='string'&&c.text.includes(v.evidence)?v.evidence:null,invalidEvidence:!(typeof v?.evidence==='string'&&c.text.includes(v.evidence))});
 }catch(error){out.push({id:c.id,split:c.split,input:c.text,predicted:'ERROR',error:String(error).slice(0,150)});}
}
fs.writeFileSync(new URL('./observed_llm.json',import.meta.url),JSON.stringify(out,null,2));
console.log('Live model fixture run finished:',out.length,'cases. No gold labels were provided to the model.');
