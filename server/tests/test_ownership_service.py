import pytest
from uuid import uuid4

from sqlalchemy import select

from graph_service.models.user import DocumentOwnership, Permission, User, OAuthProvider
from graph_service.services.ownership_service import OwnershipService


class TestOwnershipService:
    """Test document ownership service"""
    
    @pytest.fixture
    def ownership_service(self):
        """Create ownership service instance"""
        return OwnershipService()
    
    @pytest.fixture
    async def second_user(self, test_db) -> User:
        """Create a second test user"""
        user = User(
            email="user2@example.com",
            name="Second User",
            provider=OAuthProvider.GITHUB,
            provider_id="789012",
            is_active=True,
        )
        test_db.add(user)
        await test_db.commit()
        await test_db.refresh(user)
        return user
    
    async def test_create_document_ownership(self, ownership_service, test_db, test_user):
        """Test creating document ownership"""
        group_id = str(uuid4())
        
        ownership = await ownership_service.create_document_ownership(
            test_db, test_user.id, group_id, Permission.OWNER
        )
        
        assert ownership.user_id == test_user.id
        assert ownership.group_id == group_id
        assert ownership.permissions == Permission.OWNER.value
        
        # Verify saved
        result = await test_db.execute(
            select(DocumentOwnership).where(
                DocumentOwnership.user_id == test_user.id,
                DocumentOwnership.group_id == group_id
            )
        )
        saved = result.scalar_one()
        assert saved.id == ownership.id
    
    async def test_get_user_documents(self, ownership_service, test_db, test_user):
        """Test getting user's documents"""
        # Create multiple document ownerships
        group_ids = [str(uuid4()) for _ in range(3)]
        for i, group_id in enumerate(group_ids):
            await ownership_service.create_document_ownership(
                test_db, test_user.id, group_id,
                Permission.OWNER if i == 0 else Permission.EDITOR
            )
        
        documents = await ownership_service.get_user_documents(test_db, test_user.id)
        
        assert len(documents) == 3
        assert all(doc.user_id == test_user.id for doc in documents)
        assert set(doc.group_id for doc in documents) == set(group_ids)
    
    async def test_get_user_group_ids(self, ownership_service, test_db, test_user):
        """Test getting user's accessible group IDs"""
        group_ids = [str(uuid4()) for _ in range(3)]
        for group_id in group_ids:
            await ownership_service.create_document_ownership(
                test_db, test_user.id, group_id
            )
        
        accessible_groups = await ownership_service.get_user_group_ids(test_db, test_user.id)
        
        assert len(accessible_groups) == 3
        assert set(accessible_groups) == set(group_ids)
    
    async def test_check_user_access_allowed(self, ownership_service, test_db, test_user):
        """Test checking user access when allowed"""
        group_id = str(uuid4())
        await ownership_service.create_document_ownership(
            test_db, test_user.id, group_id, Permission.EDITOR
        )
        
        # Check without required permission
        access = await ownership_service.check_user_access(
            test_db, test_user.id, group_id
        )
        assert access is not None
        assert access.permissions == Permission.EDITOR.value
        
        # Check with lower required permission
        access = await ownership_service.check_user_access(
            test_db, test_user.id, group_id, Permission.VIEWER
        )
        assert access is not None
        
        # Check with same required permission
        access = await ownership_service.check_user_access(
            test_db, test_user.id, group_id, Permission.EDITOR
        )
        assert access is not None
    
    async def test_check_user_access_denied(self, ownership_service, test_db, test_user):
        """Test checking user access when denied"""
        group_id = str(uuid4())
        
        # No ownership exists
        access = await ownership_service.check_user_access(
            test_db, test_user.id, group_id
        )
        assert access is None
        
        # Create viewer permission
        await ownership_service.create_document_ownership(
            test_db, test_user.id, group_id, Permission.VIEWER
        )
        
        # Check with higher required permission
        access = await ownership_service.check_user_access(
            test_db, test_user.id, group_id, Permission.EDITOR
        )
        assert access is None
    
    async def test_share_document_success(self, ownership_service, test_db, test_user, second_user):
        """Test sharing a document successfully"""
        group_id = str(uuid4())
        
        # Create owner access
        await ownership_service.create_document_ownership(
            test_db, test_user.id, group_id, Permission.OWNER
        )
        
        # Share with second user
        ownership = await ownership_service.share_document(
            test_db, group_id, test_user.id,
            second_user.email, Permission.EDITOR
        )
        
        assert ownership is not None
        assert ownership.user_id == second_user.id
        assert ownership.group_id == group_id
        assert ownership.permissions == Permission.EDITOR.value
        assert ownership.user.email == second_user.email
    
    async def test_share_document_update_permissions(self, ownership_service, test_db, test_user, second_user):
        """Test updating permissions when sharing again"""
        group_id = str(uuid4())
        
        # Create owner access
        await ownership_service.create_document_ownership(
            test_db, test_user.id, group_id, Permission.OWNER
        )
        
        # Share with viewer permission
        await ownership_service.share_document(
            test_db, group_id, test_user.id,
            second_user.email, Permission.VIEWER
        )
        
        # Update to editor permission
        ownership = await ownership_service.share_document(
            test_db, group_id, test_user.id,
            second_user.email, Permission.EDITOR
        )
        
        assert ownership.permissions == Permission.EDITOR.value
        
        # Verify only one ownership exists
        result = await test_db.execute(
            select(DocumentOwnership).where(
                DocumentOwnership.user_id == second_user.id,
                DocumentOwnership.group_id == group_id
            )
        )
        all_ownerships = result.scalars().all()
        assert len(all_ownerships) == 1
    
    async def test_share_document_not_owner(self, ownership_service, test_db, test_user, second_user):
        """Test sharing when not the owner"""
        group_id = str(uuid4())
        
        # Create editor access (not owner)
        await ownership_service.create_document_ownership(
            test_db, test_user.id, group_id, Permission.EDITOR
        )
        
        # Try to share
        ownership = await ownership_service.share_document(
            test_db, group_id, test_user.id,
            second_user.email, Permission.VIEWER
        )
        
        assert ownership is None
    
    async def test_share_document_user_not_found(self, ownership_service, test_db, test_user):
        """Test sharing with non-existent user"""
        group_id = str(uuid4())
        
        # Create owner access
        await ownership_service.create_document_ownership(
            test_db, test_user.id, group_id, Permission.OWNER
        )
        
        # Try to share with non-existent user
        ownership = await ownership_service.share_document(
            test_db, group_id, test_user.id,
            "nonexistent@example.com", Permission.VIEWER
        )
        
        assert ownership is None
    
    async def test_revoke_access_success(self, ownership_service, test_db, test_user, second_user):
        """Test revoking access successfully"""
        group_id = str(uuid4())
        
        # Create owner and viewer access
        await ownership_service.create_document_ownership(
            test_db, test_user.id, group_id, Permission.OWNER
        )
        await ownership_service.create_document_ownership(
            test_db, second_user.id, group_id, Permission.VIEWER
        )
        
        # Revoke second user's access
        success = await ownership_service.revoke_access(
            test_db, group_id, test_user.id, second_user.id
        )
        
        assert success is True
        
        # Verify access was removed
        access = await ownership_service.check_user_access(
            test_db, second_user.id, group_id
        )
        assert access is None
    
    async def test_revoke_access_not_owner(self, ownership_service, test_db, test_user, second_user):
        """Test revoking access when not owner"""
        group_id = str(uuid4())
        
        # Create editor access (not owner)
        await ownership_service.create_document_ownership(
            test_db, test_user.id, group_id, Permission.EDITOR
        )
        await ownership_service.create_document_ownership(
            test_db, second_user.id, group_id, Permission.VIEWER
        )
        
        # Try to revoke
        success = await ownership_service.revoke_access(
            test_db, group_id, test_user.id, second_user.id
        )
        
        assert success is False
    
    async def test_revoke_own_access(self, ownership_service, test_db, test_user):
        """Test that owner cannot revoke their own access"""
        group_id = str(uuid4())
        
        # Create owner access
        await ownership_service.create_document_ownership(
            test_db, test_user.id, group_id, Permission.OWNER
        )
        
        # Try to revoke own access
        success = await ownership_service.revoke_access(
            test_db, group_id, test_user.id, test_user.id
        )
        
        assert success is False
    
    async def test_get_document_users(self, ownership_service, test_db, test_user, second_user):
        """Test getting all users with access to a document"""
        group_id = str(uuid4())
        
        # Create multiple accesses
        await ownership_service.create_document_ownership(
            test_db, test_user.id, group_id, Permission.OWNER
        )
        await ownership_service.create_document_ownership(
            test_db, second_user.id, group_id, Permission.EDITOR
        )
        
        # Get all users
        users = await ownership_service.get_document_users(
            test_db, group_id, test_user.id
        )
        
        assert len(users) == 2
        user_ids = {u.user_id for u in users}
        assert test_user.id in user_ids
        assert second_user.id in user_ids
        
        # Check that user info is loaded
        assert all(u.user is not None for u in users)
    
    async def test_get_document_users_no_access(self, ownership_service, test_db, test_user, second_user):
        """Test getting document users when requester has no access"""
        group_id = str(uuid4())
        
        # Create access for second user only
        await ownership_service.create_document_ownership(
            test_db, second_user.id, group_id, Permission.OWNER
        )
        
        # Try to get users as first user (no access)
        users = await ownership_service.get_document_users(
            test_db, group_id, test_user.id
        )
        
        assert users is None