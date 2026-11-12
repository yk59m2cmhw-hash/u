#!/usr/bin/env bash
# Daily backup of Okno data (leads and knowledge base). Keeps 14 days.
# The archive contains personal data: keep backups on servers in the same country and encrypt them
# (set OKNO_BACKUP_PASSPHRASE to encrypt with gpg). Cron example:
#   15 3 * * * cd /opt/okno && ./deploy/backup.sh >> backups/backup.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
stamp=$(date +%F)
archive="backups/okno-$stamp.tar.gz"
tar czf "$archive" data/
if [ -n "${OKNO_BACKUP_PASSPHRASE:-}" ]; then
  gpg --batch --yes --symmetric --cipher-algo AES256 --passphrase "$OKNO_BACKUP_PASSPHRASE" -o "$archive.gpg" "$archive"
  rm -f "$archive"
fi
find backups -name 'okno-*.tar.gz*' -mtime +14 -delete
echo "backup done: $stamp"
