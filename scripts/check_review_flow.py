"""Synthetic review using a real locally created lesson task; no actual visit claims."""
import json,urllib.request,urllib.error,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];base='http://localhost:9011'
def call(p,b=None,t=None):
 req=urllib.request.Request(base+p,data=json.dumps(b).encode() if b is not None else None,headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+t} if t else {})})
 with urllib.request.urlopen(req,timeout=180) as r:return json.load(r)
result={'test_kind':'SIMULATED_EXCHANGE'}
try:
 t=call('/v1/mobile/auth/login',json.loads((ROOT/'runtime/local-account.json').read_text()))['access_token']
 rid=json.loads((ROOT/'runtime/live-run.json').read_text())['id']
 task=call('/v1/mobile/review/action',{'action':'import','kind':'runs','id':rid},t);result['task_id']=task['id']
 raw='这是一次模拟练习记录，不是真实拜访。医生问：“两条路线各自现在是什么状态？”我回答：“未确认的信息，我会核对课程资料后再回复。”我觉得自己对两条路线的表达还不够清楚，需要重新学习。'
 f=call('/v1/mobile/review/action',{'action':'saveRaw','taskId':task['id'],'exchangeMode':'SIMULATED_EXCHANGE','raw':{'text':raw,'source':'VOICE_TRANSCRIPT','confirmed':True,'exchangeOccurred':True}},t);result['feedback_id']=f['id']
 print('Raw saved; analyzing.',flush=True)
 a=call('/v1/mobile/review/action',{'action':'analyze','taskId':task['id'],'feedbackId':f['id'],'expectedVersion':f['versions'][-1]['version']},t);result['analysis_state']=a['state'];result['error_code']=a.get('errorCode');result['unit_count']=len(a.get('analysis',{}).get('units',[]))
 w=call('/v1/mobile/review/workspace?task_id='+task['id'],t=t);view=next((v for v in w['assets'] if v['taskId']==task['id']),{});result['view_state']=view.get('state');result['actual_count']=view.get('visitCount');result['simulated_assets']={k:len(v) for k,v in view.get('simulatedAssets',{}).items() if isinstance(v,list)}
 result['passed']=a['state']=='ANALYZED' and view.get('visitCount')==0
except urllib.error.HTTPError as e:result['error']={'status':e.code,'message':e.read().decode()[:350]}
(ROOT/'runtime/review-flow-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
