#!/usr/bin/env python3
"""Separate process, JSON-only reviewer. Never imports development source or calls the model.
This is an isolated automated audit, NOT an independent LLM agent or a real-world AI accuracy evaluation.
"""
import json, sys, pathlib
p = pathlib.Path(__file__).resolve().parent
observed_path = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else p/'observed.json'
observed = json.loads(observed_path.read_text(encoding='utf8'))
gold = json.loads((p/'frozen_expectations.json').read_text(encoding='utf8'))
checks = []
def check(name, actual, expected):
    checks.append({'id':name,'passed':actual == expected,'expected':expected,'observed':actual})
def pick(rows, kind): return [r for r in rows if r['kind']==kind]
def label(rows, kind): return [r['label'] for r in pick(rows,kind)]
def summary(rows,key): return next((row for row in rows if row['key']==key),None)
check('step count',len(observed),gold['expected_steps'])
if len(observed)==gold['expected_steps']:
    s1,s2,s3,s4,s5,s6=observed
    check('V1 forecast gap',label(s1['newEntries'],'FORECAST'),[gold['at_step_1']['forecast']])
    check('V1 personal source',label(s1['newEntries'],'PERSONAL_SKILL'),[gold['at_step_1']['skill']])
    check('V1 knowledge supported',label(s1['newEntries'],'KNOWLEDGE_COVERAGE'),[gold['at_step_1']['knowledge']])
    check('V1 expert first observation',label(s1['newEntries'],'EXPERT_OBSERVATION'),[gold['at_step_1']['expert']])
    check('V2 forecast covered',label(s2['newEntries'],'FORECAST'),[gold['at_step_2']['forecast']])
    check('V2 only practice evidence',label(s2['newEntries'],'PERSONAL_SKILL'),[gold['at_step_2']['practice']])
    cohort2=summary(s2['cohort'],'studyA:extrapolation') or {}
    check('repeat visits count as two visits',cohort2.get('reportedVisits'),2)
    check('repeat visits do not double count employees',cohort2.get('reportedReps'),gold['at_step_2']['unique_reps'])
    check('repeat visits do not double count experts',cohort2.get('reportedExperts'),gold['at_step_2']['unique_experts'])
    q3=pick(s3['newEntries'],'KNOWLEDGE_COVERAGE')
    check('knowledge no result label', [r['label'] for r in q3],[gold['at_step_3']['knowledge']])
    check('knowledge candidate not approved', [r['status'] for r in q3],[gold['at_step_3']['knowledge_status']])
    check('explicit negation no expert/forecast/cohort',sorted(set(r['kind'] for r in s4['newEntries'])),gold['at_step_4']['allowed_kinds'])
    check('hypothetical no expert/forecast/cohort',sorted(set(r['kind'] for r in s5['newEntries'])),gold['at_step_5']['allowed_kinds'])
    check('revision V1 version preserved',s6['submitted']['rawVersion'],gold['at_step_6']['rawVersion'])
    check('revision history preserved',s6['historyV1'],gold['at_step_6']['history_v1'])
    check('revised current visit count',s6['activeVisits'],gold['at_step_6']['current_visits'])
    check('ghost observations from revised V1 cleared', len([r for r in s6['activeEntries'] if r['visitId']=='V1' and r['kind'] in ('FORECAST','EXPERT_OBSERVATION','COHORT_EVENT','KNOWLEDGE_COVERAGE')]),0)
    a=summary(s6['cohort'],'studyA:extrapolation') or {}
    b=summary(s6['cohort'],'studyB:long-term') or {}
    check('final study A visit frequency',a.get('reportedVisits'),gold['at_step_6']['reported_studyA_visits'])
    check('final study B visit frequency',b.get('reportedVisits'),gold['at_step_6']['reported_studyB_visits'])
    check('final denominator visits',a.get('denominatorVisits'),gold['at_step_6']['total_visits'])
    check('final denominator unique reps',a.get('denominatorReps'),gold['at_step_6']['total_reps'])
    check('no stable profile or proven medical gaps', sorted(set(r['label'] for s in observed for r in s['activeEntries']) & set(gold['forbidden_labels'])), [])
    check('new source references for non-practice entries',all(r['evidenceObservationIds'] for s in observed for r in s['newEntries'] if r['status']!='TRAINING_EVIDENCE'),True)
result={'test_type':'INDEPENDENT_CODE_OUTPUT_REVIEW','gold_version':gold['version'],'passed':sum(1 for x in checks if x['passed']),'total':len(checks),'checks':checks,'limitations':['No second agent was launched. This is a separate program that consumes JSON only.','Structured inputs are human-created mock annotations, not model extraction.','Knowledge check statuses are supplied fixtures, not RAG retrieval.','Cannot prove downstream training effectiveness or predictive accuracy.']}
(p/('audit_report.json' if len(sys.argv) == 1 else 'audit_mutation_report.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print('Review:',result['passed'],'/',result['total'],'checks passed')
for c in checks:
    if not c['passed']:print('FAILED:',c['id'],'expected',c['expected'],'observed',c['observed'])
sys.exit(0 if result['passed']==result['total'] else 1)
