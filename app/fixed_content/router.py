"""
Fixed Content Router - Main Router Module
Contains all API endpoints for fixed content system
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_active_user
from app.rate_limiter import rate_limit
from app.schemas import SuccessResponse, PaginatedResponse
from app.models import User

# Import schemas from this module
from .schemas import (
    SubjectResponse,
    CourseResponse,
    CourseDetailResponse,
    LessonResponse,
    LessonDetailResponse,
    CourseProgressResponse,
    LessonProgressResponse,
    CreditEarningResponse,
    CourseEnrollmentRequest,
    LessonStartRequest,
    LessonCompletionRequest,
    CourseFilters,
    PaginationParams,
    SortParams,
    UserLearningStats,
    LearningDashboard,
)

# Import service from this module
from .service import fixed_content_service

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


# ===============================
# Subject Endpoints
# ===============================


@router.get("/subjects", response_model=List[SubjectResponse])
async def get_subjects(
    language: str = Query("en", regex="^(ar|en)$", description="Response language"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get all available subjects"""
    try:
        subjects = fixed_content_service.get_subjects(
            db=db, language=language, include_course_count=True
        )
        return subjects

    except Exception as e:
        logger.error(f"Get subjects failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve subjects",
        )


@router.get("/subjects/{subject_id}", response_model=SubjectResponse)
async def get_subject(
    subject_id: str,
    language: str = Query("en", regex="^(ar|en)$"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get specific subject details"""
    try:
        subject = fixed_content_service.get_subject_by_id(
            subject_id=subject_id, db=db, language=language
        )

        if not subject:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found"
            )

        return subject

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get subject failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve subject",
        )


# ===============================
# Course Endpoints
# ===============================


@router.get("/courses", response_model=PaginatedResponse)
async def get_courses(
    # Filtering parameters
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
    age_group: Optional[int] = Query(
        None, ge=2, le=12, description="Filter by age group"
    ),
    difficulty_level: Optional[str] = Query(
        None, regex="^(beginner|intermediate|advanced)$"
    ),
    is_featured: Optional[bool] = Query(None, description="Filter featured courses"),
    search: Optional[str] = Query(
        None, min_length=1, max_length=100, description="Search in title/description"
    ),
    # Pagination and sorting
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query(
        "sort_order", regex="^(sort_order|created_at|title|difficulty_level|duration)$"
    ),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    # Language
    language: str = Query("en", regex="^(ar|en)$"),
    # Dependencies
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get courses with filtering, pagination, and sorting"""
    try:
        courses, total = fixed_content_service.get_courses(
            db=db,
            subject_id=subject_id,
            age_group=age_group,
            difficulty_level=difficulty_level,
            is_featured=is_featured,
            search=search,
            language=language,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        # Calculate pagination metadata
        pages = (total + limit - 1) // limit
        has_next = page < pages
        has_prev = page > 1

        return PaginatedResponse(
            items=courses,
            total=total,
            page=page,
            limit=limit,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev,
        )

    except Exception as e:
        logger.error(f"Get courses failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve courses",
        )


@router.get("/courses/{course_id}", response_model=CourseDetailResponse)
async def get_course(
    course_id: str,
    child_id: Optional[str] = Query(None, description="Child ID for progress tracking"),
    language: str = Query("en", regex="^(ar|en)$"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get detailed course information with progress"""
    try:
        course = fixed_content_service.get_course_by_id(
            course_id=course_id,
            db=db,
            user_id=str(current_user.id),
            child_id=child_id,
            language=language,
            include_lessons=True,
        )

        if not course:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Course not found"
            )

        return course

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get course failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve course",
        )


@router.post("/courses/{course_id}/enroll", response_model=CourseProgressResponse)
@rate_limit("api")
async def enroll_in_course(
    course_id: str,
    child_id: Optional[str] = Query(None, description="Child ID for enrollment"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Enroll in a course"""
    try:
        # Check subscription status
        if current_user.tier.value == "free":
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Subscription required to access courses",
            )

        progress = fixed_content_service.enroll_in_course(
            user_id=str(current_user.id), course_id=course_id, child_id=child_id, db=db
        )

        return progress

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Course enrollment failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enroll in course",
        )


# ===============================
# Lesson Endpoints
# ===============================


@router.get("/lessons/{lesson_id}", response_model=LessonDetailResponse)
async def get_lesson(
    lesson_id: str,
    child_id: Optional[str] = Query(None, description="Child ID for progress tracking"),
    language: str = Query("en", regex="^(ar|en)$"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get detailed lesson content with progress"""
    try:
        # Check subscription status
        if current_user.tier.value == "free":
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Subscription required to access lessons",
            )

        lesson = fixed_content_service.get_lesson_by_id(
            lesson_id=lesson_id,
            db=db,
            user_id=str(current_user.id),
            child_id=child_id,
            language=language,
            include_content=True,
        )

        if not lesson:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found"
            )

        return lesson

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get lesson failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve lesson",
        )


@router.post("/lessons/{lesson_id}/start", response_model=LessonProgressResponse)
@rate_limit("api")
async def start_lesson(
    lesson_id: str,
    child_id: Optional[str] = Query(None, description="Child ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Start a lesson"""
    try:
        # Check subscription status
        if current_user.tier.value == "free":
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Subscription required to access lessons",
            )

        progress = fixed_content_service.start_lesson(
            user_id=str(current_user.id), lesson_id=lesson_id, child_id=child_id, db=db
        )

        return progress

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Start lesson failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start lesson",
        )


@router.post("/lessons/{lesson_id}/complete")
@rate_limit("api")
async def complete_lesson(
    lesson_id: str,
    completion_data: LessonCompletionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Complete a lesson and update progress"""
    try:
        # Check subscription status
        if current_user.tier.value == "free":
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Subscription required to complete lessons",
            )

        result = fixed_content_service.complete_lesson(
            user_id=str(current_user.id),
            lesson_id=lesson_id,
            child_id=completion_data.child_id,
            score=completion_data.score,
            time_spent_minutes=completion_data.time_spent_minutes,
            responses=completion_data.responses,
            db=db,
        )

        return SuccessResponse(message="Lesson completed successfully", data=result)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Complete lesson failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete lesson",
        )


# ===============================
# Progress Tracking Endpoints
# ===============================


@router.get("/progress/courses", response_model=List[CourseProgressResponse])
async def get_user_course_progress(
    child_id: Optional[str] = Query(None, description="Filter by child ID"),
    status: Optional[str] = Query(None, regex="^(not_started|in_progress|completed)$"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get user's course progress"""
    try:
        from .models import UserCourseProgress, CompletionStatus

        # Build query
        query = db.query(UserCourseProgress).filter(
            UserCourseProgress.user_id == current_user.id
        )

        if child_id:
            query = query.filter(UserCourseProgress.child_id == child_id)

        if status:
            query = query.filter(UserCourseProgress.status == CompletionStatus(status))

        progress_list = query.order_by(
            UserCourseProgress.last_accessed_at.desc().nullslast()
        ).all()

        return [progress.to_dict() for progress in progress_list]

    except Exception as e:
        logger.error(f"Get course progress failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve course progress",
        )


@router.get("/progress/courses/{course_id}", response_model=CourseProgressResponse)
async def get_course_progress(
    course_id: str,
    child_id: Optional[str] = Query(None, description="Child ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get specific course progress"""
    try:
        progress = fixed_content_service.get_course_progress(
            user_id=str(current_user.id), course_id=course_id, child_id=child_id, db=db
        )

        if not progress:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course progress not found",
            )

        return progress

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get course progress failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve course progress",
        )


# ===============================
# Credit Management Endpoints
# ===============================


@router.get("/credits/monthly", response_model=CreditEarningResponse)
async def get_monthly_credits(
    current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    """Get current month's credit earning status"""
    try:
        credit_status = fixed_content_service.get_monthly_credit_status(
            user_id=str(current_user.id), db=db
        )

        return credit_status

    except Exception as e:
        logger.error(f"Get monthly credits failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve credit status",
        )


@router.get("/credits/history")
async def get_credit_history(
    months: int = Query(12, ge=1, le=24, description="Number of months to retrieve"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get credit earning history"""
    try:
        from .models import UserCreditEarning
        from datetime import datetime, timedelta

        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=months * 31)  # Approximate

        # Get credit history
        history = (
            db.query(UserCreditEarning)
            .filter(
                UserCreditEarning.user_id == current_user.id,
                UserCreditEarning.created_at >= start_date,
            )
            .order_by(UserCreditEarning.year.desc(), UserCreditEarning.month.desc())
            .all()
        )

        return {
            "history": [earning.to_dict() for earning in history],
            "total_credits_earned": sum(
                earning.credits_earned_total for earning in history
            ),
            "total_courses_completed": sum(
                earning.courses_completed for earning in history
            ),
            "months_retrieved": len(history),
        }

    except Exception as e:
        logger.error(f"Get credit history failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve credit history",
        )


# ===============================
# Dashboard & Analytics Endpoints
# ===============================


@router.get("/dashboard", response_model=LearningDashboard)
async def get_learning_dashboard(
    language: str = Query("en", regex="^(ar|en)$"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get comprehensive learning dashboard"""
    try:
        dashboard = fixed_content_service.get_user_dashboard(
            user_id=str(current_user.id), db=db, language=language
        )

        return dashboard

    except Exception as e:
        logger.error(f"Get dashboard failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard",
        )


@router.get("/stats", response_model=UserLearningStats)
async def get_learning_stats(
    child_id: Optional[str] = Query(None, description="Child ID for specific stats"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get detailed learning statistics"""
    try:
        stats = fixed_content_service.get_user_learning_stats(
            user_id=str(current_user.id), child_id=child_id, db=db
        )

        return stats

    except Exception as e:
        logger.error(f"Get learning stats failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve learning statistics",
        )


# ===============================
# Recommendations & Search
# ===============================


@router.get("/recommendations", response_model=List[CourseResponse])
async def get_course_recommendations(
    child_id: Optional[str] = Query(
        None, description="Child ID for personalized recommendations"
    ),
    limit: int = Query(5, ge=1, le=20, description="Number of recommendations"),
    language: str = Query("en", regex="^(ar|en)$"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get personalized course recommendations"""
    try:
        # Simple recommendation logic - can be enhanced with ML later
        from .models import Course, UserCourseProgress, Subject
        from app.models import Child

        # Get child's age if specified
        age_group = None
        if child_id:
            child = (
                db.query(Child)
                .filter(Child.id == child_id, Child.user_id == current_user.id)
                .first()
            )
            if child:
                age_group = child.age_group

        # Get completed course subjects
        completed_subjects = (
            db.query(Course.subject_id)
            .distinct()
            .join(UserCourseProgress)
            .filter(
                UserCourseProgress.user_id == current_user.id,
                UserCourseProgress.child_id == child_id if child_id else None,
                UserCourseProgress.status == "completed",
            )
            .subquery()
        )

        # Find courses in subjects not yet completed
        query = db.query(Course).filter(
            Course.is_published == True, ~Course.subject_id.in_(completed_subjects)
        )

        # Filter by age group if specified
        if age_group:
            query = query.filter(
                Course.age_group_min <= age_group, Course.age_group_max >= age_group
            )

        # Prioritize featured courses
        recommendations = (
            query.order_by(Course.is_featured.desc(), Course.sort_order.asc())
            .limit(limit)
            .all()
        )

        return [course.to_dict(language) for course in recommendations]

    except Exception as e:
        logger.error(f"Get recommendations failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve recommendations",
        )


@router.get("/search")
async def search_content(
    q: str = Query(..., min_length=2, max_length=100, description="Search query"),
    type: Optional[str] = Query(None, regex="^(courses|lessons|subjects)$"),
    age_group: Optional[int] = Query(None, ge=2, le=12),
    language: str = Query("en", regex="^(ar|en)$"),
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Search across courses, lessons, and subjects"""
    try:
        from .models import Course, Lesson, Subject
        from sqlalchemy import or_

        results = {"courses": [], "lessons": [], "subjects": []}
        search_term = f"%{q}%"

        # Search courses
        if not type or type == "courses":
            course_query = db.query(Course).filter(
                Course.is_published == True,
                or_(
                    Course.title_en.ilike(search_term),
                    Course.title_ar.ilike(search_term),
                    Course.description_en.ilike(search_term),
                    Course.description_ar.ilike(search_term),
                ),
            )

            if age_group:
                course_query = course_query.filter(
                    Course.age_group_min <= age_group, Course.age_group_max >= age_group
                )

            courses = course_query.limit(limit).all()
            results["courses"] = [course.to_dict(language) for course in courses]

        # Search lessons
        if not type or type == "lessons":
            lesson_query = db.query(Lesson).filter(
                Lesson.is_published == True,
                or_(
                    Lesson.title_en.ilike(search_term),
                    Lesson.title_ar.ilike(search_term),
                    Lesson.description_en.ilike(search_term),
                    Lesson.description_ar.ilike(search_term),
                ),
            )

            lessons = lesson_query.limit(limit).all()
            results["lessons"] = [
                lesson.to_dict(language, include_content=False) for lesson in lessons
            ]

        # Search subjects
        if not type or type == "subjects":
            subject_query = db.query(Subject).filter(
                Subject.is_active == True,
                or_(
                    Subject.display_name_en.ilike(search_term),
                    Subject.display_name_ar.ilike(search_term),
                    Subject.description_en.ilike(search_term),
                    Subject.description_ar.ilike(search_term),
                ),
            )

            subjects = subject_query.limit(limit).all()
            results["subjects"] = [subject.to_dict(language) for subject in subjects]

        return {
            "query": q,
            "results": results,
            "total_found": sum(len(results[key]) for key in results),
        }

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Search failed"
        )


# ===============================
# Health Check
# ===============================


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check for fixed content system"""
    try:
        from .models import Subject, Course, Lesson

        # Check database connectivity
        subject_count = db.query(Subject).count()
        course_count = db.query(Course).filter(Course.is_published == True).count()
        lesson_count = db.query(Lesson).filter(Lesson.is_published == True).count()

        return {
            "status": "healthy",
            "timestamp": "2024-12-21T10:00:00Z",
            "database": "connected",
            "content_stats": {
                "subjects": subject_count,
                "published_courses": course_count,
                "published_lessons": lesson_count,
            },
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": "2024-12-21T10:00:00Z",
            "database": "error",
            "error": str(e),
        }


# Export the router
__all__ = ["router"]
