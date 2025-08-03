from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from graph_service.models.user import DocumentOwnership, Permission, User


class OwnershipService:
    async def create_document_ownership(
        self, db: AsyncSession, user_id: UUID, group_id: str, 
        permissions: Permission = Permission.OWNER
    ) -> DocumentOwnership:
        """Create document ownership record"""
        ownership = DocumentOwnership(
            user_id=user_id,
            group_id=group_id,
            permissions=permissions,
        )
        db.add(ownership)
        await db.commit()
        await db.refresh(ownership)
        return ownership
    
    async def get_user_documents(
        self, db: AsyncSession, user_id: UUID
    ) -> List[DocumentOwnership]:
        """Get all documents accessible by a user"""
        stmt = select(DocumentOwnership).where(
            DocumentOwnership.user_id == user_id
        ).options(selectinload(DocumentOwnership.user))
        
        result = await db.execute(stmt)
        return result.scalars().all()
    
    async def get_user_group_ids(
        self, db: AsyncSession, user_id: UUID
    ) -> List[str]:
        """Get all group IDs accessible by a user"""
        stmt = select(DocumentOwnership.group_id).where(
            DocumentOwnership.user_id == user_id
        )
        
        result = await db.execute(stmt)
        return [row[0] for row in result.all()]
    
    async def check_user_access(
        self, db: AsyncSession, user_id: UUID, group_id: str, 
        required_permission: Optional[Permission] = None
    ) -> Optional[DocumentOwnership]:
        """Check if user has access to a document"""
        stmt = select(DocumentOwnership).where(
            DocumentOwnership.user_id == user_id,
            DocumentOwnership.group_id == group_id
        )
        
        result = await db.execute(stmt)
        ownership = result.scalar_one_or_none()
        
        if not ownership:
            return None
        
        # Check permission level if required
        if required_permission:
            permission_levels = {
                Permission.VIEWER: 0,
                Permission.EDITOR: 1,
                Permission.OWNER: 2,
            }
            
            user_level = permission_levels.get(ownership.permissions, 0)
            required_level = permission_levels.get(required_permission, 0)
            
            if user_level < required_level:
                return None
        
        return ownership
    
    async def share_document(
        self, db: AsyncSession, group_id: str, owner_id: UUID, 
        target_email: str, permissions: Permission = Permission.VIEWER
    ) -> Optional[DocumentOwnership]:
        """Share document with another user"""
        # Check if current user is owner
        owner_check = await self.check_user_access(
            db, owner_id, group_id, Permission.OWNER
        )
        if not owner_check:
            return None
        
        # Find target user by email
        stmt = select(User).where(User.email == target_email)
        result = await db.execute(stmt)
        target_user = result.scalar_one_or_none()
        
        if not target_user:
            return None
        
        # Check if access already exists
        existing = await self.check_user_access(db, target_user.id, group_id)
        if existing:
            # Update permissions
            existing.permissions = permissions
        else:
            # Create new access
            ownership = DocumentOwnership(
                user_id=target_user.id,
                group_id=group_id,
                permissions=permissions,
            )
            db.add(ownership)
        
        await db.commit()
        
        # Return with user loaded
        stmt = select(DocumentOwnership).where(
            DocumentOwnership.user_id == target_user.id,
            DocumentOwnership.group_id == group_id
        ).options(selectinload(DocumentOwnership.user))
        
        result = await db.execute(stmt)
        return result.scalar_one()
    
    async def revoke_access(
        self, db: AsyncSession, group_id: str, owner_id: UUID, target_user_id: UUID
    ) -> bool:
        """Revoke user access to a document"""
        # Check if current user is owner
        owner_check = await self.check_user_access(
            db, owner_id, group_id, Permission.OWNER
        )
        if not owner_check:
            return False
        
        # Cannot revoke owner's own access
        if owner_id == target_user_id:
            return False
        
        # Find and delete access
        stmt = select(DocumentOwnership).where(
            DocumentOwnership.user_id == target_user_id,
            DocumentOwnership.group_id == group_id
        )
        result = await db.execute(stmt)
        ownership = result.scalar_one_or_none()
        
        if ownership:
            await db.delete(ownership)
            await db.commit()
            return True
        
        return False
    
    async def get_document_users(
        self, db: AsyncSession, group_id: str, owner_id: UUID
    ) -> Optional[List[DocumentOwnership]]:
        """Get all users with access to a document"""
        # Check if current user has access
        access_check = await self.check_user_access(db, owner_id, group_id)
        if not access_check:
            return None
        
        stmt = select(DocumentOwnership).where(
            DocumentOwnership.group_id == group_id
        ).options(selectinload(DocumentOwnership.user))
        
        result = await db.execute(stmt)
        return result.scalars().all()