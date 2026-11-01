import http from 'node:http';
import {loadEnvFile} from 'node:process';
import {fileURLToPath} from 'node:url';
import app from '../worker/index.js';
try { loadEnvFile(fileURLToPath(new URL('../.env.local', import.meta.url))); }
catch (error) { if (error.code !== 'ENOENT') throw error; }
const port=Number(process.env.PORT||8787);
const env={LLM_THINKING:process.env.LLM_THINKING,MODULE1_BASE_URL:process.env.MODULE1_BASE_URL,LLM_API_KEY:process.env.LLM_API_KEY,LLM_API_URL:process.env.LLM_API_URL,LLM_MODEL:process.env.LLM_MODEL,OPENALEX_API_KEY:process.env.OPENALEX_API_KEY,BRAVE_SEARCH_API_KEY:process.env.BRAVE_SEARCH_API_KEY,FEISHU_APP_ID:process.env.FEISHU_APP_ID,FEISHU_APP_SECRET:process.env.FEISHU_APP_SECRET,FEISHU_DELIVERY_ENABLED:process.env.FEISHU_DELIVERY_ENABLED};
http.createServer(async(req,res)=>{try{const result=await app.fetch(new Request('http://127.0.0.1:'+port+req.url,{method:req.method}),env,{waitUntil:p=>p.catch(()=>{})});res.writeHead(result.status,Object.fromEntries(result.headers));res.end(Buffer.from(await result.arrayBuffer()));}catch(e){res.writeHead(500,{'Content-Type':'application/json'});res.end(JSON.stringify({error:'服务暂时不可用'}));console.error(e.message);}}).listen(port,'127.0.0.1',()=>console.log('MedRep Daily: http://127.0.0.1:'+port));
