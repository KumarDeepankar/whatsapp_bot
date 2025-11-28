import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict

from ..config import get_settings


class AuthService:
    def __init__(self):
        self.settings = get_settings()
        # In-memory session store (use Redis in production)
        self._sessions: Dict[str, dict] = {}

    def _hash_password(self, password: str) -> str:
        """Simple password hashing"""
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_credentials(self, username: str, password: str) -> bool:
        """Verify username and password against config"""
        return (
            username == self.settings.AUTH_USERNAME and
            password == self.settings.AUTH_PASSWORD
        )

    def create_session(self, username: str) -> str:
        """Create a new session and return session token"""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=self.settings.SESSION_EXPIRE_HOURS)

        self._sessions[token] = {
            "username": username,
            "created_at": datetime.now(),
            "expires_at": expires_at
        }

        return token

    def validate_session(self, token: str) -> Optional[str]:
        """Validate session token and return username if valid"""
        if not token or token not in self._sessions:
            return None

        session = self._sessions[token]

        # Check if session expired
        if datetime.now() > session["expires_at"]:
            del self._sessions[token]
            return None

        return session["username"]

    def destroy_session(self, token: str) -> bool:
        """Destroy a session (logout)"""
        if token in self._sessions:
            del self._sessions[token]
            return True
        return False

    def cleanup_expired_sessions(self):
        """Remove expired sessions"""
        now = datetime.now()
        expired = [
            token for token, session in self._sessions.items()
            if now > session["expires_at"]
        ]
        for token in expired:
            del self._sessions[token]


# Singleton instance
_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
