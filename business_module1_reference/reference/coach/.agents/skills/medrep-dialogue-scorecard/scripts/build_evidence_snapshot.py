#!/usr/bin/env python3
"""Export a portable provenance index; does not include full book or PDF text."""
import argparse
import json
import sqlite3
from pathlib import Path

def snapshot(db_path):
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    records = {}
    for row in db.execute('''SELECT p.*, d.title, d.issuer, d.edition, d.url,
        d.source_level, d.layer, d.authority_scope
        FROM external_reference_points p JOIN external_reference_documents d USING(document_id)'''):
        r = dict(row)
        records[r['point_id']] = {k: r[k] for k in (
            'document_id','title','issuer','edition','url','source_level','layer',
            'authority_scope','locator','summary','fingerprint','review_status','usage_scope')}
    for row in db.execute('''SELECT p.*, d.title, d.authors, d.published_year,
        d.publisher, d.file_sha256, d.source_level, d.layer, d.usage_note
        FROM local_book_points p JOIN local_book_documents d USING(book_id)'''):
        r = dict(row)
        records[r['point_id']] = {k: r[k] for k in (
            'book_id','title','authors','published_year','publisher','file_sha256',
            'source_level','layer','usage_note','locator','summary','fingerprint',
            'review_status','usage_scope')}
    # The clinical inventory and project-course examples are only locators, not approved claims.
    for row in db.execute('SELECT item_id, prompt, source_id, review_status FROM competency_items'):
        if row['item_id'] == 'CLN-0001':
            records[row['item_id']] = dict(row) | {'locator': 'competency_items.item_id=CLN-0001', 'source_level': 'project_clinical_candidate'}
    for path in ['course-specs/D-RCC.json']:
        records[path] = {'locator': path, 'source_level': 'project_course_candidate',
                         'review_status': 'pending_human_review',
                         'summary': '对话情境中的回答顺序、证据边界和未知核实'}
    return {'schema_version': 1, 'purpose': 'candidate_evidence_only', 'records': records}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot(args.db), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {out}')

if __name__ == '__main__':
    main()
