"""
Kiddos - Database Models (FIXED)
All SQLAlchemy models for the application - Fixed PostgreSQL constraints and foreign keys
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
    LargeBinary,
    JSON,
    Enum as SQLEnum,
    Index,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum
import secrets

from .database import Base
from .config import settings


class UserTier(str, Enum):
    """User subscription tiers"""

    FREE = "free"
    BASIC = "basic"
    FAMILY = "family"


class ContentType(str, Enum):
    """Types of content that can be generated"""

    STORY = "story"
    WORKSHEET = "worksheet"
    QUIZ = "quiz"
    EXERCISE = "exercise"


class ContentStatus(str, Enum):
    """Content generation status"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    APPROVED = "approved"
    REJECTED = "rejected"


class TransactionType(str, Enum):
    """Credit transaction types"""

    PURCHASE = "purchase"
    CONSUMPTION = "consumption"
    REFUND = "refund"
    BONUS = "bonus"
    EXPIRY = "expiry"


class User(Base):
    """Parent/user account"""

    __tablename__ = "users"

    # Primary fields
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_encrypted = Column(LargeBinary, nullable=False)
    email_hash = Column(LargeBinary, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)

    # Personal information (encrypted)
    first_name_encrypted = Column(LargeBinary, nullable=True)
    last_name_encrypted = Column(LargeBinary, nullable=True)

    # Account settings
    tier = Column(SQLEnum(UserTier), default=UserTier.FREE, nullable=False)
    credits = Column(Integer, default=10, nullable=False)
    preferred_language = Column(String(2), default="ar", nullable=False)
    timezone = Column(String(50), default="Asia/Dubai", nullable=False)

    # Status and verification
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    email_verified_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Compliance fields
    gdpr_consent = Column(Boolean, default=False, nullable=False)
    coppa_consent = Column(Boolean, default=False, nullable=False)
    marketing_consent = Column(Boolean, default=False, nullable=False)
    data_retention_until = Column(DateTime, nullable=True)

    # Referral system
    referral_code = Column(String(10), unique=True, nullable=True, index=True)
    referred_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Relationships - FIXED with explicit foreign_keys
    children = relationship(
        "Child", back_populates="parent", cascade="all, delete-orphan"
    )
    sessions = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )
    transactions = relationship(
        "CreditTransaction",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="[CreditTransaction.user_id]",  # FIXED: Explicit foreign key
    )
    content_sessions = relationship(
        "ContentSession", back_populates="user", cascade="all, delete-orphan"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint("credits >= 0", name="check_credits_non_negative"),
        CheckConstraint(
            "preferred_language IN ('ar', 'en', 'fr', 'de')",
            name="check_supported_language",
        ),
        Index("idx_user_tier_active", "tier", "is_active"),
        Index("idx_user_created_at", "created_at"),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.referral_code:
            self.referral_code = self._generate_referral_code()

    def _generate_referral_code(self) -> str:
        """Generate unique referral code"""
        return secrets.token_urlsafe(6).upper()

    def can_generate_content(self, credit_cost: int) -> bool:
        """Check if user has enough credits"""
        return self.credits >= credit_cost

    def to_dict(self, include_sensitive: bool = False) -> dict:
        """Convert to dictionary for API responses"""
        data = {
            "id": str(self.id),
            "tier": self.tier.value,
            "credits": self.credits,
            "preferred_language": self.preferred_language,
            "timezone": self.timezone,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat(),
            "referral_code": self.referral_code,
        }

        if include_sensitive:
            # Only include for data export (GDPR compliance)
            data.update(
                {
                    "last_login": self.last_login.isoformat()
                    if self.last_login
                    else None,
                    "gdpr_consent": self.gdpr_consent,
                    "coppa_consent": self.coppa_consent,
                    "marketing_consent": self.marketing_consent,
                }
            )

        return data


class Child(Base):
    """Child profile managed by parent"""

    __tablename__ = "children"

    # Primary fields
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Child information (encrypted)
    nickname_encrypted = Column(LargeBinary, nullable=True)
    full_name_encrypted = Column(LargeBinary, nullable=True)

    # Learning profile
    age_group = Column(Integer, nullable=False)  # 2-12
    learning_level = Column(String(20), default="beginner", nullable=False)
    interests = Column(
        JSON, default=list, nullable=False
    )  # ["animals", "space", "math"]

    # Preferences
    preferred_language = Column(
        String(2), nullable=True
    )  # Inherits from parent if null
    content_difficulty = Column(String(20), default="age_appropriate", nullable=False)

    # Avatar (no real photos for privacy)
    avatar_id = Column(Integer, default=1, nullable=False)  # 1-20 cartoon avatars

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)

    # Privacy settings
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    parent = relationship("User", back_populates="children")
    content_sessions = relationship(
        "ContentSession", back_populates="child", cascade="all, delete-orphan"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint("age_group >= 2 AND age_group <= 12", name="check_valid_age"),
        CheckConstraint(
            "avatar_id >= 1 AND avatar_id <= 20", name="check_valid_avatar"
        ),
        CheckConstraint(
            "learning_level IN ('beginner', 'intermediate', 'advanced')",
            name="check_learning_level",
        ),
        Index("idx_child_user_age", "user_id", "age_group"),
        Index("idx_child_last_used", "last_used"),
    )

    def get_effective_language(self) -> str:
        """Get language preference (child's or parent's)"""
        return self.preferred_language or self.parent.preferred_language

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "id": str(self.id),
            "age_group": self.age_group,
            "learning_level": self.learning_level,
            "interests": self.interests,
            "preferred_language": self.get_effective_language(),
            "content_difficulty": self.content_difficulty,
            "avatar_id": self.avatar_id,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None,
        }


