import pytest
from unittest.mock import AsyncMock, patch

from graph_service.models.user import User, OAuthProvider
from graph_service.services.oauth_service import OAuthService


class TestOAuthEndpoints:
    """Test OAuth API endpoints"""
    
    def test_login_endpoint_google(self, client):
        """Test initiating Google OAuth login"""
        response = await client.post("/auth/google/login")
        
        assert response.status_code == 200
        data = response.json()
        assert "authorization_url" in data
        assert "state" in data
        assert "https://example.com/auth" in data["authorization_url"]
    
    async def test_login_endpoint_github(self, client: AsyncClient):
        """Test initiating GitHub OAuth login"""
        response = await client.post("/auth/github/login")
        
        assert response.status_code == 200
        data = response.json()
        assert "authorization_url" in data
        assert "state" in data
    
    async def test_login_endpoint_invalid_provider(self, client: AsyncClient):
        """Test login with invalid provider"""
        response = await client.post("/auth/invalid/login")
        
        assert response.status_code == 400
        assert "not supported" in response.json()["detail"]
    
    async def test_login_rate_limiting(self, client: AsyncClient):
        """Test rate limiting on login endpoint"""
        # Make 5 requests (the limit)
        for _ in range(5):
            response = await client.post("/auth/google/login")
            assert response.status_code == 200
        
        # 6th request should be rate limited
        response = await client.post("/auth/google/login")
        assert response.status_code == 429
        assert "Too many login attempts" in response.json()["detail"]
    
    async def test_oauth_callback_success(self, client: AsyncClient, test_db, mock_oauth_client):
        """Test successful OAuth callback"""
        # Mock user info response
        mock_oauth_client.get.return_value.json.return_value = {
            'id': '12345',
            'email': 'oauth@example.com',
            'name': 'OAuth User',
            'picture': 'https://example.com/photo.jpg'
        }
        mock_oauth_client.get.return_value.raise_for_status = AsyncMock()
        
        response = await client.get(
            "/auth/google/callback",
            params={"code": "test-code", "state": "test-state"}
        )
        
        # Should redirect with token
        assert response.status_code == 307  # Temporary redirect
        assert "token=" in response.headers["location"]
    
    async def test_oauth_callback_error(self, client: AsyncClient, mock_oauth_client):
        """Test OAuth callback with error"""
        # Mock token exchange failure
        mock_oauth_client.fetch_token.side_effect = Exception("OAuth error")
        
        response = await client.get(
            "/auth/google/callback",
            params={"code": "test-code", "state": "test-state"}
        )
        
        # Should redirect with error
        assert response.status_code == 307
        assert "error=authentication_failed" in response.headers["location"]
    
    async def test_get_current_user(self, client: AsyncClient, test_user, test_settings):
        """Test getting current user info"""
        # Create JWT token
        oauth_service = OAuthService(test_settings)
        token, _ = oauth_service.create_jwt_token(test_user.id)
        
        response = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["name"] == test_user.name
        assert data["provider"] == test_user.provider.value
    
    async def test_get_current_user_no_auth(self, client: AsyncClient):
        """Test getting current user without authentication"""
        response = await client.get("/auth/me")
        
        assert response.status_code == 401
        assert "OAuth authentication required" in response.json()["detail"]
    
    async def test_get_current_user_api_key(self, client: AsyncClient):
        """Test that API key auth doesn't work for OAuth endpoints"""
        response = await client.get(
            "/auth/me",
            headers={"X-API-Key": "test-api-key"}
        )
        
        assert response.status_code == 401
        assert "OAuth authentication required" in response.json()["detail"]
    
    async def test_logout(self, client: AsyncClient):
        """Test logout endpoint"""
        response = await client.post("/auth/logout")
        
        assert response.status_code == 200
        assert response.json()["message"] == "Logged out successfully"


