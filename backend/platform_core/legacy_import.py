"""Offline, explicitly approved import of legacy *record ownership metadata*.

Never loads source SQLite patient/medical payloads and never guesses owners.
All rows are validated before writing; --apply is an atomic transaction.
"""
import argparse
import csv
import hashlib
import io
import re
from pathlib import Path
from uuid import UUID

from sqlalchemy import and_, insert, select

from .db import (audit, ensure_schema, engine_for, import_batches, import_evidence,
                 record_links, users)
from .records import BUSINESS_MODULES, KIND_RE, REF_RE
from .security import new_id, now
from .config import load_settings

FIELDS = ('source_module', 'object_kind', 'external_ref', 'owner_user_id', 'evidence_ref')
APPROVAL_RE = re.compile(r'^[A-Za-z0-9_.:/#-]{6,128}$')
EVIDENCE_RE = re.compile(r'^[A-Za-z0-9_.:/#-]{6,128}$')
MAX_MANIFEST_SIZE = 2 * 1024 * 1024
MAX_ROWS = 10000


class ImportRejected(ValueError):
    pass


def read_manifest(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_MANIFEST_SIZE:
        raise ImportRejected('Manifest absent or larger than 2 MiB')
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        contents = raw.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(contents, newline=''), strict=True)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ImportRejected('Incorrect CSV header or column order')
        records, seen = [], set()
        for row in reader:
            if len(records) >= MAX_ROWS:
                raise ImportRejected('More than 10000 rows')
            if None in row or any(value is None for value in row.values()):
                raise ImportRejected('Missing field or unexpected column')
            module, kind, ref, owner, evidence = [row[f].strip() for f in FIELDS]
            if module not in BUSINESS_MODULES or not KIND_RE.fullmatch(kind) or not REF_RE.fullmatch(ref):
                raise ImportRejected('Invalid module or business identifier')
            try:
                owner = str(UUID(owner))
            except (ValueError, AttributeError):
                raise ImportRejected('Invalid owner UUID') from None
            if not EVIDENCE_RE.fullmatch(evidence):
                raise ImportRejected('Each row needs an opaque, non-PII evidence reference')
            key = module, kind, ref
            if key in seen:
                raise ImportRejected('Duplicate business identifier in manifest')
            seen.add(key)
            records.append((module, kind, ref, owner, evidence))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ImportRejected('Manifest must be valid UTF-8 CSV') from exc
    if not records:
        raise ImportRejected('Empty manifest')
    return digest, records


def process_manifest(engine, tenant_id, manifest, approved_by, approval_reference,
                     *, apply=False, confirm_digest=None):
    if not APPROVAL_RE.fullmatch(approval_reference):
        raise ImportRejected('A non-PII approval ticket reference is required')
    approved_by = str(UUID(approved_by))
    digest, entries = read_manifest(manifest)
    if apply and confirm_digest != digest:
        raise ImportRejected('Apply requires the exact SHA256 digest displayed by the dry run')

    # Transaction spans validation + every insert; failures roll back entire batch.
    with engine.begin() as conn:
        admin = conn.execute(select(users.c.id).where(
            users.c.id == approved_by, users.c.tenant_id == tenant_id,
            users.c.role == 'admin', users.c.status == 'active',
        )).scalar_one_or_none()
        if admin is None:
            raise ImportRejected('Approver must be an active platform admin in this tenant')
        old_batch = conn.execute(select(import_batches).where(
            import_batches.c.tenant_id == tenant_id,
            import_batches.c.manifest_sha256 == digest,
        )).mappings().first()
        if old_batch is not None:
            if old_batch['approved_by_user_id'] != approved_by or old_batch['approval_reference'] != approval_reference:
                raise ImportRejected('Same manifest has different approval metadata')
            return {'sha256': digest, 'rows': len(entries), 'already_imported': True, 'applied': False}

        owners = {row[3] for row in entries}
        found = set(conn.execute(select(users.c.id).where(
            users.c.tenant_id == tenant_id, users.c.id.in_(owners), users.c.status == 'active',
        )).scalars())
        if found != owners:
            raise ImportRejected('Unknown, disabled or out-of-tenant owner: no rows imported')

        existing_links = {}
        for module, kind, ref, owner, evidence in entries:
            record = conn.execute(select(record_links).where(and_(
                record_links.c.tenant_id == tenant_id,
                record_links.c.source_module == module,
                record_links.c.object_kind == kind,
                record_links.c.external_ref == ref,
            ))).mappings().first()
            if record is not None:
                if record['owner_user_id'] != owner:
                    raise ImportRejected('Conflicting existing record owner: no rows imported')
                prior_evidence = conn.execute(select(import_evidence.c.record_link_id).where(
                    import_evidence.c.record_link_id == record['id'],
                )).scalar_one_or_none()
                if prior_evidence:
                    raise ImportRejected('One record already imported with other provenance')
                existing_links[(module, kind, ref)] = record['id']

        if apply:
            timestamp, batch_id = now(), new_id()
            conn.execute(insert(import_batches).values(
                id=batch_id, tenant_id=tenant_id, manifest_sha256=digest,
                approval_reference=approval_reference, approved_by_user_id=approved_by,
                record_count=len(entries), created_at=timestamp,
            ))
            for module, kind, ref, owner, evidence in entries:
                link_id = existing_links.get((module, kind, ref))
                if link_id is None:
                    link_id = new_id()
                    conn.execute(insert(record_links).values(
                        id=link_id, tenant_id=tenant_id, owner_user_id=owner,
                        source_module=module, object_kind=kind, external_ref=ref,
                        created_at=timestamp,
                    ))
                conn.execute(insert(import_evidence).values(
                    record_link_id=link_id, batch_id=batch_id, evidence_ref=evidence,
                    imported_at=timestamp,
                ))
            conn.execute(insert(audit).values(
                id=new_id(), actor_user_id=approved_by,
                action='legacy.import', target_id=batch_id, created_at=timestamp,
            ))
    return {'sha256': digest, 'rows': len(entries), 'already_imported': False, 'applied': bool(apply),
            'reused_links': len(existing_links)}


def main():
    parser = argparse.ArgumentParser(description='Dry-run by default; approved ownership metadata ONLY.')
    parser.add_argument('--manifest', required=True, help='Reviewed UTF-8 CSV; never upload PHI or real customer data')
    parser.add_argument('--approved-by', required=True, help='Active platform admin UUID')
    parser.add_argument('--approval-reference', required=True, help='Opaque change ticket (no personal data)')
    parser.add_argument('--apply', action='store_true', help='Commit all rows atomically')
    parser.add_argument('--confirm-digest', default='', help='Full SHA256 from dry-run required for --apply')
    args = parser.parse_args()
    settings = load_settings()
    engine = engine_for(settings.database_url)
    try:
        ensure_schema(engine)
        result = process_manifest(engine, settings.tenant_id, args.manifest, args.approved_by,
                                  args.approval_reference, apply=args.apply,
                                  confirm_digest=args.confirm_digest)
    except (ImportRejected, ValueError) as exc:
        parser.exit(2, f'IMPORT REJECTED: {exc}\n')
    print(f"status={'applied' if result['applied'] else 'no change'} rows={result['rows']} "
          f"sha256={result['sha256']} existing={result['already_imported']}")


if __name__ == '__main__':
    main()