class UserSession(Base):
    """User authentication sessions (database tokens)"""

    __tablename__ = "user_sessions"

    # Primary fields
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String(64), unique=True, nullable=False, index=True)

    # Session metadata
    ip_address = Column(String(45), nullable=True)  # IPv6 support
    user_agent = Column(Text, nullable=True)
    device_fingerprint = Column(String(64), nullable=True)

    # Status and expiry
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    last_used = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="sessions")

    # Constraints
    __table_args__ = (
        Index("idx_session_token_active", "token", "is_active"),
        Index("idx_session_user_active", "user_id", "is_active"),
        Index("idx_session_expires", "expires_at"),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.expires_at:
            self.expires_at = datetime.utcnow() + timedelta(
                days=settings.SESSION_EXPIRE_DAYS
            )
        if not self.token:
            self.token = secrets.token_urlsafe(48)

    def is_expired(self) -> bool:
        """Check if session is expired"""
        return datetime.utcnow() > self.expires_at

    def extend_session(self, days: int = None) -> None:
        """Extend session expiry"""
        days = days or settings.SESSION_EXPIRE_DAYS
        self.expires_at = datetime.utcnow() + timedelta(days=days)
        self.last_used = datetime.utcnow()


class ContentSession(Base):
    """Content generation sessions with auto-expiry"""

    __tablename__ = "content_sessions"

    # Primary fields
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    child_id = Column(UUID(as_uuid=True), ForeignKey("children.id"), nullable=True)

    # Content details
    content_type = Column(SQLEnum(ContentType), nullable=False)
    status = Column(
        SQLEnum(ContentStatus), default=ContentStatus.PENDING, nullable=False
    )

    # Generation parameters
    prompt_text = Column(Text, nullable=False)
    topic = Column(String(200), nullable=False)
    age_group = Column(Integer, nullable=False)
    language = Column(String(2), nullable=False)
    difficulty_level = Column(String(20), default="age_appropriate", nullable=False)

    # Generated content (encrypted)
    generated_content = Column(LargeBinary, nullable=True)  # Not Text!
    generated_title = Column(String(200), nullable=True)
    content_metadata = Column(JSON, default=dict, nullable=False)

    # Credits and cost
    credits_cost = Column(Integer, nullable=False)
    credits_charged = Column(Boolean, default=False, nullable=False)

    # Content moderation
    safety_approved = Column(Boolean, nullable=True)
    moderation_notes = Column(Text, nullable=True)
    parent_approved = Column(Boolean, nullable=True)

    # Generation tracking
    generation_started_at = Column(DateTime, nullable=True)
    generation_completed_at = Column(DateTime, nullable=True)
    generation_duration_seconds = Column(Integer, nullable=True)

    # Auto-expiry
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    include_images: bool = Column(Boolean, default=False)  # NEW FIELD

    # Relationships
    user = relationship("User", back_populates="content_sessions")
    child = relationship("Child", back_populates="content_sessions")

    # Constraints
    __table_args__ = (
        CheckConstraint("age_group >= 2 AND age_group <= 12", name="check_content_age"),
        CheckConstraint("credits_cost > 0", name="check_positive_cost"),
        CheckConstraint(
            "language IN ('ar', 'en', 'fr', 'de')", name="check_content_language"
        ),
        Index("idx_content_user_status", "user_id", "status"),
        Index("idx_content_expires", "expires_at"),
        Index("idx_content_type_age", "content_type", "age_group"),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.expires_at:
            self.expires_at = datetime.utcnow() + timedelta(
                hours=settings.CONTENT_AUTO_EXPIRE_HOURS
            )

    def is_expired(self) -> bool:
        """Check if content session is expired"""
        return datetime.utcnow() > self.expires_at

    def can_regenerate(self) -> bool:
        """Check if content can be regenerated"""
        return (
            self.status in [ContentStatus.FAILED, ContentStatus.REJECTED]
            and not self.is_expired()
        )

    def __repr__(self):
        return f"<ContentSession(id={self.id}, topic='{self.topic}', status={self.status}, include_images={self.include_images})>"

    @property
    def calculated_cost(self):
        return calculate_content_cost(
            self.content_type.value,
            self.user.tier.value if self.user else "free",
            self.include_images,  # Pass the image option
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "id": str(self.id),
            "content_type": self.content_type.value,
            "status": self.status.value,
            "topic": self.topic,
            "age_group": self.age_group,
            "language": self.language,
            "generated_title": self.generated_title,
            "credits_cost": self.credits_cost,
            "safety_approved": self.safety_approved,
            "parent_approved": self.parent_approved,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "generation_duration_seconds": self.generation_duration_seconds,
        }


class CreditTransaction(Base):
    """Credit purchase and usage tracking"""

    __tablename__ = "credit_transactions"

    # Primary fields
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Transaction details
    transaction_type = Column(SQLEnum(TransactionType), nullable=False)
    amount = Column(
        Integer, nullable=False
    )  # Credits (positive for purchase/bonus, negative for consumption)

    # Payment information
    cost_usd = Column(Integer, nullable=True)  # Cost in cents (for purchases)
    payment_method = Column(String(50), nullable=True)  # stripe, apple_pay, etc.
    stripe_payment_id = Column(String(128), nullable=True, index=True)
    stripe_charge_id = Column(String(128), nullable=True)

    # Content reference
    content_session_id = Column(
        UUID(as_uuid=True), ForeignKey("content_sessions.id"), nullable=True
    )
    content_type = Column(String(50), nullable=True)  # For consumption transactions

    # Transaction metadata
    description = Column(String(500), nullable=True)
    transaction_metadata = Column(
        JSON, default=dict, nullable=False
    )  # Renamed from metadata

    # Status tracking
    status = Column(
        String(20), default="completed", nullable=False
    )  # pending, completed, failed, refunded
    failure_reason = Column(String(500), nullable=True)

    # Referral system
    referral_bonus = Column(Boolean, default=False, nullable=False)
    referred_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)

    # Relationships - FIXED with explicit foreign_keys
    user = relationship("User", back_populates="transactions", foreign_keys=[user_id])
    content_session = relationship("ContentSession")

    # Constraints
    __table_args__ = (
        CheckConstraint("amount != 0", name="check_non_zero_amount"),
        CheckConstraint(
            "(transaction_type = 'PURCHASE' AND amount > 0) OR "
            "(transaction_type = 'CONSUMPTION' AND amount < 0) OR "
            "(transaction_type = 'REFUND') OR "
            "(transaction_type = 'BONUS' AND amount > 0) OR "
            "(transaction_type = 'EXPIRY' AND amount < 0)",
            name="check_transaction_type_amount",
        ),
        Index("idx_transaction_user_type", "user_id", "transaction_type"),
        Index("idx_transaction_stripe", "stripe_payment_id"),
        Index("idx_transaction_created", "created_at"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "id": str(self.id),
            "transaction_type": self.transaction_type.value,
            "amount": self.amount,
            "cost_usd": self.cost_usd / 100
            if self.cost_usd
            else None,  # Convert cents to dollars
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "processed_at": self.processed_at.isoformat()
            if self.processed_at
            else None,
        }


class ContentModeration(Base):
    """Content moderation and safety tracking"""

    __tablename__ = "content_moderation"

    # Primary fields
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content_session_id = Column(
        UUID(as_uuid=True), ForeignKey("content_sessions.id"), nullable=False
    )

    # Moderation results
    automated_check = Column(Boolean, default=True, nullable=False)
    human_reviewed = Column(Boolean, default=False, nullable=False)

    # Safety flags
    flagged_categories = Column(
        JSON, default=list, nullable=False
    )  # ["violence", "inappropriate"]
    safety_score = Column(Integer, nullable=True)  # 0-100

    # Actions taken
    action_taken = Column(String(50), nullable=False)  # approved, rejected, flagged
    reviewer_notes = Column(Text, nullable=True)

    # Reviewer information
    reviewed_by = Column(
        String(100), nullable=True
    )  # "claude_ai", "human_moderator", "parent"
    review_duration_seconds = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    content_session = relationship("ContentSession")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "safety_score >= 0 AND safety_score <= 100", name="check_safety_score"
        ),
        CheckConstraint(
            "action_taken IN ('approved', 'rejected', 'flagged', 'pending')",
            name="check_action",
        ),
        Index("idx_moderation_action", "action_taken"),
        Index("idx_moderation_reviewed", "reviewed_at"),
    )


