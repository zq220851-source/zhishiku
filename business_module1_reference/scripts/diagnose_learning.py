import json,sys,tempfile,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.credentials import configure
configure(sys.argv[1])
from app import RemoteDoctorProvider
from workflow import Engine
from tests.doubles import FIXTURES as F
class Capture:
    def __init__(self):self.p=RemoteDoctorProvider();self.calls=[]
    def readiness(self):return self.p.readiness()
    def chat(self,system,user,**kwargs):
        raw=self.p.chat(system,user,**kwargs);self.calls.append({'system':system,'input':json.loads(user),'response':raw});Path('test-results/learning-diagnostic.json').write_text(json.dumps(self.calls,ensure_ascii=False,indent=2));return raw
p=Capture()
with tempfile.TemporaryDirectory() as td:
 e=Engine(Path(td)/'db',p);r=e.create({'mode':'learn','lesson_id':'demo-evidence'},'test')
 try:
  for i,text in enumerate([F['learning']['wrong'],F['learning']['followup_wrong']]):
   print('STAGE answer',i,flush=True)
   r=e.answer(r['id'],{'answer':text,'request_id':'diag-request'+str(i),'revision':r['revision']},'test');print('STATE',r['state'],flush=True)
   if r['state']=='review':break
  print('STAGE support/retry',flush=True);e.support(r['id'],'test');r=e.retry(r['id'],'test')
  print('STAGE good',flush=True);e.support(r['id'],'test')
  r=e.answer(r['id'],{'answer':F['learning']['good_variant'],'request_id':'diag-request-good','revision':r['revision']},'test')
  print('FINAL',r['state'],[(o['criterion_id'],o['status']) for o in r['review']['observations']])
 except Exception as exc:
  print(type(exc).__name__,str(exc))
  print('CAUSE',type(exc.__cause__).__name__)
  if type(exc.__cause__).__name__ in ('ValidationError','JSONDecodeError','ValueError'):print(str(exc.__cause__)[:1200])
