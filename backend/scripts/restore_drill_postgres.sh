#!/usr/bin/env bash
# Restore one backup into a RANDOM disposable PostgreSQL database, never production.
# This only checks DB backup viability; it DOES NOT test business modules or offsite storage.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
umask 077
if [[ $# -ne 1 ]]; then echo "Usage: $0 backup/platform-YYYYMMDDTHHMMSSZ.dump" >&2; exit 2; fi
backup="$1"
if [[ ! -s "$backup" || ! -f "${backup}.sha256" ]]; then echo 'Backup or digest file missing' >&2; exit 2; fi
sha256sum -c "${backup}.sha256"
# Use fixed-character generated name only; no user-controlled SQL interpolation.
drill="medrep_drill_$(date -u +%s)_$RANDOM"
cleanup() {
  docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --if-exists "$1"' sh "$drill" >/dev/null 2>&1 || true
}
trap cleanup EXIT
# pg_restore list checks that the compressed dump is a valid archive.
docker compose exec -T db pg_restore --list < "$backup" > /dev/null
docker compose exec -T db sh -c 'createdb -U "$POSTGRES_USER" "$1"' sh "$drill"
docker compose exec -T db sh -c 'exec pg_restore -U "$POSTGRES_USER" -d "$1" --exit-on-error --single-transaction' sh "$drill" < "$backup"
# Count includes schema tables from all platform phases; a successful empty DB is valid.
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$1" -v ON_ERROR_STOP=1 -tAc "SELECT version_num FROM alembic_version"' sh "$drill"
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$1" -v ON_ERROR_STOP=1 -tAc "SELECT count(*) FROM platform_users"' sh "$drill"
echo 'Restore drill PASSED in disposable DB; no production database was overwritten.'
