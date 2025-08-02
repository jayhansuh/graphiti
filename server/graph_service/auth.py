from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from .config import get_settings

API_KEY_NAME = 'X-API-Key'
_api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def verify_api_key(api_key: str = Security(_api_key_header), settings=Depends(get_settings)):
    expected = settings.api_key
    if expected is None:
        return True
    if api_key == expected:
        return api_key
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid or missing API key')
