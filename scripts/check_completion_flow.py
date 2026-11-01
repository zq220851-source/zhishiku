"""Complete the synthetic voice run and verify review, support, retry and linkage."""
import json,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];base='http://localhost:9011'
def call(p,b=None,t=None):
 req=urllib.request.Request(base+p,data=json.dumps(b).encode() if b is not None else None,headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+t} if t else {})})
 with urllib.request.urlopen(req,timeout=170) as r:return json.load(r)
result={'test_kind':'SYNTHETIC_TRAINING'}
try:
 t=call('/v1/mobile/auth/login',json.loads((ROOT/'runtime/local-account.json').read_text()))['access_token']
 rid=json.loads((ROOT/'runtime/live-run.json').read_text())['id'];task=json.loads((ROOT/'runtime/review-flow-check.json').read_text())['task_id']
 r=call('/v1/mobile/coach/runs/'+rid+'/finish',{},t);result['state']=r['state'];result['observation_count']=len(r.get('review',{}).get('observations',[]));result['medical_accuracy']=r.get('review',{}).get('medical_accuracy')
 support=call('/v1/mobile/coach/runs/'+rid+'/support',{},t);result['support_sections']=len(support.get('sections',[]))
 linked=call('/v1/mobile/review/action',{'action':'linkPractice','taskId':task,'runId':rid},t);result['linked']=linked['linked']
 retry=call('/v1/mobile/coach/runs/'+rid+'/retry',{},t);result['retry_state']=retry['state'];result['retry_attempt_advanced']=retry['attempt']==r['attempt']+1
 saved=call('/v1/mobile/coach/runs/'+rid,t=t);result['original_review_retained']=any(a['review']==r['review'] and a['transcript']==r['transcript'] for a in saved.get('attempts',[]))
 result['passed']=result['state']=='review' and result['linked'] and result['retry_attempt_advanced'] and result['original_review_retained'] and result['support_sections']>0
except urllib.error.HTTPError as e:result['error']={'status':e.code,'message':e.read().decode()[:350]}
(ROOT/'runtime/completion-flow-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
