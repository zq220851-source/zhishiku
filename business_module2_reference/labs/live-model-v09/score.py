#!/usr/bin/env python3
"""Independent evaluator. Frozen gold stays outside the model runner's input path."""
import hashlib, json, sys, pathlib, collections
BASE = pathlib.Path(__file__).resolve().parent
GOLD = (BASE / '../../../../review_lab/frozen_gold.json').resolve()
INPUT = BASE / 'inputs.json'
# This digest locks the human key that existed before this benchmark was created.
GOLD_SHA256 = '465ab7050396387dd262dc829e487dc0a62a22505a3106f7aa309fdeb91b567a'
LABELS=['REPORTED','DENIED','HYPOTHETICAL','UNCERTAIN']

def classify(rec):
    """Score the target *reported expert question* without discarding
    hypothetical/uncertain events for having a different time or agent.

    An explicit denial of a visit question outranks a merely hypothetical
    future question. A later reported visit question outranks an earlier denial.
    This is still a narrow event-level benchmark, not comprehensive extraction.
    """
    if rec.get('status') != 'UNREVIEWED_PROPOSAL':
        return 'INVALID'
    events = rec.get('events', [])
    if not isinstance(events, list) or any(not isinstance(e, dict) for e in events):
        return 'INVALID'
    target = [e for e in events if e.get('action') == 'QUESTION'
              and e.get('capabilityId') == 'extrapolation']
    during = [e for e in target if e.get('agent') == 'EXPERT'
              and e.get('when') == 'DURING_VISIT']
    if any(e.get('factuality') == 'REPORTED' for e in during):
        return 'REPORTED'
    # Relevant uncertainty includes unclear speaker or unclear time, but not
    # questions clearly asked by a nonexpert or only after the visit.
    eligible = [e for e in target if e.get('agent') in ('EXPERT', 'UNKNOWN')
                and e.get('when') in ('DURING_VISIT', 'UNKNOWN', 'FUTURE')]
    if any(e.get('factuality') == 'UNCERTAIN' for e in eligible):
        return 'UNCERTAIN'
    if any(e.get('factuality') == 'REPORTED'
           and (e.get('agent') == 'UNKNOWN' or e.get('when') == 'UNKNOWN')
           for e in eligible):
        return 'UNCERTAIN'
    # Explicitly denied *visit* questions win over hypothetical future asks.
    if any(e.get('factuality') == 'DENIED' for e in during):
        return 'DENIED'
    if any(e.get('factuality') == 'HYPOTHETICAL' for e in eligible):
        return 'HYPOTHETICAL'
    return 'DENIED'

def evaluate(output):
    assert hashlib.sha256(GOLD.read_bytes()).hexdigest()==GOLD_SHA256,'Frozen gold checksum mismatch'
    gold=json.loads(GOLD.read_text(encoding='utf-8'))
    inputs=json.loads(INPUT.read_text(encoding='utf-8'))
    input_by_id={c['id']:c['text'] for c in inputs}
    assert len(input_by_id)==len(inputs),'Duplicate frozen input ids'
    assert hashlib.sha256(INPUT.read_bytes()).hexdigest()==output.get('sourceHash'),'Model input manifest mismatch'
    exp={c['id']:c['expected'] for c in gold['cases']}
    records=output.get('records',[])
    assert len({r['id'] for r in records})==len(records),'Duplicate model result IDs'
    assert all(r['id'] in exp for r in records),'Unknown model output ID'
    for r in records:
        assert r['inputHash']==hashlib.sha256(input_by_id[r['id']].encode()).hexdigest(),'Input changed after run'
    confusion=collections.Counter()
    results=[]
    for r in records:
        pred=classify(r)
        expected=exp[r['id']]
        results.append({'id':r['id'],'expected':expected,'predicted':pred,'correct':pred==expected,'status':r.get('status')})
        confusion[(expected,pred)]+=1
    accuracy=sum(x['correct'] for x in results)
    pos_false=sum(x['expected']!='REPORTED' and x['predicted']=='REPORTED' for x in results)
    pos_missed=sum(x['expected']=='REPORTED' and x['predicted']!='REPORTED' for x in results)
    return {'evaluation':('ACTUAL_MODEL_PROPOSALS' if any(r.get('status')=='UNREVIEWED_PROPOSAL' for r in records) else 'NO_VALID_MODEL_RESPONSES') if output.get('actualModelRequested') else 'SIMULATED_ONLY',
        'n':len(results),'correct':accuracy,'accuracy':round(accuracy/max(len(results),1),3),
        'falsePositiveExpertQuestions':pos_false,'missedExpertQuestions':pos_missed,
        'confusion':[{'expected':e,'predicted':p,'n':n} for (e,p),n in sorted(confusion.items())],
        'cases':results,'all25Completed':len(records)==25,'reviewed':False,'assetUpdates':0}
if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: python3 score.py <unreviewed-results.json>')
    file=pathlib.Path(sys.argv[1]); output=json.loads(file.read_text(encoding='utf-8'))
    result=evaluate(output)
    summary=file.with_suffix('.score.json');summary.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='cases'},ensure_ascii=False,indent=2))
    print('Score saved:',summary)
