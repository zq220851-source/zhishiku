"""Independent regression cases for material-backed learning and preparation."""
import json,tempfile,unittest
from pathlib import Path
from fastapi.testclient import TestClient
from knowledge import LESSONS
from materials import snapshot,search_materials
from workflow import Engine,ModelFailure
from asgi import create_app
from doubles import ScriptedProvider,FIXTURES as F


class MaterialJourneys(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.provider=ScriptedProvider()
        self.engine=Engine(Path(self.tmp.name)/'state.sqlite',self.provider);self.owner='case-owner'
    def tearDown(self):self.tmp.cleanup()
    def test_full_course_contains_explanations_and_visual_not_just_steps(self):
        s=snapshot('D-NSCLC__CE');blocks={b['locator']:b for b in s['blocks']}
        self.assertIn('医生推开的那份材料',blocks['hook']['text'])
        self.assertIn('入组标准',blocks['visual']['text']);self.assertIn('类比',blocks['analogy']['text'])
        self.assertIn('没有同期对照',blocks['misconceptions.0']['text'])
        self.assertNotIn('http',blocks['steps.0']['text'])
        self.assertTrue(all('text' in b and b['text'] for b in s['blocks']))
    def test_chinese_retrieval_is_course_scoped_and_source_locatable(self):
        results=search_materials('D-NSCLC__CE','EGFR 状态未明 人群')
        self.assertTrue(results);self.assertTrue(any(b['locator']=='misconceptions.2' for b in results))
        self.assertTrue(all(b['id'].startswith('D-NSCLC__CE:') for b in results))
        self.assertEqual(search_materials('D-NSCLC__CE','zzzxqvunfindabletoken'),[])
    def test_no_fixed_two_turn_limit_or_interim_feedback(self):
        original=self.provider.chat;count=[0]
        def chat(system,user,**kw):
            if '扮演当前培训情境' in system:
                count[0]+=1
                return json.dumps({'complete':count[0]>=4,'question':'' if count[0]>=4 else '请进一步解释这句话。','reason':'继续完成本段任务'})
            return original(system,user,**kw)
        self.provider.chat=chat
        r=self.engine.create({'mode':'learn','lesson_id':'demo-evidence'},self.owner)
        for i in range(4):
            r=self.engine.answer(r['id'],{'answer':F['learning']['good'],'revision':r['revision'],'request_id':f'four-turn-{i}'},self.owner)
            self.assertEqual(r['state'],'active' if i<3 else 'review')
            if i<3:self.assertIsNone(r['review']);self.assertEqual(self.engine.history(self.owner),[])
    def test_finish_failure_preserves_transcript_and_can_retry(self):
        r=self.engine.create({'mode':'learn','lesson_id':'demo-evidence'},self.owner)
        r=self.engine.answer(r['id'],{'answer':F['learning']['wrong'],'revision':0,'request_id':'finish-case-1'},self.owner)
        self.provider.failure=True
        with self.assertRaises(ModelFailure):self.engine.finish(r['id'],self.owner)
        raw=self.engine.load('runs',r['id'],self.owner);self.assertTrue(raw['finish_pending'])
        self.provider.failure=False;done=self.engine.finish(r['id'],self.owner)
        self.assertEqual(done['transcript'],r['transcript']);self.assertEqual(done['state'],'review')
    def test_task_rejects_reference_only_or_invented_source(self):
        original=self.provider.chat
        def invalid(system,user,**kw):
            raw=original(system,user,**kw)
            if '培训任务设计助手' in system:
                d=json.loads(raw);d['criteria'][0]['source_ids']=['NONEXISTENT-PAPER'];return json.dumps(d)
            return raw
        self.provider.chat=invalid
        with self.assertRaises(ModelFailure):self.engine.create({'mode':'learn','lesson_id':'D-NSCLC__CE'},self.owner)
        self.assertEqual(self.engine.listing(self.owner),[])
    def test_preparation_repairs_once_but_never_accepts_invented_citations(self):
        original=self.provider.chat;attempts=[]
        def once(system,user,**kw):
            raw=original(system,user,**kw)
            if '本次拜访的准备助手' in system:
                attempts.append(json.loads(user))
                if len(attempts)==1:
                    d=json.loads(raw);d['priorities'][0]['criteria'][0]['source_ids']=['invented'];return json.dumps(d)
            return raw
        self.provider.chat=once
        s=self.engine.prepare('custom',self.owner,{**F['visit']['custom_context'],'lesson_id':'D-NSCLC__CE'})
        self.assertEqual(len(attempts),2)
        self.assertIn('validation_error',attempts[1])
        self.assertTrue(set(s['priorities'][0]['criteria'][0]['source_ids'])<=set(attempts[1]['allowed_source_ids']))
        def always(system,user,**kw):
            raw=original(system,user,**kw)
            if '本次拜访的准备助手' in system:
                d=json.loads(raw);d['priorities'][0]['criteria'][0]['source_ids']=['invented'];return json.dumps(d)
            return raw
        self.provider.chat=always
        before=len(self.engine.sheets_listing(self.owner))
        with self.assertRaises(ModelFailure):self.engine.prepare('custom',self.owner,{**F['visit']['custom_context'],'lesson_id':'D-NSCLC__CE'})
        self.assertEqual(len(self.engine.sheets_listing(self.owner)),before)
    def test_snapshot_survives_in_memory_course_update(self):
        r=self.engine.create({'mode':'learn','lesson_id':'D-NSCLC__CE'},self.owner)
        original=LESSONS['D-NSCLC__CE']['content']['goal']
        try:
            LESSONS['D-NSCLC__CE']['content']['goal']='修改后的另一个版本'
            stored=self.engine.load('runs',r['id'],self.owner)
            self.assertEqual(stored['material']['content']['goal'],original)
            self.assertNotEqual(stored['material']['revision'],snapshot('D-NSCLC__CE')['revision'])
        finally:LESSONS['D-NSCLC__CE']['content']['goal']=original
    def test_custom_visit_uses_selected_course_and_can_skip_practice(self):
        s=self.engine.prepare('custom',self.owner,{**F['visit']['custom_context'],'lesson_id':'D-NSCLC__CE'})
        self.assertEqual(s['material']['lesson_id'],'D-NSCLC__CE')
        self.assertEqual(s['practice_results'],[]);self.assertEqual(self.engine.listing(self.owner),[])
        r=self.engine.create({'mode':'visit','sheet_id':s['id'],'option_id':s['priorities'][0]['id']},self.owner)
        self.assertEqual(r['material']['revision'],s['material']['revision'])
        self.assertNotIn('C-17',str(r['material']))
    def test_fastapi_full_course_and_missing_voice_status(self):
        with TestClient(create_app(Path(self.tmp.name)/'http.db',self.provider,True),base_url='http://127.0.0.1:8791') as c:
            headers={'origin':'http://127.0.0.1:8791'}
            s=c.get('/api/courses/D-NSCLC__CE');self.assertEqual(s.status_code,200)
            self.assertIn('visual',s.json()['content'])
            self.assertEqual(c.get('/api/courses/no-such-course').status_code,404)
            self.assertEqual(c.post('/api/runs',json={'mode':'learn','lesson_id':'demo-evidence'}).status_code,403)
            r=c.post('/api/runs',json={'mode':'learn','lesson_id':'demo-evidence'},headers=headers)
            self.assertEqual(r.status_code,201)
            voice=c.get('/api/voice/config');self.assertIn('ready',voice.json())
            found=c.post('/api/materials/search',json={'lesson_id':'D-NSCLC__CE','query':'EGFR','filters':{'lesson_id':'other'}},headers=headers)
            self.assertTrue(all(b['id'].startswith('D-NSCLC__CE:') for b in found.json()['blocks']))
            self.assertNotIn('api_secret',str(voice.json()).lower())
