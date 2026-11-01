#!/usr/bin/env python3
"""Fail-closed basic source hygiene; NOT a substitute for legal/security review."""
from pathlib import Path
import re, sys
root=Path(__file__).resolve().parents[1]
forbidden={'.env','.env.local','.env.production','.env.development','id_rsa','id_ed25519'}
blocked={'.db','.sqlite','.sqlite3','.pem','.p12','.pfx','.key','.dump','.bak'}
patterns=[re.compile(r'\b(?:sk-[A-Za-z0-9_-]{24,}|AKIA[A-Z0-9]{16}|LTAI[0-9A-Za-z]{12,})\b'),
          re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]
violations=[]
for p in root.rglob('*'):
    if not p.is_file() or '.git' in p.parts: continue
    rel=p.relative_to(root).as_posix()
    if p.name in forbidden or p.suffix.lower() in blocked or p.name.startswith('.env.') and p.name!='.env.example':
        violations.append(rel+': forbidden file type'); continue
    if p.stat().st_size>2_000_000: continue
    if p.suffix.lower() not in {'.py','.ts','.tsx','.mjs','.js','.json','.yml','.yaml','.md','.html','.css','.txt','.example','.env','.sh','.toml'}: continue
    try: text=p.read_text(encoding='utf-8')
    except UnicodeDecodeError: continue
    if any(pattern.search(text) for pattern in patterns): violations.append(rel+': possible secret (review immediately)')
if violations:
    print('STOP: publication hygiene failed.\n'+'\n'.join(violations));sys.exit(1)
print('PASS: no obvious secret pattern or forbidden file types detected.')
print('NOTICE: source licenses, copyrighted medical content, full git history and real tenant data still REQUIRE MANUAL REVIEW. Default to PRIVATE repository.')
