"""Actual source/model/HTTP integration, with explicitly simulated speech.

No invented study, employee or expert history is inserted. Uses an isolated
browser cookie jar. The simulated record is separated from reported exchanges.
"""
import http.cookiejar,json,urllib.request,urllib.error,uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'verification/real-knowledge';OUT.mkdir(parents=True,exist_ok=True)
client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
def call(port,path,data=None,timeout=115):
    base=f'http://127.0.0.1:{port}'
    req=urllib.request.Request(base+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json','Origin':base,'idempotency-key':str(uuid.uuid4())})
    try:
        with client.open(req,timeout=timeout) as r:return json.load(r)
    except urllib.error.HTTPError as e:raise RuntimeError(f'HTTP {e.code}: '+e.read().decode()[:600]) from None
def m2(data=None,path='/api/live'):return call(3302,path,data)['data']

corpus=call(8892,'/api/knowledge/catalog')
assert corpus['employeeProfile'] is None and not any(c['lesson_id']=='demo-evidence' for c in corpus['courses'])
lesson='daboshu__PB'
course=call(8892,'/api/courses/'+lesson)
daily=call(8787,'/api/knowledge/course?lessonId='+lesson)
assert daily['revision']==course['revision'] and daily['blocks']==course['blocks']
print('Module 3 reads identical module-1 source blocks and revision',flush=True)

run=call(8892,'/api/runs',{'mode':'learn','lesson_id':lesson})
print('Module 1 real-model task generated:',run['title'],flush=True)
answer='我先核对达伯舒的通用名称和靶点。材料给出的是信迪利单抗注射液、PD-1方向，但靶点知识不能直接推出获批适应症。我不会据此说适用于所有肿瘤；具体人群、联合方案和使用范围需要查现行批准说明书，未核实的部分明确保留。'
run=call(8892,'/api/runs/'+run['id']+'/answer',{'answer':answer,'revision':run['revision'],'request_id':str(uuid.uuid4())})
if run['state']=='active':run=call(8892,'/api/runs/'+run['id']+'/finish',{})
assert run['state']=='review'
(OUT/'module1-run.json').write_text(json.dumps(run,ensure_ascii=False,indent=2))
print('Module 1 source-bound model review completed',flush=True)

m2({'action':'session'})
state=m2();assert any(s['id']==run['id'] for s in state['sourceTasks'])
task=m2({'action':'import','kind':'runs','id':run['id']})
same=m2({'action':'import','kind':'runs','id':run['id']});assert same['id']==task['id']
assert task['snapshot']['kind']=='MODULE1_SNAPSHOT' and all(e['usage']=='INTERNAL_READING' for e in task['snapshot']['evidence'])
assert task['snapshot']['origin']['revision']==course['revision']
raw='这是根据原课程进行的模拟交流。医生问达伯舒的通用名称和靶点是什么，能不能只凭靶点就推断适应症。我当时说了信迪利单抗注射液和PD-1，但后面适应症的边界我没讲清楚，医生接着追问时我卡住了。'
f=m2({'action':'saveRaw','taskId':task['id'],'exchangeMode':'SIMULATED_EXCHANGE','raw':{'text':raw,'confirmed':True,'exchangeOccurred':True}})
result=m2({'action':'analyze','taskId':task['id'],'feedbackId':f['id'],'expectedVersion':1})
assert result['state']=='ANALYZED',result.get('errorCode')
state=m2(path='/api/live?taskId='+task['id']);view=next(v for v in state['assets'] if v['taskId']==task['id'])
assert view['state']=='CURRENT' and view['visitCount']==0
assert not view['assets']['experts'] and not view['assets']['cohort']
assert view['simulatedAssets']['personal'], 'Real-model extraction must produce a grounded difficulty, not an empty successful reply'
assert view['retrieval'] and all(r['system']=='MODULE1' and r['revision']==course['revision'] for r in view['retrieval'])
(OUT/'module2-result.json').write_text(json.dumps({'task':task,'feedback':result,'projection':view},ensure_ascii=False,indent=2))
print('Module 2 imported original task, actual model extraction, live retrieval and five-asset projection completed; simulated records isolated',flush=True)

f2=m2({'action':'saveRaw','taskId':task['id'],'feedbackId':f['id'],'exchangeMode':'SIMULATED_EXCHANGE','raw':{'text':'更正：这些问题是模拟练习，不是实际专家的现场提问。我对适应症边界的解释还不熟练。','confirmed':True,'exchangeOccurred':True,'expectedVersion':1}})
state=m2(path='/api/live?taskId='+task['id']);assert all(v['state']=='STALE_REQUIRES_ANALYSIS' and v['assets'] is None for v in state['assets'])
result2=m2({'action':'analyze','taskId':task['id'],'feedbackId':f['id'],'expectedVersion':2});assert result2['state']=='ANALYZED',result2.get('errorCode')
state=m2(path='/api/live?taskId='+task['id']);updated=next(v for v in state['assets'] if v['taskId']==task['id'])
assert not updated['simulatedAssets']['experts'] and not updated['simulatedAssets']['forecast']
summary={'passed':True,'sourceMode':'MODULE1_SOURCE_CORPUS','lessonId':lesson,'revision':course['revision'],'sourceCounts':{k:len(corpus[k]) for k in ['courses','products','questions','claims','sources']},'module1RunId':run['id'],'module2TaskId':task['id'],'model':result['analysis']['model'],'retrievalQueries':len(view['retrieval']),'simulatedPersonalEntries':len(view['simulatedAssets']['personal']),'actualVisitCount':view['visitCount'],'revisionInvalidation':True,'correctedQuestionRemoved':True,'module3IdenticalSource':True,'limitations':['Simulated spoken reflections, not actual expert visits','Source corpus still pending medical review','No verified employees, expert identity, company denominator or automatic method approval']}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False),flush=True)
