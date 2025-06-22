"""
Fixed Content Models - Separate from Custom Content System
Database models for structured courses, lessons, and user progress tracking
"""

import uuid
from datetime import datetime, timedelta
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Boolean,
    Text,
    ForeignKey,
    JSON,
    Enum as SQLEnum,
    Index,
    CheckConstraint,
    UniqueConstraint,
    Float,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum

from app.database import Base
from app.config import settings


class SubjectCategory(str, Enum):
    """Subject categories for fixed courses"""

    MATH = "math"
    SCIENCE = "science"
    LANGUAGE_ARTS = "language_arts"
    GEOGRAPHY = "geography"
    ART = "art"
    MUSIC = "music"
    HEALTH = "health"
    SOCIAL_STUDIES = "social_studies"


class DifficultyLevel(str, Enum):
    """Course difficulty levels"""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class LessonType(str, Enum):
    """Types of lessons within courses"""

    STORY = "story"
    QUIZ = "quiz"
    WORKSHEET = "worksheet"
    ACTIVITY = "activity"
    VIDEO = "video"
    INTERACTIVE = "interactive"


class CompletionStatus(str, Enum):
    """Completion status for courses and lessons"""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


# ===============================
# Core Fixed Content Models
# ===============================


class Subject(Base):
    """Subject categories (Math, Science, etc.)"""

    __tablename__ = "subjects"

    # Primary fields
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    category = Column(SQLEnum(SubjectCategory), nullable=False)

    # Display information
    display_name_en = Column(String(100), nullable=False)
    display_name_ar = Column(String(100), nullable=False)
    description_en = Column(Text, nullable=True)
    description_ar = Column(Text, nullable=True)
    icon_name = Column(String(50), nullable=True)  # For UI icons
    color_code = Column(String(7), nullable=True)  # Hex color for theming

    # Metadata
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    courses = relationship(
        "Course", back_populates="subject", cascade="all, delete-orphan"
    )

    # Constraints
    __table_args__ = (
        Index("idx_subject_category_active", "category", "is_active"),
        Index("idx_subject_sort_order", "sort_order"),
    )

    def to_dict(self, language="en"):
        """Convert to dictionary for API responses"""
        return {
            "id": str(self.id),
            "name": self.name,
            "category": self.category.value,
            "display_name": self.display_name_en
            if language == "en"
            else self.display_name_ar,
            "description": self.description_en
            if language == "en"
            else self.description_ar,
            "icon_name": self.icon_name,
            "color_code": self.color_code,
            "sort_order": self.sort_order,
            "is_active": self.is_active,
        }


class Course(Base):
    """Individual courses within subjects"""

    __tablename__ = "courses"

    # Primary fields
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False)

    # Course information
    name = Column(String(200), nullable=False)
    slug = Column(String(250), nullable=False, unique=True)  # URL-friendly name

    # Localized content
    title_en = Column(String(200), nullable=False)
    title_ar = Column(String(200), nullable=False)
    description_en = Column(Text, nullable=True)
    description_ar = Column(Text, nullable=True)

    # Course settings
    age_group_min = Column(Integer, nullable=False)  # 2-12
    age_group_max = Column(Integer, nullable=False)  # 2-12
    difficulty_level = Column(SQLEnum(DifficultyLevel), nullable=False)
    estimated_duration_minutes = Column(Integer, nullable=False)  # Total course time

    # Content metadata
    lesson_count = Column(Integer, default=0, nullable=False)
    prerequisite_course_id = Column(
        UUID(as_uuid=True), ForeignKey("courses.id"), nullable=True
    )

    # Gamification
    credit_reward = Column(
        Float, default=0.5, nullable=False
    )  # Credits earned on completion
    xp_reward = Column(Integer, default=100, nullable=False)  # Experience points

    # Status and visibility
    is_published = Column(Boolean, default=False, nullable=False)
    is_featured = Column(Boolean, default=False, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)

    # Relationships
    subject = relationship("Subject", back_populates="courses")
    lessons = relationship(
        "Lesson",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Lesson.lesson_order",
    )
    prerequisite = relationship("Course", remote_side=[id])
    user_progress = relationship(
        "UserCourseProgress", back_populates="course", cascade="all, delete-orphan"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "age_group_min >= 2 AND age_group_min <= 12", name="check_age_min"
        ),
        CheckConstraint(
            "age_group_max >= 2 AND age_group_max <= 12", name="check_age_max"
        ),
        CheckConstraint("age_group_max >= age_group_min", name="check_age_range"),
        CheckConstraint("credit_reward >= 0", name="check_credit_reward"),
        CheckConstraint("lesson_count >= 0", name="check_lesson_count"),
        Index("idx_course_subject_published", "subject_id", "is_published"),
        Index(
            "idx_course_age_difficulty",
            "age_group_min",
            "age_group_max",
            "difficulty_level",
        ),
        Index("idx_course_featured", "is_featured", "sort_order"),
        UniqueConstraint("subject_id", "slug", name="uq_course_subject_slug"),
    )

    def to_dict(self, language="en", include_lessons=False):
        """Convert to dictionary for API responses"""
        data = {
            "id": str(self.id),
            "subject_id": str(self.subject_id),
            "name": self.name,
            "slug": self.slug,
            "title": self.title_en if language == "en" else self.title_ar,
            "description": self.description_en
            if language == "en"
            else self.description_ar,
            "age_group_min": self.age_group_min,
            "age_group_max": self.age_group_max,
            "difficulty_level": self.difficulty_level.value,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "lesson_count": self.lesson_count,
            "credit_reward": self.credit_reward,
            "xp_reward": self.xp_reward,
            "is_featured": self.is_featured,
            "published_at": self.published_at.isoformat()
            if self.published_at
            else None,
            "prerequisite_course_id": str(self.prerequisite_course_id)
            if self.prerequisite_course_id
            else None,
        }

        if include_lessons and self.lessons:
            data["lessons"] = [lesson.to_dict(language) for lesson in self.lessons]

        return data


