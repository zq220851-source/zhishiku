"""Independent output-only review. No access to Engine or decision-engine logic."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
EX=ROOT/'shared_exchange'

def inspect(d,old):
    failures=[];success=[]
    def check(name,cond):
        (success if cond else failures).append(name)
    m1=d.get('module1',{});m3=d.get('module3',{});a=d.get('audit',{})
    check('marked test-only',d.get('usage')=='TEST_ONLY' and d.get('kind')=='THREE_MODULE_HTTP_TEST_V2')
    check('source sheet has two chosen topics',m1.get('originalSelected')==['needs','followup'])
    check('new sheet selected different topics',m1.get('newSelected')==['needs','evidence_scope'])
    check('old and new sheet use different IDs',m1.get('originalSheetId')!=m1.get('newSheetId'))
    check('old sheet stays frozen',m1.get('originalStillImmutable') is True)
    check('review replay does not create a duplicate',m1.get('replayedIdempotently') is True)
    check('added topic justified',m1.get('added')==['evidence_scope'])
    check('displaced topic explicit',m1.get('displaced')==['followup'])
    check('new choice comes from independent M2 engine candidate',m1.get('newSelected')==old.get('module2',{}).get('nextPreparation',{}).get('after'))
    p=m1.get('practice',{})
    check('real M1 engine ran a completed practice',p.get('state')=='review' and p.get('attempt')==1)
    check('M1 practice had source-aligned itemized review',len(p.get('criteria',[]))==3 and all(x.get('anchored') is True for x in p.get('criteria',[])))
    check('practice is not medical certification',p.get('medicalAccuracy')=='NA')
    check('real M3 sample source matched search',m3.get('matchedSources')==['example-rwe'])
    check('M3 sources initially unreviewed',m3.get('inboxStatus')==['PENDING_MEDICAL_REVIEW'])
    check('test review only permits reading',m3.get('testReadingAllowed') is True)
    check('no medical knowledge was approved',m3.get('medicalKnowledgeApproved') is False)
    check('no knowledge version upgraded',m3.get('knowledgeVersionUpgraded') is False)
    check('unreviewed plan rejected',a.get('unreviewedProposalRejected') is True)
    check('production medical approval rejected',a.get('productionMedicalApprovalRejected') is True)
    check('invalid external lookup rejected',a.get('malformedSearchRejected') is True)
    return success,failures
if __name__=='__main__':
    observed=json.loads((EX/'three-module-runtime-http-results.json').read_text())
    old=json.loads((EX/'three-module-results.json').read_text())
    ok,bad=inspect(observed,old)
    print(json.dumps({'passed':len(ok),'failed':len(bad),'failureChecks':bad},ensure_ascii=False))
    if bad:sys.exit(1)
    # Negative control: independent reviewer actually catches a corrupted selected plan.
    altered=json.loads(json.dumps(observed));altered['module1']['newSelected']=['needs','followup']
    _,detected=inspect(altered,old)
    if not detected:raise RuntimeError('审查器没有抓住故意篡改的选题')
    print('tamper-negative-control: DETECTED')
