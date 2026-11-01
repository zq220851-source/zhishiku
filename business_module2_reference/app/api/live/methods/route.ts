import path from 'node:path';
import { actor,body,gate,json,route } from '../../../../lib/http';
import { Service } from '../../../../lib/service';
import { Store } from '../../../../lib/store';
import { MethodEvolution,type TrialCase } from '../../../../lib/method-evolution';
import { object,text,invalid } from '../../../../lib/errors';
export const runtime='nodejs';
export const dynamic='force-dynamic';
const state=globalThis as typeof globalThis&{liveMethodService?:Service};
function services(){
 const service=state.liveMethodService??=new Service(new Store(process.env.MODULE2_LIVE_DATABASE_PATH||path.join(process.cwd(),'.data/live-module2.sqlite')));
 return {service,methods:new MethodEvolution(service.store)};
}
function context(user:ReturnType<typeof actor>){
 const {service,methods}=services();
 const episodes=methods.episodes(user,service.tasks(user).filter(t=>t.snapshot.origin),id=>service.feedback(user,id));
 return {methods,episodes};
}
export function GET(request:Request){return route(async()=>{
 gate(request);const user=actor(request),{methods,episodes}=context(user);
 const active=new URL(request.url).searchParams.get('active')==='1';
 return json(active?{purpose:'TEST_ONLY',methods:methods.active(user,episodes)}:
   {purpose:'TEST_ONLY',sourceCount:episodes.length,distinctVisits:new Set(episodes.map(x=>x.taskId)).size,
    methods:methods.reconcile(user,episodes).map(({episodes:source,dependencies,...m})=>({...m,sourceCount:source.length}))});
});}
export function POST(request:Request){return route(async()=>{
 gate(request);const input=object(await body(request)),user=actor(request),{methods,episodes}=context(user);
 if(input.action==='propose')return json({candidate:await methods.propose(user,episodes)});
 if(input.action==='evaluate'){
   const cases=input.cases;if(!Array.isArray(cases)||cases.length>24)invalid('需提供数量受限的独立案例');
   return json(await methods.evaluate(user,text(input.id),cases as TrialCase[],episodes));
 }
 if(input.action==='revoke')return json(methods.revoke(user,text(input.id),text(input.reason,1000),episodes));
 if(input.action==='approve')return json(methods.approve(user,text(input.id),text(input.reason,1000),episodes));
 invalid('未知方法操作');
});}
