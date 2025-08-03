import logging
from typing import Dict, Optional

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from graph_service.config import Settings, get_settings
from graph_service.models.database import get_db
from graph_service.models.user import OAuthProvider
from graph_service.schemas.user import (
    DocumentOwnershipResponse,
    DocumentShareRequest,
    LoginResponse,
    OAuthTokenResponse,
    UserResponse,
)
from graph_service.auth import get_current_oauth_user
from graph_service.models.user import User
from graph_service.services.oauth_service import OAuthService
from graph_service.services.ownership_service import OwnershipService
from graph_service.utils.security import RateLimiter, validate_redirect_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/auth', tags=['authentication'])

# Initialize rate limiter for auth endpoints
auth_rate_limiter = RateLimiter(max_attempts=5, window_seconds=300)


async def get_oauth_service(settings: Settings = Depends(get_settings)) -> OAuthService:
    return OAuthService(settings)


async def get_ownership_service() -> OwnershipService:
    return OwnershipService()


async def get_redis_client(settings: Settings = Depends(get_settings)) -> Optional[redis.Redis]:
    """Get Redis client for state storage"""
    if settings.redis_url:
        return await redis.from_url(settings.redis_url, decode_responses=True)
    return None


@router.post('/{provider}/login', response_model=LoginResponse)
async def login(
    provider: str,
    request: Request,
    oauth_service: OAuthService = Depends(get_oauth_service),
    redis_client: Optional[redis.Redis] = Depends(get_redis_client),
):
    """Initiate OAuth login flow"""
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not auth_rate_limiter.check_rate_limit(f"login:{client_ip}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later."
        )
    
    try:
        # Validate provider
        if provider not in ['google', 'github']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Provider {provider} not supported"
            )
        
        # Get authorization URL
        auth_url, state = await oauth_service.get_authorization_url(provider)
        
        # Store state in Redis if available (for CSRF protection)
        if redis_client:
            await redis_client.setex(f"oauth_state:{state}", 600, provider)  # 10 min expiry
        
        return LoginResponse(authorization_url=auth_url, state=state)
        
    except ValueError as e:
        # Check if this is due to missing credentials
        error_msg = str(e)
        if "not configured" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{provider.title()} OAuth is not configured. Please add {provider.upper()}_CLIENT_ID and {provider.upper()}_CLIENT_SECRET to your .env file. See /docs/OAUTH_SETUP_DETAILED.md for instructions."
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    except Exception as e:
        logger.error(f"Error initiating OAuth login: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate login"
        )


@router.get('/{provider}/callback')
async def oauth_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
    oauth_service: OAuthService = Depends(get_oauth_service),
    redis_client: Optional[redis.Redis] = Depends(get_redis_client),
    settings: Settings = Depends(get_settings),
):
    """Handle OAuth callback"""
    try:
        # Validate state if Redis is available
        if redis_client:
            stored_provider = await redis_client.get(f"oauth_state:{state}")
            if not stored_provider or stored_provider != provider:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid state parameter"
                )
            # Clean up state
            await redis_client.delete(f"oauth_state:{state}")
        
        # Exchange code for token
        token_data = await oauth_service.exchange_code_for_token(provider, code, state)
        access_token = token_data['access_token']
        
        # Get user info
        user_info = await oauth_service.get_user_info(provider, access_token)
        
        # Create or update user
        oauth_provider = OAuthProvider(provider)
        user = await oauth_service.create_or_update_user(db, oauth_provider, user_info)
        
        # Create JWT token
        jwt_token, expires_at = oauth_service.create_jwt_token(user.id)
        
        # Store OAuth session
        await oauth_service.create_session(
            db, user, access_token,
            refresh_token=token_data.get('refresh_token'),
            expires_at=expires_at
        )
        
        # Redirect to frontend with token
        redirect_url = f"{settings.oauth_redirect_base_url}/?token={jwt_token}"
        return RedirectResponse(url=redirect_url)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        # Redirect to frontend with error
        redirect_url = f"{settings.oauth_redirect_base_url}/?error=authentication_failed"
        return RedirectResponse(url=redirect_url)


@router.post('/logout')
async def logout(response: Response):
    """Logout user by clearing token cookie"""
    response.delete_cookie('access_token')
    return {'message': 'Logged out successfully'}


@router.get('/me', response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_oauth_user),
):
    """Get current authenticated user"""
    return current_user


# Document ownership endpoints
@router.get('/documents/owned', response_model=list[DocumentOwnershipResponse])
async def get_owned_documents(
    db: AsyncSession = Depends(get_db),
    ownership_service: OwnershipService = Depends(get_ownership_service),
    current_user: User = Depends(get_current_oauth_user),
):
    """Get all documents owned by or shared with the current user"""
    documents = await ownership_service.get_user_documents(db, current_user.id)
    return documents


@router.post('/documents/{group_id}/share', response_model=DocumentOwnershipResponse)
async def share_document(
    group_id: str,
    share_request: DocumentShareRequest,
    db: AsyncSession = Depends(get_db),
    ownership_service: OwnershipService = Depends(get_ownership_service),
    current_user: User = Depends(get_current_oauth_user),
):
    """Share a document with another user"""
    ownership = await ownership_service.share_document(
        db, group_id, current_user.id,
        share_request.user_email, share_request.permissions
    )
    
    if not ownership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot share document - insufficient permissions or user not found"
        )
    
    return ownership


@router.delete('/documents/{group_id}/access/{user_id}')
async def revoke_document_access(
    group_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    ownership_service: OwnershipService = Depends(get_ownership_service),
    current_user: User = Depends(get_current_oauth_user),
):
    """Revoke a user's access to a document"""
    success = await ownership_service.revoke_access(
        db, group_id, current_user.id, user_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot revoke access - insufficient permissions"
        )
    
    return {'message': 'Access revoked successfully'}


@router.get('/documents/{group_id}/users', response_model=list[DocumentOwnershipResponse])
async def get_document_users(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    ownership_service: OwnershipService = Depends(get_ownership_service),
    current_user: User = Depends(get_current_oauth_user),
):
    """Get all users with access to a document"""
    users = await ownership_service.get_document_users(db, group_id, current_user.id)
    
    if users is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this document"
        )
    
    return users