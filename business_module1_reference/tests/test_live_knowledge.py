import unittest,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from live_knowledge import catalog,export_task,owned_tasks,real_lesson
from workflow import Engine,Problem
from materials import snapshot

class LiveKnowledgeTests(unittest.TestCase):
    def test_corpus_has_real_sources_and_never_demo_or_employee(self):
        c=catalog()
        self.assertEqual(len(c['courses']),71)
        self.assertTrue(c['products'] and c['questions'] and c['claims'] and c['sources'])
        self.assertIsNone(c['employeeProfile'])
        self.assertNotIn('demo-evidence',[x['lesson_id'] for x in c['courses']])
        for lesson in c['courses']:
            self.assertTrue((Path(__file__).resolve().parents[1]/lesson['sourcePath']).is_file())
        with self.assertRaises(Problem):real_lesson('demo-evidence')

    def test_task_export_preserves_frozen_material_and_owner(self):
        with tempfile.TemporaryDirectory() as td:
            e=Engine(Path(td)/'state.db',None)
            m=snapshot('D-NSCLC__CE')
            task={'id':'actual-course-run','lesson_id':'D-NSCLC__CE','material':m,'state':'active',
                  'criteria':[{'id':'boundary','label':'材料边界','expected':'保留证据边界','source_ids':[m['blocks'][0]['id']]}],
                  'task':{'question':'研究有哪些限制？'},'transcript':[],'created_at':1,'updated_at':2}
            e.save('runs',task,'owner-one')
            x=export_task(e,'owner-one','runs',task['id'])
            self.assertEqual(x['material']['revision'],m['revision'])
            self.assertFalse(x['candidatePoolKnown']);self.assertIsNone(x['expertId'])
            self.assertEqual(len(owned_tasks(e,'owner-one')),1)
            self.assertEqual(owned_tasks(e,'owner-two'),[])
            with self.assertRaises(Problem):export_task(e,'owner-two','runs',task['id'])
            task['material']={};e.save('runs',task,'owner-one')
            with self.assertRaises(Problem):export_task(e,'owner-one','runs',task['id'])
