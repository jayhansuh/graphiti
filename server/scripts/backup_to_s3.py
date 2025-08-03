#!/usr/bin/env python3
"""Script to perform automated backup to S3."""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from graph_service.backup import Neo4jExporter, PostgresExporter, S3BackupService
from graph_service.config import get_settings

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Perform automated backup."""
    try:
        settings = get_settings()
        
        # Initialize S3 service
        s3_service = S3BackupService(
            bucket_name=os.getenv('S3_BACKUP_BUCKET', 'graphiti-backups'),
            region=os.getenv('AWS_REGION', 'ap-northeast-3'),
            # Don't pass credentials - use AWS configure or IAM role
        )
        
        backup_data = {
            'created_by': 'automated_backup',
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        
        # Export Neo4j data
        logger.info("Starting Neo4j export...")
        neo4j_exporter = Neo4jExporter(
            uri=settings.neo4j_uri,
            username=settings.neo4j_user,
            password=settings.neo4j_password,
            database='neo4j',
        )
        
        neo4j_data = await neo4j_exporter.export_all_data()
        backup_data['neo4j'] = neo4j_data
        logger.info(f"Exported {neo4j_data['statistics']['total_nodes']} nodes and {neo4j_data['statistics']['total_edges']} edges")
        
        # Export PostgreSQL data
        logger.info("Starting PostgreSQL export...")
        if settings.postgres_uri.startswith('sqlite'):
            logger.info("Skipping PostgreSQL export (using SQLite for testing)")
            backup_data['postgres'] = {
                'users': [],
                'statistics': {'user_count': 0}
            }
        else:
            postgres_exporter = PostgresExporter(dsn=settings.postgres_uri)
            
            postgres_data = await postgres_exporter.export_all_data()
            backup_data['postgres'] = postgres_data
            logger.info(f"Exported {postgres_data['statistics']['user_count']} users")
        
        # Upload to S3
        logger.info("Uploading backup to S3...")
        backup_key = await s3_service.upload_backup(
            data=backup_data,
            backup_type='scheduled',
            description='Daily automated backup',
        )
        
        logger.info(f"Backup completed successfully: {backup_key}")
        
        # Clean up old backups (lifecycle policy will handle this)
        # Just log the current backup count
        backups = await s3_service.list_backups(backup_type='scheduled', limit=10)
        logger.info(f"Total scheduled backups: {len(backups)}")
        
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())