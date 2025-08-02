import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from graph_service.config import get_settings
from graph_service.routers import ingest, retrieve
from graph_service.zep_graphiti import initialize_graphiti, ZepGraphitiDep

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    await initialize_graphiti(settings)
    yield
    # Shutdown
    # No need to close Graphiti here, as it's handled per-request


app = FastAPI(lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(retrieve.router)
app.include_router(ingest.router)


@app.get('/')
async def root():
    return FileResponse('static/index.html')


@app.get('/healthcheck')
async def healthcheck():
    return JSONResponse(content={'status': 'healthy'}, status_code=200)


@app.get('/graph-data')
async def get_graph_data(graphiti: ZepGraphitiDep, group_id: str | None = None):
    """Get graph data for visualization"""
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


@app.get('/stats')
async def get_stats(graphiti: ZepGraphitiDep):
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