class DataDeletionRequest(Base):
    """GDPR/COPPA compliance - data deletion requests"""

    __tablename__ = "data_deletion_requests"

    # Primary fields
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Request details
    request_type = Column(
        String(30), nullable=False
    )  # account, voice_data, content, child_data
    reason = Column(String(500), nullable=True)

    # Status tracking
    status = Column(
        String(20), default="pending", nullable=False
    )  # pending, processing, completed, failed
    completion_notes = Column(Text, nullable=True)

    # Processing information
    data_types_deleted = Column(JSON, default=list, nullable=False)
    retention_override = Column(Boolean, default=False, nullable=False)  # Legal hold

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "request_type IN ('account', 'voice_data', 'content', 'child_data')",
            name="check_deletion_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="check_deletion_status",
        ),
        Index("idx_deletion_status", "status"),
        Index("idx_deletion_created", "created_at"),
    )


class SystemLog(Base):
    """System events and audit trail"""

    __tablename__ = "system_logs"

    # Primary fields
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Event details
    event_type = Column(
        String(50), nullable=False
    )  # login, content_generation, payment, etc.
    severity = Column(
        String(20), default="info", nullable=False
    )  # debug, info, warning, error, critical
    message = Column(Text, nullable=False)

    # Context
    user_id = Column(UUID(as_uuid=True), nullable=True)
    session_id = Column(String(64), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    # Additional data
    log_metadata = Column(JSON, default=dict, nullable=False)  # Renamed from metadata
    stack_trace = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "severity IN ('debug', 'info', 'warning', 'error', 'critical')",
            name="check_log_severity",
        ),
        Index("idx_log_event_type", "event_type"),
        Index("idx_log_severity", "severity"),
        Index("idx_log_created", "created_at"),
        Index("idx_log_user", "user_id"),
    )


