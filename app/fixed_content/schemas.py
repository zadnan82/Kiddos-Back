"""
Fixed Content Schemas - API Request/Response Models
Pydantic schemas for fixed content courses, lessons, and progress tracking
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from enum import Enum

from .models import SubjectCategory, DifficultyLevel, LessonType, CompletionStatus


# ===============================
# Enum Schemas
# ===============================


class SubjectCategoryEnum(str, Enum):
    """Subject categories for API"""

    MATH = "math"
    SCIENCE = "science"
    LANGUAGE_ARTS = "language_arts"
    GEOGRAPHY = "geography"
    ART = "art"
    MUSIC = "music"
    HEALTH = "health"
    SOCIAL_STUDIES = "social_studies"


class DifficultyLevelEnum(str, Enum):
    """Difficulty levels for API"""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class LessonTypeEnum(str, Enum):
    """Lesson types for API"""

    STORY = "story"
    QUIZ = "quiz"
    WORKSHEET = "worksheet"
    ACTIVITY = "activity"
    VIDEO = "video"
    INTERACTIVE = "interactive"


class CompletionStatusEnum(str, Enum):
    """Completion status for API"""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


# ===============================
# Subject Schemas
# ===============================


class SubjectBase(BaseModel):
    """Base subject schema"""

    name: str = Field(..., min_length=1, max_length=100)
    category: SubjectCategoryEnum
    display_name_en: str = Field(..., min_length=1, max_length=100)
    display_name_ar: str = Field(..., min_length=1, max_length=100)
    description_en: Optional[str] = Field(None, max_length=1000)
    description_ar: Optional[str] = Field(None, max_length=1000)
    icon_name: Optional[str] = Field(None, max_length=50)
    color_code: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    sort_order: int = Field(0, ge=0)


class SubjectCreate(SubjectBase):
    """Create subject schema"""

    pass


class SubjectUpdate(BaseModel):
    """Update subject schema"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[SubjectCategoryEnum] = None
    display_name_en: Optional[str] = Field(None, min_length=1, max_length=100)
    display_name_ar: Optional[str] = Field(None, min_length=1, max_length=100)
    description_en: Optional[str] = Field(None, max_length=1000)
    description_ar: Optional[str] = Field(None, max_length=1000)
    icon_name: Optional[str] = Field(None, max_length=50)
    color_code: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    sort_order: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class SubjectResponse(BaseModel):
    """Subject response schema"""

    id: str
    name: str
    category: SubjectCategoryEnum
    display_name: str
    description: Optional[str]
    icon_name: Optional[str]
    color_code: Optional[str]
    sort_order: int
    is_active: bool
    course_count: Optional[int] = None

    model_config = {"from_attributes": True}


# ===============================
# Course Schemas
# ===============================


class CourseBase(BaseModel):
    """Base course schema"""

    subject_id: str = Field(..., description="Subject UUID")
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(
        ..., min_length=1, max_length=250, description="URL-friendly name"
    )
    title_en: str = Field(..., min_length=1, max_length=200)
    title_ar: str = Field(..., min_length=1, max_length=200)
    description_en: Optional[str] = Field(None, max_length=2000)
    description_ar: Optional[str] = Field(None, max_length=2000)
    age_group_min: int = Field(..., ge=2, le=12)
    age_group_max: int = Field(..., ge=2, le=12)
    difficulty_level: DifficultyLevelEnum
    estimated_duration_minutes: int = Field(..., gt=0, le=600)
    prerequisite_course_id: Optional[str] = Field(
        None, description="Prerequisite course UUID"
    )
    credit_reward: float = Field(0.5, ge=0, le=5.0)
    xp_reward: int = Field(100, ge=0, le=1000)
    is_featured: bool = Field(False)
    sort_order: int = Field(0, ge=0)

    @field_validator("age_group_max")
    @classmethod
    def validate_age_range(cls, v, info):
        """Validate age range"""
        if "age_group_min" in info.data and v < info.data["age_group_min"]:
            raise ValueError("age_group_max must be >= age_group_min")
        return v

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v):
        """Validate slug format"""
        import re

        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError(
                "Slug must contain only lowercase letters, numbers, and hyphens"
            )
        return v


