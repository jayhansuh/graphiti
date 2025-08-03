from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from graph_service.config import get_settings

Base = declarative_base()

# Global variables for engine and session maker
_engine: Optional[AsyncEngine] = None
_async_session_maker: Optional[sessionmaker] = None


def get_engine() -> AsyncEngine:
    """Get or create the database engine"""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.postgres_uri,
            echo=False,
            future=True,
            pool_size=10,
            max_overflow=20,
        )
    return _engine


def get_session_maker() -> sessionmaker:
    """Get or create the session maker"""
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_maker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session"""
    async_session_maker = get_session_maker()
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


