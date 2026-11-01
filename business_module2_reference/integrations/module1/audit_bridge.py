"""Independent read-only auditor of the deterministic M1 -> M2 -> M1 fictional demo.
Does not import implementation modules or regenerate expected output.
"""
import json, sys
from pathlib import Path
p=Path(sys.argv[1]);d=json.loads(p.read_text(encoding='utf8'))
checks={
 'strict test-only scope':d['scope'].startswith('TEST_ONLY'),
 'original selections':d['initial']['selectedOptionIds']==['needs','followup'],
 'source includes the full candidate pool':d['initial']['candidateOptionIds']==['needs','evidence_scope','followup'],
 'first practice needs retraining':d['first']['personalStatus']=='TARGETED_RETRAIN',
 'first practice quote provenance':bool(d['first']['practice'][0]['origin']['quote']),
 'first practice original source id':d['first']['practice'][0]['origin']['sourceIds']==['demo-evidence:sections.2'],
 'second practice changes state':d['second']['personalStatus']=='RETEST_OR_RETENTION',
 'new option is evidence scope':d['next']['newOptionIds']==['needs','evidence_scope'],
 'displaced option explicit':d['next']['oldOptionIds']==['needs','followup'],
 'proposal not automatically applied':d['next']['selectionStatus']=='CANDIDATE_NOT_APPLIED',
 'historical task snapshot not overwritten':d['initial']['snapshotHash']!=d['next']['nextTaskSnapshotHash'],
 'historical visits included':d['next']['usedVisitIds']==['fictional-v1','fictional-v2'],
 'future holdout improves test coverage':d['holdout']['newCovered']>d['holdout']['oldCovered'],
 'lost capability disclosed':len(d['holdout']['lost'])>0,
 'same budget constraint':d['holdout']['passedBudget'] is True,
 'no API or medical approval claimed':any('not a medically reviewed' in x for x in d['limitations'])
}
for k,ok in checks.items():print(('PASS' if ok else 'FAIL')+' '+k)
print(f'{sum(checks.values())}/{len(checks)} independent checks passed')
if not all(checks.values()):sys.exit(1)