class Lesson(Base):
    """Individual lessons within courses"""

    __tablename__ = "lessons"

    # Primary fields
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)

    # Lesson information
    lesson_order = Column(Integer, nullable=False)  # Order within course
    name = Column(String(200), nullable=False)
    slug = Column(String(250), nullable=False)  # URL-friendly name

    # Localized content
    title_en = Column(String(200), nullable=False)
    title_ar = Column(String(200), nullable=False)
    description_en = Column(Text, nullable=True)
    description_ar = Column(Text, nullable=True)

    # Lesson settings
    lesson_type = Column(SQLEnum(LessonType), nullable=False)
    estimated_duration_minutes = Column(Integer, nullable=False)

    # Content storage (JSON)
    content_data = Column(JSON, nullable=False)  # Stores the actual lesson content

    # Gamification
    xp_reward = Column(Integer, default=20, nullable=False)

    # Settings
    is_required = Column(Boolean, default=True, nullable=False)
    is_published = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    course = relationship("Course", back_populates="lessons")
    user_progress = relationship(
        "UserLessonProgress", back_populates="lesson", cascade="all, delete-orphan"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint("lesson_order > 0", name="check_lesson_order"),
        CheckConstraint("estimated_duration_minutes > 0", name="check_duration"),
        CheckConstraint("xp_reward >= 0", name="check_xp_reward"),
        Index("idx_lesson_course_order", "course_id", "lesson_order"),
        Index("idx_lesson_type", "lesson_type"),
        UniqueConstraint("course_id", "lesson_order", name="uq_lesson_course_order"),
        UniqueConstraint("course_id", "slug", name="uq_lesson_course_slug"),
    )

    def to_dict(self, language="en", include_content=True):
        """Convert to dictionary for API responses"""
        data = {
            "id": str(self.id),
            "course_id": str(self.course_id),
            "lesson_order": self.lesson_order,
            "name": self.name,
            "slug": self.slug,
            "title": self.title_en if language == "en" else self.title_ar,
            "description": self.description_en
            if language == "en"
            else self.description_ar,
            "lesson_type": self.lesson_type.value,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "xp_reward": self.xp_reward,
            "is_required": self.is_required,
        }

        if include_content:
            data["content"] = self.content_data

        return data


# ===============================
# User Progress Tracking Models
# ===============================


