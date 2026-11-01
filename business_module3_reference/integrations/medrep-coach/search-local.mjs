/** Module 3 consumes Module 2 search request and its own sample feed. No API / real medical lookup. */
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {dirname} from 'node:path';
const [reqPath,feedPath,outPath]=process.argv.slice(2);
if(!reqPath||!feedPath||!outPath)throw Error('Usage: node search-local.mjs request.json feed.json output.json');
const req=JSON.parse(readFileSync(reqPath,'utf8')),feed=JSON.parse(readFileSync(feedPath,'utf8'));
if(req.kind!=='M2_TO_M3_SEARCH_V1'||req.usage!=='TEST_ONLY'||req.state!=='REQUEST_FOR_EXTERNAL_CANDIDATES'||
   !/^[\p{L}\p{N}\s-]{2,120}$/u.test(req.queryTerm)||feed.kind!=='M3_EXTERNAL_CANDIDATES_V1')
  throw Error('不接受不受控的检索请求');
const matches=feed.sourceItems.filter(x=>`${x.title} ${x.excerpt}`.includes(req.queryTerm));
const result={kind:'M3_TO_M2_SEARCH_RESPONSE_V1',usage:'TEST_ONLY',requestId:req.requestId,
 status:matches.length?'LOCAL_SAMPLE_MATCHES_NOT_VERIFIED':'NO_LOCAL_MATCH',matches,searchedAt:'2026-11-02T09:02:00Z'};
mkdirSync(dirname(outPath),{recursive:true});writeFileSync(outPath,JSON.stringify(result,null,2),'utf8');
console.log(JSON.stringify({query:req.queryTerm,matches:matches.map(x=>x.sourceId),status:result.status}));