class CourseCreate(CourseBase):
    """Create course schema"""

    pass


class CourseUpdate(BaseModel):
    """Update course schema"""

    subject_id: Optional[str] = None
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    slug: Optional[str] = Field(None, min_length=1, max_length=250)
    title_en: Optional[str] = Field(None, min_length=1, max_length=200)
    title_ar: Optional[str] = Field(None, min_length=1, max_length=200)
    description_en: Optional[str] = Field(None, max_length=2000)
    description_ar: Optional[str] = Field(None, max_length=2000)
    age_group_min: Optional[int] = Field(None, ge=2, le=12)
    age_group_max: Optional[int] = Field(None, ge=2, le=12)
    difficulty_level: Optional[DifficultyLevelEnum] = None
    estimated_duration_minutes: Optional[int] = Field(None, gt=0, le=600)
    prerequisite_course_id: Optional[str] = None
    credit_reward: Optional[float] = Field(None, ge=0, le=5.0)
    xp_reward: Optional[int] = Field(None, ge=0, le=1000)
    is_featured: Optional[bool] = None
    is_published: Optional[bool] = None
    sort_order: Optional[int] = Field(None, ge=0)


class CourseResponse(BaseModel):
    """Course response schema"""

    id: str
    subject_id: str
    name: str
    slug: str
    title: str
    description: Optional[str]
    age_group_min: int
    age_group_max: int
    difficulty_level: DifficultyLevelEnum
    estimated_duration_minutes: int
    lesson_count: int
    credit_reward: float
    xp_reward: int
    is_featured: bool
    published_at: Optional[datetime]
    prerequisite_course_id: Optional[str]

    # Progress information (if user is enrolled)
    user_progress: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class CourseDetailResponse(CourseResponse):
    """Detailed course response with lessons"""

    lessons: List[Dict[str, Any]] = []
    subject: Optional[Dict[str, Any]] = None
    prerequisite: Optional[Dict[str, Any]] = None


# ===============================
# Lesson Schemas
# ===============================


class LessonBase(BaseModel):
    """Base lesson schema"""

    course_id: str = Field(..., description="Course UUID")
    lesson_order: int = Field(..., gt=0, le=100)
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=250)
    title_en: str = Field(..., min_length=1, max_length=200)
    title_ar: str = Field(..., min_length=1, max_length=200)
    description_en: Optional[str] = Field(None, max_length=1000)
    description_ar: Optional[str] = Field(None, max_length=1000)
    lesson_type: LessonTypeEnum
    estimated_duration_minutes: int = Field(..., gt=0, le=120)
    content_data: Dict[str, Any] = Field(
        ..., description="Lesson content in JSON format"
    )
    xp_reward: int = Field(20, ge=0, le=100)
    is_required: bool = Field(True)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v):
        """Validate slug format"""
        import re

        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError(
                "Slug must contain only lowercase letters, numbers, and hyphens"
            )
        return v

    @field_validator("content_data")
    @classmethod
    def validate_content_data(cls, v, info):
        """Validate content data based on lesson type"""
        if not isinstance(v, dict):
            raise ValueError("content_data must be a valid JSON object")

        # Basic validation - content must have required fields
        required_fields = ["content", "title"]
        for field in required_fields:
            if field not in v:
                raise ValueError(f"content_data must include '{field}' field")

        # Type-specific validation
        lesson_type = info.data.get("lesson_type")
        if lesson_type == "quiz" and "questions" not in v:
            raise ValueError("Quiz lessons must include 'questions' in content_data")
        elif lesson_type == "worksheet" and "activities" not in v:
            raise ValueError(
                "Worksheet lessons must include 'activities' in content_data"
            )

        return v


class LessonCreate(LessonBase):
    """Create lesson schema"""

    pass


