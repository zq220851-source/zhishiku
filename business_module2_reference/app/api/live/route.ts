import path from 'node:path';
import { actor,body,gate,json,route,session } from '../../../lib/http';
import { Store } from '../../../lib/store';
import { Service } from '../../../lib/service';
import { configured,modelProvider,settings } from '../../../lib/provider';
import { object,text,invalid,Module2Error } from '../../../lib/errors';
import { adaptModule1,module1,projectLiveAssets,followupKey,type Module1Export } from '../../../lib/live-module1';
export const runtime='nodejs';
export const dynamic='force-dynamic';
const state=globalThis as typeof globalThis & { liveModule2Service?:Service };
function service(){return state.liveModule2Service??=new Service(new Store(process.env.MODULE2_LIVE_DATABASE_PATH||path.join(process.cwd(),'.data/live-module2.sqlite')));}
function sourceCookie(response:Response,cookie:string|null){if(cookie)response.headers.append('Set-Cookie',cookie);return response;}
export function GET(request:Request){return route(async()=>{
  gate(request);const user=actor(request),cookie=request.headers.get('cookie')||'';
  const source=await module1('/api/integration/tasks',cookie);
  const catalog=await module1('/api/knowledge/catalog',cookie);
  const tasks=service().tasks(user).filter(t=>t.snapshot.origin),config=settings();
  const taskId=new URL(request.url).searchParams.get('taskId');
  const task=taskId?service().getTask(user,taskId):undefined;
  if(task&&!task.snapshot.origin)invalid('不能将虚构任务当成知识库任务');
  return sourceCookie(json({source:'MODULE1',sourceTasks:source.data.tasks,
    courses:catalog.data.courses,knowledgeVersion:catalog.data.version,
    tasks,task,feedback:task?service().feedback(user,task.id):[],
    assets:service().store.list('live_asset_view',user.id),
    practiceLinks:service().store.list('followup_practice',user.id),
    model:{configured:configured(config),name:config.model},
    notice:catalog.data.notice}),source.cookie);
});}
export function POST(request:Request){return route(async()=>{
  gate(request);const input=object(await body(request));
  if(input.action==='session')return session(request);
  const user=actor(request);if(user.role!=='EMPLOYEE')throw new Module2Error('FORBIDDEN','仅本人可以导入和复盘',403);
  const cookie=request.headers.get('cookie')||'',key=request.headers.get('idempotency-key')||'';
  if(input.action==='import'){
    const kind=text(input.kind),id=text(input.id);
    if(!['runs','sheets'].includes(kind))invalid('任务类型无效');
    const source=await module1(`/api/integration/tasks/${kind}/${encodeURIComponent(id)}`,cookie);
    const adapted=adaptModule1(source.data);
    const prior=service().tasks(user).find(t=>t.snapshot.origin?.sourceTaskId===id&&t.snapshot.origin?.sourceKind===kind&&t.snapshot.knowledgeVersion===adapted.knowledgeVersion&&t.snapshot.scenarioVersion===adapted.scenarioVersion);
    const task=prior||service().createTask(user,adapted,key);
    service().store.put('source:'+task.id,'live_source',user.id,source.data);
    return json(task,201);
  }
  const task=service().getTask(user,text(input.taskId));
  if(!task.snapshot.origin)invalid('缺少模块一任务来源');
  if(input.action==='linkPractice'){
    const result=await module1('/api/integration/tasks/runs/'+encodeURIComponent(text(input.runId)),cookie);
    const source=result.data as Module1Export;
    if(source.lessonId!==task.snapshot.origin.lessonId||source.material.revision!==task.snapshot.origin.revision||!source.review)invalid('补练课程、资料版本或完成状态不匹配');
    service().store.put(followupKey(task.id,source),'followup_practice',user.id,
      {taskId:task.id,runId:source.sourceTaskId,attempt:source.attempt??1,lessonId:source.lessonId,review:source.review,transcript:source.transcript,observedAt:source.observedAt,sourceVersion:source.material.revision,source});
    for(const view of service().store.list<{taskId:string}>('live_asset_view',user.id))service().store.put('view:'+view.taskId,'live_asset_view',user.id,{taskId:view.taskId,assets:null,state:'STALE_REQUIRES_ANALYSIS'});
    return json({linked:true,taskId:task.id,runId:source.sourceTaskId});
  }
  if(input.action==='saveRaw'){
    if(!['REPORTED_EXCHANGE','SIMULATED_EXCHANGE'].includes(String(input.exchangeMode)))invalid('请明确这是实际交流复盘还是模拟联调');
    const f=service().saveRaw(user,task.id,input.raw,key,input.feedbackId===undefined?undefined:text(input.feedbackId));
    service().store.put('meta:'+f.id,'live_feedback_meta',user.id,{id:f.id,exchangeMode:input.exchangeMode});
    service().store.event(f.id,user.id,'LIVE_SOURCE_CLASSIFIED',{exchangeMode:input.exchangeMode,rawVersion:f.versions.at(-1)?.version});
    // Invalidate all derived views immediately, including when a revision is
    // now restricted or awaiting another model extraction.
    for(const v of service().store.list<{taskId:string}>('live_asset_view',user.id))service().store.put('view:'+v.taskId,'live_asset_view',user.id,{taskId:v.taskId,assets:null,state:'STALE_REQUIRES_ANALYSIS'});
    service().store.put('view:'+task.id,'live_asset_view',user.id,{taskId:task.id,assets:null,state:'STALE_REQUIRES_ANALYSIS'});
    return json(f);
  }
  if(input.action==='refreshPractice'){
    const o=task.snapshot.origin;
    const result=await module1(`/api/integration/tasks/${o.sourceKind}/${encodeURIComponent(o.sourceTaskId)}`,cookie);
    if(adaptModule1(result.data).scenarioVersion!==task.snapshot.scenarioVersion||result.data.material.revision!==o.revision)throw new Module2Error('VERSION_MISMATCH','原任务计划或资料变化，不覆盖旧快照',409);
    service().store.put('source:'+task.id,'live_source',user.id,result.data as Module1Export);
    return json({refreshed:true});
  }
  if(input.action==='refreshAssets'){
    const projection=await projectLiveAssets(service().store,user,service().tasks(user),id=>service().feedback(user,id),cookie);
    service().store.put('view:'+task.id,'live_asset_view',user.id,{taskId:task.id,state:'CURRENT',...projection});
    return json({refreshed:true});
  }
  if(input.action==='analyze'){
    if(process.env.MODULE2_KNOWLEDGE_DATA_AUTHORIZED!=='true')throw new Module2Error('DATA_NOT_AUTHORIZED','尚未授权原知识库内容调用模型',403);
    if(!Number.isSafeInteger(input.expectedVersion))invalid('需要原文版本');
    const f=service().getFeedback(user,text(input.feedbackId));if(f.taskId!==task.id)invalid('复盘不属于该任务');
    const config=settings();
    const result=await service().analyze(user,f.id,Number(input.expectedVersion),modelProvider(config),config.model);
    if(result.state==='ANALYZED'){
      const projection=await projectLiveAssets(service().store,user,service().tasks(user),id=>service().feedback(user,id),cookie);
      service().store.put('view:'+task.id,'live_asset_view',user.id,{taskId:task.id,state:'CURRENT',...projection});
    }
    return json(result);
  }
  invalid('未知操作');
});}
