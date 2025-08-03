import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from jose import jwt
from sqlalchemy import select

from graph_service.models.user import OAuthProvider, User, OAuthSession
from graph_service.services.oauth_service import OAuthService


class TestOAuthService:
    """Test OAuth service functionality"""
    
    @pytest.fixture
    def oauth_service(self, test_settings):
        """Create OAuth service instance"""
        return OAuthService(test_settings)
    
    def test_init_providers(self, oauth_service):
        """Test OAuth provider initialization"""
        assert 'google' in oauth_service.providers
        assert 'github' in oauth_service.providers
        
        google_config = oauth_service.providers['google']
        assert google_config['client_id'] == 'test-google-client'
        assert google_config['client_secret'] == 'test-google-secret'
        assert 'https://accounts.google.com' in google_config['authorize_url']
        
        github_config = oauth_service.providers['github']
        assert github_config['client_id'] == 'test-github-client'
        assert github_config['client_secret'] == 'test-github-secret'
        assert 'https://github.com' in github_config['authorize_url']
    
    def test_get_redirect_uri(self, oauth_service):
        """Test redirect URI generation"""
        assert oauth_service.get_redirect_uri('google') == 'http://testserver/auth/google/callback'
        assert oauth_service.get_redirect_uri('github') == 'http://testserver/auth/github/callback'
    
    async def test_get_authorization_url(self, oauth_service):
        """Test authorization URL generation"""
        auth_url, state = await oauth_service.get_authorization_url('google')
        
        # Check that we got a valid OAuth URL (could be mocked or real)
        assert auth_url is not None
        assert len(auth_url) > 10
        assert state is not None
        assert len(state) > 20  # Should be a secure random string
    
    async def test_get_authorization_url_invalid_provider(self, oauth_service):
        """Test authorization URL with invalid provider"""
        with pytest.raises(ValueError, match="Provider invalid not configured"):
            await oauth_service.get_authorization_url('invalid')
    
    async def test_exchange_code_for_token(self, oauth_service, mock_oauth_client):
        """Test OAuth code exchange"""
        token = await oauth_service.exchange_code_for_token(
            'google', 'test-code', 'test-state'
        )
        
        assert token['access_token'] == 'test-access-token'
        assert token['refresh_token'] == 'test-refresh-token'
        mock_oauth_client.fetch_token.assert_called_once()
    
    async def test_get_user_info_google(self, oauth_service, mock_oauth_client):
        """Test fetching user info from Google"""
        # Set up the mock response
        mock_oauth_client.get.return_value.json = MagicMock(
            return_value={
                'id': '12345',
                'email': 'user@gmail.com',
                'name': 'Google User',
                'picture': 'https://example.com/photo.jpg'
            }
        )
        
        user_info = await oauth_service.get_user_info('google', 'test-token')
        
        assert user_info['email'] == 'user@gmail.com'
        assert user_info['name'] == 'Google User'
        mock_oauth_client.get.assert_called_once()
    
    async def test_get_user_info_github(self, oauth_service, mock_oauth_client):
        """Test fetching user info from GitHub"""
        # Set up the mock response
        mock_oauth_client.get.return_value.json = MagicMock(
            return_value={
                'id': 67890,
                'login': 'githubuser',
                'email': 'user@example.com',
                'name': 'GitHub User',
                'avatar_url': 'https://github.com/avatar.jpg'
            }
        )
        
        user_info = await oauth_service.get_user_info('github', 'test-token')
        
        assert user_info['email'] == 'user@example.com'
        assert user_info['login'] == 'githubuser'
        mock_oauth_client.get.assert_called_once()
    
    async def test_create_new_user_google(self, oauth_service, test_db):
        """Test creating a new user from Google OAuth"""
        user_info = {
            'id': '12345',
            'email': 'newuser@gmail.com',
            'name': 'New Google User',
            'picture': 'https://example.com/photo.jpg'
        }
        
        user = await oauth_service.create_or_update_user(
            test_db, OAuthProvider.GOOGLE, user_info
        )
        
        assert user.email == 'newuser@gmail.com'
        assert user.name == 'New Google User'
        assert user.avatar_url == 'https://example.com/photo.jpg'
        assert user.provider == OAuthProvider.GOOGLE
        assert user.provider_id == '12345'
        assert user.last_login_at is not None
        
        # Verify user was saved
        result = await test_db.execute(
            select(User).where(User.email == 'newuser@gmail.com')
        )
        saved_user = result.scalar_one()
        assert saved_user.id == user.id
    
    async def test_update_existing_user(self, oauth_service, test_db, test_user):
        """Test updating an existing user"""
        user_info = {
            'id': '123456',  # Same as test_user
            'email': 'updated@gmail.com',
            'name': 'Updated Name',
            'picture': 'https://example.com/new-photo.jpg'
        }
        
        user = await oauth_service.create_or_update_user(
            test_db, OAuthProvider.GOOGLE, user_info
        )
        
        assert user.id == test_user.id
        assert user.email == 'updated@gmail.com'
        assert user.name == 'Updated Name'
        assert user.avatar_url == 'https://example.com/new-photo.jpg'
    
    async def test_create_user_github_no_email(self, oauth_service, test_db):
        """Test creating GitHub user without email"""
        user_info = {
            'id': 67890,
            'login': 'githubuser',
            'email': None,  # No email provided
            'name': None,
            'avatar_url': 'https://github.com/avatar.jpg'
        }
        
        user = await oauth_service.create_or_update_user(
            test_db, OAuthProvider.GITHUB, user_info
        )
        
        assert user.email == 'githubuser@users.noreply.github.com'
        assert user.name == 'githubuser'
        assert user.provider_id == '67890'
    
    def test_create_jwt_token(self, oauth_service, test_settings):
        """Test JWT token creation"""
        user_id = uuid4()
        token, expires_at = oauth_service.create_jwt_token(user_id)
        
        # Decode and verify token
        payload = jwt.decode(
            token,
            test_settings.jwt_secret_key,
            algorithms=[test_settings.jwt_algorithm]
        )
        
        assert payload['sub'] == str(user_id)
        assert 'exp' in payload
        assert 'iat' in payload
        
        # Check expiration
        expected_exp = datetime.now(timezone.utc) + timedelta(hours=1)
        assert abs((expires_at - expected_exp).total_seconds()) < 5
    
    async def test_verify_jwt_token_valid(self, oauth_service, test_db, test_user):
        """Test verifying a valid JWT token"""
        token, _ = oauth_service.create_jwt_token(test_user.id)
        
        verified_user = await oauth_service.verify_jwt_token(token, test_db)
        
        assert verified_user is not None
        assert verified_user.id == test_user.id
        assert verified_user.email == test_user.email
    
    async def test_verify_jwt_token_invalid(self, oauth_service, test_db):
        """Test verifying an invalid JWT token"""
        verified_user = await oauth_service.verify_jwt_token('invalid-token', test_db)
        assert verified_user is None
    
    async def test_verify_jwt_token_expired(self, oauth_service, test_db, test_user, test_settings):
        """Test verifying an expired JWT token"""
        # Create expired token
        expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        payload = {
            'sub': str(test_user.id),
            'exp': expires_at,
            'iat': datetime.now(timezone.utc),
        }
        expired_token = jwt.encode(
            payload,
            test_settings.jwt_secret_key,
            algorithm=test_settings.jwt_algorithm,
        )
        
        verified_user = await oauth_service.verify_jwt_token(expired_token, test_db)
        assert verified_user is None
    
    async def test_verify_jwt_token_inactive_user(self, oauth_service, test_db, test_user):
        """Test verifying token for inactive user"""
        # Make user inactive
        test_user.is_active = False
        await test_db.commit()
        
        token, _ = oauth_service.create_jwt_token(test_user.id)
        verified_user = await oauth_service.verify_jwt_token(token, test_db)
        
        assert verified_user is None
    
    async def test_create_session(self, oauth_service, test_db, test_user):
        """Test creating an OAuth session"""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        session = await oauth_service.create_session(
            test_db,
            test_user,
            'test-access-token',
            'test-refresh-token',
            expires_at
        )
        
        assert session.user_id == test_user.id
        assert session.access_token == 'test-access-token'
        assert session.refresh_token == 'test-refresh-token'
        # SQLite might strip timezone info, so compare without timezone
        assert session.expires_at.replace(tzinfo=timezone.utc) == expires_at
        
        # Verify session was saved
        result = await test_db.execute(
            select(OAuthSession).where(OAuthSession.user_id == test_user.id)
        )
        saved_session = result.scalar_one()
        assert saved_session.id == session.id