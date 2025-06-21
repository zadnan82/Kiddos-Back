"""
Kiddos - Dashboard Router
Parent dashboard, analytics, and usage statistics
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..schemas import DashboardStats, UsageAnalytics
from ..auth import get_current_active_user, field_encryption
from ..models import (
    User,
    Child,
    ContentSession,
    ContentStatus,
    CreditTransaction,
    TransactionType,
)

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.get("", response_model=DashboardStats)
async def get_dashboard(
    current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    """Get parent dashboard statistics"""
    try:
        # Children count
        children_count = (
            db.query(Child)
            .filter(Child.user_id == current_user.id, Child.is_active == True)
            .count()
        )

        # Total content generated
        total_content = (
            db.query(ContentSession)
            .filter(
                ContentSession.user_id == current_user.id,
                ContentSession.status == ContentStatus.COMPLETED,
            )
            .count()
        )

        # Content this week
        week_ago = datetime.utcnow() - timedelta(days=7)
        content_this_week = (
            db.query(ContentSession)
            .filter(
                ContentSession.user_id == current_user.id,
                ContentSession.status == ContentStatus.COMPLETED,
                ContentSession.created_at >= week_ago,
            )
            .count()
        )

        # Favorite topics (top 5)
        topic_stats = (
            db.query(ContentSession.topic, func.count(ContentSession.id).label("count"))
            .filter(
                ContentSession.user_id == current_user.id,
                ContentSession.status == ContentStatus.COMPLETED,
            )
            .group_by(ContentSession.topic)
            .order_by(func.count(ContentSession.id).desc())
            .limit(5)
            .all()
        )

        favorite_topics = [
            {"topic": topic, "count": count} for topic, count in topic_stats
        ]

        # Usage by child
        child_usage = (
            db.query(
                Child.nickname_encrypted,
                func.count(ContentSession.id).label("content_count"),
            )
            .join(ContentSession, Child.id == ContentSession.child_id, isouter=True)
            .filter(Child.user_id == current_user.id, Child.is_active == True)
            .group_by(Child.id, Child.nickname_encrypted)
            .all()
        )

        usage_by_child = []
        for nickname_encrypted, count in child_usage:
            nickname = (
                field_encryption.decrypt(nickname_encrypted)
                if nickname_encrypted
                else "Unknown"
            )
            usage_by_child.append({"child_name": nickname, "content_count": count or 0})

        return DashboardStats(
            children_count=children_count,
            total_content_generated=total_content,
            content_this_week=content_this_week,
            favorite_topics=favorite_topics,
            usage_by_child=usage_by_child,
            credits_remaining=current_user.credits,
            tier=current_user.tier,
        )

    except Exception as e:
        logger.error(f"Get dashboard failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get dashboard data",
        )


@router.get("/analytics", response_model=UsageAnalytics)
async def get_usage_analytics(
    current_user: User = Depends(get_current_active_user),
    days: int = 30,
    db: Session = Depends(get_db),
):
    """Get detailed usage analytics"""
    try:
        start_date = datetime.utcnow() - timedelta(days=days)

        # Daily usage over time
        daily_usage = (
            db.query(
                func.date(ContentSession.created_at).label("date"),
                func.count(ContentSession.id).label("count"),
            )
            .filter(
                ContentSession.user_id == current_user.id,
                ContentSession.status == ContentStatus.COMPLETED,
                ContentSession.created_at >= start_date,
            )
            .group_by(func.date(ContentSession.created_at))
            .order_by(func.date(ContentSession.created_at))
            .all()
        )

        daily_data = [
            {"date": date.isoformat(), "content_count": count}
            for date, count in daily_usage
        ]

        # Popular content types
        content_type_stats = (
            db.query(
                ContentSession.content_type,
                func.count(ContentSession.id).label("count"),
            )
            .filter(
                ContentSession.user_id == current_user.id,
                ContentSession.status == ContentStatus.COMPLETED,
                ContentSession.created_at >= start_date,
            )
            .group_by(ContentSession.content_type)
            .all()
        )

        content_types = [
            {"content_type": content_type.value, "count": count}
            for content_type, count in content_type_stats
        ]

        # Learning progress by child
        progress_data = []
        children = (
            db.query(Child)
            .filter(Child.user_id == current_user.id, Child.is_active == True)
            .all()
        )

        for child in children:
            child_content = (
                db.query(ContentSession)
                .filter(
                    ContentSession.child_id == child.id,
                    ContentSession.status == ContentStatus.COMPLETED,
                    ContentSession.created_at >= start_date,
                )
                .count()
            )

            nickname = (
                field_encryption.decrypt(child.nickname_encrypted)
                if child.nickname_encrypted
                else f"Child {child.age_group}"
            )
            progress_data.append(
                {
                    "child_name": nickname,
                    "content_count": child_content,
                    "age_group": child.age_group,
                }
            )

        # Time patterns (hour of day)
        time_patterns = (
            db.query(
                func.extract("hour", ContentSession.created_at).label("hour"),
                func.count(ContentSession.id).label("count"),
            )
            .filter(
                ContentSession.user_id == current_user.id,
                ContentSession.status == ContentStatus.COMPLETED,
                ContentSession.created_at >= start_date,
            )
            .group_by(func.extract("hour", ContentSession.created_at))
            .all()
        )

        hourly_data = {str(int(hour)): count for hour, count in time_patterns}

        return UsageAnalytics(
            daily_usage=daily_data,
            popular_content_types=content_types,
            learning_progress=progress_data,
            time_patterns=hourly_data,
        )

    except Exception as e:
        logger.error(f"Get analytics failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get analytics data",
        )


@router.get("/summary")
async def get_summary_stats(
    current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    """Get quick summary statistics"""
    try:
        # Quick stats
        total_content = (
            db.query(ContentSession)
            .filter(
                ContentSession.user_id == current_user.id,
                ContentSession.status == ContentStatus.COMPLETED,
            )
            .count()
        )

        total_spent = abs(
            db.query(func.sum(CreditTransaction.amount))
            .filter(
                CreditTransaction.user_id == current_user.id,
                CreditTransaction.transaction_type == TransactionType.CONSUMPTION,
            )
            .scalar()
            or 0
        )

        children_count = (
            db.query(Child)
            .filter(Child.user_id == current_user.id, Child.is_active == True)
            .count()
        )

        # Recent activity
        recent_content = (
            db.query(ContentSession)
            .filter(
                ContentSession.user_id == current_user.id,
                ContentSession.status == ContentStatus.COMPLETED,
            )
            .order_by(ContentSession.created_at.desc())
            .limit(5)
            .all()
        )

        recent_activity = [
            {
                "topic": session.topic,
                "content_type": session.content_type.value,
                "created_at": session.created_at.isoformat(),
                "age_group": session.age_group,
            }
            for session in recent_content
        ]

        return {
            "total_content_generated": total_content,
            "total_credits_spent": total_spent,
            "children_count": children_count,
            "current_credits": current_user.credits,
            "tier": current_user.tier.value,
            "recent_activity": recent_activity,
        }

    except Exception as e:
        logger.error(f"Get summary failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get summary statistics",
        )


@router.get("/insights")
async def get_insights(
    current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    """Get personalized insights and recommendations"""
    try:
        insights = []

        # Credit usage insights
        week_ago = datetime.utcnow() - timedelta(days=7)
        weekly_usage = (
            db.query(func.sum(func.abs(CreditTransaction.amount)))
            .filter(
                CreditTransaction.user_id == current_user.id,
                CreditTransaction.transaction_type == TransactionType.CONSUMPTION,
                CreditTransaction.created_at >= week_ago,
            )
            .scalar()
            or 0
        )

        if weekly_usage > 20:
            insights.append(
                {
                    "type": "high_usage",
                    "message": f"You've used {weekly_usage} credits this week! Consider upgrading to the Family tier for better value.",
                    "action": "upgrade_tier",
                }
            )
        elif weekly_usage == 0:
            insights.append(
                {
                    "type": "low_usage",
                    "message": "Haven't generated content this week? Try our new story templates!",
                    "action": "explore_templates",
                }
            )

        # Content variety insights
        content_types = (
            db.query(ContentSession.content_type, func.count(ContentSession.id))
            .filter(
                ContentSession.user_id == current_user.id,
                ContentSession.status == ContentStatus.COMPLETED,
                ContentSession.created_at >= week_ago,
            )
            .group_by(ContentSession.content_type)
            .all()
        )

        if len(content_types) == 1:
            insights.append(
                {
                    "type": "content_variety",
                    "message": "Try different content types! Mix stories with worksheets for better learning.",
                    "action": "try_new_content",
                }
            )

        # Language insights
        languages = (
            db.query(ContentSession.language)
            .filter(
                ContentSession.user_id == current_user.id,
                ContentSession.status == ContentStatus.COMPLETED,
            )
            .distinct()
            .count()
        )

        if languages == 1 and current_user.preferred_language == "ar":
            insights.append(
                {
                    "type": "language_learning",
                    "message": "Help your child learn English too! Try generating bilingual content.",
                    "action": "try_english",
                }
            )

        return {"insights": insights}

    except Exception as e:
        logger.error(f"Get insights failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get insights",
        )
