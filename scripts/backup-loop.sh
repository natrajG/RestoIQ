#!/bin/sh
# Nightly pg_dump (custom format) with retention. Runs inside the backup container.
set -eu
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
HOUR="${BACKUP_HOUR_UTC:-21}"   # 21:00 UTC = 02:30 IST
mkdir -p /backups
dump() {
  f="/backups/restoiq-$(date -u +%Y%m%d-%H%M%S).dump"
  if pg_dump -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f "$f.tmp"; then
    mv "$f.tmp" "$f"; echo "backup ok: $f ($(du -h "$f" | cut -f1))"
  else
    rm -f "$f.tmp"; echo "BACKUP FAILED" >&2
  fi
  find /backups -name 'restoiq-*.dump' -mtime +"$KEEP_DAYS" -delete
}
[ "${BACKUP_ON_START:-1}" = "1" ] && dump
while true; do
  now=$(date -u +%s); next=$(date -u -d "$(date -u +%Y-%m-%d) $HOUR:00:00" +%s 2>/dev/null || echo $((now+86400)))
  [ "$next" -le "$now" ] && next=$((next+86400))
  sleep $((next-now)); dump
done
