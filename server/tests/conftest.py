import asyncio
import os
from typing import AsyncGenerator, Generator
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from graph_service.config import Settings
from graph_service.main import app
from graph_service.models.database import Base, get_db
from graph_service.models.user import User, OAuthProvider
from graph_service.zep_graphiti import get_graphiti


# Test database URL - use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings():
    """Override settings for testing"""
    return Settings(
        openai_api_key="test-key",
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="test",
        postgres_uri=TEST_DATABASE_URL,
        jwt_secret_key="test-secret-key-for-testing-only-32chars",
        jwt_algorithm="HS256",
        jwt_expiration_hours=1,
        oauth_redirect_base_url="http://testserver",
        google_client_id="test-google-client",
        google_client_secret="test-google-secret",
        github_client_id="test-github-client",
        github_client_secret="test-github-secret",
        api_key="test-api-key",
    )


@pytest.fixture
async def test_db(test_settings):
    """Create a test database and return a session"""
    # Create test engine
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session factory
    async_session_maker = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session_maker() as session:
        yield session
        await session.rollback()
    
    # Clean up
    await engine.dispose()


@pytest.fixture
async def test_user(test_db: AsyncSession) -> User:
    """Create a test user"""
    user = User(
        email="test@example.com",
        name="Test User",
        provider=OAuthProvider.GOOGLE,
        provider_id="123456",
        is_active=True,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.fixture
def mock_graphiti():
    """Mock Graphiti instance for testing"""
    mock = AsyncMock()
    mock.driver = AsyncMock()
    mock.driver.execute_query = AsyncMock(return_value=([], None, None))
    mock.add_episode = AsyncMock()
    mock.save_entity_node = AsyncMock()
    mock.delete_entity_edge = AsyncMock()
    mock.delete_group = AsyncMock()
    mock.search = AsyncMock(return_value=[])
    mock.get_entity_edge = AsyncMock()
    mock.retrieve_episodes = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def client(test_settings, test_db, mock_graphiti):
    """Create test client with overridden dependencies"""
    # Override dependencies  
    from graph_service.config import get_settings
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_db] = lambda: test_db
    
    # Create async wrapper for graphiti mock
    async def get_mock_graphiti():
        return mock_graphiti
    app.dependency_overrides[get_graphiti] = get_mock_graphiti
    
    with TestClient(app) as client:
        yield client
    
    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def mock_oauth_client(monkeypatch):
    """Mock OAuth client for testing OAuth flows"""
    mock_client_instance = AsyncMock()
    mock_client_instance.create_authorization_url = MagicMock(
        return_value=("https://example.com/auth", "state123")
    )
    mock_client_instance.fetch_token = AsyncMock(
        return_value={
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_in": 3600,
        }
    )
    
    # Mock the response for get requests
    mock_response = AsyncMock()
    mock_response.json = MagicMock(return_value={})
    mock_response.raise_for_status = MagicMock()
    mock_client_instance.get = AsyncMock(return_value=mock_response)
    
    # Create a mock class that returns our instance
    mock_client_class = MagicMock(return_value=mock_client_instance)
    
    # Mock the OAuth client constructor in the OAuth service module
    monkeypatch.setattr(
        "graph_service.services.oauth_service.AsyncOAuth2Client",
        mock_client_class
    )
    
    return mock_client_instance