class UserCourseProgress(Base):
    """Track user progress through courses"""

    __tablename__ = "user_course_progress"

    # Primary fields
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    child_id = Column(UUID(as_uuid=True), ForeignKey("children.id"), nullable=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False)

    # Progress tracking
    status = Column(
        SQLEnum(CompletionStatus), default=CompletionStatus.NOT_STARTED, nullable=False
    )
    progress_percentage = Column(Float, default=0.0, nullable=False)  # 0.0 to 100.0
    lessons_completed = Column(Integer, default=0, nullable=False)
    total_lessons = Column(Integer, nullable=False)

    # Completion data
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    last_accessed_at = Column(DateTime, nullable=True)

    # Rewards tracking
    credits_earned = Column(Float, default=0.0, nullable=False)
    xp_earned = Column(Integer, default=0, nullable=False)
    certificate_generated = Column(Boolean, default=False, nullable=False)

    # Performance metrics
    total_time_spent_minutes = Column(Integer, default=0, nullable=False)
    average_score = Column(Float, nullable=True)  # For quizzes/assessments

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User")
    child = relationship("Child")
    course = relationship("Course", back_populates="user_progress")
    lesson_progress = relationship(
        "UserLessonProgress",
        back_populates="course_progress",
        cascade="all, delete-orphan",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "progress_percentage >= 0 AND progress_percentage <= 100",
            name="check_progress_percentage",
        ),
        CheckConstraint("lessons_completed >= 0", name="check_lessons_completed"),
        CheckConstraint(
            "lessons_completed <= total_lessons", name="check_lessons_vs_total"
        ),
        CheckConstraint("credits_earned >= 0", name="check_credits_earned"),
        CheckConstraint("xp_earned >= 0", name="check_xp_earned"),
        CheckConstraint("total_time_spent_minutes >= 0", name="check_time_spent"),
        Index("idx_user_course_progress", "user_id", "course_id"),
        Index("idx_child_course_progress", "child_id", "course_id"),
        Index("idx_course_status", "course_id", "status"),
        Index("idx_completion_date", "completed_at"),
        UniqueConstraint(
            "user_id", "child_id", "course_id", name="uq_user_child_course"
        ),
    )

    def update_progress(self):
        """Calculate and update progress percentage"""
        if self.total_lessons > 0:
            self.progress_percentage = (
                self.lessons_completed / self.total_lessons
            ) * 100

            if (
                self.progress_percentage >= 100
                and self.status != CompletionStatus.COMPLETED
            ):
                self.status = CompletionStatus.COMPLETED
                self.completed_at = datetime.utcnow()
            elif (
                self.progress_percentage > 0
                and self.status == CompletionStatus.NOT_STARTED
            ):
                self.status = CompletionStatus.IN_PROGRESS
                self.started_at = datetime.utcnow()

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "child_id": str(self.child_id) if self.child_id else None,
            "course_id": str(self.course_id),
            "status": self.status.value,
            "progress_percentage": round(self.progress_percentage, 1),
            "lessons_completed": self.lessons_completed,
            "total_lessons": self.total_lessons,
            "credits_earned": self.credits_earned,
            "xp_earned": self.xp_earned,
            "certificate_generated": self.certificate_generated,
            "total_time_spent_minutes": self.total_time_spent_minutes,
            "average_score": self.average_score,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "last_accessed_at": self.last_accessed_at.isoformat()
            if self.last_accessed_at
            else None,
        }


class UserLessonProgress(Base):
    """Track user progress through individual lessons"""

    __tablename__ = "user_lesson_progress"

    # Primary fields
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    child_id = Column(UUID(as_uuid=True), ForeignKey("children.id"), nullable=True)
    lesson_id = Column(UUID(as_uuid=True), ForeignKey("lessons.id"), nullable=False)
    course_progress_id = Column(
        UUID(as_uuid=True), ForeignKey("user_course_progress.id"), nullable=False
    )

    # Progress tracking
    status = Column(
        SQLEnum(CompletionStatus), default=CompletionStatus.NOT_STARTED, nullable=False
    )
    attempts = Column(Integer, default=0, nullable=False)

    # Performance data
    score = Column(Float, nullable=True)  # Quiz/assessment score (0-100)
    time_spent_minutes = Column(Integer, default=0, nullable=False)
    xp_earned = Column(Integer, default=0, nullable=False)

    # Lesson data storage
    responses = Column(JSON, nullable=True)  # User answers/responses
    feedback = Column(JSON, nullable=True)  # System feedback/corrections

    # Timestamps
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    last_accessed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User")
    child = relationship("Child")
    lesson = relationship("Lesson", back_populates="user_progress")
    course_progress = relationship(
        "UserCourseProgress", back_populates="lesson_progress"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint("attempts >= 0", name="check_attempts"),
        CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)", name="check_score"
        ),
        CheckConstraint("time_spent_minutes >= 0", name="check_time_spent"),
        CheckConstraint("xp_earned >= 0", name="check_xp_earned"),
        Index("idx_user_lesson_progress", "user_id", "lesson_id"),
        Index("idx_child_lesson_progress", "child_id", "lesson_id"),
        Index("idx_course_progress_lesson", "course_progress_id", "lesson_id"),
        Index("idx_lesson_status", "lesson_id", "status"),
        UniqueConstraint(
            "user_id", "child_id", "lesson_id", name="uq_user_child_lesson"
        ),
    )

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "child_id": str(self.child_id) if self.child_id else None,
            "lesson_id": str(self.lesson_id),
            "course_progress_id": str(self.course_progress_id),
            "status": self.status.value,
            "attempts": self.attempts,
            "score": self.score,
            "time_spent_minutes": self.time_spent_minutes,
            "xp_earned": self.xp_earned,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "last_accessed_at": self.last_accessed_at.isoformat()
            if self.last_accessed_at
            else None,
        }


