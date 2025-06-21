"""
Kiddos - Authentication & Security
Database token authentication, password hashing, and encryption
"""

import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
from passlib.context import CryptContext
from cryptography.fernet import Fernet
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import base64
import logging

from .database import get_db, redis_manager
from .models import User, UserSession
from .config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token extractor
security = HTTPBearer(auto_error=False)


# Custom exceptions
class AuthenticationError(HTTPException):
    """Authentication error with custom handling"""

    def __init__(
        self,
        detail: str = "Authentication failed",
        status_code: int = status.HTTP_401_UNAUTHORIZED,
        headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)


# Field encryption for PII
class FieldEncryption:
    """Handle field-level encryption for PII data"""

    def __init__(self):
        key = settings.ENCRYPTION_KEY.encode()
        try:
            # Validate key length (32 bytes after base64 decoding)
            decoded_key = base64.urlsafe_b64decode(key)
            if len(decoded_key) != 32:
                raise ValueError("Invalid Fernet key length")
            self.fernet = Fernet(key)  # Use the original base64-encoded key
        except Exception as e:
            logger.critical(f"Invalid encryption key: {e}")
            raise RuntimeError("Encryption key configuration error") from e

    def encrypt(self, data: str) -> bytes:
        """Encrypt string data"""
        if not data:
            return b""
        if isinstance(data, str):
            data = data.encode("utf-8")
        return self.fernet.encrypt(data)

    def decrypt(self, encrypted_data: bytes) -> str:
        """Decrypt bytes data"""
        if not encrypted_data:
            return ""
        try:
            if isinstance(encrypted_data, str):
                encrypted_data = encrypted_data.encode("utf-8")
            return self.fernet.decrypt(encrypted_data).decode("utf-8")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return ""

    def hash_for_lookup(self, data: str) -> bytes:
        """Create hash for database lookups (email indexing)"""
        return hashlib.sha256(data.encode("utf-8")).digest()


# Global encryption instance
field_encryption = FieldEncryption()


class AuthService:
    """Authentication service with user management"""

    def __init__(self):
        self.pwd_context = pwd_context
        self.field_encryption = field_encryption

    def create_user(
        self,
        email: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        preferred_language: str = "ar",
        timezone: str = "Asia/Dubai",
        referral_code: Optional[str] = None,
        db: Session = None,
    ) -> User:
        """Create new user account"""
        try:
            # Check if user already exists
            email_hash = field_encryption.hash_for_lookup(email)
            existing_user = db.query(User).filter(User.email_hash == email_hash).first()

            if existing_user:
                raise AuthenticationError(
                    "Email already registered", status.HTTP_400_BAD_REQUEST
                )

            # Create user
            user = User(
                email_encrypted=field_encryption.encrypt(email),
                email_hash=email_hash,
                password_hash=self.pwd_context.hash(password),
                first_name_encrypted=field_encryption.encrypt(first_name)
                if first_name
                else None,
                last_name_encrypted=field_encryption.encrypt(last_name)
                if last_name
                else None,
                preferred_language=preferred_language,
                timezone=timezone,
                gdpr_consent=True,
                coppa_consent=True,
            )

            db.add(user)
            db.commit()
            db.refresh(user)

            return user

        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"User creation failed: {e}")
            db.rollback()
            raise AuthenticationError("Failed to create user account")

    def authenticate_user(
        self, email: str, password: str, db: Session
    ) -> Optional[User]:
        """Authenticate user credentials"""
        try:
            email_hash = field_encryption.hash_for_lookup(email)
            user = db.query(User).filter(User.email_hash == email_hash).first()

            if not user or not self.pwd_context.verify(password, user.password_hash):
                return None

            # Update last login
            user.last_login = datetime.utcnow()
            db.commit()

            return user

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return None

    def create_session_token(
        self,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        remember_me: bool = False,
        db: Session = None,
    ) -> Tuple[str, datetime]:
        """Create session token"""
        try:
            # Calculate expiry
            if remember_me:
                expires_at = datetime.utcnow() + timedelta(
                    days=settings.SESSION_EXPIRE_DAYS * 2
                )
            else:
                expires_at = datetime.utcnow() + timedelta(
                    days=settings.SESSION_EXPIRE_DAYS
                )

            # Create session
            session = UserSession(
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                expires_at=expires_at,
            )

            db.add(session)
            db.commit()

            return session.token, expires_at

        except Exception as e:
            logger.error(f"Session creation failed: {e}")
            db.rollback()
            raise AuthenticationError("Failed to create session")

    def verify_session_token(self, token: str, db: Session) -> Optional[User]:
        """Verify session token and return user"""
        try:
            session = (
                db.query(UserSession)
                .filter(UserSession.token == token, UserSession.is_active == True)
                .first()
            )

            if not session or session.is_expired():
                return None

            # Update last used
            session.last_used = datetime.utcnow()
            db.commit()

            # Get user
            user = db.query(User).filter(User.id == session.user_id).first()
            return user if user and user.is_active else None

        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            return None

    def revoke_session(self, token: str, db: Session) -> bool:
        """Revoke session token"""
        try:
            session = db.query(UserSession).filter(UserSession.token == token).first()
            if session:
                session.is_active = False
                db.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Session revocation failed: {e}")
            return False

    def revoke_all_user_sessions(self, user_id: str, db: Session) -> int:
        """Revoke all user sessions"""
        try:
            count = (
                db.query(UserSession)
                .filter(UserSession.user_id == user_id, UserSession.is_active == True)
                .update({"is_active": False})
            )
            db.commit()
            return count
        except Exception as e:
            logger.error(f"Session revocation failed: {e}")
            return 0

    def get_user_sessions(self, user_id: str, db: Session) -> list:
        """Get user's active sessions"""
        try:
            sessions = (
                db.query(UserSession)
                .filter(UserSession.user_id == user_id, UserSession.is_active == True)
                .all()
            )

            return [
                {
                    "id": str(session.id),
                    "ip_address": session.ip_address,
                    "user_agent": session.user_agent,
                    "created_at": session.created_at.isoformat(),
                    "last_used": session.last_used.isoformat(),
                    "expires_at": session.expires_at.isoformat(),
                }
                for session in sessions
            ]
        except Exception as e:
            logger.error(f"Get sessions failed: {e}")
            return []


# Global auth service
auth_service = AuthService()


# Dependency functions
async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Get current user from token"""
    if not credentials or not credentials.credentials:
        return None

    user = auth_service.verify_session_token(credentials.credentials, db)
    return user


async def get_current_active_user(
    current_user: Optional[User] = Depends(get_current_user),
) -> User:
    """Get current active user (required)"""
    if not current_user:
        raise AuthenticationError("Authentication required")

    if not current_user.is_active:
        raise AuthenticationError("Account deactivated")

    return current_user


def get_client_info(request: Request) -> Tuple[Optional[str], Optional[str]]:
    """Extract client IP and user agent"""
    try:
        # Get IP address (check for forwarded headers first)
        ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not ip:
            ip = request.headers.get("X-Real-IP", "")
        if not ip:
            ip = request.client.host if request.client else None

        # Get user agent
        user_agent = request.headers.get("User-Agent", "")

        return ip, user_agent
    except Exception as e:
        logger.error(f"Failed to get client info: {e}")
        return None, None


# Export main components
__all__ = [
    "auth_service",
    "field_encryption",
    "AuthenticationError",
    "get_current_user",
    "get_current_active_user",
    "get_client_info",
]
