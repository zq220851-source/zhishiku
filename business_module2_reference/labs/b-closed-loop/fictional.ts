import type { VisitEvidence, EvidenceObservation, PracticeEvidence, KnowledgeCheck } from '../../lib/five-assets';
export const study='fictional-research-alpha';
export const K={endpoint:'endpoint-definition',subgroup:'subgroup-interpretation',extrapolation:'extrapolation-boundary',safety:'safety-context'};
const caps=Object.values(K);
type Obs={id:string;kind:EvidenceObservation['kind'];mode:EvidenceObservation['mode'];capabilityId:string|null;quote:string};
interface Setup {id:string;rep:string;expert:string|null;time:string;questions?:{cap:string;mode?:EvidenceObservation['mode'];phrase:string;knowledge?:KnowledgeCheck['status']}[];
  difficulties?:{cap:string;phrase:string}[];practices?:PracticeEvidence[];selected?:string[]; }
export function visit(x:Setup):VisitEvidence{
  const pieces:Obs[]=[];let i=0;
  for(const q of x.questions??[])pieces.push({id:`q${++i}`,kind:'EXPERT_QUESTION',mode:q.mode??'REPORTED',capabilityId:q.cap,quote:q.phrase});
  for(const d of x.difficulties??[])pieces.push({id:`d${++i}`,kind:'REP_DIFFICULTY',mode:'REPORTED',capabilityId:d.cap,quote:d.phrase});
  const rawText=pieces.map(p=>p.quote).join('\n');let cursor=0;
  const observations:EvidenceObservation[]=pieces.map(p=>{const s=cursor;cursor+=Array.from(p.quote).length+1;return {...p,startCp:s,endCp:s+Array.from(p.quote).length};});
  const checks:KnowledgeCheck[]=[];
  for(const q of x.questions??[])if(q.knowledge){const o=observations.find(o=>o.quote===q.phrase)!;
    if((q.mode??'REPORTED')==='REPORTED')checks.push({observationId:o.id,capabilityId:q.cap,status:q.knowledge,queriedEvidenceIds:q.knowledge==='NOT_FOUND'?[]:['fictional-e1'],queryAttempts:['冻结虚构知识库检索'],knowledgeVersion:'kb-fiction-v1'});
  }
  return {usage:'TEST_ONLY',visitId:x.id,taskId:`task-${x.id}`,repId:x.rep,expertId:x.expert,researchId:study,snapshotHash:`snapshot-${x.id}`,rawVersion:1,rawText,occurredAt:x.time,
    forecast:{candidateCapabilityIds:caps,selectedCapabilityIds:x.selected??[K.endpoint,K.subgroup],budget:2},
    observations,knowledgeChecks:checks,practices:x.practices??[]};
}
export function sampleVisits():VisitEvidence[]{
  return [
    visit({id:'v1',rep:'repA',expert:'expertX',time:'2026-01-02T10:00:00Z',
      questions:[{cap:K.extrapolation,phrase:'医生追问了亚组结果能不能直接推广到其他人群。',knowledge:'SUPPORTED'}],
      difficulties:[{cap:K.extrapolation,phrase:'我说得太满了，现在还是讲不清证据边界。'}],
      practices:[{capabilityId:K.extrapolation,trainingAttemptId:'p1',criterion:'解释外推限制',result:'GAP'}]}),
    visit({id:'v2',rep:'repA',expert:'expertX',time:'2026-01-05T10:00:00Z',
      questions:[{cap:K.extrapolation,phrase:'专家再次确认研究证据能不能外推。',knowledge:'SUPPORTED'}],
      practices:[{capabilityId:K.extrapolation,trainingAttemptId:'p2',criterion:'表述证据限制',result:'SATISFIED'}],
      selected:[K.endpoint,K.extrapolation]}),
    visit({id:'v3',rep:'repB',expert:'expertY',time:'2026-01-07T10:00:00Z',
      questions:[{cap:K.extrapolation,phrase:'医生想了解其他人群能否照搬这个结果。',knowledge:'PARTIAL'}],
      selected:[K.endpoint,K.subgroup]}),
    visit({id:'v4',rep:'repC',expert:'expertZ',time:'2026-01-08T10:00:00Z',
      questions:[{cap:K.safety,phrase:'医生问到了资料没有解释清楚的安全性比较问题。',knowledge:'NOT_FOUND'}],
      selected:[K.endpoint,K.subgroup]}),
    visit({id:'v5',rep:'repD',expert:'expertW',time:'2026-01-09T10:00:00Z',
      questions:[{cap:K.extrapolation,mode:'DENIED',phrase:'医生其实没有追问亚组外推，是我回来自己想到的。'}],
      difficulties:[{cap:K.extrapolation,phrase:'但我仍然不会解释这个证据边界。'}]}),
    visit({id:'v6',rep:'repC',expert:'expertZ',time:'2026-01-12T10:00:00Z',
      questions:[{cap:K.safety,phrase:'安全性比较的问题在这次交流中又被提到。',knowledge:'NOT_FOUND'}],
      selected:[K.endpoint,K.safety]})
  ];
}
export function revisedV3(original:VisitEvidence):VisitEvidence{
  const quote='我以前说医生问了外推，那是记错了，其实是我自己想到的。';
  return {...original,rawVersion:2,reviewedAt:'2026-01-14T10:00:00Z',rawText:quote,observations:[{id:'correction',kind:'EXPERT_QUESTION',mode:'DENIED',capabilityId:K.extrapolation,quote,startCp:0,endCp:Array.from(quote).length}],knowledgeChecks:[]};
}
