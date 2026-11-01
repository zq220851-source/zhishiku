import test from 'node:test';import assert from 'node:assert/strict';
import {buildSampleFeed} from '../integrations/medrep-coach/sample-feed.mjs';
test('shared M3 feed is source-derived and never medically approved',()=>{
 const p=buildSampleFeed();assert.equal(p.kind,'M3_EXTERNAL_CANDIDATES_V1');
 assert.ok(p.sourceItems.length>1);
 for(const x of p.sourceItems){assert.equal(x.approval,'UNREVIEWED');assert.equal(x.usage,'LEARNING_CANDIDATE_ONLY');
 assert.equal(x.sourceReviewStatus,'not_reviewed');assert.ok(x.sourceUrl.startsWith('https://'));}
});
