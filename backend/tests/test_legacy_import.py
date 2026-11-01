import csv
import hashlib
from pathlib import Path

import pytest
from sqlalchemy import select, insert

from platform_core.db import (audit, import_batches, import_evidence, record_links, users)
from platform_core.legacy_import import ImportRejected, process_manifest, read_manifest
from platform_core.security import now

ALICE = '11111111-1111-4111-8111-111111111111'
BOB = '22222222-2222-4222-8222-222222222222'
ADMIN = '44444444-4444-4444-8444-444444444444'
DISABLED = '33333333-3333-4333-8333-333333333333'
FIELDS = ['source_module', 'object_kind', 'external_ref', 'owner_user_id', 'evidence_ref']
APPROVAL = 'CHANGE-2026-1042'


def manifest(tmp_path, rows):
    p = tmp_path / 'reviewed_ownership.csv'
    with p.open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return p


def row(ref='s01', owner=ALICE, evidence='REVIEW-CASE-1001', module='coach'):
    return dict(source_module=module, object_kind='session', external_ref=ref,
                owner_user_id=owner, evidence_ref=evidence)


def run(engine, path, **kw):
    return process_manifest(engine, 'test-team', path, kw.pop('approved_by', ADMIN),
                            kw.pop('approval_reference', APPROVAL), **kw)


def test_dry_run_no_write_and_commit_with_digest(environment, tmp_path):
    _, engine = environment
    path = manifest(tmp_path, [row(), row('s02', BOB, 'REVIEW-CASE-1002')])
    result = run(engine, path)
    assert result['rows'] == 2 and not result['applied']
    with engine.connect() as conn:
        assert conn.execute(select(record_links.c.id)).all() == []
    with pytest.raises(ImportRejected, match='SHA256'):
        run(engine, path, apply=True, confirm_digest='0'*64)
    result = run(engine, path, apply=True, confirm_digest=result['sha256'])
    assert result['applied'] is True
    with engine.connect() as conn:
        assert len(conn.execute(select(record_links)).all()) == 2
        assert len(conn.execute(select(import_evidence)).all()) == 2
        assert len(conn.execute(select(import_batches)).all()) == 1
        assert len(conn.execute(select(audit).where(audit.c.action == 'legacy.import')).all()) == 1
    result = run(engine, path, apply=True, confirm_digest=result['sha256'])
    assert result['already_imported'] and not result['applied']


def test_unknown_disabled_or_cross_tenant_owner_atomic(environment, tmp_path):
    _, engine = environment
    with engine.begin() as conn:
        conn.execute(insert(users).values(id='55555555-5555-4555-8555-555555555555',
            tenant_id='other',feishu_open_id='ou_other',display_name='Other',
            role='employee',status='active',created_at=now(),updated_at=now()))
    for bad in [DISABLED, '55555555-5555-4555-8555-555555555555',
                '66666666-6666-4666-8666-666666666666']:
        path = manifest(tmp_path, [row(),row('s02', bad, 'REVIEW-CASE-1002')])
        with pytest.raises(ImportRejected, match='Unknown'):
            run(engine, path, apply=True, confirm_digest=read_manifest(path)[0])
    with engine.connect() as conn:
        assert conn.execute(select(record_links)).all() == []
        assert conn.execute(select(import_batches)).all() == []


def test_conflicting_owner_fail_all(environment, tmp_path):
    _, engine = environment
    path = manifest(tmp_path, [row()])
    run(engine, path, apply=True, confirm_digest=read_manifest(path)[0])
    collision = manifest(tmp_path, [row('s99'), row('s01', BOB, 'REVIEW-CASE-1003')])
    with pytest.raises(ImportRejected, match='Conflicting'):
        run(engine, collision, apply=True, confirm_digest=read_manifest(collision)[0])
    with engine.connect() as conn:
        assert len(conn.execute(select(record_links)).all()) == 1


def test_approval_enforced(environment, tmp_path):
    _, engine = environment
    p = manifest(tmp_path, [row()])
    for other in [ALICE, BOB, DISABLED]:
        with pytest.raises(ImportRejected, match='Approver'):
            run(engine, p, approved_by=other)
    with pytest.raises(ImportRejected, match='approval ticket'):
        run(engine, p, approval_reference='bad')
    result = run(engine, p, apply=True, confirm_digest=read_manifest(p)[0])
    assert result['applied']
    with pytest.raises(ImportRejected, match='different approval'):
        run(engine, p, approval_reference='CHANGE-2026-9999')


def test_manifest_strict_schema_and_no_guessing(environment, tmp_path):
    _, engine = environment
    for entries in [[row('s01', evidence='')], [row('s01', evidence='alice@example.com')],
                    [row('s01'), row('s01')], [row('s01', owner='Alice')],
                    [row('with/slash')], [row(module='unknown')]]:
        p = manifest(tmp_path, entries)
        with pytest.raises(ImportRejected):
            run(engine, p)
    p = manifest(tmp_path, [row()])
    p.write_text('unknown,headers\n1,2\n')
    with pytest.raises(ImportRejected, match='header'):
        run(engine, p)


def test_existing_link_can_be_annotated_not_reassigned(environment, tmp_path):
    _, engine = environment
    with engine.begin() as conn:
        conn.execute(insert(record_links).values(
            id='77777777-7777-4777-8777-777777777777', tenant_id='test-team',
            owner_user_id=ALICE, source_module='coach', object_kind='session',
            external_ref='s01', created_at=now(),
        ))
    p = manifest(tmp_path, [row()])
    result = run(engine, p, apply=True, confirm_digest=read_manifest(p)[0])
    assert result['reused_links'] == 1
    with engine.connect() as conn:
        assert len(conn.execute(select(record_links)).all()) == 1
        assert len(conn.execute(select(import_evidence)).all()) == 1
    again = manifest(tmp_path, [row(evidence='REVIEW-CASE-9999')])
    with pytest.raises(ImportRejected, match='other provenance'):
        run(engine, again)


def test_manifest_digest_changes_with_bytes(tmp_path):
    p = manifest(tmp_path, [row()])
    first = read_manifest(p)[0]
    assert first == hashlib.sha256(p.read_bytes()).hexdigest()
    p.write_bytes(p.read_bytes() + b'\n')
    assert first != read_manifest(p)[0]
