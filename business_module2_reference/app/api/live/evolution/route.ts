import path from 'node:path';
import {actor,body,gate,json,route} from '../../../../lib/http';
import {object,text,strings,invalid} from '../../../../lib/errors';
import {Store} from '../../../../lib/store';
import {LiveEvolution} from '../../../../lib/live-evolution';
export const runtime='nodejs';
export const dynamic='force-dynamic';
const state=globalThis as typeof globalThis&{liveEvolution?:LiveEvolution};
function engine(){return state.liveEvolution??=new LiveEvolution(new Store(process.env.MODULE2_LIVE_DATABASE_PATH||path.join(process.cwd(),'.data/live-module2.sqlite')));}
export function GET(request:Request){return route(()=>{
 gate(request);const user=actor(request),e=engine();
 if(new URL(request.url).searchParams.get('active')==='1')return json({releases:e.active(user)});
 return json({sources:e.sources(user),candidates:e.list(user),releases:e.active(user),teams:user.scope!.teams.map(t=>({id:t.id,name:t.name})),notice:'训练用途共享；原资料审核状态不变。L2 不证明整个知识库缺失；L3 只比较原始候选和固定预算。'});
});}
export function POST(request:Request){return route(async()=>{
 gate(request);const user=actor(request),input=object(await body(request)),e=engine();
 const reason=text(input.reason,1000);
 if(input.action==='propose'){
  if(!Number.isSafeInteger(input.optionIndex)||Number(input.optionIndex)<0)invalid('请选择原始候选');
  return json(e.propose(user,{level:text(input.level),teamId:text(input.teamId),feedbackId:text(input.feedbackId),optionIndex:Number(input.optionIndex),reason}));
 }
 const id=text(input.id),revision=Number(input.expectedRevision);
 if(!Number.isSafeInteger(revision)||revision<1)invalid('需要当前版本');
 if(input.action==='evaluate')return json(e.evaluate(user,id,revision,strings(input.caseFeedbackIds,2),reason));
 if(input.action==='approve')return json(e.approve(user,id,revision,reason));
 if(input.action==='revoke')return json(e.revoke(user,id,revision,reason));
 invalid('未知共享操作');
});}
