"""Package source reproducibly, excluding local credentials, state and dependencies."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'node_modules', '.venv', '.next', '__pycache__', '.pytest_cache', '.git', '.cache',
            'runtime', 'test-results', '.data', 'dist', 'build', '.medrep_patch_backups', '.mypy_cache', '.ruff_cache'}
CLINICAL_DB = 'business_module1_reference/reference/coach/clinical/medrep-innovent-clinical-knowledge-v0.5/medrep_clinical_knowledge_v0.5.sqlite'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        raise SystemExit('Output directory must be outside the source tree')
    output.mkdir(parents=True, exist_ok=True)
    secrets = []
    env = ROOT / '.env.local'
    if env.exists():
        for line in env.read_text().splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                value = value.strip().strip('"').strip("'")
                if any(word in key.upper() for word in ('KEY', 'SECRET', 'PASSWORD')) and len(value) >= 12:
                    secrets.append(value.encode())
    account = ROOT / 'runtime/local-account.json'
    if account.exists():
        secrets.append(json.loads(account.read_text())['password'].encode())
    files = []
    for path in sorted(ROOT.rglob('*')):
        rel = path.relative_to(ROOT)
        if not path.is_file() or path.is_symlink() or any(p in EXCLUDED for p in rel.parts):
            continue
        if path.name in ('本机体验说明.txt', '.DS_Store') or (path.name.startswith('.env') and not path.name.endswith('.example')):
            continue
        if path.suffix in ('.pyc', '.log', '.key', '.pem', '.tsbuildinfo') or path.name.endswith(('-wal', '-shm')):
            continue
        if path.suffix in ('.db', '.sqlite', '.sqlite3') and rel.as_posix() != CLINICAL_DB:
            continue
        data = path.read_bytes()
        if any(secret in data for secret in secrets):
            raise SystemExit('Credential scan rejected: ' + rel.as_posix())
        files.append((rel, data))
    archive = output / 'MedRepCoach_接续开发版_20261101.zip'
    temporary = archive.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel, data in files:
            info = zipfile.ZipInfo('MedRepCoach/' + rel.as_posix(), date_time=(2026, 11, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, data)
    with zipfile.ZipFile(temporary) as z:
        if z.testzip() is not None:
            raise SystemExit('Archive verification failed')
    temporary.replace(archive)
    (output / 'SHA256.txt').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')
    (output / '本轮实现与验收.txt').write_text((ROOT / 'docs/06_本轮实现与验收.md').read_text())
    print(json.dumps({'archive': str(archive), 'files': len(files), 'bytes': archive.stat().st_size,
                      'credential_scan': 'passed', 'archive_integrity': 'passed'}, ensure_ascii=False))

if __name__ == '__main__':
    main()
