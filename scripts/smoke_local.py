"""Local authenticated smoke; training answers are synthetic tests, never visit reports."""
import json
from pathlib import Path
import urllib.request
import urllib.error
ROOT=Path(__file__).resolve().parents[1]
base='http://localhost:9011'
def read(path,body=None,token=None,timeout=160):
    request=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})})
    with urllib.request.urlopen(request,timeout=timeout) as r:return json.load(r)
account=json.loads((ROOT/'runtime/local-account.json').read_text());token=read('/v1/mobile/auth/login',account)['access_token']
results=[]
for path in ['/v1/mobile/learning/catalog','/v1/mobile/daily/config','/v1/mobile/review/workspace','/v1/mobile/review/methods']:
 try:
  d=read(path,token=token)
  results.append({'path':path,'passed':True,'count':len(d.get('lessons',d.get('tasks',d.get('methods',d.get('products',[])))))})
 except urllib.error.HTTPError as e:results.append({'path':path,'passed':False,'status':e.code,'error':e.read().decode()[:200]})
(ROOT/'runtime/smoke-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps(results,ensure_ascii=False))
