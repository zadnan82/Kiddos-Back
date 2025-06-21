"""
Kiddos - User Management Router
Profile management, settings, privacy
"""

import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    UserProfile,
    UserUpdate,
    UserLimits,
    DataExportRequest,
    DataDeletionRequest as DataDeletionSchema,
    SuccessResponse,
)
from ..auth import get_current_active_user, field_encryption
from ..rate_limiter import rate_limit, get_user_rate_limits
from ..models import User, Child, DataDeletionRequest
from ..worker import backup_user_data, delete_user_data

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.get("/profile", response_model=UserProfile)
async def get_user_profile(
    current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    """Get user profile"""
    try:
        children_count = (
            db.query(Child)
            .filter(Child.user_id == current_user.id, Child.is_active == True)
            .count()
        )

        # Decrypt personal information
        email = field_encryption.decrypt(current_user.email_encrypted)
        first_name = None
        last_name = None

        if current_user.first_name_encrypted:
            first_name = field_encryption.decrypt(current_user.first_name_encrypted)
        if current_user.last_name_encrypted:
            last_name = field_encryption.decrypt(current_user.last_name_encrypted)

        return UserProfile(
            id=str(current_user.id),
            email=email,
            first_name=first_name,
            last_name=last_name,
            tier=current_user.tier,
            credits=current_user.credits,
            preferred_language=current_user.preferred_language,
            timezone=current_user.timezone,
            is_verified=current_user.is_verified,
            created_at=current_user.created_at,
            referral_code=current_user.referral_code,
            children_count=children_count,
        )

    except Exception as e:
        logger.error(f"Get profile failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get profile",
        )


@router.put("/profile", response_model=UserProfile)
async def update_user_profile(
    update_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update user profile"""
    try:
        # Update fields
        if update_data.first_name is not None:
            current_user.first_name_encrypted = field_encryption.encrypt(
                update_data.first_name
            )
        if update_data.last_name is not None:
            current_user.last_name_encrypted = field_encryption.encrypt(
                update_data.last_name
            )
        if update_data.preferred_language:
            current_user.preferred_language = update_data.preferred_language
        if update_data.timezone:
            current_user.timezone = update_data.timezone
        if update_data.marketing_consent is not None:
            current_user.marketing_consent = update_data.marketing_consent

        current_user.updated_at = datetime.utcnow()
        db.commit()

        # Return updated profile
        return await get_user_profile(current_user, db)

    except Exception as e:
        logger.error(f"Profile update failed: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile",
        )


@router.get("/limits", response_model=UserLimits)
async def get_user_limits(current_user: User = Depends(get_current_active_user)):
    """Get user rate limits and usage"""
    try:
        limits = await get_user_rate_limits(
            str(current_user.id), current_user.tier.value
        )

        return UserLimits(
            tier=current_user.tier,
            credits=current_user.credits,
            limits={k: v["remaining"] for k, v in limits.items()},
            usage_today={k: v["used"] for k, v in limits.items()},
            next_reset=datetime.utcnow() + timedelta(hours=1),  # Simplified
        )

    except Exception as e:
        logger.error(f"Get limits failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get limits",
        )


@router.post("/export-data", response_model=SuccessResponse)
@rate_limit("api")
async def request_data_export(
    export_request: DataExportRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Request GDPR data export"""
    try:
        # Queue background task for data export
        backup_user_data.delay(str(current_user.id))

        logger.info(f"Data export requested for user {current_user.id}")

        return SuccessResponse(
            message="Data export request submitted. You will receive an email when ready."
        )

    except Exception as e:
        logger.error(f"Data export request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to request data export",
        )


@router.post("/delete-data", response_model=SuccessResponse)
@rate_limit("api")
async def request_data_deletion(
    deletion_request: DataDeletionSchema,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Request GDPR data deletion"""
    try:
        if not deletion_request.confirm_deletion:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Deletion confirmation required",
            )

        # Create deletion request record
        deletion_record = DataDeletionRequest(
            user_id=current_user.id,
            request_type=deletion_request.deletion_type,
            reason=deletion_request.reason,
            status="pending",
        )

        db.add(deletion_record)
        db.commit()

        # Queue background task for data deletion
        delete_user_data.delay(str(current_user.id), deletion_request.deletion_type)

        logger.info(
            f"Data deletion requested for user {current_user.id}: {deletion_request.deletion_type}"
        )

        return SuccessResponse(
            message="Data deletion request submitted and will be processed within 30 days."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Data deletion request failed: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to request data deletion",
        )
