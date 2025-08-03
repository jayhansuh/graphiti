"""Backup and restore API endpoints."""

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..auth import get_current_user
from ..models.user import User
from ..backup import Neo4jExporter, PostgresExporter, RestoreService, S3BackupService
from ..dependencies import get_neo4j_config, get_postgres_config

router = APIRouter(prefix="/backup", tags=["backup"])


class Result(BaseModel):
    """Generic result response."""
    message: str
    success: bool


class BackupRequest(BaseModel):
    """Request model for creating a backup."""
    
    description: Optional[str] = Field(None, description="Backup description")
    include_neo4j: bool = Field(True, description="Include Neo4j data")
    include_postgres: bool = Field(True, description="Include PostgreSQL data")


class BackupResponse(BaseModel):
    """Response model for backup operations."""
    
    backup_key: str
    timestamp: str
    description: Optional[str] = None
    statistics: Dict[str, Any] = Field(default_factory=dict)


class BackupListResponse(BaseModel):
    """Response model for listing backups."""
    
    backups: List[Dict[str, Any]]
    total: int


class RestoreRequest(BaseModel):
    """Request model for restoring from backup."""
    
    backup_key: str = Field(..., description="S3 backup key to restore from")
    restore_neo4j: bool = Field(True, description="Restore Neo4j data")
    restore_postgres: bool = Field(True, description="Restore PostgreSQL data")
    clear_existing: bool = Field(False, description="Clear existing data before restore")


class RestoreResponse(BaseModel):
    """Response model for restore operations."""
    
    backup_key: str
    timestamp: str
    results: Dict[str, Any]


def get_s3_service() -> S3BackupService:
    """Get S3 backup service instance."""
    bucket_name = os.getenv('S3_BACKUP_BUCKET', 'graphiti-backups')
    region = os.getenv('AWS_REGION', 'ap-northeast-3')
    
    return S3BackupService(
        bucket_name=bucket_name,
        region=region,
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    )


@router.post("/create", response_model=BackupResponse)
async def create_backup(
    request: BackupRequest,
    current_user: User = Depends(get_current_user),
    s3_service: S3BackupService = Depends(get_s3_service),
    neo4j_config: dict = Depends(get_neo4j_config),
    postgres_config: dict = Depends(get_postgres_config),
) -> BackupResponse:
    """Create a manual backup of the system data."""
    backup_data = {
        'created_by': current_user.email,
        'neo4j': {},
        'postgres': {},
    }
    
    # Export Neo4j data
    if request.include_neo4j:
        neo4j_exporter = Neo4jExporter(
            uri=neo4j_config['uri'],
            username=neo4j_config['username'],
            password=neo4j_config['password'],
            database=neo4j_config.get('database', 'neo4j'),
        )
        
        try:
            neo4j_data = await neo4j_exporter.export_all_data()
            backup_data['neo4j'] = neo4j_data
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to export Neo4j data: {str(e)}"
            )
            
    # Export PostgreSQL data
    if request.include_postgres:
        postgres_exporter = PostgresExporter(dsn=postgres_config['dsn'])
        
        try:
            postgres_data = await postgres_exporter.export_all_data()
            backup_data['postgres'] = postgres_data
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to export PostgreSQL data: {str(e)}"
            )
            
    # Upload to S3
    try:
        backup_key = await s3_service.upload_backup(
            data=backup_data,
            backup_type='manual',
            description=request.description,
        )
        
        return BackupResponse(
            backup_key=backup_key,
            timestamp=backup_data.get('metadata', {}).get('timestamp', ''),
            description=request.description,
            statistics={
                'neo4j': backup_data['neo4j'].get('statistics', {}),
                'postgres': backup_data['postgres'].get('statistics', {}),
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload backup: {str(e)}"
        )


@router.get("/list", response_model=BackupListResponse)
async def list_backups(
    backup_type: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    s3_service: S3BackupService = Depends(get_s3_service),
) -> BackupListResponse:
    """List available backups."""
    try:
        backups = await s3_service.list_backups(
            backup_type=backup_type,
            limit=limit
        )
        
        return BackupListResponse(
            backups=backups,
            total=len(backups)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list backups: {str(e)}"
        )


@router.post("/restore", response_model=RestoreResponse)
async def restore_backup(
    request: RestoreRequest,
    current_user: User = Depends(get_current_user),
    s3_service: S3BackupService = Depends(get_s3_service),
    neo4j_config: dict = Depends(get_neo4j_config),
    postgres_config: dict = Depends(get_postgres_config),
) -> RestoreResponse:
    """Restore data from a backup.
    
    WARNING: This operation can overwrite existing data.
    """
    restore_service = RestoreService(
        s3_service=s3_service,
        neo4j_uri=neo4j_config['uri'],
        neo4j_username=neo4j_config['username'],
        neo4j_password=neo4j_config['password'],
        neo4j_database=neo4j_config.get('database', 'neo4j'),
        postgres_dsn=postgres_config['dsn'],
    )
    
    try:
        results = await restore_service.restore_from_backup(
            backup_key=request.backup_key,
            restore_neo4j=request.restore_neo4j,
            restore_postgres=request.restore_postgres,
            clear_existing=request.clear_existing,
        )
        
        return RestoreResponse(
            backup_key=request.backup_key,
            timestamp=results['timestamp'],
            results=results
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restore backup: {str(e)}"
        )


@router.get("/status", response_model=dict)
async def get_backup_status(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get the status of the backup worker."""
    from graph_service.main import backup_worker
    
    if not backup_worker:
        return {
            'enabled': False,
            'message': 'Continuous backup is not enabled'
        }
    
    status = backup_worker.get_status()
    return {
        'enabled': True,
        **status
    }


@router.post("/force-sync", response_model=Result)
async def force_backup_sync(
    current_user: User = Depends(get_current_user),
) -> Result:
    """Force an immediate backup sync."""
    from graph_service.main import backup_worker
    
    if not backup_worker:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Continuous backup is not enabled"
        )
    
    success = await backup_worker.force_sync()
    
    if success:
        return Result(message='Backup sync triggered successfully', success=True)
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger backup sync"
        )


@router.delete("/{backup_key:path}")
async def delete_backup(
    backup_key: str,
    current_user: User = Depends(get_current_user),
    s3_service: S3BackupService = Depends(get_s3_service),
) -> Dict[str, str]:
    """Delete a specific backup.
    
    Note: Deletion backups with _ prefix are protected and cannot be deleted through this endpoint.
    """
    # Check if this is a protected deletion backup
    if '/deletions/_' in backup_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Deletion backups are protected and cannot be deleted"
        )
        
    try:
        await s3_service.delete_backup(backup_key)
        return {"message": f"Backup {backup_key} deleted successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete backup: {str(e)}"
        )