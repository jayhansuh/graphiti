"""S3 backup service for automated backups and restoration."""

import gzip
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aioboto3
import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime objects."""
    
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

logger = logging.getLogger(__name__)


class BackupMetadata(BaseModel):
    """Metadata for a backup."""
    
    timestamp: datetime
    backup_type: str  # 'manual', 'scheduled', 'pre_deletion'
    description: Optional[str] = None
    neo4j_node_count: int = 0
    neo4j_edge_count: int = 0
    postgres_record_count: int = 0
    deleted_items: List[str] = Field(default_factory=list)
    source_version: str = '0.1.0'


class S3BackupService:
    """Service for managing S3 backups."""
    
    def __init__(
        self,
        bucket_name: str,
        prefix: str = 'graphiti-backups',
        region: str = 'ap-northeast-3',
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ):
        """Initialize S3 backup service.
        
        Args:
            bucket_name: S3 bucket name
            prefix: Prefix for backup objects
            region: AWS region
            aws_access_key_id: AWS access key (optional, uses IAM role if not provided)
            aws_secret_access_key: AWS secret key (optional)
        """
        self.bucket_name = bucket_name
        self.prefix = prefix
        self.region = region
        
        # Initialize boto3 session
        session_kwargs = {'region_name': region}
        if aws_access_key_id and aws_secret_access_key:
            session_kwargs.update({
                'aws_access_key_id': aws_access_key_id,
                'aws_secret_access_key': aws_secret_access_key,
            })
        
        self.session = aioboto3.Session(**session_kwargs)
        
    async def upload_backup(
        self,
        data: Dict[str, Any],
        backup_type: str = 'manual',
        description: Optional[str] = None,
    ) -> str:
        """Upload backup data to S3.
        
        Args:
            data: Backup data to upload
            backup_type: Type of backup (manual, scheduled, pre_deletion)
            description: Optional backup description
            
        Returns:
            S3 object key for the uploaded backup
        """
        timestamp = datetime.now(timezone.utc)
        timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S')
        
        # Create metadata
        metadata = BackupMetadata(
            timestamp=timestamp,
            backup_type=backup_type,
            description=description,
            neo4j_node_count=len(data.get('neo4j', {}).get('nodes', [])),
            neo4j_edge_count=len(data.get('neo4j', {}).get('edges', [])),
            postgres_record_count=len(data.get('postgres', {}).get('users', [])),
        )
        
        # Add metadata to backup data
        data['metadata'] = metadata.model_dump(mode='json')
        
        # Compress data
        json_data = json.dumps(data, indent=2, cls=DateTimeEncoder).encode('utf-8')
        compressed_data = gzip.compress(json_data)
        
        # Generate S3 key
        key = f'{self.prefix}/{backup_type}/{timestamp_str}_backup.json.gz'
        
        # Upload to S3
        async with self.session.client('s3') as s3:
            try:
                await s3.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=compressed_data,
                    ContentType='application/gzip',
                    Metadata={
                        'backup-type': backup_type,
                        'timestamp': timestamp.isoformat(),
                        'description': description or '',
                    },
                )
                logger.info(f'Successfully uploaded backup to S3: {key}')
                return key
                
            except ClientError as e:
                logger.error(f'Failed to upload backup to S3: {e}')
                raise
                
    async def list_backups(
        self,
        backup_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List available backups.
        
        Args:
            backup_type: Filter by backup type
            limit: Maximum number of backups to return
            
        Returns:
            List of backup metadata
        """
        prefix = f'{self.prefix}/'
        if backup_type:
            prefix = f'{self.prefix}/{backup_type}/'
            
        backups = []
        
        async with self.session.client('s3') as s3:
            try:
                paginator = s3.get_paginator('list_objects_v2')
                page_iterator = paginator.paginate(
                    Bucket=self.bucket_name,
                    Prefix=prefix,
                    PaginationConfig={'MaxItems': limit}
                )
                
                async for page in page_iterator:
                    for obj in page.get('Contents', []):
                        # Get object metadata
                        head_response = await s3.head_object(
                            Bucket=self.bucket_name,
                            Key=obj['Key']
                        )
                        
                        backups.append({
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'].isoformat(),
                            'backup_type': head_response.get('Metadata', {}).get('backup-type', 'unknown'),
                            'description': head_response.get('Metadata', {}).get('description', ''),
                        })
                        
                return sorted(backups, key=lambda x: x['last_modified'], reverse=True)
                
            except ClientError as e:
                logger.error(f'Failed to list backups from S3: {e}')
                raise
                
    async def download_backup(self, key: str) -> Dict[str, Any]:
        """Download and decompress backup from S3.
        
        Args:
            key: S3 object key
            
        Returns:
            Decompressed backup data
        """
        async with self.session.client('s3') as s3:
            try:
                response = await s3.get_object(Bucket=self.bucket_name, Key=key)
                compressed_data = await response['Body'].read()
                
                # Decompress data
                json_data = gzip.decompress(compressed_data)
                data = json.loads(json_data)
                
                logger.info(f'Successfully downloaded backup from S3: {key}')
                return data
                
            except ClientError as e:
                logger.error(f'Failed to download backup from S3: {e}')
                raise
                
    async def delete_backup(self, key: str) -> None:
        """Delete a backup from S3.
        
        Args:
            key: S3 object key
        """
        async with self.session.client('s3') as s3:
            try:
                await s3.delete_object(Bucket=self.bucket_name, Key=key)
                logger.info(f'Successfully deleted backup from S3: {key}')
                
            except ClientError as e:
                logger.error(f'Failed to delete backup from S3: {e}')
                raise
                
    async def save_deletion_backup(
        self,
        deleted_items: List[Dict[str, Any]],
        item_type: str,
        reason: str = 'manual_deletion',
    ) -> str:
        """Save a backup before deletion with _ prefix for protection.
        
        Args:
            deleted_items: Items being deleted
            item_type: Type of items (e.g., 'nodes', 'edges', 'users')
            reason: Reason for deletion
            
        Returns:
            S3 object key for the deletion backup
        """
        timestamp = datetime.now(timezone.utc)
        timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S')
        
        # Create deletion backup data
        data = {
            'deletion_metadata': {
                'timestamp': timestamp.isoformat(),
                'item_type': item_type,
                'item_count': len(deleted_items),
                'reason': reason,
            },
            'deleted_items': deleted_items,
        }
        
        # Compress data
        json_data = json.dumps(data, indent=2, cls=DateTimeEncoder).encode('utf-8')
        compressed_data = gzip.compress(json_data)
        
        # Generate S3 key with _ prefix for protection
        key = f'{self.prefix}/deletions/_{timestamp_str}_{item_type}_deletion.json.gz'
        
        # Upload to S3
        async with self.session.client('s3') as s3:
            try:
                await s3.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=compressed_data,
                    ContentType='application/gzip',
                    Metadata={
                        'deletion-type': item_type,
                        'timestamp': timestamp.isoformat(),
                        'reason': reason,
                        'protected': 'true',  # Mark as protected
                    },
                )
                logger.info(f'Successfully saved deletion backup to S3: {key}')
                return key
                
            except ClientError as e:
                logger.error(f'Failed to save deletion backup to S3: {e}')
                raise
                
    async def setup_lifecycle_policy(self) -> None:
        """Set up S3 lifecycle policy for automatic cleanup.
        
        - Regular backups: 30 days retention
        - Scheduled backups: 90 days retention  
        - Deletion backups (with _ prefix): Never expire
        """
        lifecycle_config = {
            'Rules': [
                {
                    'ID': 'RegularBackupRetention',
                    'Filter': {
                        'And': {
                            'Prefix': f'{self.prefix}/manual/',
                            'Tags': []
                        }
                    },
                    'Status': 'Enabled',
                    'Expiration': {
                        'Days': 30
                    }
                },
                {
                    'ID': 'ScheduledBackupRetention',
                    'Filter': {
                        'Prefix': f'{self.prefix}/scheduled/'
                    },
                    'Status': 'Enabled',
                    'Expiration': {
                        'Days': 90
                    }
                },
                # Deletion backups with _ prefix are NOT included in lifecycle policy
                # They will be retained indefinitely
            ]
        }
        
        async with self.session.client('s3') as s3:
            try:
                await s3.put_bucket_lifecycle_configuration(
                    Bucket=self.bucket_name,
                    LifecycleConfiguration=lifecycle_config
                )
                logger.info('Successfully set up S3 lifecycle policy')
                
            except ClientError as e:
                logger.error(f'Failed to set up lifecycle policy: {e}')
                raise