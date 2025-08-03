from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from graph_service.models.user import OAuthProvider, Permission


class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserCreate(UserBase):
    provider: OAuthProvider
    provider_id: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(UserBase):
    id: UUID
    provider: OAuthProvider
    created_at: datetime
    last_login_at: Optional[datetime] = None
    is_active: bool
    
    model_config = ConfigDict(from_attributes=True)


class DocumentOwnershipBase(BaseModel):
    group_id: str
    permissions: Permission = Permission.OWNER


class DocumentOwnershipCreate(DocumentOwnershipBase):
    user_id: UUID


class DocumentOwnershipResponse(DocumentOwnershipBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    user: Optional[UserResponse] = None
    
    model_config = ConfigDict(from_attributes=True)


class DocumentShareRequest(BaseModel):
    user_email: EmailStr
    permissions: Permission = Permission.VIEWER


class OAuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    expires_in: int
    user: UserResponse


class LoginResponse(BaseModel):
    authorization_url: str
    state: str