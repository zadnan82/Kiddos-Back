"""
Kiddos - Pydantic Schemas for API Request/Response Models
All API validation and serialization schemas - Fixed for Pydantic v2
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator, Field
from enum import Enum

from .models import UserTier, ContentType, ContentStatus, TransactionType


# ===============================
# Authentication Schemas
# ===============================


class UserRegister(BaseModel):
    """User registration request"""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    preferred_language: str = Field("ar", pattern="^(ar|en|fr|de)$")
    timezone: str = Field("Asia/Dubai", max_length=50)
    gdpr_consent: bool = Field(..., description="GDPR consent required")
    coppa_consent: bool = Field(..., description="COPPA consent required")
    marketing_consent: bool = Field(False, description="Marketing emails consent")
    referral_code: Optional[str] = Field(None, max_length=10)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        return v

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, v):
        """Validate names contain only letters and spaces"""
        if v and not all(c.isalpha() or c.isspace() for c in v):
            raise ValueError("Names can only contain letters and spaces")
        return v


class UserLogin(BaseModel):
    """User login request"""

    email: EmailStr
    password: str
    remember_me: bool = Field(False, description="Extend session duration")


class PasswordReset(BaseModel):
    """Password reset request"""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation"""

    token: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v):
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class TokenResponse(BaseModel):
    """Authentication token response"""

    token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: Dict[str, Any]


# ===============================
# User Management Schemas
# ===============================


class UserProfile(BaseModel):
    """User profile response"""

    id: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    tier: UserTier
    credits: int
    preferred_language: str
    timezone: str
    is_verified: bool
    created_at: datetime
    referral_code: str
    children_count: int


class UserUpdate(BaseModel):
    """User profile update request"""

    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    preferred_language: Optional[str] = Field(None, pattern="^(ar|en|fr|de)$")
    timezone: Optional[str] = Field(None, max_length=50)
    marketing_consent: Optional[bool] = None


class UserLimits(BaseModel):
    """User rate limits and usage"""

    tier: UserTier
    credits: int
    limits: Dict[str, int]
    usage_today: Dict[str, int]
    next_reset: datetime


# ===============================
# Child Management Schemas
# ===============================


class ChildCreate(BaseModel):
    """Create child profile request - FIXED to handle empty strings"""

    nickname: str = Field(
        ..., min_length=1, max_length=50, description="Child's nickname"
    )
    full_name: Optional[str] = Field(
        None, max_length=100, description="Child's full name"
    )
    age_group: int = Field(..., ge=2, le=12, description="Child age 2-12")
    learning_level: str = Field("beginner", description="Learning level")
    interests: List[str] = Field(
        default_factory=list, max_length=10, description="Child's interests"
    )
    preferred_language: Optional[str] = Field(None, description="Preferred language")
    content_difficulty: str = Field(
        "age_appropriate", description="Content difficulty preference"
    )
    avatar_id: int = Field(1, ge=1, le=20, description="Avatar ID (1-20)")

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, v):
        """Validate nickname is not empty after stripping"""
        if not v or not v.strip():
            raise ValueError("Nickname cannot be empty")
        if len(v.strip()) > 50:
            raise ValueError("Nickname is too long (max 50 characters)")
        return v.strip()

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v):
        """Validate full name"""
        if v is not None:
            # Convert empty string to None
            if not v.strip():
                return None
            if len(v.strip()) > 100:
                raise ValueError("Full name is too long (max 100 characters)")
            return v.strip()
        return v

    @field_validator("learning_level")
    @classmethod
    def validate_learning_level(cls, v):
        """Validate learning level"""
        valid_levels = ["beginner", "intermediate", "advanced"]
        if v not in valid_levels:
            raise ValueError(
                f"Learning level must be one of: {', '.join(valid_levels)}"
            )
        return v

    @field_validator("interests")
    @classmethod
    def validate_interests(cls, v):
        """Validate interests list"""
        if not isinstance(v, list):
            raise ValueError("Interests must be a list")

        valid_interests = [
            "animals",
            "space",
            "math",
            "science",
            "art",
            "music",
            "sports",
            "cooking",
            "nature",
            "stories",
            "puzzles",
            "history",
        ]

        if len(v) > 10:
            raise ValueError("Too many interests (max 10)")

        for interest in v:
            if not isinstance(interest, str):
                raise ValueError("All interests must be strings")
            if interest not in valid_interests:
                raise ValueError(
                    f"Invalid interest: {interest}. Valid interests: {', '.join(valid_interests)}"
                )

        return v

    @field_validator("preferred_language")
    @classmethod
    def validate_preferred_language(cls, v):
        """Validate preferred language - FIXED to handle empty strings"""
        if v is not None:
            # Convert empty string to None
            if not v.strip():
                return None

            valid_languages = ["ar", "en", "fr", "de"]
            if v not in valid_languages:
                raise ValueError(
                    f"Language must be one of: {', '.join(valid_languages)}"
                )
            return v
        return v

    @field_validator("content_difficulty")
    @classmethod
    def validate_content_difficulty(cls, v):
        """Validate content difficulty"""
        valid_difficulties = ["easy", "age_appropriate", "challenging"]
        if v not in valid_difficulties:
            raise ValueError(
                f"Content difficulty must be one of: {', '.join(valid_difficulties)}"
            )
        return v

    model_config = {
        "extra": "forbid",
        "str_strip_whitespace": True,
    }


