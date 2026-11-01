"""Synthetic future-visit preparation, freeze and optional practice smoke."""
import json,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];base='http://localhost:9011'
def call(p,b=None,t=None):
 req=urllib.request.Request(base+p,data=json.dumps(b).encode() if b is not None else None,headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+t} if t else {})})
 with urllib.request.urlopen(req,timeout=180) as r:return json.load(r)
result={'test_kind':'SYNTHETIC_PREVISIT_NOT_REAL_VISIT'}
try:
 t=call('/v1/mobile/auth/login',json.loads((ROOT/'runtime/local-account.json').read_text()))['access_token']
 s=call('/v1/mobile/coach/prepare',{'doctor':'模拟医生（验收用）','goal':'练习清晰说明课程资料中的两条路线及证据边界','facts':'这是本机模拟验收场景，不涉及实际医生或患者；计划在模拟会面前准备资料。','lesson_id':'D-AD','use_approved_methods':False},t)
 result['sheet_id']=s['id'];result['candidate_count']=len(s['priorities']);option=s['priorities'][0]['id']
 r=call('/v1/mobile/coach/runs/visit',{'sheet_id':s['id'],'option_id':option},t);result['optional_practice_before_freeze']=r['mode']=='visit' and r['state']=='active'
 frozen=call('/v1/mobile/coach/sheets/'+s['id']+'/freeze',{'selected_ids':[option],'previsit_confirmed':True},t);result['frozen']=frozen['forecast']['status']=='FROZEN';result['budget']=frozen['forecast']['budget']
 reread=call('/v1/mobile/coach/sheets/'+s['id'],t=t);result['persisted']=reread['forecast']==frozen['forecast']
 try:call('/v1/mobile/coach/sheets/'+s['id']+'/freeze',{'selected_ids':[option],'previsit_confirmed':True},t);result['refreeze_rejected']=False
 except urllib.error.HTTPError as e:result['refreeze_rejected']=e.code==409
 result['passed']=all(result.get(k) for k in ['optional_practice_before_freeze','frozen','persisted','refreeze_rejected'])
except urllib.error.HTTPError as e:result['error']={'status':e.code,'message':e.read().decode()[:350]}
(ROOT/'runtime/previsit-flow-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
