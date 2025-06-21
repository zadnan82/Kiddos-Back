"""
Kiddos - Admin Router
Administrative functions, statistics, and management
"""

import logging
from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..schemas import AdminStats, UserManagement, SuccessResponse
from ..auth import get_current_active_user
from ..models import (
    User,
    Child,
    ContentSession,
    ContentStatus,
    CreditTransaction,
    TransactionType,
    UserTier,
)
from ..rate_limiter import reset_user_rate_limits

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


# TODO: Add proper admin authentication in production
# For now, using regular user auth - replace with admin role checking
async def verify_admin_user(current_user: User = Depends(get_current_active_user)):
    """Verify user has admin privileges"""
    # TODO: Add admin role checking
    # For MVP, allow any user to access admin endpoints (NOT for production!)
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return current_user


@router.get("/stats", response_model=AdminStats)
async def get_admin_stats(
    current_user: User = Depends(verify_admin_user), db: Session = Depends(get_db)
):
    """Get admin dashboard statistics"""
    try:
        today = datetime.utcnow().date()

        # Basic stats
        total_users = db.query(User).filter(User.is_active == True).count()
        active_today = (
            db.query(User)
            .filter(User.last_login >= today, User.is_active == True)
            .count()
        )

        content_today = (
            db.query(ContentSession)
            .filter(
                ContentSession.created_at >= today,
                ContentSession.status == ContentStatus.COMPLETED,
            )
            .count()
        )

        # Revenue calculation
        monthly_revenue = (
            db.query(func.sum(CreditTransaction.cost_usd))
            .filter(
                CreditTransaction.transaction_type == TransactionType.PURCHASE,
                CreditTransaction.created_at >= datetime.utcnow().replace(day=1),
                CreditTransaction.status == "completed",
            )
            .scalar()
            or 0
        )

        revenue_usd = monthly_revenue / 100 if monthly_revenue else 0

        # Top content types
        content_type_stats = (
            db.query(
                ContentSession.content_type,
                func.count(ContentSession.id).label("count"),
            )
            .filter(
                ContentSession.status == ContentStatus.COMPLETED,
                ContentSession.created_at >= datetime.utcnow() - timedelta(days=30),
            )
            .group_by(ContentSession.content_type)
            .order_by(func.count(ContentSession.id).desc())
            .limit(5)
            .all()
        )

        top_content_types = [
            {"content_type": ct.value, "count": count}
            for ct, count in content_type_stats
        ]

        # User growth (last 30 days)
        growth_data = (
            db.query(
                func.date(User.created_at).label("date"),
                func.count(User.id).label("count"),
            )
            .filter(User.created_at >= datetime.utcnow() - timedelta(days=30))
            .group_by(func.date(User.created_at))
            .order_by(func.date(User.created_at))
            .all()
        )

        user_growth = [
            {"date": date.isoformat(), "new_users": count}
            for date, count in growth_data
        ]

        # Error rate (simplified calculation)
        total_content_attempts = (
            db.query(ContentSession).filter(ContentSession.created_at >= today).count()
        )

        failed_content = (
            db.query(ContentSession)
            .filter(
                ContentSession.created_at >= today,
                ContentSession.status == ContentStatus.FAILED,
            )
            .count()
        )

        error_rate = (
            (failed_content / total_content_attempts * 100)
            if total_content_attempts > 0
            else 0
        )

        return AdminStats(
            total_users=total_users,
            active_users_today=active_today,
            content_generated_today=content_today,
            revenue_this_month=revenue_usd,
            top_content_types=top_content_types,
            user_growth=user_growth,
            error_rate=round(error_rate, 2),
        )

    except Exception as e:
        logger.error(f"Get admin stats failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get admin statistics",
        )