class ChildUpdate(BaseModel):
    """Update child profile request - FIXED"""

    nickname: Optional[str] = Field(None, min_length=1, max_length=50)
    full_name: Optional[str] = Field(None, max_length=100)
    age_group: Optional[int] = Field(None, ge=2, le=12)
    learning_level: Optional[str] = None
    interests: Optional[List[str]] = Field(None, max_length=10)
    preferred_language: Optional[str] = None
    content_difficulty: Optional[str] = None
    avatar_id: Optional[int] = Field(None, ge=1, le=20)

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, v):
        """Validate nickname"""
        if v is not None:
            if not v or not v.strip():
                raise ValueError("Nickname cannot be empty")
            if len(v.strip()) > 50:
                raise ValueError("Nickname is too long (max 50 characters)")
            return v.strip()
        return v

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v):
        """Validate full name"""
        if v is not None:
            if len(v.strip()) > 100:
                raise ValueError("Full name is too long (max 100 characters)")
            return v.strip() if v.strip() else None
        return v

    @field_validator("learning_level")
    @classmethod
    def validate_learning_level(cls, v):
        """Validate learning level"""
        if v is not None:
            valid_levels = ["beginner", "intermediate", "advanced"]
            if v not in valid_levels:
                raise ValueError(
                    f"Learning level must be one of: {', '.join(valid_levels)}"
                )
        return v

    @field_validator("interests")
    @classmethod
    def validate_interests(cls, v):
        """Validate interests list"""
        if v is not None:
            if not isinstance(v, list):
                raise ValueError("Interests must be a list")

            valid_interests = [
                "animals",
                "space",
                "math",
                "science",
                "art",
                "music",
                "sports",
                "cooking",
                "nature",
                "stories",
                "puzzles",
                "history",
            ]

            if len(v) > 10:
                raise ValueError("Too many interests (max 10)")

            for interest in v:
                if not isinstance(interest, str):
                    raise ValueError("All interests must be strings")
                if interest not in valid_interests:
                    raise ValueError(f"Invalid interest: {interest}")

        return v

    @field_validator("preferred_language")
    @classmethod
    def validate_preferred_language(cls, v):
        if v is not None:
            # Convert empty string to None
            if not v.strip():
                return None

            valid_languages = ["ar", "en", "fr", "de"]
            if v not in valid_languages:
                raise ValueError(
                    f"Language must be one of: {', '.join(valid_languages)}"
                )
            return v
        return v

    @field_validator("content_difficulty")
    @classmethod
    def validate_content_difficulty(cls, v):
        """Validate content difficulty"""
        if v is not None:
            valid_difficulties = ["easy", "age_appropriate", "challenging"]
            if v not in valid_difficulties:
                raise ValueError(
                    f"Content difficulty must be one of: {', '.join(valid_difficulties)}"
                )
        return v

    model_config = {
        "extra": "forbid",
        "str_strip_whitespace": True,
    }


