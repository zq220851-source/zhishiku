/** Module 3 -> MedRep Coach: read-only, offline, and never medical approval. */
import {SEEDS,assemble,PRODUCTS} from '../../src/core.mjs';
import {DEMO_PROFILE} from '../../src/demo-profile.mjs';
import {writeFileSync,mkdirSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {createHash} from 'node:crypto';
const hash=v=>createHash('sha256').update(JSON.stringify(v)).digest('hex');
function exportSample(){
  const digest=assemble({mode:'sample',items:SEEDS,date:'2026-10-31'},['cervical'],'brief',[]);
  const items=[...digest.industry,...digest.learning];
  if(items.length<2)throw Error('模块3示例资讯输出缺失');
  const candidates=items.map(x=>({
    sourceId:x.id,sourceType:x.kind,sourceUrl:x.url,title:x.title,
    publishedAt:x.publishedAt??null,sourceName:x.source,
    excerpt:x.summary??'',limitations:x.limitations??'',
    sourceReviewStatus:x.reviewStatus,sourceMode:x.mode,
    contentHash:hash({title:x.title,summary:x.summary,limitations:x.limitations,url:x.url}),
    approval:'UNREVIEWED',usage:'LEARNING_CANDIDATE_ONLY'
  }));
  const p=DEMO_PROFILE;
  return {kind:'M3_EXTERNAL_CANDIDATES_V1',usage:'TEST_ONLY',generatedAt:'2026-11-01T08:00:00Z',
    sourceSystem:'MEDREP_DAILY',sourceFeed:'src/core.mjs:SEEDS -> assemble()',
    sourceItems:candidates,
    academicExample:{name:p.name,fictional:true,doctorsCount:p.hospitals.reduce((n,h)=>n+h.doctors.length,0),
      publicScholarSample:{...p.hospitals[0].doctors[0],hospital:p.hospitals[0].name},
      identityVerification:'NOT_VERIFIED',linkedModule1ExpertId:null},
    note:'离线历史示例而非今天实际抓取；不包含医学审核，不应自动成为模块1的训练知识'};
}
const packet=exportSample();
const dest=resolve(process.argv[2]??'../../shared_exchange/module3-external-candidates.json');
mkdirSync(dirname(dest),{recursive:true});writeFileSync(dest,JSON.stringify(packet,null,2),'utf8');
console.log(JSON.stringify({sourceSystem:packet.sourceSystem,sourceFeed:packet.sourceFeed,items:packet.sourceItems.length,allUnreviewed:packet.sourceItems.every(x=>x.approval==='UNREVIEWED'),file:dest}));