# Utility functions for models
def create_referral_code() -> str:
    """Generate unique referral code"""
    return secrets.token_urlsafe(6).upper()


def calculate_content_cost(
    content_type: str, user_tier: str, include_images: bool = False
) -> int:
    """Calculate credit cost for content generation"""

    # Base costs by content type
    base_costs = {
        "story": 1,
        "worksheet": 2,
        "quiz": 2,
        "exercise": 1,
    }

    # Tier multipliers (if you have different tiers)
    tier_multipliers = {
        "free": 1.0,
        "premium": 0.8,  # 20% discount for premium users
        "enterprise": 0.5,  # 50% discount for enterprise
    }

    base_cost = base_costs.get(content_type, 1)
    tier_multiplier = tier_multipliers.get(user_tier, 1.0)

    # Add image generation cost
    image_cost = 2 if include_images else 0

    total_cost = int((base_cost + image_cost) * tier_multiplier)

    # Minimum cost is always 1 credit
    return max(1, total_cost)


def get_content_expiry() -> datetime:
    """Get content expiry datetime"""
    return datetime.utcnow() + timedelta(hours=settings.CONTENT_AUTO_EXPIRE_HOURS)


# Model relationships summary for reference:
# User -> Children (1:N)
# User -> UserSessions (1:N)
# User -> CreditTransactions (1:N)
# User -> ContentSessions (1:N)
# Child -> ContentSessions (1:N)
# ContentSession -> CreditTransaction (1:1)
# ContentSession -> ContentModeration (1:1)