class LessonUpdate(BaseModel):
    """Update lesson schema"""

    course_id: Optional[str] = None
    lesson_order: Optional[int] = Field(None, gt=0, le=100)
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    slug: Optional[str] = Field(None, min_length=1, max_length=250)
    title_en: Optional[str] = Field(None, min_length=1, max_length=200)
    title_ar: Optional[str] = Field(None, min_length=1, max_length=200)
    description_en: Optional[str] = Field(None, max_length=1000)
    description_ar: Optional[str] = Field(None, max_length=1000)
    lesson_type: Optional[LessonTypeEnum] = None
    estimated_duration_minutes: Optional[int] = Field(None, gt=0, le=120)
    content_data: Optional[Dict[str, Any]] = None
    xp_reward: Optional[int] = Field(None, ge=0, le=100)
    is_required: Optional[bool] = None
    is_published: Optional[bool] = None


class LessonResponse(BaseModel):
    """Lesson response schema"""

    id: str
    course_id: str
    lesson_order: int
    name: str
    slug: str
    title: str
    description: Optional[str]
    lesson_type: LessonTypeEnum
    estimated_duration_minutes: int
    xp_reward: int
    is_required: bool

    # Progress information (if user has started)
    user_progress: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class LessonDetailResponse(LessonResponse):
    """Detailed lesson response with content"""

    content: Dict[str, Any]


# ===============================
# Progress Tracking Schemas
# ===============================


class CourseEnrollmentRequest(BaseModel):
    """Course enrollment request"""

    course_id: str = Field(..., description="Course UUID to enroll in")
    child_id: Optional[str] = Field(None, description="Child UUID (optional)")


class LessonStartRequest(BaseModel):
    """Lesson start request"""

    lesson_id: str = Field(..., description="Lesson UUID to start")
    child_id: Optional[str] = Field(None, description="Child UUID (optional)")


class LessonCompletionRequest(BaseModel):
    """Lesson completion request"""

    lesson_id: str = Field(..., description="Lesson UUID to complete")
    child_id: Optional[str] = Field(None, description="Child UUID (optional)")
    score: Optional[float] = Field(
        None, ge=0, le=100, description="Quiz/assessment score"
    )
    time_spent_minutes: int = Field(
        ..., ge=0, le=240, description="Time spent on lesson"
    )
    responses: Optional[Dict[str, Any]] = Field(
        None, description="User responses/answers"
    )

    @field_validator("score")
    @classmethod
    def validate_score(cls, v):
        """Validate score is reasonable"""
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Score must be between 0 and 100")
        return v


class CourseProgressResponse(BaseModel):
    """Course progress response"""

    id: str
    user_id: str
    child_id: Optional[str]
    course_id: str
    status: CompletionStatusEnum
    progress_percentage: float
    lessons_completed: int
    total_lessons: int
    credits_earned: float
    xp_earned: int
    certificate_generated: bool
    total_time_spent_minutes: int
    average_score: Optional[float]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    last_accessed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class LessonProgressResponse(BaseModel):
    """Lesson progress response"""

    id: str
    user_id: str
    child_id: Optional[str]
    lesson_id: str
    course_progress_id: str
    status: CompletionStatusEnum
    attempts: int
    score: Optional[float]
    time_spent_minutes: int
    xp_earned: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    last_accessed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class CreditEarningResponse(BaseModel):
    """Monthly credit earning response"""

    id: str
    user_id: str
    year: int
    month: int
    credits_earned_courses: float
    credits_earned_bonuses: float
    credits_earned_total: float
    monthly_cap: float
    cap_reached: bool
    remaining_credits: float
    courses_completed: int
    subjects_completed: int
    perfect_scores: int

    model_config = {"from_attributes": True}


# ===============================
# Dashboard & Analytics Schemas
# ===============================


class UserLearningStats(BaseModel):
    """User learning statistics"""

    total_courses_enrolled: int
    total_courses_completed: int
    total_lessons_completed: int
    total_credits_earned: float
    total_xp_earned: int
    current_month_credits: float
    current_month_cap: float
    subjects_studied: List[str]
    favorite_subject: Optional[str]
    average_score: Optional[float]
    total_time_spent_hours: float
    current_streak: int  # Days of consecutive activity