class ChildProfile(BaseModel):
    """Child profile response"""

    id: str
    nickname: Optional[str]
    age_group: int
    learning_level: str
    interests: List[str]
    preferred_language: str
    content_difficulty: str
    avatar_id: int
    created_at: datetime
    last_used: Optional[datetime]
    content_count: int

    model_config = {"from_attributes": True}


# ===============================
# Content Generation Schemas
# ===============================


class ContentRequest(BaseModel):
    """Content generation request"""

    child_id: Optional[str] = None
    content_type: ContentType
    topic: str = Field(..., min_length=3, max_length=200)
    age_group: int = Field(..., ge=2, le=12)
    language: str = Field("ar", pattern="^(ar|en|fr|de)$")
    difficulty_level: str = Field(
        "age_appropriate", pattern="^(easy|age_appropriate|challenging)$"
    )
    specific_requirements: Optional[str] = Field(None, max_length=500)
    include_questions: bool = Field(True, description="Include comprehension questions")
    include_activity: bool = Field(False, description="Include hands-on activity")
    include_images: bool = Field(default=False)  # NEW FIELD

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v):
        """Validate topic content"""
        # Remove common prompt injection attempts
        dangerous_patterns = [
            "ignore previous",
            "system:",
            "assistant:",
            "forget",
            "disregard",
            "override",
            "bypass",
        ]
        v_lower = v.lower()
        for pattern in dangerous_patterns:
            if pattern in v_lower:
                raise ValueError(f"Topic contains inappropriate content: {pattern}")
        return v.strip()


class ContentResponse(BaseModel):
    """Content generation response"""

    session_id: str
    status: ContentStatus
    estimated_completion_time: Optional[int] = None  # seconds
    credits_cost: int
    queue_position: Optional[int] = None


class ContentStatusResponse(BaseModel):
    """Content generation status"""

    session_id: str
    status: ContentStatus
    progress_percentage: int = Field(0, ge=0, le=100)
    estimated_completion: Optional[datetime] = None
    error_message: Optional[str] = None


class GeneratedContent(BaseModel):
    """Generated content response"""

    session_id: str
    content_type: ContentType
    title: str
    content: str
    metadata: Dict[str, Any]
    topic: str
    age_group: int
    language: str
    credits_used: int
    generation_time: Optional[int]  # seconds
    safety_approved: bool
    parent_approved: Optional[bool]
    created_at: datetime
    expires_at: datetime


class ContentApproval(BaseModel):
    """Parent content approval"""

    approved: bool
    feedback: Optional[str] = Field(None, max_length=500)


class ContentRegenerate(BaseModel):
    """Content regeneration request"""

    feedback: Optional[str] = Field(None, max_length=500)
    adjust_difficulty: Optional[str] = Field(None, pattern="^(easier|harder)$")
    change_focus: Optional[str] = Field(None, max_length=200)


# ===============================
# Credit System Schemas
# ===============================


class CreditPurchase(BaseModel):
    """Credit purchase request"""

    package_type: str = Field(..., pattern="^(mini|basic|family|bulk)$")
    payment_method: str = Field("stripe", pattern="^(stripe|apple_pay|google_pay)$")
    promo_code: Optional[str] = Field(None, max_length=20)


class CreditPackage(BaseModel):
    """Credit package details"""

    package_type: str
    credits: int
    price_usd: float
    bonus_credits: int = 0
    description: str
    popular: bool = False


class TransactionHistory(BaseModel):
    """Credit transaction history"""

    id: str
    transaction_type: TransactionType
    amount: int
    cost_usd: Optional[float]
    description: Optional[str]
    status: str
    created_at: datetime


class CreditBalance(BaseModel):
    """User credit balance and history"""

    current_balance: int
    total_purchased: int
    total_spent: int
    pending_transactions: int
    recent_transactions: List[TransactionHistory]


# ===============================
# Dashboard & Analytics Schemas
# ===============================


