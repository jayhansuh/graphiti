# S3 Backup System Implementation

## Overview
Implemented a comprehensive backup and restore system for Graphiti with AWS S3 storage, automated backups, real-time sync capability, and deletion protection.

### Backup Strategies Available:
1. **Daily Scheduled Backups** - Traditional daily backups at 2 AM UTC
2. **Minute-by-Minute Backups** - Using systemd timer for near real-time sync (recommended)
3. **Real-time Incremental Backups** - Built-in BackupWorker for continuous tracking (experimental)
4. **Manual Backups** - On-demand backups via API or CLI

For production use, the **minute-by-minute backup strategy** using systemd timer is recommended as it provides reliable near real-time synchronization without the complexity of incremental backups.

## Features Implemented

### 1. Core Backup Functionality
- **S3BackupService**: Async S3 operations with compression and metadata
- **Neo4jExporter**: Export all nodes, relationships, and statistics
- **PostgresExporter**: Export user auth data with token masking
- **RestoreService**: Full or selective restore with data integrity

### 2. Deletion Protection
- Files with `_` prefix are protected from automatic deletion
- Excluded from S3 lifecycle policies
- Cannot be deleted via API endpoints
- Automatic backup before any deletion operation

### 3. REST API Endpoints
- `POST /backup/create` - Create manual backup
- `GET /backup/list` - List available backups  
- `POST /backup/restore` - Restore from backup
- `DELETE /backup/{key}` - Delete backup (protected files excluded)

### 4. Automated Backups
- Systemd timer for daily backups at 2 AM UTC
- Optional frequent backup timer (every minute) for near real-time sync
- Configurable retention: 30 days (manual), 90 days (scheduled)
- Protected deletion backups retained indefinitely

### 5. Real-time Backup System
- BackupWorker class for continuous incremental backups
- Tracks all data changes (creates, updates, deletes)
- Configurable sync interval (default: 60 seconds)
- Monitoring endpoints for backup status and force sync
- Integrated with ingest endpoints for automatic change tracking

### 6. Operational Features
- Startup restoration from latest backup (optional)
- Comprehensive logging and monitoring
- End-to-end test suite
- Setup scripts for easy deployment

## Configuration

Add to `.env`:
```bash
# S3 Configuration
S3_BACKUP_BUCKET=graphiti-backups
AWS_REGION=ap-northeast-3
AWS_ACCESS_KEY_ID=your-key  # Optional with IAM role
AWS_SECRET_ACCESS_KEY=your-secret  # Optional with IAM role

# Optional startup restore
RESTORE_FROM_S3_ON_STARTUP=false

# Real-time backup configuration
ENABLE_CONTINUOUS_BACKUP=true
BACKUP_SYNC_INTERVAL=60  # seconds
ENABLE_FULL_BACKUP=true
FULL_BACKUP_INTERVAL=3600  # 1 hour
```

## Setup Instructions

1. Install systemd timer for daily backups:
   ```bash
   ./scripts/setup_backup_timer.sh
   ```

2. For minute-by-minute backups (near real-time sync):
   ```bash
   sudo cp systemd/graphiti-backup-frequent.timer /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable graphiti-backup-frequent.timer
   sudo systemctl start graphiti-backup-frequent.timer
   ```

3. Test backup functionality:
   ```bash
   python tests/test_backup_restore.py
   ```

4. Manual backup:
   ```bash
   python scripts/backup_to_s3.py
   ```

5. Monitor backup status via API:
   ```bash
   curl http://localhost:8002/backup/status -H "X-API-Key: your-api-key"
   curl -X POST http://localhost:8002/backup/force-sync -H "X-API-Key: your-api-key"
   ```

## Security Considerations
- All credentials loaded from environment variables
- OAuth tokens masked in backups
- IAM roles preferred over API keys
- Compression reduces storage costs

## Files Added/Modified
- `server/graph_service/backup/` - Core backup module
  - `s3_service.py` - S3 operations
  - `neo4j_export.py` - Neo4j data export
  - `postgres_export.py` - PostgreSQL data export
  - `restore_service.py` - Restoration logic
  - `backup_worker.py` - Real-time backup worker
- `server/graph_service/routers/backup.py` - API endpoints with monitoring
- `server/graph_service/routers/ingest.py` - Added change tracking
- `server/scripts/` - Backup and setup scripts
- `server/systemd/` - Service and timer files
  - `graphiti-backup.service` - Backup service
  - `graphiti-backup.timer` - Daily backup timer
  - `graphiti-backup-frequent.timer` - Minute-by-minute timer
- `server/tests/test_backup_restore.py` - Test suite
- `server/pyproject.toml` - Added boto3/aioboto3 dependencies
- `server/graph_service/main.py` - Integrated backup router, worker, and startup restore