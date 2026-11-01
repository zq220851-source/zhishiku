/** Loopback-only HTTP service, not a production document fetcher. */
import {createServer} from 'node:http';
import {buildSampleFeed} from './sample-feed.mjs';
if(process.env.MEDREP_TEST_BRIDGE_ENABLED!=='1')throw Error('Requires MEDREP_TEST_BRIDGE_ENABLED=1');
const port=Number(process.env.M3_BRIDGE_PORT??8798);
if(!Number.isInteger(port)||port<1024||port>65535)throw Error('Invalid port');
const feed=buildSampleFeed();
const respond=(res,status,obj)=>{res.writeHead(status,{'content-type':'application/json; charset=utf-8','cache-control':'no-store'});res.end(JSON.stringify(obj));};
createServer(async(req,res)=>{
  if(req.method==='GET'&&req.url==='/health')return respond(res,200,{status:'TEST_ONLY',module:'MODULE3',sources:feed.sourceItems.length});
  if(req.method!=='POST'||req.url!=='/test/search')return respond(res,404,{error:'not found'});
  if(req.headers['content-type']!=='application/json'||Number(req.headers['content-length']??0)>100000)return respond(res,400,{error:'JSON only'});
  let body='';try{
    for await(const part of req){body+=part;if(body.length>100000)throw Error('large request');}
    const q=JSON.parse(body);
    if(q.kind!=='M2_TO_M3_SEARCH_V1'||q.usage!=='TEST_ONLY'||q.state!=='REQUEST_FOR_EXTERNAL_CANDIDATES'||
        typeof q.queryTerm!=='string'||!(/^[\p{L}\p{N}\s-]{2,120}$/u.test(q.queryTerm))||
        typeof q.requestId!=='string'||q.requestId.length<5||!Number.isFinite(Date.parse(q.requestedAt)))throw Error('invalid test search');
    const matches=feed.sourceItems.filter(x=>`${x.title} ${x.excerpt}`.includes(q.queryTerm));
    const searchedAt=process.env.MEDREP_TEST_CLOCK??new Date().toISOString();if(Date.parse(searchedAt)<Date.parse(q.requestedAt))throw Error('request from future');
    return respond(res,200,{kind:'M3_TO_M2_SEARCH_RESPONSE_V1',usage:'TEST_ONLY',requestId:q.requestId,
      status:matches.length?'LOCAL_SAMPLE_MATCHES_NOT_VERIFIED':'NO_LOCAL_MATCH',matches,searchedAt});
  }catch(e){return respond(res,400,{error:String(e.message).slice(0,120)});}
}).listen(port,'127.0.0.1',()=>console.log(`M3 TEST bridge on 127.0.0.1:${port}`));