class ChildLearningStats(BaseModel):
    """Child-specific learning statistics"""

    child_id: str
    child_name: str
    age_group: int
    total_courses_completed: int
    total_lessons_completed: int
    total_xp_earned: int
    favorite_subjects: List[str]
    recent_achievements: List[Dict[str, Any]]
    current_courses: List[Dict[str, Any]]
    learning_streak: int


class LearningDashboard(BaseModel):
    """Complete learning dashboard"""

    user_stats: UserLearningStats
    children_stats: List[ChildLearningStats]
    recent_activity: List[Dict[str, Any]]
    recommended_courses: List[CourseResponse]
    monthly_progress: Dict[str, Any]


# ===============================
# Filtering & Search Schemas
# ===============================


class CourseFilters(BaseModel):
    """Course filtering parameters"""

    subject_id: Optional[str] = None
    category: Optional[SubjectCategoryEnum] = None
    age_group: Optional[int] = Field(None, ge=2, le=12)
    difficulty_level: Optional[DifficultyLevelEnum] = None
    is_featured: Optional[bool] = None
    search: Optional[str] = Field(None, min_length=1, max_length=100)
    language: str = Field("en", pattern="^(ar|en)$")


class PaginationParams(BaseModel):
    """Pagination parameters"""

    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


class SortParams(BaseModel):
    """Sorting parameters"""

    sort_by: str = Field(
        "sort_order",
        pattern="^(sort_order|created_at|title|difficulty_level|duration)$",
    )
    sort_order: str = Field("asc", pattern="^(asc|desc)$")


# ===============================
# Bulk Operations Schemas
# ===============================


class BulkCourseCreate(BaseModel):
    """Bulk course creation"""

    courses: List[CourseCreate] = Field(..., min_length=1, max_length=50)


class BulkLessonCreate(BaseModel):
    """Bulk lesson creation"""

    course_id: str
    lessons: List[LessonCreate] = Field(..., min_length=1, max_length=20)


# ===============================
# Response Wrappers
# ===============================


class PaginatedResponse(BaseModel):
    """Paginated response wrapper"""

    items: List[Any]
    total: int
    page: int
    limit: int
    pages: int
    has_next: bool
    has_prev: bool


class SuccessResponse(BaseModel):
    """Generic success response"""

    success: bool = True
    message: str
    data: Optional[Any] = None


class ErrorResponse(BaseModel):
    """Error response schema"""

    success: bool = False
    error: str
    detail: Optional[str] = None
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ===============================
# Content Templates
# ===============================


class StoryContent(BaseModel):
    """Story lesson content structure"""

    title: str
    content: str  # The story text
    characters: List[Dict[str, str]] = []
    moral_lesson: Optional[str] = None
    vocabulary_words: List[Dict[str, str]] = []
    discussion_questions: List[str] = []
    image_descriptions: List[str] = []


class QuizContent(BaseModel):
    """Quiz lesson content structure"""

    title: str
    instructions: str
    questions: List[Dict[str, Any]]
    passing_score: int = 70
    max_attempts: int = 3
    feedback_correct: str = "Great job!"
    feedback_incorrect: str = "Try again!"


class WorksheetContent(BaseModel):
    """Worksheet lesson content structure"""

    title: str
    instructions: str
    activities: List[Dict[str, Any]]
    materials_needed: List[str] = []
    estimated_time: int  # minutes
    difficulty_notes: Optional[str] = None


class ActivityContent(BaseModel):
    """Activity lesson content structure"""

    title: str
    description: str
    instructions: List[str]
    materials: List[str] = []
    safety_notes: List[str] = []
    learning_objectives: List[str] = []
    variations: List[Dict[str, str]] = []


# ===============================
# Configuration
# ===============================

# Configure all schemas to forbid extra fields
for schema_class in [
    SubjectCreate,
    SubjectUpdate,
    CourseCreate,
    CourseUpdate,
    LessonCreate,
    LessonUpdate,
    CourseEnrollmentRequest,
    LessonStartRequest,
    LessonCompletionRequest,
    CourseFilters,
]:
    if hasattr(schema_class, "model_config"):
        schema_class.model_config.update({"extra": "forbid"})
    else:
        schema_class.model_config = {"extra": "forbid"}
