"""Shared versions: fixed budget, exact criteria, actual consumption and signed handoff."""
import copy,json,tempfile,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workflow import Engine,Problem
from shared_evolution import apply_releases,consumed
from live_knowledge import export_task
from doubles import ScriptedProvider,FIXTURES

class SharedEvolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.owner='protocol-owner'
        self.engine=Engine(Path(self.tmp.name)/'shared.sqlite',ScriptedProvider())
        self.context={**FIXTURES['visit']['custom_context'],'lesson_id':'D-NSCLC__CE'}
        self.sheet=self.engine.prepare('custom',self.owner,self.context)
        extra=copy.deepcopy(self.sheet['priorities'][0]);extra['id']='protocol_second'
        extra['criteria'][0]['expected']+=' independent protocol criterion'
        self.sheet['priorities'].append(extra)
    def tearDown(self):self.tmp.cleanup()
    def release(self,level='L3',option=None):
        return {'id':'protocol-release','version':3,'level':level,'teamId':'protocol-team','lessonId':self.sheet['visit']['lesson_id'],
                'sourceRevision':self.sheet['material']['revision'],'option':copy.deepcopy(option or self.sheet['priorities'][-1])}
    def test_l3_budget_criteria_and_actual_consumption(self):
        sheet=self.sheet;original=copy.deepcopy(sheet['priorities']);release=self.release()
        apply_releases(sheet,[release],1)
        self.assertEqual(sheet['priorities'],original)
        self.assertEqual(len(sheet['evolution']['baseline']),len(sheet['evolution']['proposed']))
        self.assertEqual(sheet['evolution']['proposed'],[original[-1]['id']])
        self.assertFalse(sheet.get('consumed_evolution_versions'))
        self.engine.save('sheets',sheet,self.owner)
        with self.assertRaises(Problem):self.engine.freeze_forecast(sheet['id'],self.owner,[p['id'] for p in original],True)
        frozen=self.engine.freeze_forecast(sheet['id'],self.owner,sheet['evolution']['proposed'],True)
        self.assertEqual(frozen['consumed_evolution_versions'],[{'id':release['id'],'version':3}])
        self.assertEqual(export_task(self.engine,self.owner,'sheets',sheet['id'])['consumedEvolutionVersions'],frozen['consumed_evolution_versions'])
        with self.assertRaises(Problem):self.engine.freeze_forecast(sheet['id'],self.owner,[original[0]['id']],True)
    def test_unchanged_or_unselected_offer_is_not_claimed_as_consumed(self):
        sheet=self.sheet;apply_releases(sheet,[self.release()],1)
        self.assertFalse(consumed(sheet,[sheet['priorities'][0]['id']]))
        same=self.engine.prepare('custom',self.owner,self.context)
        apply_releases(same,[self.release(option=same['priorities'][0])],1)
        self.assertFalse(consumed(same,same['evolution']['proposed']))
    def test_l2_preserves_source_criteria_and_tracks_only_chosen_scene(self):
        # Isolated test fixture variant, never a production release.
        option=copy.deepcopy(self.sheet['priorities'][0]);option['criteria'][0]['expected']+=' protocol variant'
        release=self.release('L2',option);apply_releases(self.sheet,[release],1)
        added=self.sheet['priorities'][-1]
        self.assertEqual(added['criteria'],option['criteria']);self.assertEqual(added['question'],option['question'])
        self.assertFalse(consumed(self.sheet,[self.sheet['priorities'][0]['id']]))
        self.engine.save('sheets',self.sheet,self.owner)
        run=self.engine.create({'mode':'visit','sheet_id':self.sheet['id'],'option_id':added['id']},self.owner)
        self.assertEqual(run['consumed_evolution_versions'],[{'id':release['id'],'version':3}])
    def test_reject_version_mismatch_invalid_sources_and_strategy_stacking(self):
        release=self.release();release['sourceRevision']='changed'
        with self.assertRaises(Problem):apply_releases(self.sheet,[release],1)
        release=self.release();release['option']['criteria'][0]['source_ids']=['invented']
        with self.assertRaises(Problem):apply_releases(self.sheet,[release],1)
        with self.assertRaises(Problem):apply_releases(self.sheet,[self.release(),self.release()],1)
        with self.assertRaises(Problem):apply_releases(self.sheet,[self.release()],20)
    def test_http_handoff_requires_signed_owner_lesson_and_unexpired_release(self):
        import base64,hashlib,hmac,time
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from asgi import create_app
        secret='protocol-test-owner-secret-at-least-32-characters'
        owner='a'*43
        app=create_app(Path(self.tmp.name)/'http.sqlite',ScriptedProvider())
        with patch.dict('os.environ',{'MEDREP_MODULE1_OWNER_SECRET':secret}), TestClient(app,base_url='http://127.0.0.1') as client:
            client.cookies.set('medrep_owner',owner)
            payload={'owner':owner,'lesson_id':self.context['lesson_id'],'expires':int(time.time())+60,'releases':[self.release()],'budget':1}
            def sign(value):
                encoded=base64.urlsafe_b64encode(json.dumps(value).encode()).decode()
                return encoded+'.'+hmac.new(secret.encode(),encoded.encode(),hashlib.sha256).hexdigest()
            def post(token):return client.post('/api/prepare',headers={'Origin':'http://127.0.0.1'},json={'visit_id':'custom','context':self.context,'platform_evolution':token})
            self.assertEqual(post(sign({**payload,'owner':'b'*43})).status_code,403)
            self.assertEqual(post(sign({**payload,'expires':1})).status_code,403)
            self.assertEqual(post(sign({**payload,'lesson_id':'other-course'})).status_code,403)
            self.assertEqual(post(sign(payload)[:-1]+'Z').status_code,403)
            valid=post(sign(payload));self.assertEqual(valid.status_code,200,valid.text)
            self.assertEqual(valid.json()['evolution']['budget'],1)
            self.assertFalse(valid.json().get('consumed_evolution_versions'))

    def test_engine_handoff_saves_offers_without_automatic_adoption(self):
        sheet=self.engine.prepare('custom',self.owner,self.context,shared_releases=[self.release()],shared_budget=1)
        self.assertTrue(sheet['evolution']['offers']);self.assertFalse(sheet.get('consumed_evolution_versions'))
        self.assertEqual(self.engine.load('sheets',sheet['id'],self.owner)['evolution'],sheet['evolution'])

if __name__=='__main__':unittest.main()
