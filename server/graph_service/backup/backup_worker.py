"""Background worker for continuous incremental backups."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from enum import Enum
from collections import defaultdict

from pydantic import BaseModel, Field

from .s3_service import S3BackupService
from .neo4j_export import Neo4jExporter
from .postgres_export import PostgresExporter


logger = logging.getLogger(__name__)


class ChangeType(str, Enum):
    """Types of data changes."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class DataChange(BaseModel):
    """Represents a single data change."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    change_type: ChangeType
    entity_type: str  # 'node', 'edge', 'user'
    entity_id: str
    data: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BackupWorker:
    """Worker for continuous incremental backups."""
    
    def __init__(
        self,
        s3_service: S3BackupService,
        neo4j_config: Dict[str, str],
        postgres_config: Dict[str, str],
        sync_interval: int = 60,  # seconds
        enable_full_backup: bool = True,
        full_backup_interval: int = 3600,  # 1 hour
    ):
        self.s3_service = s3_service
        self.neo4j_config = neo4j_config
        self.postgres_config = postgres_config
        self.sync_interval = sync_interval
        self.enable_full_backup = enable_full_backup
        self.full_backup_interval = full_backup_interval
        
        # Change tracking
        self.change_queue: asyncio.Queue[DataChange] = asyncio.Queue()
        self.pending_changes: List[DataChange] = []
        
        # State tracking
        self.last_sync_time: Optional[datetime] = None
        self.last_full_backup_time: Optional[datetime] = None
        self.total_changes_synced = 0
        self.is_running = False
        
        # Tasks
        self.sync_task: Optional[asyncio.Task] = None
        self.full_backup_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start the backup worker."""
        if self.is_running:
            logger.warning("Backup worker is already running")
            return
            
        self.is_running = True
        
        # Start sync task
        self.sync_task = asyncio.create_task(self._sync_loop())
        logger.info(f"Started incremental backup sync (interval: {self.sync_interval}s)")
        
        # Start full backup task if enabled
        if self.enable_full_backup:
            self.full_backup_task = asyncio.create_task(self._full_backup_loop())
            logger.info(f"Started full backup task (interval: {self.full_backup_interval}s)")
            
    async def stop(self):
        """Stop the backup worker."""
        self.is_running = False
        
        # Cancel tasks
        if self.sync_task:
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass
                
        if self.full_backup_task:
            self.full_backup_task.cancel()
            try:
                await self.full_backup_task
            except asyncio.CancelledError:
                pass
                
        # Perform final sync
        if self.pending_changes or not self.change_queue.empty():
            logger.info("Performing final sync before shutdown...")
            await self._sync_changes()
            
        logger.info("Backup worker stopped")
        
    async def track_change(
        self,
        change_type: ChangeType,
        entity_type: str,
        entity_id: str,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Track a data change for backup."""
        change = DataChange(
            change_type=change_type,
            entity_type=entity_type,
            entity_id=entity_id,
            data=data,
            metadata=metadata or {},
        )
        
        await self.change_queue.put(change)
        logger.debug(f"Tracked {change_type} for {entity_type} {entity_id}")
        
    async def _sync_loop(self):
        """Main sync loop for incremental backups."""
        while self.is_running:
            try:
                await asyncio.sleep(self.sync_interval)
                await self._sync_changes()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in sync loop: {e}", exc_info=True)
                
    async def _sync_changes(self):
        """Sync pending changes to S3."""
        # Collect all pending changes
        while not self.change_queue.empty():
            try:
                change = self.change_queue.get_nowait()
                self.pending_changes.append(change)
            except asyncio.QueueEmpty:
                break
                
        if not self.pending_changes:
            return
            
        logger.info(f"Syncing {len(self.pending_changes)} changes to S3...")
        
        try:
            # Group changes by type and entity
            grouped_changes = self._group_changes(self.pending_changes)
            
            # Create incremental backup data
            backup_data = {
                'backup_type': 'incremental',
                'start_time': self.last_sync_time.isoformat() if self.last_sync_time else None,
                'end_time': datetime.now(timezone.utc).isoformat(),
                'change_count': len(self.pending_changes),
                'changes': grouped_changes,
            }
            
            # Upload to S3
            backup_key = await self.s3_service.upload_backup(
                data=backup_data,
                backup_type='incremental',
                description=f'Incremental backup with {len(self.pending_changes)} changes'
            )
            
            # Update state
            self.last_sync_time = datetime.now(timezone.utc)
            self.total_changes_synced += len(self.pending_changes)
            self.pending_changes.clear()
            
            logger.info(f"Successfully synced changes to S3: {backup_key}")
            
        except Exception as e:
            logger.error(f"Failed to sync changes: {e}", exc_info=True)
            # Keep changes for next sync attempt
            
    def _group_changes(self, changes: List[DataChange]) -> Dict[str, Any]:
        """Group changes by type and entity for efficient storage."""
        grouped = defaultdict(lambda: defaultdict(list))
        
        for change in changes:
            key = f"{change.entity_type}_{change.change_type.value}"
            grouped[key]['entities'].append({
                'id': change.entity_id,
                'timestamp': change.timestamp.isoformat(),
                'data': change.data,
                'metadata': change.metadata,
            })
            
        # Convert to regular dict for JSON serialization
        return dict(grouped)
        
    async def _full_backup_loop(self):
        """Periodic full backup loop."""
        while self.is_running:
            try:
                await asyncio.sleep(self.full_backup_interval)
                await self._create_full_backup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in full backup loop: {e}", exc_info=True)
                
    async def _create_full_backup(self):
        """Create a full backup."""
        logger.info("Creating periodic full backup...")
        
        try:
            backup_data = {
                'created_by': 'backup_worker',
                'neo4j': {},
                'postgres': {},
            }
            
            # Export Neo4j data
            neo4j_exporter = Neo4jExporter(
                uri=self.neo4j_config['uri'],
                username=self.neo4j_config['username'],
                password=self.neo4j_config['password'],
                database=self.neo4j_config.get('database', 'neo4j'),
            )
            
            neo4j_data = await neo4j_exporter.export_all_data()
            backup_data['neo4j'] = neo4j_data
            
            # Export PostgreSQL data (if not using SQLite)
            if 'sqlite' not in self.postgres_config['dsn']:
                postgres_exporter = PostgresExporter(dsn=self.postgres_config['dsn'])
                postgres_data = await postgres_exporter.export_all_data()
                backup_data['postgres'] = postgres_data
            
            # Upload to S3
            backup_key = await self.s3_service.upload_backup(
                data=backup_data,
                backup_type='scheduled',
                description='Periodic full backup by worker'
            )
            
            self.last_full_backup_time = datetime.now(timezone.utc)
            logger.info(f"Successfully created full backup: {backup_key}")
            
        except Exception as e:
            logger.error(f"Failed to create full backup: {e}", exc_info=True)
            
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the backup worker."""
        return {
            'is_running': self.is_running,
            'last_sync_time': self.last_sync_time.isoformat() if self.last_sync_time else None,
            'last_full_backup_time': self.last_full_backup_time.isoformat() if self.last_full_backup_time else None,
            'pending_changes': len(self.pending_changes),
            'queue_size': self.change_queue.qsize(),
            'total_changes_synced': self.total_changes_synced,
            'sync_interval': self.sync_interval,
            'full_backup_enabled': self.enable_full_backup,
            'full_backup_interval': self.full_backup_interval,
        }
        
    async def force_sync(self) -> bool:
        """Force an immediate sync."""
        logger.info("Forcing immediate sync...")
        try:
            await self._sync_changes()
            return True
        except Exception as e:
            logger.error(f"Failed to force sync: {e}")
            return False