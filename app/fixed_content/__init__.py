"""
Fixed Content Module
Separate system for structured courses and lessons
"""

from .models import (
    Subject,
    Course,
    Lesson,
    UserCourseProgress,
    UserLessonProgress,
    UserCreditEarning,
    SubjectCategory,
    DifficultyLevel,
    LessonType,
    CompletionStatus,
    get_monthly_credit_cap,
    get_or_create_monthly_earning,
)

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
    UserLearningStats,
    LearningDashboard,
)

from .service import fixed_content_service
from . import router

__all__ = [
    # Models
    "Subject",
    "Course",
    "Lesson",
    "UserCourseProgress",
    "UserLessonProgress",
    "UserCreditEarning",
    "SubjectCategory",
    "DifficultyLevel",
    "LessonType",
    "CompletionStatus",
    "get_monthly_credit_cap",
    "get_or_create_monthly_earning",
    # Schemas
    "SubjectResponse",
    "CourseResponse",
    "CourseDetailResponse",
    "LessonResponse",
    "LessonDetailResponse",
    "CourseProgressResponse",
    "LessonProgressResponse",
    "CreditEarningResponse",
    "CourseEnrollmentRequest",
    "LessonStartRequest",
    "LessonCompletionRequest",
    "UserLearningStats",
    "LearningDashboard",
    # Service
    "fixed_content_service",
    # Router
    "router",
]
