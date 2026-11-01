import json, tempfile, threading, unittest, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from knowledge import LESSONS
from workflow import Engine, Problem, ModelFailure
from doubles import ScriptedProvider, FIXTURES as F


class Workflows(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.provider=ScriptedProvider()
        self.path=Path(self.tmp.name)/'state.sqlite';self.e=Engine(self.path,self.provider);self.owner='owner-a'
    def tearDown(self):self.tmp.cleanup()
    def create(self):return self.e.create({'mode':'learn','lesson_id':F['lesson_id']},self.owner)
    def answer(self,r,text,request='request-0001'):
        return self.e.answer(r['id'],{'answer':text,'request_id':request,'revision':r['revision']},self.owner)
    def finish_wrong(self,r):
        r=self.answer(r,F['learning']['wrong']);return self.answer(r,F['learning']['followup_wrong'],'request-0002')

    def test_voice_playback_persists_partial_status_and_cannot_touch_other_owner(self):
        r=self.create()
        r=self.e.playback(r['id'],{'turn_index':0,'status':'interrupted','played_ms':550},self.owner)
        self.assertEqual(r['transcript'][0]['playback']['played_ms'],550)
        with self.assertRaises(Problem):self.e.playback(r['id'],{'turn_index':0,'status':'completed'},'other-owner')
        self.e.playback(r['id'],{'turn_index':0,'status':'completed','played_ms':1500},self.owner)
        r=self.e.playback(r['id'],{'turn_index':0,'status':'interrupted','played_ms':0},self.owner)
        self.assertEqual(r['transcript'][0]['playback']['status'],'completed')

    def test_resume_retries_saved_voice_without_duplicate_answer(self):
        r=self.create();self.provider.failure=True
        with self.assertRaises(ModelFailure):self.answer(r,F['learning']['good'])
        self.provider.failure=False
        done=self.e.resume(r['id'],self.owner)
        self.assertEqual(done['state'],'review')
        self.assertEqual(sum(m['role']=='药代' for m in done['transcript']),1)
        self.assertEqual(self.e.resume(r['id'],self.owner)['revision'],done['revision'])

    def test_learning_wrong_support_retry_good_full_journey(self):
        r=self.finish_wrong(self.create());self.assertEqual(r['state'],'review')
        self.assertTrue(any(x['status']=='needs_work' for x in r['review']['observations']))
        self.assertIn(F['learning']['wrong'],str(r['transcript']))
        self.e.support(r['id'],self.owner)
        r=self.e.retry(r['id'],self.owner);self.assertEqual(r['attempt'],2);self.assertEqual(len(r['attempts']),1)
        self.e.support(r['id'],self.owner)
        r=self.answer(r,F['learning']['good_variant'],'request-0003')
        self.assertEqual(r['state'],'review');self.assertTrue(r['review']['support_used'])
        self.assertFalse(r['review']['independent_mastery']);self.assertEqual(r['review']['medical_accuracy'],'NA')
        self.assertEqual(len(self.e.history(self.owner)),2)
        self.assertEqual(self.e.history('other-owner'),[])

    def test_visit_can_end_with_sheet_without_simulation(self):
        s=self.e.prepare('demo-visit',self.owner)
        self.assertEqual(s['practice_results'],[]);self.assertEqual(self.e.listing(self.owner),[])
        self.assertIn('未知',str(s['unknowns']))
        for p in s['priorities']:self.assertTrue(set(p['fact_ids']) <= {f['id'] for f in s['visit']['facts']})

    def test_visit_one_selected_task_updates_same_sheet(self):
        s=self.e.prepare('demo-visit',self.owner)
        r=self.e.create({'mode':'visit','sheet_id':s['id'],'option_id':'evidence_scope'},self.owner)
        r=self.answer(r,F['visit']['good'])
        s2=self.e.load('sheets',s['id'],self.owner)
        self.assertEqual(s2['id'],s['id']);self.assertEqual(len(s2['practice_results']),1)
        self.assertEqual(s2['practice_results'][0]['run_id'],r['id'])

    def test_custom_context_does_not_import_fictional_study(self):
        s=self.e.prepare('custom',self.owner,F['visit']['custom_context'])
        r=self.e.create({'mode':'visit','sheet_id':s['id'],'option_id':'evidence_scope'},self.owner)
        raw=self.e.load('runs',r['id'],self.owner)
        self.assertNotIn('C-17',str(raw['sources'])+str(raw['context']))
        self.assertIn('未独立核实',str(s['visit']['facts']))

    def test_unrelated_history_does_not_raise_priority(self):
        r=self.finish_wrong(self.create())
        raw=self.e.load('runs',r['id'],self.owner);raw['skills']=['unrelated-biology'];self.e.record(raw,self.owner)
        s=self.e.prepare('demo-visit',self.owner)
        self.assertFalse(any(x['history_reason'] for x in s['priorities']))

    def test_failure_saved_answer_retry_and_idempotency(self):
        r=self.create();self.provider.failure=True
        with self.assertRaises(ModelFailure):self.answer(r,F['learning']['good'])
        r=self.e.view(self.e.load('runs',r['id'],self.owner));self.assertEqual(r['state'],'retryable')
        self.provider.failure=False
        r=self.answer(r,F['learning']['good']);self.assertEqual(r['state'],'review')
        calls=self.provider.calls;r2=self.answer(r,F['learning']['good'])
        self.assertEqual(calls,self.provider.calls);self.assertEqual(len(r2['transcript']),2)
        with self.assertRaises(Problem):self.answer(r,'changed answer')

    def test_duplicate_concurrent_requests_call_model_once(self):
        r=self.create()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.answer(r,F['learning']['good']),range(2)))
        self.assertEqual(self.provider.calls,2);self.assertEqual(results[0]['id'],results[1]['id'])

    def test_model_quote_must_exist_and_cannot_keep_unverified_praise(self):
        self.provider.corrupt_quote=True
        r=self.answer(self.create(),F['learning']['good'])
        self.assertTrue(all(x['status']=='uncertain' for x in r['review']['observations']))
        self.assertIn('待核实',r['review']['feedback'])

    def test_source_not_in_snapshot_rejects_review(self):
        self.provider.corrupt_source=True
        with self.assertRaises(ModelFailure):self.answer(self.create(),F['learning']['good'])
        self.assertEqual(self.e.history(self.owner),[])

    def test_invalid_json_not_half_credit(self):
        self.provider.chat=lambda *a,**k:'not-json'
        with self.assertRaises(ModelFailure):self.answer(self.create(),F['learning']['good'])
        self.assertEqual(self.e.history(self.owner),[])

    def test_owner_boundary_and_invalid_input(self):
        r=self.create()
        with self.assertRaises(Problem):self.e.load('runs',r['id'],'other-owner')
        for text in ['', ' '*3,'x'*1601]:
            with self.assertRaises(Problem):self.answer(r,text)
        with self.assertRaises(Problem):self.e.create({'mode':'unknown'},self.owner)
        with self.assertRaises(Problem):self.e.create({'mode':'learn','lesson_id':'missing'},self.owner)

    def test_restart_recovery_and_correction_retracts_old_review(self):
        r=self.answer(self.create(),F['learning']['good'])
        self.assertEqual(len(self.e.history(self.owner)),1)
        e2=Engine(self.path,self.provider);r=e2.view(e2.load('runs',r['id'],self.owner))
        r=e2.correct(r['id'],{'answer':F['learning']['wrong'],'revision':r['revision']},self.owner)
        self.assertIsNone(r['review']);self.assertEqual(e2.history(self.owner),[])
        req=r['pending_request'];r=e2.answer(r['id'],{'answer':req['answer'],'request_id':req['id'],'revision':r['revision']},self.owner)
        r=e2.finish(r['id'],self.owner)
        self.assertTrue(any(x['status']=='needs_work' for x in r['review']['observations']))

    def test_original_courses_available_and_not_approved(self):
        self.assertEqual(len([x for x in LESSONS.values() if x.get('source_path')]),71)
        original=LESSONS['D-NSCLC__CE'];self.assertEqual(original['status'],'pending_medical_review')
        r=self.e.create({'mode':'learn','lesson_id':original['id']},self.owner)
        self.assertEqual(r['source_status'],'pending_medical_review')
        self.assertTrue(r['source_hash'])

    def test_prepare_failure_does_not_return_fabricated_fallback(self):
        self.provider.failure=True
        with self.assertRaises(ModelFailure):self.e.prepare('demo-visit',self.owner)

    def test_retry_does_not_let_model_speak_the_answer_as_doctor_question(self):
        r=self.finish_wrong(self.create())
        calls=self.provider.calls
        self.provider.chat=lambda *a,**k:json.dumps({'question':'我来告诉你答案：只有A类和X，没有对照。'})
        r=self.e.retry(r['id'],self.owner)
        self.assertNotIn('我来告诉你答案',r['transcript'][0]['text'])
        self.assertEqual(self.provider.calls,calls)

    def test_model_selects_original_evidence_instead_of_rewriting_quote(self):
        original=self.provider.chat
        def by_id(system,user,**kw):
            d=json.loads(original(system,user,**kw))
            if 'observations' not in d:return json.dumps(d,ensure_ascii=False)
            for o in d['observations']:
                o.pop('quote');o.pop('turn_index');o['evidence_id']='T1'
            return json.dumps(d,ensure_ascii=False)
        self.provider.chat=by_id
        r=self.answer(self.create(),F['learning']['negation'])
        self.assertTrue(all(o['status']=='demonstrated' for o in r['review']['observations']))
        self.assertTrue(all(o['quote']==F['learning']['negation'] for o in r['review']['observations']))

    def test_original_course_behavior_observations_can_inform_custom_preparation(self):
        r=self.e.create({'mode':'learn','lesson_id':'D-NSCLC__CE'},self.owner)
        r=self.finish_wrong(r)
        self.assertTrue(all(x.startswith('course_') for x in r['skills']))
        s=self.e.prepare('custom',self.owner,F['visit']['custom_context'])
        p=next(x for x in s['priorities'] if x['id']=='evidence_scope')
        self.assertIsNone(p['history_reason']) # Course-specific observations must not become generic weaknesses.
        self.assertFalse(self.e.history(self.owner)[0]['permanent_mastery'])

if __name__=='__main__':unittest.main()
