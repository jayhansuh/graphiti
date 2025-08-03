import logging
import os
from contextlib import asynccontextmanager

from typing import Union

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from graph_service.config import get_settings
from graph_service.auth import get_current_user_required, verify_api_key
from graph_service.models.database import get_engine, Base, get_db
from graph_service.models.user import User
from graph_service.routers import ingest, oauth, retrieve, backup
from graph_service.services.ownership_service import OwnershipService
from graph_service.zep_graphiti import initialize_graphiti, ZepGraphitiDep

logger = logging.getLogger(__name__)

# Global variable to store backup worker
backup_worker = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    
    # Initialize database
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Initialize Graphiti
    await initialize_graphiti(settings)
    
    # Initialize backup worker if continuous backup is enabled
    global backup_worker
    if os.getenv('ENABLE_CONTINUOUS_BACKUP', 'true').lower() == 'true':
        try:
            from graph_service.backup import S3BackupService, BackupWorker
            from graph_service.dependencies import get_neo4j_config, get_postgres_config
            
            s3_service = S3BackupService(
                bucket_name=os.getenv('S3_BACKUP_BUCKET', 'graphiti-backups-test'),
                region=os.getenv('AWS_REGION', 'ap-northeast-3'),
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            )
            
            neo4j_config = get_neo4j_config()
            postgres_config = get_postgres_config()
            
            backup_worker = BackupWorker(
                s3_service=s3_service,
                neo4j_config=neo4j_config,
                postgres_config=postgres_config,
                sync_interval=int(os.getenv('BACKUP_SYNC_INTERVAL', '60')),
                enable_full_backup=os.getenv('ENABLE_FULL_BACKUP', 'true').lower() == 'true',
                full_backup_interval=int(os.getenv('FULL_BACKUP_INTERVAL', '3600')),
            )
            
            await backup_worker.start()
            logger.info("Started continuous backup worker")
            
            # Store backup worker in app state for access in endpoints
            app.state.backup_worker = backup_worker
            
        except Exception as e:
            logger.error(f"Failed to start backup worker: {e}")
    
    # Check if we need to restore from S3 backup on startup
    if os.getenv('RESTORE_FROM_S3_ON_STARTUP', 'false').lower() == 'true':
        try:
            from graph_service.backup import S3BackupService, RestoreService
            from graph_service.dependencies import get_neo4j_config, get_postgres_config
            
            if not 's3_service' in locals():
                s3_service = S3BackupService(
                    bucket_name=os.getenv('S3_BACKUP_BUCKET', 'graphiti-backups-test'),
                    region=os.getenv('AWS_REGION', 'ap-northeast-3'),
                    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                )
                
                neo4j_config = get_neo4j_config()
                postgres_config = get_postgres_config()
            
            restore_service = RestoreService(
                s3_service=s3_service,
                neo4j_uri=neo4j_config['uri'],
                neo4j_username=neo4j_config['username'],
                neo4j_password=neo4j_config['password'],
                neo4j_database=neo4j_config.get('database', 'neo4j'),
                postgres_dsn=postgres_config['dsn'],
            )
            
            result = await restore_service.initialize_from_latest_backup()
            if result:
                logger.info(f"Successfully initialized from S3 backup: {result}")
        except Exception as e:
            logger.error(f"Failed to initialize from S3 backup: {e}")
            # Continue startup even if restore fails
    
    yield
    # Shutdown
    # Stop backup worker if running
    if backup_worker:
        await backup_worker.stop()
        logger.info("Stopped backup worker")
    
    # No need to close Graphiti here, as it's handled per-request


