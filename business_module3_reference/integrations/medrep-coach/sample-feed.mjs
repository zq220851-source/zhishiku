/** Offline sample feed built from the real MedRep Daily assemble() implementation. */
import {SEEDS,assemble} from '../../src/core.mjs';
import {DEMO_PROFILE} from '../../src/demo-profile.mjs';
import {createHash} from 'node:crypto';
const hash=v=>createHash('sha256').update(JSON.stringify(v)).digest('hex');
export function buildSampleFeed(){
  const digest=assemble({mode:'sample',items:SEEDS,date:'2026-10-31'},['cervical'],'brief',[]);
  const items=[...digest.industry,...digest.learning];
  if(items.length<2)throw Error('Missing Module3 demo source items');
  return {kind:'M3_EXTERNAL_CANDIDATES_V1',usage:'TEST_ONLY',generatedAt:'2026-11-01T08:00:00Z',
    sourceSystem:'MEDREP_DAILY',sourceFeed:'src/core.mjs:SEEDS -> assemble()',
    sourceItems:items.map(x=>({sourceId:x.id,sourceType:x.kind,sourceUrl:x.url,title:x.title,
      publishedAt:x.publishedAt??null,sourceName:x.source,excerpt:x.summary??'',limitations:x.limitations??'',
      sourceReviewStatus:x.reviewStatus,sourceMode:x.mode,
      contentHash:hash({title:x.title,summary:x.summary,limitations:x.limitations,url:x.url}),
      approval:'UNREVIEWED',usage:'LEARNING_CANDIDATE_ONLY'})),
    academicExample:{name:DEMO_PROFILE.name,fictional:true,
      identityVerification:'NOT_VERIFIED',linkedModule1ExpertId:null},
    note:'离线历史示例，不代表当天新证据或医学审核通过'};
}
