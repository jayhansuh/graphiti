import asyncio
from contextlib import asynccontextmanager
from functools import partial

from typing import Union
from uuid import uuid4

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from graphiti_core.nodes import EpisodeType  # type: ignore
from graphiti_core.utils.maintenance.graph_data_operations import clear_data  # type: ignore
from sqlalchemy.ext.asyncio import AsyncSession

from graph_service.auth import get_current_user_required
from graph_service.dto import AddEntityNodeRequest, AddMessagesRequest, Message, Result
from graph_service.models.database import get_db
from graph_service.models.user import Permission, User
from graph_service.services.ownership_service import OwnershipService
from graph_service.zep_graphiti import ZepGraphitiDep
from graph_service.backup import ChangeType


class AsyncWorker:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.task = None

    async def worker(self):
        while True:
            try:
                print(f'Got a job: (size of remaining queue: {self.queue.qsize()})')
                job = await self.queue.get()
                await job()
            except asyncio.CancelledError:
                break

    async def start(self):
        self.task = asyncio.create_task(self.worker())

    async def stop(self):
        if self.task:
            self.task.cancel()
            await self.task
        while not self.queue.empty():
            self.queue.get_nowait()


async_worker = AsyncWorker()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await async_worker.start()
    yield
    await async_worker.stop()


router = APIRouter(lifespan=lifespan, dependencies=[Depends(get_current_user_required)])


@router.post('/messages', status_code=status.HTTP_202_ACCEPTED)
async def add_messages(
    request: AddMessagesRequest,
    graphiti: ZepGraphitiDep,
    current_user: Union[User, str] = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    # Validate that OpenAI API key is configured properly
    from graph_service.config import get_settings
    settings = get_settings()
    
    if not settings.openai_api_key or settings.openai_api_key.startswith("sk-test-"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Knowledge base service is not properly configured. OpenAI API key is required for document processing."
        )
    
    ownership_service = OwnershipService()
    
    # If OAuth user, check permissions or create new ownership
    if isinstance(current_user, User):
        # If no group_id provided, generate one
        if not request.group_id:
            request.group_id = str(uuid4())
            # Create ownership for new document
            await ownership_service.create_document_ownership(
                db, current_user.id, request.group_id
            )
        else:
            # Check if user has access to existing document
            access = await ownership_service.check_user_access(
                db, current_user.id, request.group_id, Permission.EDITOR
            )
            if not access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions to add messages to this document"
                )
    
    async def add_messages_task(m: Message):
        await graphiti.add_episode(
            uuid=m.uuid,
            group_id=request.group_id,
            name=m.name,
            episode_body=f'{m.role or ""}({m.role_type}): {m.content}',
            reference_time=m.timestamp,
            source=EpisodeType.message,
            source_description=m.source_description,
        )
        
        # Track change for backup if backup worker is available
        from graph_service.main import backup_worker
        if backup_worker:
            await backup_worker.track_change(
                change_type=ChangeType.CREATE,
                entity_type='episode',
                entity_id=m.uuid,
                data={
                    'group_id': request.group_id,
                    'name': m.name,
                    'content': m.content,
                    'role': m.role,
                    'timestamp': m.timestamp.isoformat() if m.timestamp else None,
                },
                metadata={'source': 'messages_endpoint'}
            )

    for m in request.messages:
        await async_worker.queue.put(partial(add_messages_task, m))

    return Result(message='Messages added to processing queue', success=True)


@router.post('/entity-node', status_code=status.HTTP_201_CREATED)
async def add_entity_node(
    request: AddEntityNodeRequest,
    graphiti: ZepGraphitiDep,
    current_user: Union[User, str] = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    ownership_service = OwnershipService()
    
    # If OAuth user, check permissions
    if isinstance(current_user, User):
        access = await ownership_service.check_user_access(
            db, current_user.id, request.group_id, Permission.EDITOR
        )
        if not access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to add entities to this document"
            )
    
    node = await graphiti.save_entity_node(
        uuid=request.uuid,
        group_id=request.group_id,
        name=request.name,
        summary=request.summary,
    )
    
    # Track change for backup if backup worker is available
    from graph_service.main import backup_worker
    if backup_worker:
        await backup_worker.track_change(
            change_type=ChangeType.CREATE,
            entity_type='node',
            entity_id=request.uuid,
            data={
                'group_id': request.group_id,
                'name': request.name,
                'summary': request.summary,
            },
            metadata={'source': 'entity_node_endpoint'}
        )
    
    return node


@router.delete('/entity-edge/{uuid}', status_code=status.HTTP_200_OK)
async def delete_entity_edge(uuid: str, graphiti: ZepGraphitiDep):
    await graphiti.delete_entity_edge(uuid)
    return Result(message='Entity Edge deleted', success=True)


@router.delete('/group/{group_id}', status_code=status.HTTP_200_OK)
async def delete_group(
    group_id: str,
    graphiti: ZepGraphitiDep,
    current_user: Union[User, str] = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
):
    ownership_service = OwnershipService()
    
    # If OAuth user, check owner permissions
    if isinstance(current_user, User):
        access = await ownership_service.check_user_access(
            db, current_user.id, group_id, Permission.OWNER
        )
        if not access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only document owner can delete the group"
            )
    
    await graphiti.delete_group(group_id)
    return Result(message='Group deleted', success=True)


@router.delete('/episode/{uuid}', status_code=status.HTTP_200_OK)
async def delete_episode(uuid: str, graphiti: ZepGraphitiDep):
    await graphiti.delete_episodic_node(uuid)
    return Result(message='Episode deleted', success=True)


@router.post('/clear', status_code=status.HTTP_200_OK)
async def clear(
    graphiti: ZepGraphitiDep,
):
    await clear_data(graphiti.driver)
    await graphiti.build_indices_and_constraints()
    return Result(message='Graph cleared', success=True)