app = FastAPI(lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(retrieve.router)
app.include_router(ingest.router)
app.include_router(oauth.router)
app.include_router(backup.router)


@app.get('/')
async def root():
    return FileResponse('static/index.html')


@app.get('/login')
async def login_page():
    return FileResponse('static/login.html')


@app.get('/healthcheck')
async def healthcheck():
    return JSONResponse(content={'status': 'healthy'}, status_code=200)


@app.get('/graph-data', dependencies=[Depends(get_current_user_required)])
async def get_graph_data(
    graphiti: ZepGraphitiDep,
    group_id: str | None = None,
    current_user: Union[User, str] = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """Get graph data for visualization"""
    ownership_service = OwnershipService()
    
    # If OAuth user, check access and filter by accessible groups
    if isinstance(current_user, User):
        if group_id:
            # Check access to specific group
            access = await ownership_service.check_user_access(
                db, current_user.id, group_id
            )
            if not access:
                raise HTTPException(
                    status_code=403,
                    detail="No access to this document"
                )
        else:
            # Get all accessible groups for filtering
            accessible_groups = await ownership_service.get_user_group_ids(db, current_user.id)
            if not accessible_groups:
                return JSONResponse(content={'nodes': [], 'edges': []})
    
    try:
        # Query for nodes
        if group_id:
            nodes_query = """
            MATCH (n:Entity)
            WHERE n.group_id IS NOT NULL AND n.group_id = $group_id
            RETURN n.uuid as id, n.name as label, n.group_id as group, 
                   labels(n) as labels, n.summary as summary
            LIMIT 100
            """
            nodes_records, _, _ = await graphiti.driver.execute_query(
                nodes_query, group_id=group_id
            )
        else:
            # For OAuth users, filter by accessible groups
            if isinstance(current_user, User) and accessible_groups:
                nodes_query = """
                MATCH (n:Entity)
                WHERE n.group_id IS NOT NULL AND n.group_id IN $group_ids
                RETURN n.uuid as id, n.name as label, n.group_id as group, 
                       labels(n) as labels, n.summary as summary
                LIMIT 100
                """
                nodes_records, _, _ = await graphiti.driver.execute_query(
                    nodes_query, group_ids=accessible_groups
                )
            else:
                # API key auth - show all
                nodes_query = """
                MATCH (n:Entity)
                WHERE n.group_id IS NOT NULL
                RETURN n.uuid as id, n.name as label, n.group_id as group, 
                       labels(n) as labels, n.summary as summary
                LIMIT 100
                """
                nodes_records, _, _ = await graphiti.driver.execute_query(nodes_query)
        
        # Query for relationships
        if group_id:
            rel_query = """
            MATCH (n:Entity)-[r:RELATES_TO]->(m:Entity)
            WHERE n.group_id IS NOT NULL AND m.group_id IS NOT NULL
                  AND n.group_id = $group_id AND m.group_id = $group_id
            RETURN n.uuid as source, m.uuid as target, r.fact as label, type(r) as type
            LIMIT 200
            """
            edges_records, _, _ = await graphiti.driver.execute_query(
                rel_query, group_id=group_id
            )
        else:
            # For OAuth users, filter by accessible groups
            if isinstance(current_user, User) and accessible_groups:
                rel_query = """
                MATCH (n:Entity)-[r:RELATES_TO]->(m:Entity)
                WHERE n.group_id IS NOT NULL AND m.group_id IS NOT NULL
                      AND n.group_id IN $group_ids AND m.group_id IN $group_ids
                RETURN n.uuid as source, m.uuid as target, r.fact as label, type(r) as type
                LIMIT 200
                """
                edges_records, _, _ = await graphiti.driver.execute_query(
                    rel_query, group_ids=accessible_groups
                )
            else:
                # API key auth - show all
                rel_query = """
                MATCH (n:Entity)-[r:RELATES_TO]->(m:Entity)
                WHERE n.group_id IS NOT NULL AND m.group_id IS NOT NULL
                RETURN n.uuid as source, m.uuid as target, r.fact as label, type(r) as type
                LIMIT 200
                """
                edges_records, _, _ = await graphiti.driver.execute_query(rel_query)
        
        nodes = [dict(record) for record in nodes_records]
        edges = [dict(record) for record in edges_records]
        
        return JSONResponse(content={
            'nodes': nodes,
            'edges': edges
        })
    except Exception as e:
        logger.error(f"Error in get_graph_data: {e}")
        return JSONResponse(
            content={'error': 'Failed to fetch graph data'},
            status_code=500
        )


@app.get('/stats', dependencies=[Depends(get_current_user_required)])
async def get_stats(
    graphiti: ZepGraphitiDep,
    current_user: Union[User, str] = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    """Get graph statistics"""
    try:
        # Count entities
        entity_query = "MATCH (n:Entity) RETURN count(n) as entity_count"
        entity_records, _, _ = await graphiti.driver.execute_query(entity_query)
        entity_count = entity_records[0]['entity_count'] if entity_records else 0
        
        # Count episodes
        episode_query = "MATCH (e:Episodic) RETURN count(e) as episode_count"
        episode_records, _, _ = await graphiti.driver.execute_query(episode_query)
        episode_count = episode_records[0]['episode_count'] if episode_records else 0
        
        # Count relations
        relation_query = "MATCH ()-[r:RELATES_TO]->() RETURN count(r) as relation_count"
        relation_records, _, _ = await graphiti.driver.execute_query(relation_query)
        relation_count = relation_records[0]['relation_count'] if relation_records else 0
        
        stats = {
            'entity_count': entity_count,
            'episode_count': episode_count,
            'relation_count': relation_count
        }
        
        return JSONResponse(content=stats)
    except Exception as e:
        logger.error(f"Error in get_stats: {e}")
        return JSONResponse(
            content={'error': 'Failed to fetch statistics'},
            status_code=500
        )