# ===============================
# Credit Tracking Models
# ===============================


class UserCreditEarning(Base):
    """Track monthly credit earnings with caps"""

    __tablename__ = "user_credit_earnings"

    # Primary fields
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Time period tracking
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)  # 1-12

    # Credit tracking
    credits_earned_courses = Column(Float, default=0.0, nullable=False)
    credits_earned_bonuses = Column(Float, default=0.0, nullable=False)
    credits_earned_total = Column(Float, default=0.0, nullable=False)

    # Caps and limits
    monthly_cap = Column(Float, nullable=False)  # Based on user tier
    cap_reached = Column(Boolean, default=False, nullable=False)

    # Activity tracking
    courses_completed = Column(Integer, default=0, nullable=False)
    subjects_completed = Column(Integer, default=0, nullable=False)
    perfect_scores = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User")

    # Constraints
    __table_args__ = (
        CheckConstraint("month >= 1 AND month <= 12", name="check_month"),
        CheckConstraint("year >= 2024", name="check_year"),
        CheckConstraint("credits_earned_courses >= 0", name="check_credits_courses"),
        CheckConstraint("credits_earned_bonuses >= 0", name="check_credits_bonuses"),
        CheckConstraint("credits_earned_total >= 0", name="check_credits_total"),
        CheckConstraint("monthly_cap > 0", name="check_monthly_cap"),
        CheckConstraint("courses_completed >= 0", name="check_courses_completed"),
        Index("idx_user_year_month", "user_id", "year", "month"),
        Index("idx_cap_reached", "cap_reached"),
        UniqueConstraint("user_id", "year", "month", name="uq_user_year_month"),
    )

    def can_earn_credits(self, amount: float) -> bool:
        """Check if user can earn additional credits"""
        return (self.credits_earned_total + amount) <= self.monthly_cap

    def add_credits(self, amount: float, source: str = "course"):
        """Add credits if under cap"""
        if not self.can_earn_credits(amount):
            # Calculate how much can still be earned
            remaining = max(0, self.monthly_cap - self.credits_earned_total)
            amount = min(amount, remaining)

        if amount > 0:
            if source == "course":
                self.credits_earned_courses += amount
            else:
                self.credits_earned_bonuses += amount

            self.credits_earned_total += amount

            if self.credits_earned_total >= self.monthly_cap:
                self.cap_reached = True

        return amount

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "year": self.year,
            "month": self.month,
            "credits_earned_courses": self.credits_earned_courses,
            "credits_earned_bonuses": self.credits_earned_bonuses,
            "credits_earned_total": self.credits_earned_total,
            "monthly_cap": self.monthly_cap,
            "cap_reached": self.cap_reached,
            "remaining_credits": max(0, self.monthly_cap - self.credits_earned_total),
            "courses_completed": self.courses_completed,
            "subjects_completed": self.subjects_completed,
            "perfect_scores": self.perfect_scores,
        }


# ===============================
# Utility Functions
# ===============================


def get_monthly_credit_cap(user_tier: str) -> float:
    """Get monthly credit earning cap based on user tier"""
    caps = {
        "free": 0.0,  # Free users don't earn credits
        "basic": 2.0,  # Basic plan: 2 credits/month
        "family": 3.0,  # Family plan: 3 credits/month
    }
    return caps.get(user_tier, 0.0)


def get_or_create_monthly_earning(
    user_id: str, user_tier: str, db_session
) -> UserCreditEarning:
    """Get or create the current month's credit earning record"""
    now = datetime.utcnow()
    year, month = now.year, now.month

    earning = (
        db_session.query(UserCreditEarning)
        .filter(
            UserCreditEarning.user_id == user_id,
            UserCreditEarning.year == year,
            UserCreditEarning.month == month,
        )
        .first()
    )

    if not earning:
        earning = UserCreditEarning(
            user_id=user_id,
            year=year,
            month=month,
            monthly_cap=get_monthly_credit_cap(user_tier),
        )
        db_session.add(earning)
        db_session.flush()

    return earning
