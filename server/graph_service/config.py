from functools import lru_cache
from typing import Annotated, Optional, Union

from fastapi import Depends
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore


class Settings(BaseSettings):
    openai_api_key: str
    openai_base_url: Optional[str] = Field(None)
    model_name: Optional[str] = Field(None)
    embedding_model_name: Optional[str] = Field(None)
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    api_key: Optional[str] = Field(None, description='API key for securing endpoints')
    
    # OAuth settings
    google_client_id: Optional[str] = Field(None)
    google_client_secret: Optional[str] = Field(None)
    github_client_id: Optional[str] = Field(None)
    github_client_secret: Optional[str] = Field(None)
    oauth_redirect_base_url: str = Field('http://localhost:8000')
    
    # JWT settings
    jwt_secret_key: str = Field(..., description='Secret key for JWT tokens')
    jwt_algorithm: str = Field('HS256')
    jwt_expiration_hours: int = Field(24)
    
    # Database settings
    postgres_uri: str = Field(..., description='PostgreSQL connection URI for user database')
    
    # Redis settings (optional)
    redis_url: Optional[str] = Field(None, description='Redis URL for session storage')

    model_config = SettingsConfigDict(env_file='.env', extra='ignore')


@lru_cache
def get_settings():
    return Settings()  # type: ignore[call-arg]


ZepEnvDep = Annotated[Settings, Depends(get_settings)]