class DashboardStats(BaseModel):
    """Parent dashboard statistics"""

    children_count: int
    total_content_generated: int
    content_this_week: int
    favorite_topics: List[Dict[str, Union[str, int]]]
    usage_by_child: List[Dict[str, Any]]
    credits_remaining: int
    tier: UserTier


class ContentHistory(BaseModel):
    """Content generation history"""

    session_id: str
    content_type: ContentType
    title: str
    topic: str
    child_name: Optional[str]
    age_group: int
    language: str
    status: ContentStatus
    parent_approved: Optional[bool]
    created_at: datetime
    expires_at: datetime


class UsageAnalytics(BaseModel):
    """Usage analytics for parents"""

    daily_usage: List[Dict[str, Any]]
    popular_content_types: List[Dict[str, Any]]
    learning_progress: List[Dict[str, Any]]
    time_patterns: Dict[str, Any]


# ===============================
# System & Health Schemas
# ===============================


class HealthCheck(BaseModel):
    """System health check response"""

    status: str
    timestamp: datetime
    version: str
    environment: str
    services: Dict[str, Dict[str, str]]
    uptime_seconds: int


class ErrorResponse(BaseModel):
    """Error response schema"""

    error: str
    detail: Optional[str] = None
    error_code: Optional[str] = None
    timestamp: datetime
    request_id: Optional[str] = None


# ===============================
# Admin Schemas
# ===============================


class AdminStats(BaseModel):
    """Admin dashboard statistics"""

    total_users: int
    active_users_today: int
    content_generated_today: int
    revenue_this_month: float
    top_content_types: List[Dict[str, Any]]
    user_growth: List[Dict[str, Any]]
    error_rate: float


class UserManagement(BaseModel):
    """Admin user management"""

    user_id: str
    email: str
    tier: UserTier
    credits: int
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]
    total_content: int
    total_spent: float


# ===============================
# Compliance & Privacy Schemas
# ===============================


class DataExportRequest(BaseModel):
    """GDPR data export request"""

    data_types: List[str] = Field(
        default_factory=lambda: ["profile", "children", "content", "transactions"],
        description="Types of data to export",
    )
    format: str = Field("json", pattern="^(json|csv)$")


class DataDeletionRequest(BaseModel):
    """GDPR data deletion request"""

    deletion_type: str = Field(..., pattern="^(account|voice_data|content|child_data)$")
    reason: Optional[str] = Field(None, max_length=500)
    confirm_deletion: bool = Field(..., description="Confirm irreversible deletion")


class PrivacySettings(BaseModel):
    """User privacy settings"""

    data_retention_days: int = Field(730, ge=90, le=2555)  # 3 months to 7 years
    marketing_consent: bool = False
    analytics_consent: bool = True
    third_party_sharing: bool = False


# ===============================
# Validation Helpers
# ===============================


class PaginationParams(BaseModel):
    """Pagination parameters"""

    page: int = Field(1, ge=1, description="Page number")
    per_page: int = Field(20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


class SortParams(BaseModel):
    """Sorting parameters"""

    sort_by: str = Field("created_at", description="Field to sort by")
    sort_order: str = Field("desc", pattern="^(asc|desc)$", description="Sort order")


class FilterParams(BaseModel):
    """Filtering parameters"""

    language: Optional[str] = Field(None, pattern="^(ar|en|fr|de)$")
    content_type: Optional[ContentType] = None
    age_group: Optional[int] = Field(None, ge=2, le=12)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


# ===============================
# Response Wrappers
# ===============================


class PaginatedResponse(BaseModel):
    """Paginated response wrapper"""

    items: List[Any]
    total: int
    page: int
    per_page: int
    pages: int
    has_next: bool
    has_prev: bool


class SuccessResponse(BaseModel):
    """Generic success response"""

    success: bool = True
    message: str
    data: Optional[Any] = None


# ===============================
# Configuration
# ===============================

# Configure Pydantic models
for schema_class in [
    UserRegister,
    UserLogin,
    ContentRequest,
    CreditPurchase,
    ChildCreate,
    ChildUpdate,
    UserUpdate,
]:
    schema_class.model_config = {
        "extra": "forbid",  # Don't allow extra fields
        "validate_assignment": True,  # Validate on assignment
    }
