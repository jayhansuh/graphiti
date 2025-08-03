import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from uuid import UUID

from authlib.integrations.httpx_client import AsyncOAuth2Client
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from graph_service.config import Settings
from graph_service.models.user import OAuthProvider, OAuthSession, User


class OAuthService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.providers = self._init_providers()
    
    def _init_providers(self) -> Dict[str, Dict[str, str]]:
        """Initialize OAuth provider configurations"""
        providers = {}
        
        if self.settings.google_client_id and self.settings.google_client_secret:
            providers['google'] = {
                'client_id': self.settings.google_client_id,
                'client_secret': self.settings.google_client_secret,
                'authorize_url': 'https://accounts.google.com/o/oauth2/v2/auth',
                'token_url': 'https://oauth2.googleapis.com/token',
                'userinfo_url': 'https://www.googleapis.com/oauth2/v1/userinfo',
                'scope': 'openid email profile',
            }
        
        if self.settings.github_client_id and self.settings.github_client_secret:
            providers['github'] = {
                'client_id': self.settings.github_client_id,
                'client_secret': self.settings.github_client_secret,
                'authorize_url': 'https://github.com/login/oauth/authorize',
                'token_url': 'https://github.com/login/oauth/access_token',
                'userinfo_url': 'https://api.github.com/user',
                'scope': 'user:email',
            }
        
        return providers
    
    def get_redirect_uri(self, provider: str) -> str:
        """Get the redirect URI for a provider"""
        return f"{self.settings.oauth_redirect_base_url}/auth/{provider}/callback"
    
    async def get_authorization_url(self, provider: str) -> Tuple[str, str]:
        """Generate authorization URL and state for OAuth flow"""
        if provider not in self.providers:
            raise ValueError(f"Provider {provider} not configured")
        
        config = self.providers[provider]
        state = secrets.token_urlsafe(32)
        
        client = AsyncOAuth2Client(
            client_id=config['client_id'],
            scope=config['scope'],
            redirect_uri=self.get_redirect_uri(provider),
        )
        
        authorization_url, _ = client.create_authorization_url(
            config['authorize_url'],
            state=state,
        )
        
        return authorization_url, state
    
    async def exchange_code_for_token(
        self, provider: str, code: str, state: str
    ) -> Dict[str, any]:
        """Exchange authorization code for access token"""
        if provider not in self.providers:
            raise ValueError(f"Provider {provider} not configured")
        
        config = self.providers[provider]
        
        client = AsyncOAuth2Client(
            client_id=config['client_id'],
            client_secret=config['client_secret'],
            redirect_uri=self.get_redirect_uri(provider),
        )
        
        token = await client.fetch_token(
            config['token_url'],
            code=code,
            state=state,
        )
        
        return token
    
    async def get_user_info(self, provider: str, access_token: str) -> Dict[str, any]:
        """Fetch user information from OAuth provider"""
        if provider not in self.providers:
            raise ValueError(f"Provider {provider} not configured")
        
        config = self.providers[provider]
        
        client = AsyncOAuth2Client(token={'access_token': access_token})
        resp = await client.get(config['userinfo_url'])
        resp.raise_for_status()
        
        return resp.json()
    
    async def create_or_update_user(
        self, db: AsyncSession, provider: OAuthProvider, user_info: Dict[str, any]
    ) -> User:
        """Create or update user from OAuth provider info"""
        # Extract user data based on provider
        if provider == OAuthProvider.GOOGLE:
            email = user_info['email']
            name = user_info.get('name')
            avatar_url = user_info.get('picture')
            provider_id = user_info['id']
        elif provider == OAuthProvider.GITHUB:
            email = user_info['email'] or f"{user_info['login']}@users.noreply.github.com"
            name = user_info.get('name') or user_info['login']
            avatar_url = user_info.get('avatar_url')
            provider_id = str(user_info['id'])
        else:
            raise ValueError(f"Unknown provider: {provider}")
        
        # Check if user exists
        stmt = select(User).where(
            User.provider == provider,
            User.provider_id == provider_id
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user:
            # Update existing user
            user.email = email
            user.name = name
            user.avatar_url = avatar_url
            user.last_login_at = datetime.now(timezone.utc)
        else:
            # Create new user
            user = User(
                email=email,
                name=name,
                avatar_url=avatar_url,
                provider=provider,
                provider_id=provider_id,
                last_login_at=datetime.now(timezone.utc),
            )
            db.add(user)
        
        await db.commit()
        await db.refresh(user)
        
        return user
    
    def create_jwt_token(self, user_id: UUID) -> Tuple[str, datetime]:
        """Create JWT token for user session"""
        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=self.settings.jwt_expiration_hours
        )
        
        payload = {
            'sub': str(user_id),
            'exp': expires_at,
            'iat': datetime.now(timezone.utc),
        }
        
        token = jwt.encode(
            payload,
            self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm,
        )
        
        return token, expires_at
    
    async def verify_jwt_token(self, token: str, db: AsyncSession) -> Optional[User]:
        """Verify JWT token and return user"""
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret_key,
                algorithms=[self.settings.jwt_algorithm],
            )
            user_id = UUID(payload.get('sub'))
        except (JWTError, ValueError):
            return None
        
        # Get user from database
        stmt = select(User).where(User.id == user_id, User.is_active == True)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        return user
    
    async def create_session(
        self, db: AsyncSession, user: User, access_token: str, 
        refresh_token: Optional[str] = None, expires_at: Optional[datetime] = None
    ) -> OAuthSession:
        """Create OAuth session for user"""
        session = OAuthSession(
            user_id=user.id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        
        return session