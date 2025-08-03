from typing import Optional, Union

from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings, get_settings
from .models.database import get_db
from .models.user import User
from .services.oauth_service import OAuthService

API_KEY_NAME = 'X-API-Key'
_api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
_bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_key(api_key: str = Security(_api_key_header), settings=Depends(get_settings)):
    expected = settings.api_key
    if expected is None:
        return True
    if api_key == expected:
        return api_key
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid or missing API key')


async def get_current_user(
    authorization: Optional[str] = Header(None),
    api_key: Optional[str] = Security(_api_key_header),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Optional[Union[User, str]]:
    """
    Get current user from JWT token or API key.
    Returns User object for OAuth users, or 'api_key' string for API key auth.
    """
    # Check JWT token first
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        oauth_service = OAuthService(settings)
        user = await oauth_service.verify_jwt_token(token, db)
        if user:
            return user
    
    # Fall back to API key
    if api_key and settings.api_key and api_key == settings.api_key:
        return 'api_key'
    
    return None


async def get_current_user_required(
    current_user: Optional[Union[User, str]] = Depends(get_current_user)
) -> Union[User, str]:
    """Require authenticated user (either OAuth or API key)"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


async def get_current_oauth_user(
    current_user: Optional[Union[User, str]] = Depends(get_current_user)
) -> User:
    """Require OAuth authenticated user (not API key)"""
    if not current_user or isinstance(current_user, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OAuth authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user
