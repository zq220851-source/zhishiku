"""Opt-in approved method consumption, source version and frozen snapshots (fictional)."""
import json, tempfile, unittest, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workflow import Engine, Problem
from doubles import ScriptedProvider, FIXTURES
from method_client import approved_method_for_lesson, MethodUnavailable
from unittest.mock import patch
from io import BytesIO


class ApprovedMethodProvider(ScriptedProvider):
    def chat(self, system, user, **kwargs):
        value=json.loads(user)
        out=json.loads(super().chat(system,user,**kwargs))
        if '本次拜访的准备助手' in system and value.get('approved_method'):
            out['method_application']={'used':True,'reason':'本次目标要求核对资料范围，方法适用'}
        return json.dumps(out,ensure_ascii=False)


class MethodIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.provider=ApprovedMethodProvider()
        self.engine=Engine(Path(self.tmp.name)/'module1.sqlite',self.provider)
        self.context=FIXTURES['visit']['custom_context'];self.owner='owner-method-test'
    def tearDown(self):self.tmp.cleanup()
    def approved(self,revision):
        return {'id':'method-review-01','version':'m-v2','source_versions':[revision],
                'condition':'需要解释研究适用范围时','action':'先查看证据能支持哪些结论',
                'reason':'两次交流中的可迁移准备方式','exceptions':['仅询问概念定义时']} 
    def test_opt_in_consumes_method_and_keeps_source_bound_criteria(self):
        from materials import snapshot
        revision=snapshot(self.context['lesson_id'])['revision'] if 'lesson_id' in self.context else snapshot('visit-communication')['revision']
        m=self.approved(revision)
        sheet=self.engine.prepare('custom',self.owner,self.context,m)
        self.assertEqual(sheet['method_offer']['version'],'m-v2')
        self.assertEqual(sheet['consumed_method_versions'][0]['id'],'method-review-01')
        self.assertTrue(sheet['method_application']['used'])
        stored=self.engine.load('sheets',sheet['id'],self.owner)
        self.assertEqual(stored['consumed_method_versions'],sheet['consumed_method_versions'])
        allowed={b['id'] for b in sheet['material']['blocks']}
        self.assertTrue(all(set(c['source_ids'])<=allowed for p in sheet['priorities'] for c in p['criteria']))
        run=self.engine.create({'mode':'visit','sheet_id':sheet['id'],'option_id':sheet['priorities'][0]['id']},self.owner)
        self.assertEqual(run['consumed_method_versions'],sheet['consumed_method_versions'])
        no_method=self.engine.prepare('custom',self.owner,self.context)
        self.assertFalse(no_method['consumed_method_versions'])
    def test_stale_course_version_blocks_method(self):
        with self.assertRaises(Problem):
            self.engine.prepare('custom',self.owner,self.context,self.approved('different_revision'))
    def test_client_never_trusts_fake_purpose_or_unauthorized_method(self):
        class Reply:
            def __init__(self,obj):self.io=BytesIO(json.dumps(obj).encode())
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,*a):return self.io.read(*a)
        with patch('method_client.urlopen',return_value=Reply({'data':{'purpose':'UNVERIFIED','methods':[]}})):
            with self.assertRaises(MethodUnavailable):approved_method_for_lesson('signed-cookie','visit-communication')
        with patch('method_client.urlopen',return_value=Reply({'data':{'purpose':'TEST_ONLY','methods':[]}})):
            self.assertIsNone(approved_method_for_lesson('signed-cookie','visit-communication'))

if __name__=='__main__':unittest.main()
