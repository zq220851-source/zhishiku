#!/usr/bin/env bash
# Creates an encrypted-at-rest? No: dump is PRIVATE but not encrypted.
# Backups must be encrypted when sent off-site, and restore-drilled separately.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
umask 077
mkdir -p backup
stamp="$(date -u '+%Y%m%dT%H%M%SZ')"
out="backup/platform-${stamp}.dump"
# File existence is checked to prevent an empty 'successful' backup.
docker compose exec -T db sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$out"
test -s "$out"
docker compose exec -T db pg_restore --list < "$out" >/dev/null
sha256sum "$out" > "${out}.sha256"
echo "Backup created: $out (verify restore separately; no off-site copy performed)"
