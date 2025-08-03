import re
from typing import List
from urllib.parse import urlparse

from fastapi import HTTPException, status


def validate_redirect_url(url: str, allowed_hosts: List[str]) -> bool:
    """Validate that redirect URL is to an allowed host"""
    try:
        parsed = urlparse(url)
        # Check if host is in allowed list
        return parsed.hostname in allowed_hosts if parsed.hostname else False
    except Exception:
        return False


def validate_email(email: str) -> bool:
    """Basic email validation"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def sanitize_group_id(group_id: str) -> str:
    """Sanitize group_id to prevent injection attacks"""
    # Allow only alphanumeric, hyphens, and underscores
    if not re.match(r'^[a-zA-Z0-9_-]+$', group_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid group_id format"
        )
    return group_id


class RateLimiter:
    """Simple in-memory rate limiter for auth endpoints"""
    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.attempts = {}
    
    def check_rate_limit(self, key: str) -> bool:
        """Check if rate limit exceeded for a key (e.g., IP address)"""
        from datetime import datetime, timedelta
        
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=self.window_seconds)
        
        # Clean old attempts
        if key in self.attempts:
            self.attempts[key] = [
                attempt for attempt in self.attempts[key]
                if attempt > window_start
            ]
        
        # Check current attempts
        current_attempts = len(self.attempts.get(key, []))
        if current_attempts >= self.max_attempts:
            return False
        
        # Record new attempt
        if key not in self.attempts:
            self.attempts[key] = []
        self.attempts[key].append(now)
        
        return True