@router.get("/users", response_model=List[UserManagement])
async def get_users(
    current_user: User = Depends(verify_admin_user),
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Get user management list"""
    try:
        users = (
            db.query(User)
            .filter(User.is_active == True)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        user_list = []
        for user in users:
            # Get user content count
            content_count = (
                db.query(ContentSession)
                .filter(
                    ContentSession.user_id == user.id,
                    ContentSession.status == ContentStatus.COMPLETED,
                )
                .count()
            )

            # Get total spent
            total_spent = (
                db.query(func.sum(CreditTransaction.cost_usd))
                .filter(
                    CreditTransaction.user_id == user.id,
                    CreditTransaction.transaction_type == TransactionType.PURCHASE,
                    CreditTransaction.status == "completed",
                )
                .scalar()
                or 0
            )

            # Decrypt email for admin view
            from ..auth import field_encryption

            email = field_encryption.decrypt(user.email_encrypted)

            user_list.append(
                UserManagement(
                    user_id=str(user.id),
                    email=email,
                    tier=user.tier,
                    credits=user.credits,
                    is_active=user.is_active,
                    created_at=user.created_at,
                    last_login=user.last_login,
                    total_content=content_count,
                    total_spent=total_spent / 100 if total_spent else 0,
                )
            )

        return user_list

    except Exception as e:
        logger.error(f"Get users failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get users",
        )


@router.post("/users/{user_id}/credits", response_model=SuccessResponse)
async def adjust_user_credits(
    user_id: str,
    credits: int,
    reason: str,
    current_user: User = Depends(verify_admin_user),
    db: Session = Depends(get_db),
):
    """Adjust user credits (admin function)"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Update credits
        old_credits = user.credits
        user.credits += credits

        # Prevent negative credits
        if user.credits < 0:
            user.credits = 0

        # Create transaction record
        transaction = CreditTransaction(
            user_id=user.id,
            transaction_type=TransactionType.BONUS
            if credits > 0
            else TransactionType.CONSUMPTION,
            amount=credits,
            description=f"Admin adjustment: {reason}",
            status="completed",
        )

        db.add(transaction)
        db.commit()

        logger.info(
            f"Admin {current_user.id} adjusted credits for user {user_id}: {old_credits} -> {user.credits}"
        )

        return SuccessResponse(
            message=f"Credits adjusted from {old_credits} to {user.credits}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Credit adjustment failed: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to adjust credits",
        )


@router.post("/users/{user_id}/tier", response_model=SuccessResponse)
async def change_user_tier(
    user_id: str,
    new_tier: UserTier,
    current_user: User = Depends(verify_admin_user),
    db: Session = Depends(get_db),
):
    """Change user tier (admin function)"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        old_tier = user.tier
        user.tier = new_tier
        db.commit()

        logger.info(
            f"Admin {current_user.id} changed tier for user {user_id}: {old_tier} -> {new_tier}"
        )

        return SuccessResponse(
            message=f"User tier changed from {old_tier.value} to {new_tier.value}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tier change failed: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change tier",
        )


@router.post("/users/{user_id}/reset-limits", response_model=SuccessResponse)
async def reset_user_limits(
    user_id: str, current_user: User = Depends(verify_admin_user)
):
    """Reset user rate limits (admin function)"""
    try:
        await reset_user_rate_limits(user_id)

        logger.info(f"Admin {current_user.id} reset rate limits for user {user_id}")

        return SuccessResponse(message="Rate limits reset successfully")

    except Exception as e:
        logger.error(f"Rate limit reset failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset rate limits",
        )


@router.get("/content/flagged")
async def get_flagged_content(
    current_user: User = Depends(verify_admin_user),
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Get flagged content for review"""
    try:
        flagged_content = (
            db.query(ContentSession)
            .filter(ContentSession.safety_approved == False)
            .order_by(ContentSession.created_at.desc())
            .limit(limit)
            .all()
        )

        results = []
        for session in flagged_content:
            results.append(
                {
                    "session_id": str(session.id),
                    "topic": session.topic,
                    "age_group": session.age_group,
                    "language": session.language,
                    "status": session.status.value,
                    "moderation_notes": session.moderation_notes,
                    "created_at": session.created_at.isoformat(),
                }
            )

        return {"flagged_content": results}

    except Exception as e:
        logger.error(f"Get flagged content failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get flagged content",
        )


@router.get("/system/health")
async def get_system_health(
    current_user: User = Depends(verify_admin_user), db: Session = Depends(get_db)
):
    """Get detailed system health information"""
    try:
        # Database stats
        total_users = db.query(User).count()
        total_content = db.query(ContentSession).count()

        # Recent errors
        recent_errors = (
            db.query(ContentSession)
            .filter(
                ContentSession.status == ContentStatus.FAILED,
                ContentSession.created_at >= datetime.utcnow() - timedelta(hours=24),
            )
            .count()
        )

        # Queue health (simplified)
        pending_content = (
            db.query(ContentSession)
            .filter(
                ContentSession.status.in_(
                    [ContentStatus.PENDING, ContentStatus.PROCESSING]
                )
            )
            .count()
        )

        return {
            "database": {
                "total_users": total_users,
                "total_content": total_content,
                "status": "healthy",
            },
            "content_generation": {
                "pending_jobs": pending_content,
                "recent_errors": recent_errors,
                "status": "healthy" if recent_errors < 10 else "degraded",
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Get system health failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system health",
        )
