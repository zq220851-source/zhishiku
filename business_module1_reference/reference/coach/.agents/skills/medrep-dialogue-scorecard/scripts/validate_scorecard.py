#!/usr/bin/env python3
"""Check traceability and structure; not substantive medical or compliance approval."""
import argparse
import json
from pathlib import Path

def validate(scorecard, evidence):
    errors = []
    refs = evidence.get('records', {})
    if scorecard.get('official_innovent_scorecard') is not False:
        errors.append('Must explicitly state this is not an official Innovent scorecard')
    if scorecard.get('status') != 'prototype_pending_training_medical_and_compliance_review':
        errors.append('Missing prototype review status')
    dims = scorecard.get('dimensions', [])
    if not dims or len({d.get('id') for d in dims}) != len(dims):
        errors.append('Dimensions missing or IDs duplicate')
    for item in dims + scorecard.get('hard_gates', []):
        name = item.get('id', '<missing id>')
        source_ids = item.get('source_ids', [])
        if not source_ids:
            errors.append(f'{name}: no source IDs')
        for sid in source_ids:
            if sid not in refs:
                errors.append(f'{name}: unresolved source {sid}')
            elif not refs[sid].get('locator'):
                errors.append(f'{name}: no precise locator for {sid}')
        if item in dims:
            if set(item.get('anchors', {})) != {'0', '1', '2'}:
                errors.append(f'{name}: anchors must be 0/1/2')
            if not item.get('trigger') or not item.get('design_note'):
                errors.append(f'{name}: trigger or design explanation missing')
    if 'NA' not in scorecard.get('scale', {}):
        errors.append('NA rule missing')
    if '不设总分' not in scorecard.get('aggregation', ''):
        errors.append('Unapproved aggregate score present')
    return errors

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scorecard', required=True)
    ap.add_argument('--evidence', required=True)
    args = ap.parse_args()
    scorecard = json.loads(Path(args.scorecard).read_text(encoding='utf-8'))
    evidence = json.loads(Path(args.evidence).read_text(encoding='utf-8'))
    errors = validate(scorecard, evidence)
    if errors:
        for error in errors:
            print('ERROR:', error)
        raise SystemExit(1)
    print(f"Valid: {len(scorecard['dimensions'])} dimensions, {len(evidence['records'])} source records")

if __name__ == '__main__':
    main()
