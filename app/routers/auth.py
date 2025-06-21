"""
Kiddos - Authentication Router
Login, registration, logout endpoints
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import UserRegister, UserLogin, TokenResponse, SuccessResponse
from ..auth import auth_service, get_current_user, get_client_info
from ..rate_limiter import rate_limit, ip_rate_limit
from ..worker import send_email_notification
from ..models import User

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.post("/register", response_model=TokenResponse)
@ip_rate_limit("registration", 3, 86400)  # 3 registrations per day per IP
async def register(
    user_data: UserRegister, request: Request, db: Session = Depends(get_db)
):
    """Register new user account"""
    try:
        ip, user_agent = get_client_info(request)

        # Create user
        user = auth_service.create_user(
            email=user_data.email,
            password=user_data.password,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            preferred_language=user_data.preferred_language,
            timezone=user_data.timezone,
            referral_code=user_data.referral_code,
            db=db,
        )

        # Create session
        token, expires_at = auth_service.create_session_token(
            user_id=str(user.id),
            ip_address=ip,
            user_agent=user_agent,
            remember_me=False,
            db=db,
        )

        # Send welcome email
        send_email_notification.delay(
            email=user_data.email,
            template="welcome",
            context={"first_name": user_data.first_name, "credits": user.credits},
        )

        logger.info(f"User registered successfully: {user_data.email}")

        return TokenResponse(
            token=token,
            expires_in=int((expires_at - datetime.utcnow()).total_seconds()),
            user=user.to_dict(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        )


@router.post("/login", response_model=TokenResponse)
@rate_limit("login")
async def login(
    credentials: UserLogin, request: Request, db: Session = Depends(get_db)
):
    """User login"""
    try:
        ip, user_agent = get_client_info(request)

        # Authenticate user
        user = auth_service.authenticate_user(
            email=credentials.email, password=credentials.password, db=db
        )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Create session
        token, expires_at = auth_service.create_session_token(
            user_id=str(user.id),
            ip_address=ip,
            user_agent=user_agent,
            remember_me=credentials.remember_me,
            db=db,
        )

        logger.info(f"User logged in: {credentials.email}")

        return TokenResponse(
            token=token,
            expires_in=int((expires_at - datetime.utcnow()).total_seconds()),
            user=user.to_dict(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed"
        )


@router.post("/logout", response_model=SuccessResponse)
async def logout(
    current_user: User = Depends(get_current_user),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """User logout"""
    try:
        # Get token from request
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

            # Revoke session
            auth_service.revoke_session(token, db)

            logger.info(f"User logged out: {current_user.id}")

            return SuccessResponse(message="Logged out successfully")

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid authorization header",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Logout failed"
        )


@router.post("/logout-all", response_model=SuccessResponse)
async def logout_all_devices(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Logout from all devices"""
    try:
        count = auth_service.revoke_all_user_sessions(str(current_user.id), db)

        return SuccessResponse(message=f"Logged out from {count} devices")

    except Exception as e:
        logger.error(f"Logout all failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout all failed",
        )


@router.get("/sessions")
async def get_user_sessions(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get user's active sessions"""
    try:
        sessions = auth_service.get_user_sessions(str(current_user.id), db)
        return {"sessions": sessions}

    except Exception as e:
        logger.error(f"Get sessions failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get sessions",
        )
