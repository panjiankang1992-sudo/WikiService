# Backup Configuration for WikiService

# ==================== Backup Strategy ====================
# - PostgreSQL: Daily full backup + WAL archiving
# - Neo4j: Daily dump
# - WeKnora Storage: Incremental backup
# - Retention: 7 daily, 4 weekly, 12 monthly

# ==================== Environment Variables ====================
# BACKUP_DIR: /data/backups
# S3_BUCKET: weknora-backups (optional, for remote storage)
# S3_ACCESS_KEY: your_access_key
# S3_SECRET_KEY: your_secret_key

# ==================== PostgreSQL Backup Script ====================

cat > /backup/backup-postgres.sh << 'EOF'
#!/bin/bash
set -e

BACKUP_DIR="/data/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7

mkdir -p "$BACKUP_DIR"

# Full backup
echo "[$(date)] Starting PostgreSQL backup..."
pg_dump -h postgres -U weknora -d weknora -F c -f "$BACKUP_DIR/weknora_$DATE.dump"

# Compress backup
gzip "$BACKUP_DIR/weknora_$DATE.dump"

# Cleanup old backups
find "$BACKUP_DIR" -name "*.dump.gz" -mtime +$RETENTION_DAYS -delete

# Upload to S3 (optional)
if [ -n "$S3_BUCKET" ]; then
    aws s3 cp "$BACKUP_DIR/weknora_$DATE.dump.gz" "s3://$S3_BUCKET/postgres/"
fi

echo "[$(date)] PostgreSQL backup completed: weknora_$DATE.dump.gz"
EOF

chmod +x /backup/backup-postgres.sh

# ==================== Neo4j Backup Script ====================

cat > /backup/backup-neo4j.sh << 'EOF'
#!/bin/bash
set -e

BACKUP_DIR="/data/backups/neo4j"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7

mkdir -p "$BACKUP_DIR"

# Neo4j dump using neo4j-admin
echo "[$(date)] Starting Neo4j backup..."
docker exec weknora-neo4j neo4j-admin dump --database=neo4j --to-path=/var/lib/neo4j/backups

# Copy backup from container
docker cp weknora-neo4j:/var/lib/neo4j/backups/neo4j.dump "$BACKUP_DIR/neo4j_$DATE.dump"

# Compress backup
gzip "$BACKUP_DIR/neo4j_$DATE.dump"

# Cleanup old backups
find "$BACKUP_DIR" -name "*.dump.gz" -mtime +$RETENTION_DAYS -delete

# Upload to S3 (optional)
if [ -n "$S3_BUCKET" ]; then
    aws s3 cp "$BACKUP_DIR/neo4j_$DATE.dump.gz" "s3://$S3_BUCKET/neo4j/"
fi

echo "[$(date)] Neo4j backup completed: neo4j_$DATE.dump.gz"
EOF

chmod +x /backup/backup-neo4j.sh

# ==================== WeKnora Storage Backup ====================

cat > /backup/backup-storage.sh << 'EOF'
#!/bin/bash
set -e

BACKUP_DIR="/data/backups/storage"
SOURCE_DIR="/data/storage"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7

mkdir -p "$BACKUP_DIR"

# Incremental backup using rsync
echo "[$(date)] Starting storage backup..."
rsync -av --delete "$SOURCE_DIR/" "$BACKUP_DIR/latest/"

# Create compressed archive
tar -czf "$BACKUP_DIR/storage_$DATE.tar.gz" -C "$BACKUP_DIR/latest" .

# Cleanup old backups
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

# Upload to S3 (optional)
if [ -n "$S3_BUCKET" ]; then
    aws s3 cp "$BACKUP_DIR/storage_$DATE.tar.gz" "s3://$S3_BUCKET/storage/"
fi

echo "[$(date)] Storage backup completed: storage_$DATE.tar.gz"
EOF

chmod +x /backup/backup-storage.sh

# ==================== Cron Schedule ====================
# Add to crontab:

# PostgreSQL backup - daily at 2:00 AM
0 2 * * * /backup/backup-postgres.sh >> /var/log/backup-postgres.log 2>&1

# Neo4j backup - daily at 2:30 AM
30 2 * * * /backup/backup-neo4j.sh >> /var/log/backup-neo4j.log 2>&1

# Storage backup - daily at 3:00 AM
0 3 * * * /backup/backup-storage.sh >> /var/log/backup-storage.log 2>&1

# Weekly full backup - Sunday at 4:00 AM
0 4 * * 0 /backup/backup-all.sh >> /var/log/backup-weekly.log 2>&1

# ==================== Restore Scripts ====================

cat > /backup/restore-postgres.sh << 'EOF'
#!/bin/bash
# Usage: restore-postgres.sh <backup_file.dump.gz>

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: restore-postgres.sh <backup_file.dump.gz>"
    exit 1
fi

# Decompress if needed
if [[ "$BACKUP_FILE" == *.gz ]]; then
    gunzip -c "$BACKUP_FILE" > /tmp/weknora_restore.dump
    BACKUP_FILE="/tmp/weknora_restore.dump"
fi

# Restore
pg_restore -h postgres -U weknora -d weknora -c --if-exists "$BACKUP_FILE"

echo "PostgreSQL restore completed."
EOF

chmod +x /backup/restore-postgres.sh

# ==================== Backup Verification ====================
# Run restore test monthly
0 5 1 * * /backup/verify-restore.sh >> /var/log/backup-verify.log 2>&1
