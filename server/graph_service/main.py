from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from graph_service.config import get_settings
from graph_service.routers import ingest, retrieve
from graph_service.zep_graphiti import initialize_graphiti, ZepGraphitiDep


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
    # Query for nodes
    query = """
    MATCH (n:Entity)
    WHERE n.group_id IS NOT NULL
    """ + (f"AND n.group_id = '{group_id}'" if group_id else "") + """
    RETURN n.uuid as id, n.name as label, n.group_id as group, 
           labels(n) as labels, n.summary as summary
    LIMIT 100
    """
    
    nodes_result = await graphiti.driver.query(query)
    
    # Query for relationships
    rel_query = """
    MATCH (n:Entity)-[r:RELATES_TO]->(m:Entity)
    WHERE n.group_id IS NOT NULL AND m.group_id IS NOT NULL
    """ + (f"AND n.group_id = '{group_id}' AND m.group_id = '{group_id}'" if group_id else "") + """
    RETURN n.uuid as source, m.uuid as target, r.fact as label, type(r) as type
    LIMIT 200
    """
    
    edges_result = await graphiti.driver.query(rel_query)
    
    nodes = [dict(node) for node in nodes_result]
    edges = [dict(edge) for edge in edges_result]
    
    return JSONResponse(content={
        'nodes': nodes,
        'edges': edges
    })


@app.get('/stats')
async def get_stats(graphiti: ZepGraphitiDep):
    """Get graph statistics"""
    stats_query = """
    MATCH (n:Entity) WITH count(n) as entity_count
    MATCH (e:Episodic) WITH entity_count, count(e) as episode_count
    MATCH ()-[r:RELATES_TO]->() WITH entity_count, episode_count, count(r) as relation_count
    RETURN entity_count, episode_count, relation_count
    """
    
    result = await graphiti.driver.query(stats_query)
    stats = dict(result[0]) if result else {'entity_count': 0, 'episode_count': 0, 'relation_count': 0}
    
    return JSONResponse(content=stats)
