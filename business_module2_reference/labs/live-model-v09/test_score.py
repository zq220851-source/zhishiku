import unittest,hashlib,json,pathlib,sys,copy
BASE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(BASE))
from score import classify,evaluate,INPUT

class TestEvaluator(unittest.TestCase):
 def base(self):
  samples=json.loads(INPUT.read_text(encoding='utf8'))
  return dict(sourceHash=hashlib.sha256(INPUT.read_bytes()).hexdigest(),actualModelRequested=False,records=[dict(id=samples[0]['id'],inputHash=hashlib.sha256(samples[0]['text'].encode()).hexdigest(),status='UNREVIEWED_PROPOSAL',events=[])])
 def test_no_events_is_not_positive(self):
  self.assertEqual(classify({'status':'UNREVIEWED_PROPOSAL','events':[]}), 'DENIED')
 def test_denied_other_event_and_real_extrapolation(self):
  events=[dict(action='QUESTION',agent='EXPERT',when='DURING_VISIT',capabilityId='endpoint',factuality='DENIED'),dict(action='QUESTION',agent='EXPERT',when='DURING_VISIT',capabilityId='extrapolation',factuality='REPORTED')]
  self.assertEqual(classify({'status':'UNREVIEWED_PROPOSAL','events':events}), 'REPORTED')
 def test_future_hypothetical_is_not_treated_as_denied(self):
  e=dict(action='QUESTION',agent='EXPERT',when='FUTURE',capabilityId='extrapolation',factuality='HYPOTHETICAL')
  self.assertEqual(classify({'status':'UNREVIEWED_PROPOSAL','events':[e]}),'HYPOTHETICAL')
 def test_hypothetical_unspecified_time(self):
  e=dict(action='QUESTION',agent='UNKNOWN',when='UNKNOWN',capabilityId='extrapolation',factuality='HYPOTHETICAL')
  self.assertEqual(classify({'status':'UNREVIEWED_PROPOSAL','events':[e]}),'HYPOTHETICAL')
 def test_uncertain_expert_question_unknown_time(self):
  e=dict(action='QUESTION',agent='EXPERT',when='UNKNOWN',capabilityId='extrapolation',factuality='UNCERTAIN')
  self.assertEqual(classify({'status':'UNREVIEWED_PROPOSAL','events':[e]}),'UNCERTAIN')
 def test_uncertain_speaker_must_not_be_denied(self):
  e=dict(action='QUESTION',agent='UNKNOWN',when='DURING_VISIT',capabilityId='extrapolation',factuality='REPORTED')
  self.assertEqual(classify({'status':'UNREVIEWED_PROPOSAL','events':[e]}),'UNCERTAIN')
 def test_explicit_denial_overrides_future_hypothetical(self):
  h=dict(action='QUESTION',agent='EXPERT',when='FUTURE',capabilityId='extrapolation',factuality='HYPOTHETICAL')
  d=dict(action='QUESTION',agent='EXPERT',when='DURING_VISIT',capabilityId='extrapolation',factuality='DENIED')
  self.assertEqual(classify({'status':'UNREVIEWED_PROPOSAL','events':[h,d]}),'DENIED')
 def test_later_visit_question_overrides_earlier_denial(self):
  d=dict(action='QUESTION',agent='EXPERT',when='DURING_VISIT',capabilityId='extrapolation',factuality='DENIED')
  r=dict(action='QUESTION',agent='EXPERT',when='DURING_VISIT',capabilityId='extrapolation',factuality='REPORTED')
  self.assertEqual(classify({'status':'UNREVIEWED_PROPOSAL','events':[d,r]}),'REPORTED')
 def test_unrelated_capability_is_not_target_question(self):
  e=dict(action='QUESTION',agent='EXPERT',when='DURING_VISIT',capabilityId='endpoint',factuality='REPORTED')
  self.assertEqual(classify({'status':'UNREVIEWED_PROPOSAL','events':[e]}),'DENIED')
 def test_invalid_event_object(self):
  self.assertEqual(classify({'status':'UNREVIEWED_PROPOSAL','events':[None]}),'INVALID')
 def test_not_pretend_invalid_response_correct(self):
  self.assertEqual(classify({'status':'ERROR', 'events':[]}), 'INVALID')
 def test_scores_and_labels_simulation(self):
  x=self.base();r=evaluate(x)
  self.assertEqual(r['n'],1);self.assertFalse(r['all25Completed']);self.assertEqual(r['evaluation'],'SIMULATED_ONLY')
 def test_modified_input_blocked(self):
  x=self.base();x['records'][0]['inputHash']='invalid'
  with self.assertRaises(AssertionError):evaluate(x)
 def test_reused_ids_blocked(self):
  x=self.base();x['records']=x['records']*2
  with self.assertRaises(AssertionError):evaluate(x)
 def test_fake_source_manifest_blocked(self):
  x=self.base();x['sourceHash']='not-the-frozen-set'
  with self.assertRaises(AssertionError):evaluate(x)

if __name__=='__main__':unittest.main()
