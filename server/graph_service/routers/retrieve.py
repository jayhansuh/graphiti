from datetime import datetime, timezone
from typing import Union

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from graph_service.auth import get_current_user_required
from graph_service.dto import (
    GetMemoryRequest,
    GetMemoryResponse,
    Message,
    SearchQuery,
    SearchResults,
)
from graph_service.models.database import get_db
from graph_service.models.user import User
from graph_service.services.ownership_service import OwnershipService
from graph_service.zep_graphiti import ZepGraphitiDep, get_fact_result_from_edge

router = APIRouter(dependencies=[Depends(get_current_user_required)])


@router.post('/search', status_code=status.HTTP_200_OK)
async def search(
    query: SearchQuery,
    graphiti: ZepGraphitiDep,
    current_user: Union[User, str] = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    ownership_service = OwnershipService()
    
    # If OAuth user, filter group_ids by access
    if isinstance(current_user, User):
        # Get all accessible group_ids for the user
        accessible_groups = await ownership_service.get_user_group_ids(db, current_user.id)
        
        # If specific group_ids requested, filter by access
        if query.group_ids:
            query.group_ids = [g for g in query.group_ids if g in accessible_groups]
            if not query.group_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No access to any of the requested documents"
                )
        else:
            # If no group_ids specified, search only user's accessible groups
            query.group_ids = accessible_groups
    
    try:
        relevant_edges = await graphiti.search(
            group_ids=query.group_ids,
            query=query.query,
            num_results=query.max_facts,
        )
        facts = [get_fact_result_from_edge(edge) for edge in relevant_edges]
        return SearchResults(
            facts=facts,
        )
    except Exception as e:
        # Check if it's an OpenAI API key error
        if "invalid_api_key" in str(e) or "Incorrect API key" in str(e):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Search service unavailable: Invalid OpenAI API key configured"
            )
        # Log the error and return a generic message
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.get('/entity-edge/{uuid}', status_code=status.HTTP_200_OK)
async def get_entity_edge(uuid: str, graphiti: ZepGraphitiDep):
    entity_edge = await graphiti.get_entity_edge(uuid)
    return get_fact_result_from_edge(entity_edge)


@router.get('/episodes/{group_id}', status_code=status.HTTP_200_OK)
async def get_episodes(
    group_id: str,
    last_n: int,
    graphiti: ZepGraphitiDep,
    current_user: Union[User, str] = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    ownership_service = OwnershipService()
    
    # If OAuth user, check access to document
    if isinstance(current_user, User):
        access = await ownership_service.check_user_access(
            db, current_user.id, group_id
        )
        if not access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No access to this document"
            )
    
    episodes = await graphiti.retrieve_episodes(
        group_ids=[group_id], last_n=last_n, reference_time=datetime.now(timezone.utc)
    )
    return episodes


@router.post('/get-memory', status_code=status.HTTP_200_OK)
async def get_memory(
    request: GetMemoryRequest,
    graphiti: ZepGraphitiDep,
    current_user: Union[User, str] = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    ownership_service = OwnershipService()
    
    # If OAuth user, check access to document
    if isinstance(current_user, User):
        access = await ownership_service.check_user_access(
            db, current_user.id, request.group_id
        )
        if not access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No access to this document"
            )
    
    combined_query = compose_query_from_messages(request.messages)
    result = await graphiti.search(
        group_ids=[request.group_id],
        query=combined_query,
        num_results=request.max_facts,
    )
    facts = [get_fact_result_from_edge(edge) for edge in result]
    return GetMemoryResponse(facts=facts)


def compose_query_from_messages(messages: list[Message]):
    combined_query = ''
    for message in messages:
        combined_query += f'{message.role_type or ""}({message.role or ""}): {message.content}\n'
    return combined_query
