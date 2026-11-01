"""Frozen pre-visit prediction is immutable and the module-2 export has the same evidence."""
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workflow import Engine,Problem
from live_knowledge import export_task
from doubles import ScriptedProvider,FIXTURES

class FrozenForecastTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.owner='owner-forecast'
        self.engine=Engine(Path(self.tmp.name)/'forecast.sqlite',ScriptedProvider())
        self.sheet=self.engine.prepare('custom',self.owner,{**FIXTURES['visit']['custom_context'],'lesson_id':'D-NSCLC__CE'})
    def tearDown(self):self.tmp.cleanup()
    def test_freeze_requires_true_previsit_ack_and_actual_generated_option(self):
        item=self.sheet['priorities'][0]['id']
        with self.assertRaises(Problem):self.engine.freeze_forecast(self.sheet['id'],self.owner,[item],False)
        with self.assertRaises(Problem):self.engine.freeze_forecast(self.sheet['id'],self.owner,['created_after_visit'],True)
        with self.assertRaises(Problem):self.engine.freeze_forecast(self.sheet['id'],self.owner,[item,item],True)
        self.assertNotIn('forecast',self.engine.load('sheets',self.sheet['id'],self.owner))
    def test_freeze_and_export_keeps_plan_and_revision_and_does_not_rewrite(self):
        item=self.sheet['priorities'][0]['id']
        frozen=self.engine.freeze_forecast(self.sheet['id'],self.owner,[item],True)
        self.assertEqual(frozen['forecast']['candidate_ids'],[p['id'] for p in self.sheet['priorities']])
        self.assertEqual(frozen['forecast']['selected_ids'],[item])
        packet=export_task(self.engine,self.owner,'sheets',self.sheet['id'])
        self.assertTrue(packet['candidatePoolKnown'])
        self.assertEqual(packet['forecast']['frozen_at'],frozen['forecast']['frozen_at'])
        self.assertEqual(packet['material']['revision'],packet['forecast']['lesson_revision'])
        with self.assertRaises(Problem) as caught:self.engine.freeze_forecast(self.sheet['id'],self.owner,[item],True)
        self.assertEqual(caught.exception.status,409)
        self.assertEqual(export_task(self.engine,self.owner,'sheets',self.sheet['id'])['forecast'],packet['forecast'])
    def test_wrong_owner_cannot_freeze_another_users_sheet(self):
        with self.assertRaises(Problem):self.engine.freeze_forecast(self.sheet['id'],'another-owner',[self.sheet['priorities'][0]['id']],True)

if __name__=='__main__':unittest.main()
