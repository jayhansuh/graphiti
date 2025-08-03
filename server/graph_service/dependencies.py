"""Shared dependencies for the application."""

from typing import Dict

from .config import get_settings


def get_neo4j_config() -> Dict[str, str]:
    """Get Neo4j configuration."""
    settings = get_settings()
    return {
        'uri': settings.neo4j_uri,
        'username': settings.neo4j_user,
        'password': settings.neo4j_password,
        'database': 'neo4j',  # Default database
    }


def get_postgres_config() -> Dict[str, str]:
    """Get PostgreSQL configuration."""
    settings = get_settings()
    return {
        'dsn': settings.postgres_uri,
    }