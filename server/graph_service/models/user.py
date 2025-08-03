from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .database import Base


class OAuthProvider(str, Enum):
    GOOGLE = 'google'
    GITHUB = 'github'


class Permission(str, Enum):
    OWNER = 'owner'
    EDITOR = 'editor' 
    VIEWER = 'viewer'


class User(Base):
    __tablename__ = 'users'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255))
    avatar_url = Column(String(500))
    provider = Column(String(50), nullable=False)
    provider_id = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_login_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    
    # Relationships
    sessions = relationship('OAuthSession', back_populates='user', cascade='all, delete-orphan')
    documents = relationship('DocumentOwnership', back_populates='user', cascade='all, delete-orphan')
    
    __table_args__ = (
        UniqueConstraint('provider', 'provider_id', name='_provider_id_uc'),
    )


class OAuthSession(Base):
    __tablename__ = 'oauth_sessions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String)
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = relationship('User', back_populates='sessions')


class DocumentOwnership(Base):
    __tablename__ = 'document_ownership'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    group_id = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    permissions = Column(String(50), default=Permission.OWNER.value)
    
    # Relationships
    user = relationship('User', back_populates='documents')
    
    __table_args__ = (
        UniqueConstraint('user_id', 'group_id', name='_user_group_uc'),
    )