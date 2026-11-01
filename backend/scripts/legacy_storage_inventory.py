"""Read-only SQLite discovery: names and row counts ONLY; excludes payload contents.

The inventory isn't a data migration and cannot prove who owns records.
"""
import argparse
import sqlite3
from pathlib import Path


def inventory(root):
    root = Path(root).resolve()
    files = [p for p in root.rglob('*') if p.is_file() and
             p.suffix.lower() in {'.sqlite', '.sqlite3', '.db'} and
             not any(part in {'.git', 'node_modules', '.next'} for part in p.parts)]
    report = []
    for p in sorted(files):
        info = {'path': p.relative_to(root).as_posix(), 'size_bytes': p.stat().st_size, 'tables': []}
        try:
            # SQLite file URI mode=ro; no PRAGMA changes, no writes.
            uri = f'{p.as_uri()}?mode=ro'
            with sqlite3.connect(uri, uri=True, timeout=2) as conn:
                names = [r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )]
                for name in names:
                    escaped = '"' + name.replace('"', '""') + '"'
                    count = conn.execute(f'SELECT COUNT(*) FROM {escaped}').fetchone()[0]
                    info['tables'].append({'name': name, 'rows': count})
        except (sqlite3.Error, OSError) as exc:
            # No file contents or sqlite SQL in logs.
            info['error'] = type(exc).__name__
        report.append(info)
    return report


def main():
    parser = argparse.ArgumentParser(description='Read-only inventory. Reports NO record values or PII.')
    parser.add_argument('root', help='Source project directory')
    args = parser.parse_args()
    for item in inventory(args.root):
        print(f"DB: {item['path']} ({item['size_bytes']} bytes)")
        if 'error' in item:
            print('  unreadable:', item['error'])
        else:
            for table in item['tables']:
                print(f"  table {table['name']}: {table['rows']} rows")
    print('NOTE: Only existing DB files were scanned. Runtime-generated DBs are not included.')


if __name__ == '__main__':
    main()
