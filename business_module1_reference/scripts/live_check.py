"""Real provider acceptance using only fictional materials. Not a unit-test double."""
import argparse,json,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.credentials import configure

parser=argparse.ArgumentParser();parser.add_argument('--config-from',required=True);args=parser.parse_args()
configure(args.config_from)
from app import make_server
from workflow import Engine
from tests.doubles import FIXTURES as F
from remote_provider import RemoteDoctorProvider

out=Path(__file__).resolve().parents[1]/'test-results';out.mkdir(exist_ok=True)
provider=RemoteDoctorProvider()
assert provider.readiness()['ready'],'Missing API configuration'
class Capture:
    def __init__(self, inner):self.inner=inner;self.calls=[]
    def readiness(self):return self.inner.readiness()
    @property
    def model(self):return self.inner.model
    def chat(self,system,user,**kwargs):
        raw=self.inner.chat(system,user,**kwargs)
        self.calls.append({'input':json.loads(user),'response':raw})
        (out/'live-generation.json').write_text(json.dumps(self.calls,ensure_ascii=False,indent=2))
        return raw
provider=Capture(provider)
report={'kind':'real_model_semantic_acceptance','model':provider.model,'cases':[], 'recovered_model_failures':[], 'human_microphone_verified':False}

def check(name,fn):
    start=time.time()
    try:
        data=fn();report['cases'].append({'name':name,'passed':True,'seconds':round(time.time()-start,2),'result':data})
        print('PASS',name,flush=True)
    except Exception as e:
        # Never print provider errors which may contain upstream request details.
        report['cases'].append({'name':name,'passed':False,'error_type':type(e).__name__,'cause_type':type(e.__cause__).__name__,'seconds':round(time.time()-start,2)})
        print('FAIL',name,type(e).__name__,flush=True)
    (out/'live-model.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))

with tempfile.TemporaryDirectory() as td:
    e=Engine(Path(td)/'live.sqlite',provider);owner='fictional-live-test'
    def recover(label, fn):
        from workflow import ModelFailure
        try:return fn()
        except ModelFailure as exc:
            report['recovered_model_failures'].append({'stage':label,'type':type(exc).__name__,'action':'retry_same_operation_once'})
            return fn()
    def respond(r,text):
        body={'answer':text,'request_id':'live-'+str(time.time_ns()),'revision':r['revision']}
        return recover('answer',lambda:e.answer(r['id'],body,owner))
    def learning():
        r=e.create({'mode':'learn','lesson_id':'demo-evidence'},owner)
        r=respond(r,F['learning']['wrong'])
        assert any(o['status']=='needs_work' for o in r['review']['observations']),'Wrong answer not detected'
        wrong=r['review']
        if r['state']=='active':r=respond(r,F['learning']['followup_wrong'])
        e.support(r['id'],owner);r=recover('variant_question',lambda:e.retry(r['id'],owner))
        e.support(r['id'],owner);r=respond(r,F['learning']['good_variant'])
        obs={o['criterion_id']:o['status'] for o in r['review']['observations']}
        assert obs['scope']=='demonstrated' and obs['comparison']=='demonstrated',obs
        assert r['review']['support_used'] and r['review']['medical_accuracy']=='NA'
        assert not r['review']['independent_mastery']
        assert len(e.history(owner))==2
        return {'wrong_review':wrong,'corrected_review':r['review'],'attempts':r['attempt']}
    check('学习：自然错误→反馈→补学→变式正确回答',learning)
    def negation():
        r=e.create({'mode':'learn','lesson_id':'demo-evidence'},owner);r=respond(r,F['learning']['negation'])
        obs={o['criterion_id']:o['status'] for o in r['review']['observations']}
        assert obs['scope']=='demonstrated' and obs['comparison']=='demonstrated',obs
        return r['review']
    check('否定和限定条件不会被反向误判',negation)
    def visit():
        s=e.prepare('demo-visit',owner);assert s['priorities'] and not s['practice_results']
        p=next((p for p in s['priorities'] if p['id']=='evidence_scope'),s['priorities'][0])
        r=e.create({'mode':'visit','sheet_id':s['id'],'option_id':p['id']},owner)
        r=respond(r,F['visit']['good'])
        if r['state']=='active':r=respond(r,F['visit']['good'])
        s2=e.load('sheets',s['id'],owner)
        assert s2['id']==s['id'] and len(s2['practice_results'])==1
        assert '未知' in str(s2['unknowns'])
        return {'priorities':s2['priorities'],'practice_results':s2['practice_results']}
    check('访前：背景→模型整理重点→选择试练→更新同一准备单',visit)
    def custom():
        s=e.prepare('custom',owner,F['visit']['custom_context'])
        assert 'C-17' not in str(s['visit'])
        assert all(set(p['fact_ids']) <= {f['id'] for f in s['visit']['facts']} for p in s['priorities'])
        return {'priorities':s['priorities'],'unknowns':s['unknowns']}
    check('自填背景不混入虚构研究事实',custom)
report['passed']=all(c['passed'] for c in report['cases'])
(out/'live-model.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
sys.exit(0 if report['passed'] else 1)