class TestDocumentOwnershipEndpoints:
    """Test document ownership API endpoints"""
    
    @pytest.fixture
    async def auth_headers(self, test_user, test_settings):
        """Create auth headers with JWT token"""
        oauth_service = OAuthService(test_settings)
        token, _ = oauth_service.create_jwt_token(test_user.id)
        return {"Authorization": f"Bearer {token}"}
    
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
    
    async def test_get_owned_documents(self, client: AsyncClient, auth_headers, test_db, test_user):
        """Test getting user's owned documents"""
        # Create some document ownerships
        from graph_service.services.ownership_service import OwnershipService
        ownership_service = OwnershipService()
        
        for i in range(3):
            await ownership_service.create_document_ownership(
                test_db, test_user.id, f"group-{i}"
            )
        
        response = await client.get("/auth/documents/owned", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert all("group_id" in doc for doc in data)
        assert all("permissions" in doc for doc in data)
    
    async def test_share_document(self, client: AsyncClient, auth_headers, test_db, test_user, second_user):
        """Test sharing a document"""
        # Create document ownership
        from graph_service.services.ownership_service import OwnershipService
        ownership_service = OwnershipService()
        await ownership_service.create_document_ownership(
            test_db, test_user.id, "test-group"
        )
        
        response = await client.post(
            "/auth/documents/test-group/share",
            headers=auth_headers,
            json={
                "user_email": second_user.email,
                "permissions": "editor"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["group_id"] == "test-group"
        assert data["permissions"] == "editor"
        assert data["user"]["email"] == second_user.email
    
    async def test_share_document_no_permission(self, client: AsyncClient, auth_headers, second_user):
        """Test sharing a document without permission"""
        response = await client.post(
            "/auth/documents/nonexistent-group/share",
            headers=auth_headers,
            json={
                "user_email": second_user.email,
                "permissions": "viewer"
            }
        )
        
        assert response.status_code == 403
        assert "insufficient permissions" in response.json()["detail"].lower()
    
    async def test_revoke_access(self, client: AsyncClient, auth_headers, test_db, test_user, second_user):
        """Test revoking document access"""
        # Create document ownership and share
        from graph_service.services.ownership_service import OwnershipService
        ownership_service = OwnershipService()
        await ownership_service.create_document_ownership(
            test_db, test_user.id, "test-group"
        )
        await ownership_service.share_document(
            test_db, "test-group", test_user.id,
            second_user.email, "viewer"
        )
        
        response = await client.delete(
            f"/auth/documents/test-group/access/{second_user.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert "revoked successfully" in response.json()["message"]
    
    async def test_get_document_users(self, client: AsyncClient, auth_headers, test_db, test_user, second_user):
        """Test getting all users with access to a document"""
        # Create document ownership and share
        from graph_service.services.ownership_service import OwnershipService
        ownership_service = OwnershipService()
        await ownership_service.create_document_ownership(
            test_db, test_user.id, "test-group"
        )
        await ownership_service.share_document(
            test_db, "test-group", test_user.id,
            second_user.email, "editor"
        )
        
        response = await client.get(
            "/auth/documents/test-group/users",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        emails = {u["user"]["email"] for u in data}
        assert test_user.email in emails
        assert second_user.email in emails
    
    async def test_endpoints_require_oauth(self, client: AsyncClient):
        """Test that all document endpoints require OAuth (not API key)"""
        api_key_headers = {"X-API-Key": "test-api-key"}
        
        endpoints = [
            ("GET", "/auth/documents/owned"),
            ("POST", "/auth/documents/test/share"),
            ("DELETE", "/auth/documents/test/access/123"),
            ("GET", "/auth/documents/test/users"),
        ]
        
        for method, endpoint in endpoints:
            if method == "GET":
                response = await client.get(endpoint, headers=api_key_headers)
            elif method == "POST":
                response = await client.post(
                    endpoint,
                    headers=api_key_headers,
                    json={"user_email": "test@example.com", "permissions": "viewer"}
                )
            elif method == "DELETE":
                response = await client.delete(endpoint, headers=api_key_headers)
            
            assert response.status_code == 401
            assert "OAuth authentication required" in response.json()["detail"]