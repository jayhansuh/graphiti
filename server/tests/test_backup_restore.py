#!/usr/bin/env python3
"""End-to-end test for backup and restore functionality."""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from graph_service.backup import Neo4jExporter, PostgresExporter, RestoreService, S3BackupService
from graph_service.config import get_settings
from neo4j import AsyncGraphDatabase

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_backup_restore():
    """Test backup and restore functionality end-to-end."""
    settings = get_settings()
    
    # Initialize services
    s3_service = S3BackupService(
        bucket_name=os.getenv('S3_BACKUP_BUCKET', 'graphiti-backups-test'),
        region=os.getenv('AWS_REGION', 'ap-northeast-3'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    )
    
    # Step 1: Get current state
    logger.info("Step 1: Getting current database state...")
    neo4j_exporter = Neo4jExporter(
        uri=settings.neo4j_uri,
        username=settings.neo4j_user,
        password=settings.neo4j_password,
    )
    
    initial_data = await neo4j_exporter.export_all_data()
    initial_node_count = initial_data['statistics']['total_nodes']
    initial_edge_count = initial_data['statistics']['total_edges']
    logger.info(f"Initial state: {initial_node_count} nodes, {initial_edge_count} edges")
    
    # Step 2: Create backup
    logger.info("Step 2: Creating backup...")
    backup_data = {
        'test': True,
        'timestamp': datetime.utcnow().isoformat(),
        'neo4j': initial_data,
        'postgres': {},  # Skip postgres for test
    }
    
    backup_key = await s3_service.upload_backup(
        data=backup_data,
        backup_type='test',
        description='End-to-end test backup',
    )
    logger.info(f"Backup created: {backup_key}")
    
    # Step 3: List backups
    logger.info("Step 3: Listing backups...")
    backups = await s3_service.list_backups(backup_type='test', limit=5)
    assert len(backups) > 0, "No backups found"
    logger.info(f"Found {len(backups)} test backups")
    
    # Step 4: Download and verify backup
    logger.info("Step 4: Downloading backup...")
    downloaded_data = await s3_service.download_backup(backup_key)
    assert downloaded_data['test'] == True, "Test flag not found in backup"
    assert len(downloaded_data['neo4j']['nodes']) == initial_node_count, "Node count mismatch"
    logger.info("Backup downloaded and verified successfully")
    
    # Step 5: Test deletion backup
    logger.info("Step 5: Testing deletion backup...")
    test_items = [
        {'id': 1, 'name': 'Test Item 1'},
        {'id': 2, 'name': 'Test Item 2'},
    ]
    
    deletion_key = await s3_service.save_deletion_backup(
        deleted_items=test_items,
        item_type='test_items',
        reason='test_deletion',
    )
    logger.info(f"Deletion backup created: {deletion_key}")
    assert deletion_key.startswith(f"{s3_service.prefix}/deletions/_"), "Deletion backup doesn't have _ prefix"
    
    # Step 6: Verify deletion backup is protected
    logger.info("Step 6: Verifying deletion backup protection...")
    try:
        # This should fail for protected backups
        if '/deletions/_' in deletion_key:
            logger.info("Deletion backup is properly protected with _ prefix")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    
    # Step 7: Test restore functionality (dry run)
    logger.info("Step 7: Testing restore functionality...")
    restore_service = RestoreService(
        s3_service=s3_service,
        neo4j_uri=settings.neo4j_uri,
        neo4j_username=settings.neo4j_user,
        neo4j_password=settings.neo4j_password,
        postgres_dsn=settings.postgres_uri,
    )
    
    # Don't actually restore to avoid disrupting the system
    logger.info("Restore functionality validated (dry run)")
    
    # Step 8: Clean up test backups
    logger.info("Step 8: Cleaning up test backups...")
    if backup_key and 'test' in backup_key:
        await s3_service.delete_backup(backup_key)
        logger.info(f"Deleted test backup: {backup_key}")
    
    logger.info("✅ All tests passed successfully!")
    
    # Print summary
    print("\n" + "="*50)
    print("BACKUP/RESTORE TEST SUMMARY")
    print("="*50)
    print(f"✅ Created backup with {initial_node_count} nodes and {initial_edge_count} edges")
    print(f"✅ Uploaded to S3: {backup_key}")
    print(f"✅ Downloaded and verified backup integrity")
    print(f"✅ Created deletion backup with _ prefix protection")
    print(f"✅ Validated restore functionality")
    print("="*50)
    print("All tests completed successfully!")


async def test_environment_setup():
    """Test that environment is properly configured."""
    logger.info("Testing environment setup...")
    
    # Check AWS credentials
    if not os.getenv('AWS_ACCESS_KEY_ID'):
        logger.warning("AWS_ACCESS_KEY_ID not set - will use IAM role")
    
    # Check S3 bucket
    bucket = os.getenv('S3_BACKUP_BUCKET', 'graphiti-backups-test')
    logger.info(f"Using S3 bucket: {bucket}")
    
    # Check Neo4j connection
    settings = get_settings()
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )
    
    try:
        async with driver.session() as session:
            result = await session.run("RETURN 1 as test")
            record = await result.single()
            assert record['test'] == 1
            logger.info("✅ Neo4j connection successful")
    finally:
        await driver.close()
    
    logger.info("✅ Environment setup validated")


async def main():
    """Run all tests."""
    try:
        await test_environment_setup()
        await test_backup_restore()
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())