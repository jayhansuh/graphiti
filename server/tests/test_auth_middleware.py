import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi import HTTPException

from graph_service.auth import (
    get_current_user,
    get_current_user_required,
    get_current_oauth_user,
    verify_api_key,
)
from graph_service.models.user import User, OAuthProvider
from graph_service.services.oauth_service import OAuthService


class TestAuthMiddleware:
    """Test authentication middleware functions"""
    
    @pytest.fixture
    def mock_settings(self, test_settings):
        """Mock settings for testing"""
        return test_settings
    
    async def test_verify_api_key_valid(self, mock_settings):
        """Test API key verification with valid key"""
        result = await verify_api_key("test-api-key", mock_settings)
        assert result == "test-api-key"
    
    async def test_verify_api_key_invalid(self, mock_settings):
        """Test API key verification with invalid key"""
        with pytest.raises(HTTPException) as exc:
            await verify_api_key("wrong-key", mock_settings)
        assert exc.value.status_code == 401
        assert "Invalid or missing API key" in exc.value.detail
    
    async def test_verify_api_key_no_key_configured(self, mock_settings):
        """Test API key verification when no key is configured"""
        mock_settings.api_key = None
        result = await verify_api_key(None, mock_settings)
        assert result is True
    
    async def test_get_current_user_with_jwt(self, test_db, test_user, mock_settings):
        """Test getting current user with JWT token"""
        # Create JWT token
        oauth_service = OAuthService(mock_settings)
        token, _ = oauth_service.create_jwt_token(test_user.id)
        
        # Test with Bearer token
        user = await get_current_user(
            authorization=f"Bearer {token}",
            api_key=None,
            db=test_db,
            settings=mock_settings
        )
        
        assert isinstance(user, User)
        assert user.id == test_user.id
        assert user.email == test_user.email
    
    async def test_get_current_user_with_api_key(self, test_db, mock_settings):
        """Test getting current user with API key"""
        user = await get_current_user(
            authorization=None,
            api_key="test-api-key",
            db=test_db,
            settings=mock_settings
        )
        
        assert user == 'api_key'
    
    async def test_get_current_user_no_auth(self, test_db, mock_settings):
        """Test getting current user with no authentication"""
        user = await get_current_user(
            authorization=None,
            api_key=None,
            db=test_db,
            settings=mock_settings
        )
        
        assert user is None
    
    async def test_get_current_user_invalid_jwt(self, test_db, mock_settings):
        """Test getting current user with invalid JWT"""
        user = await get_current_user(
            authorization="Bearer invalid-token",
            api_key=None,
            db=test_db,
            settings=mock_settings
        )
        
        assert user is None
    
    async def test_get_current_user_jwt_priority(self, test_db, test_user, mock_settings):
        """Test that JWT takes priority over API key"""
        # Create JWT token
        oauth_service = OAuthService(mock_settings)
        token, _ = oauth_service.create_jwt_token(test_user.id)
        
        # Provide both JWT and API key
        user = await get_current_user(
            authorization=f"Bearer {token}",
            api_key="test-api-key",
            db=test_db,
            settings=mock_settings
        )
        
        # Should return User object (JWT), not 'api_key'
        assert isinstance(user, User)
        assert user.id == test_user.id
    
    async def test_get_current_user_required_with_user(self, test_user):
        """Test required auth with valid user"""
        result = await get_current_user_required(test_user)
        assert result == test_user
    
    async def test_get_current_user_required_with_api_key(self):
        """Test required auth with API key"""
        result = await get_current_user_required('api_key')
        assert result == 'api_key'
    
    async def test_get_current_user_required_no_auth(self):
        """Test required auth with no authentication"""
        with pytest.raises(HTTPException) as exc:
            await get_current_user_required(None)
        
        assert exc.value.status_code == 401
        assert exc.value.detail == "Not authenticated"
        assert exc.value.headers["WWW-Authenticate"] == "Bearer"
    
    async def test_get_current_oauth_user_valid(self, test_user):
        """Test OAuth-only auth with valid user"""
        result = await get_current_oauth_user(test_user)
        assert result == test_user
    
    async def test_get_current_oauth_user_api_key(self):
        """Test OAuth-only auth with API key"""
        with pytest.raises(HTTPException) as exc:
            await get_current_oauth_user('api_key')
        
        assert exc.value.status_code == 401
        assert exc.value.detail == "OAuth authentication required"
    
    async def test_get_current_oauth_user_no_auth(self):
        """Test OAuth-only auth with no authentication"""
        with pytest.raises(HTTPException) as exc:
            await get_current_oauth_user(None)
        
        assert exc.value.status_code == 401
        assert exc.value.detail == "OAuth authentication required"


class TestAuthIntegration:
    """Test authentication integration with endpoints"""
    
    async def test_protected_endpoint_with_jwt(self, client, test_user, test_settings):
        """Test accessing protected endpoint with JWT"""
        # Create JWT token
        oauth_service = OAuthService(test_settings)
        token, _ = oauth_service.create_jwt_token(test_user.id)
        
        # Access stats endpoint (requires auth)
        response = await client.get(
            "/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
    
    async def test_protected_endpoint_with_api_key(self, client):
        """Test accessing protected endpoint with API key"""
        response = await client.get(
            "/stats",
            headers={"X-API-Key": "test-api-key"}
        )
        
        assert response.status_code == 200
    
    async def test_protected_endpoint_no_auth(self, client):
        """Test accessing protected endpoint without auth"""
        response = await client.get("/stats")
        
        assert response.status_code == 401
        assert "Not authenticated" in response.json()["detail"]
    
    async def test_mixed_auth_preference(self, client, test_user, test_settings):
        """Test that JWT is preferred when both auth methods are provided"""
        # Create JWT token
        oauth_service = OAuthService(test_settings)
        token, _ = oauth_service.create_jwt_token(test_user.id)
        
        # Provide both JWT and API key
        response = await client.get(
            "/auth/me",
            headers={
                "Authorization": f"Bearer {token}",
                "X-API-Key": "test-api-key"
            }
        )
        
        # Should authenticate as OAuth user, not API key
        assert response.status_code == 200
        assert response.json()["email"] == test_user.email