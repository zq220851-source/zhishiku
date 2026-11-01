"""Do not import or mutate approved knowledge; synthetic-only acceptance tests."""
import copy, tempfile, time, unittest
from pathlib import Path
from test_bridge import fingerprint, sheet_hash, freeze_user_selection_for_test, apply_reviewed_test_candidate, review_external_test_candidate
from workflow import Engine, Problem
from doubles import ScriptedProvider

class TestBridge(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.e=Engine(Path(self.tmp.name)/'b.sqlite',ScriptedProvider());self.owner='fixture-owner'
        orig=self.e.prepare('demo-visit',self.owner)
        self.sheet=freeze_user_selection_for_test(self.e,self.owner,orig,['needs','followup'])
        self.candidate={'usage':'TEST_ONLY','status':'CANDIDATE_NOT_APPLIED','sourceSheetHash':sheet_hash(self.sheet),
                        'sourceSnapshotHash':'f'*64,'selectedOptionIds':['needs','evidence_scope']}
        self.review={'action':'ADOPT_TEST_ONLY','status':'REVIEWED_TEST_ONLY','candidateHash':fingerprint(self.candidate),
                     'reviewer':'fixture-reviewer-training','reviewId':'test-review-0001',
                     'reviewedAt':'2026-11-03T08:00:00Z'}
    def test_adopts_into_new_sheet_leaving_old_frozen(self):
        old=copy.deepcopy(self.e.load('sheets',self.sheet['id'],self.owner))
        new=apply_reviewed_test_candidate(self.e,self.owner,self.sheet['id'],self.candidate,self.review)
        self.assertNotEqual(new['id'],self.sheet['id'])
        self.assertEqual([p['id'] for p in new['priorities']],['needs','evidence_scope'])
        self.assertEqual(new['reviewReceipt']['added'],['evidence_scope'])
        self.assertEqual(new['reviewReceipt']['displaced'],['followup'])
        self.assertEqual(self.e.load('sheets',self.sheet['id'],self.owner),old)
        self.assertEqual(apply_reviewed_test_candidate(self.e,self.owner,self.sheet['id'],self.candidate,self.review)['id'],new['id'])
    def test_rejects_unreviewed_changed_candidate_and_mismatched_sheet(self):
        for candidate,decision in [
            (self.candidate,{**self.review,'status':'UNREVIEWED'}),
            ({**self.candidate,'selectedOptionIds':['needs','followup']},self.review),
            ({**self.candidate,'sourceSheetHash':'x'*64},self.review),
            ({**self.candidate,'selectedOptionIds':['needs','unknown']},self.review),
        ]:
            with self.assertRaises(Problem):apply_reviewed_test_candidate(self.e,self.owner,self.sheet['id'],candidate,decision)
        with self.assertRaises(Problem):apply_reviewed_test_candidate(self.e,'other-owner',self.sheet['id'],self.candidate,self.review)
    def test_reviewer_id_cannot_be_reused_for_different_payload(self):
        apply_reviewed_test_candidate(self.e,self.owner,self.sheet['id'],self.candidate,self.review)
        wrong={**self.candidate,'selectedOptionIds':['needs','followup']}
        fake={**self.review,'candidateHash':fingerprint(wrong)}
        with self.assertRaises(Problem):apply_reviewed_test_candidate(self.e,self.owner,self.sheet['id'],wrong,fake)
    def test_module3_candidate_remains_learning_only_even_if_test_accepted(self):
        inbox={'kind':'M3_TO_M1_REVIEW_INBOX_V1','usage':'TEST_ONLY','knowledgeGapResolved':False,
               'requestedCapabilityId':'cap-1','requestId':'req-001',
               'candidates':[{'sourceId':'src-1','sourceVersion':'a'*64,
                 'approvalStatus':'PENDING_MEDICAL_REVIEW','appliedToTraining':False}]}
        d=review_external_test_candidate(inbox,'src-1','fixture-medical-reviewer-a','ACCEPT_FOR_TEST_READING','a'*64)
        self.assertTrue(d['canUseForTestReading']);self.assertFalse(d['canUseAsMedicalKnowledge']);
        self.assertFalse(d['canUpdateKnowledgeVersion']);self.assertFalse(d['canUseForScoring'])
        with self.assertRaises(Problem):review_external_test_candidate(inbox,'src-1','fixture-medical-reviewer-a','ACCEPT_FOR_TEST_READING','bad')
        with self.assertRaises(Problem):review_external_test_candidate(inbox,'src-1','fixture-medical-reviewer-a','APPROVE_FOR_PRODUCTION','a'*64)
if __name__=='__main__':unittest.main()
