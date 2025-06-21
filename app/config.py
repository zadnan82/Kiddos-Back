"""
Kiddos - AI Educational Content Platform
Enhanced Configuration Management with Rich Content Support
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import validator
from enum import Enum


class ContentType(str, Enum):
    """Content types for enhanced settings"""

    STORY = "story"
    WORKSHEET = "worksheet"
    QUIZ = "quiz"
    EXERCISE = "exercise"


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Kiddos"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"

    # Security - Environment variables with NO defaults for sensitive data
    SECRET_KEY: str
    ENCRYPTION_KEY: str
    SESSION_EXPIRE_DAYS: int = 30

    # Database - Environment variable required
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 30

    # Redis - Environment variable with safe default
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_MAX_CONNECTIONS: int = 20

    # Claude AI - Environment variable required, no defaults
    CLAUDE_API_KEY: str
    CLAUDE_MODEL: str = "claude-3-5-sonnet-20241022"
    CLAUDE_MAX_TOKENS: int = 6000
    CLAUDE_TIMEOUT: int = 120
    CLAUDE_TEMPERATURE: float = 0.7
    CLAUDE_RETRY_ATTEMPTS: int = 3
    CLAUDE_ENHANCEMENT_PASSES: bool = True
    CLAUDE_QUALITY_ASSURANCE: bool = True

    # Image Generation - Environment variables required
    IMAGE_GENERATION_ENABLED: bool = True
    IMAGE_SERVICE: str = "openai"
    OPENAI_API_KEY: str
    STABILITY_API_KEY: Optional[str] = None

    # Image Settings
    MAX_IMAGES_PER_STORY: int = 6
    IMAGE_SIZE: str = "1024x1024"
    IMAGE_QUALITY: str = "standard"
    IMAGE_STYLE_PRESET: str = "child-friendly illustration"
    IMAGE_SAFETY_FILTER: bool = True
    IMAGE_RATE_LIMIT_DELAY: int = 1
    IMAGE_STORAGE_PATH: str = "uploads/generated_images"
    IMAGE_MAX_FILE_SIZE: int = 5 * 1024 * 1024  # 5MB

    # Rate Limiting
    FREE_TIER_CONTENT_PER_HOUR: int = 3
    FREE_TIER_CONTENT_PER_DAY: int = 10
    BASIC_TIER_CONTENT_PER_HOUR: int = 10
    BASIC_TIER_CONTENT_PER_DAY: int = 50
    FAMILY_TIER_CONTENT_PER_HOUR: int = 20
    FAMILY_TIER_CONTENT_PER_DAY: int = 150

    # Enhanced Content Settings
    ENHANCED_CONTENT_ENABLED: bool = True

    # Story Settings
    STORY_MIN_WORDS: int = 800
    STORY_MAX_WORDS: int = 1200
    STORY_MIN_SCENES: int = 5
    STORY_MAX_SCENES: int = 7
    STORY_MIN_CHARACTERS: int = 2
    STORY_MAX_CHARACTERS: int = 3
    STORY_INCLUDE_VOCABULARY: bool = True
    STORY_INCLUDE_DISCUSSION_QUESTIONS: bool = True
    STORY_INCLUDE_ACTIVITIES: bool = True

    # Quiz Settings
    QUIZ_MIN_QUESTIONS: int = 15
    QUIZ_MAX_QUESTIONS: int = 20
    QUIZ_MULTIPLE_CHOICE_RATIO: float = 0.6
    QUIZ_SHORT_ANSWER_RATIO: float = 0.25
    QUIZ_CREATIVE_RATIO: float = 0.15
    QUIZ_INCLUDE_FUN_FACTS: bool = True
    QUIZ_INCLUDE_LEARNING_TIPS: bool = True
    QUIZ_INCLUDE_ENCOURAGEMENT: bool = True

    # Worksheet Settings
    WORKSHEET_MIN_ACTIVITIES: int = 12
    WORKSHEET_MAX_ACTIVITIES: int = 16
    WORKSHEET_INCLUDE_HANDS_ON: bool = True
    WORKSHEET_INCLUDE_CREATIVE: bool = True
    WORKSHEET_INCLUDE_EXTENSION: bool = True
    WORKSHEET_INCLUDE_PARENT_NOTES: bool = True
    WORKSHEET_PROGRESSIVE_DIFFICULTY: bool = True

    # Exercise Settings
    EXERCISE_MIN_EXERCISES: int = 6
    EXERCISE_MAX_EXERCISES: int = 8
    EXERCISE_INCLUDE_SAFETY_NOTES: bool = True
    EXERCISE_INCLUDE_VARIATIONS: bool = True
    EXERCISE_INCLUDE_DISCUSSION: bool = True
    EXERCISE_HANDS_ON_FOCUS: bool = True

    # Payment (Stripe) - Environment variables required
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None

    # Email
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    FROM_EMAIL: str = "noreply@kiddos.app"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "kiddos.log"

    # File Upload
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_AUDIO_FORMATS: str = "mp3,wav,m4a"
    UPLOAD_DIR: str = "uploads"

    # Content Safety
    CONTENT_MODERATION_ENABLED: bool = True
    MAX_REGENERATIONS_PER_CONTENT: int = 3
    CONTENT_AUTO_EXPIRE_HOURS: int = 48
    ENHANCED_SAFETY_FILTERING: bool = True

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001,https://kiddos.app,https://www.kiddos.app"

    # Health Check
    HEALTH_CHECK_TIMEOUT: int = 5

    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}")
        return v

    @validator("DEBUG")
    def validate_debug(cls, v, values):
        if values.get("ENVIRONMENT") == "production" and v:
            raise ValueError("DEBUG cannot be True in production")
        return v

    @validator("IMAGE_SERVICE")
    def validate_image_service(cls, v):
        allowed = ["openai", "stability", "local", "disabled"]
        if v not in allowed:
            raise ValueError(f"IMAGE_SERVICE must be one of {allowed}")
        return v

    @validator(
        "QUIZ_MULTIPLE_CHOICE_RATIO", "QUIZ_SHORT_ANSWER_RATIO", "QUIZ_CREATIVE_RATIO"
    )
    def validate_quiz_ratios(cls, v):
        if not 0 <= v <= 1:
            raise ValueError("Quiz ratios must be between 0 and 1")
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def database_url_async(self) -> str:
        """Convert sync postgres URL to async"""
        if self.DATABASE_URL.startswith("postgresql://"):
            return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
        return self.DATABASE_URL

    @property
    def cors_origins_list(self) -> list:
        """Convert CORS origins string to list"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def allowed_audio_formats_list(self) -> list:
        """Convert audio formats string to list"""
        return [fmt.strip() for fmt in self.ALLOWED_AUDIO_FORMATS.split(",")]

    @property
    def images_enabled(self) -> bool:
        """Check if image generation is enabled and configured"""
        return (
            self.IMAGE_GENERATION_ENABLED
            and self.IMAGE_SERVICE != "disabled"
            and (
                (self.IMAGE_SERVICE == "openai" and self.OPENAI_API_KEY)
                or (self.IMAGE_SERVICE == "stability" and self.STABILITY_API_KEY)
                or self.IMAGE_SERVICE == "local"
            )
        )

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()

# Enhanced Content Configuration
ENHANCED_CONTENT_SETTINGS = {
    ContentType.STORY: {
        "min_words": settings.STORY_MIN_WORDS,
        "max_words": settings.STORY_MAX_WORDS,
        "min_scenes": settings.STORY_MIN_SCENES,
        "max_scenes": settings.STORY_MAX_SCENES,
        "min_characters": settings.STORY_MIN_CHARACTERS,
        "max_characters": settings.STORY_MAX_CHARACTERS,
        "min_images": 3,
        "max_images": settings.MAX_IMAGES_PER_STORY,
        "include_vocabulary": settings.STORY_INCLUDE_VOCABULARY,
        "include_discussion_questions": settings.STORY_INCLUDE_DISCUSSION_QUESTIONS,
        "include_activities": settings.STORY_INCLUDE_ACTIVITIES,
        "educational_facts_min": 5,
        "educational_facts_max": 8,
    },
    ContentType.QUIZ: {
        "min_questions": settings.QUIZ_MIN_QUESTIONS,
        "max_questions": settings.QUIZ_MAX_QUESTIONS,
        "multiple_choice_ratio": settings.QUIZ_MULTIPLE_CHOICE_RATIO,
        "short_answer_ratio": settings.QUIZ_SHORT_ANSWER_RATIO,
        "creative_ratio": settings.QUIZ_CREATIVE_RATIO,
        "include_fun_facts": settings.QUIZ_INCLUDE_FUN_FACTS,
        "include_learning_tips": settings.QUIZ_INCLUDE_LEARNING_TIPS,
        "include_encouragement": settings.QUIZ_INCLUDE_ENCOURAGEMENT,
        "min_explanation_length": 30,
        "difficulty_progression": True,
    },
    ContentType.WORKSHEET: {
        "min_activities": settings.WORKSHEET_MIN_ACTIVITIES,
        "max_activities": settings.WORKSHEET_MAX_ACTIVITIES,
        "include_hands_on": settings.WORKSHEET_INCLUDE_HANDS_ON,
        "include_creative": settings.WORKSHEET_INCLUDE_CREATIVE,
        "include_extension": settings.WORKSHEET_INCLUDE_EXTENSION,
        "include_parent_notes": settings.WORKSHEET_INCLUDE_PARENT_NOTES,
        "progressive_difficulty": settings.WORKSHEET_PROGRESSIVE_DIFFICULTY,
        "activity_types_min": 4,
        "sections_min": 3,
    },
    ContentType.EXERCISE: {
        "min_exercises": settings.EXERCISE_MIN_EXERCISES,
        "max_exercises": settings.EXERCISE_MAX_EXERCISES,
        "include_safety_notes": settings.EXERCISE_INCLUDE_SAFETY_NOTES,
        "include_variations": settings.EXERCISE_INCLUDE_VARIATIONS,
        "include_discussion": settings.EXERCISE_INCLUDE_DISCUSSION,
        "hands_on_focus": settings.EXERCISE_HANDS_ON_FOCUS,
        "materials_required": True,
        "time_estimates": True,
    },
}

# Rate limiting configuration
RATE_LIMITS = {
    "free": {
        "content": (settings.FREE_TIER_CONTENT_PER_HOUR, 3600),
        "content_daily": (settings.FREE_TIER_CONTENT_PER_DAY, 86400),
        "login": (5, 300),
        "api": (100, 3600),
        "registration": (30, 86400),
    },
    "basic": {
        "content": (settings.BASIC_TIER_CONTENT_PER_HOUR, 3600),
        "content_daily": (settings.BASIC_TIER_CONTENT_PER_DAY, 86400),
        "login": (10, 300),
        "api": (500, 3600),
        "registration": (5, 86400),
    },
    "family": {
        "content": (settings.FAMILY_TIER_CONTENT_PER_HOUR, 3600),
        "content_daily": (settings.FAMILY_TIER_CONTENT_PER_DAY, 86400),
        "login": (15, 300),
        "api": (1000, 3600),
        "registration": (5, 86400),
    },
}

# Content moderation keywords
INAPPROPRIATE_KEYWORDS = [
    "violence",
    "weapon",
    "kill",
    "murder",
    "war",
    "hate",
    "sexual",
    "drug",
    "alcohol",
    "عنف",
    "سلاح",
    "قتل",
    "حرب",
    "كراهية",
    "جنسي",
    "مخدرات",
    "كحول",
]

EDUCATIONAL_SAFE_WORDS = [
    "blood",
    "circulation",
    "heart",
    "body",
    "death",
    "life cycle",
    "extinction",
    "reproduction",
    "birth",
    "anatomy",
    "physiology",
    "cells",
    "organs",
    "دم",
    "دورة دموية",
    "قلب",
    "جسم",
    "دورة حياة",
    "تكاثر",
    "ولادة",
    "خلايا",
]

# Supported languages
SUPPORTED_LANGUAGES = {
    "ar": {"name": "Arabic", "rtl": True, "code": "ar-SA"},
    "en": {"name": "English", "rtl": False, "code": "en-US"},
    "fr": {"name": "French", "rtl": False, "code": "fr-FR"},
    "de": {"name": "German", "rtl": False, "code": "de-DE"},
}

# Claude prompt templates
CLAUDE_PROMPTS = {
    "arabic_story": """
أنت كاتب قصص أطفال محترف متخصص في القصص التعليمية الغنية والشيقة.

المهمة: اكتب قصة تعليمية طويلة ومفصلة باللغة العربية الفصحى المبسطة.

المعايير المحسنة:
- العمر: {age} سنوات
- الموضوع: {topic}
- الطول: 800-1200 كلمة (قصة طويلة ومفصلة)
- المشاهد: 5-7 مشاهد متميزة
- الشخصيات: 2-3 شخصيات رئيسية بأسماء وشخصيات واضحة
- السياق الثقافي: الخليج العربي والشرق الأوسط

يجب أن تتضمن القصة:
1. بداية جذابة تأسر القارئ
2. رحلة تعليمية مع التشويق
3. تطوير الشخصيات والحوار
4. 5-8 حقائق تعليمية مدمجة بشكل طبيعي
5. تحدٍ أو مشكلة للحل
6. خاتمة مُرضية تعزز التعلم
7. درس أخلاقي واضح

عناصر إضافية:
- 3-5 مفردات جديدة مع تعريفات بسيطة
- 4-6 أسئلة للنقاش
- 2-3 أنشطة عملية مرتبطة بالقصة
- وصف مفصل لـ 4-6 مشاهد للرسم

تجنب: العنف الحقيقي، السياسة، المحتوى غير المناسب للأطفال.
""",
    "english_story": """
You are a professional children's story writer specializing in rich, educational narratives.

Create an immersive educational story for a {age}-year-old child about {topic}.

ENHANCED REQUIREMENTS:
- Length: 800-1200 words (much longer than typical)
- Structure: 5-7 distinct scenes
- Characters: 2-3 main characters with names and personalities
- Educational integration: 5-8 facts woven naturally into the story
- Emotional journey: wonder, discovery, challenge, resolution
- Cultural context: Middle Eastern when appropriate

STORY ELEMENTS:
1. Engaging opening that hooks the reader
2. Character development with dialogue
3. Educational content integrated into plot
4. Problem-solving challenges
5. Satisfying resolution reinforcing learning
6. Inspiring conclusion

ADDITIONAL REQUIREMENTS:
- 3-5 vocabulary words with definitions
- 4-6 discussion questions
- 2-3 hands-on activities
- 4-6 detailed scene descriptions for illustration

Make it magical, memorable, and educational!
""",
    "enhanced_quiz": """
Create a comprehensive educational quiz for a {age}-year-old about {topic}.

ENHANCED SPECIFICATIONS:
- Total questions: 15-20 (much more comprehensive)
- Question types:
  * 10-12 multiple choice (4 options each)
  * 4-5 short answer questions
  * 2-3 creative application questions
- Progressive difficulty from easy to challenging
- Detailed explanations for every answer
- Fun facts and learning tips included
- Encouraging, educational tone throughout

Make this feel like an exciting learning adventure!
""",
    "safety_check": """
Review this educational content for a {age}-year-old child:

{content}

ENHANCED SAFETY CRITERIA:
1. Age-appropriate language and concepts? (Yes/No)
2. Educational value present and clear? (Yes/No)
3. Culturally sensitive for diverse families? (Yes/No)
4. Free from truly inappropriate themes? (Yes/No)
5. Encourages positive learning mindset? (Yes/No)

NOTE: Educational content about topics like "human body", "life cycles", "nature" should be APPROVED even if they mention "blood", "death", or similar educational terms.

Respond with: APPROVED or REJECTED, followed by specific educational reasoning.
""",
}

# Content Quality Thresholds
CONTENT_QUALITY_THRESHOLDS = {
    ContentType.STORY: {
        "min_word_count": settings.STORY_MIN_WORDS,
        "min_educational_facts": 3,
        "min_characters": 1,
        "required_structure": ["beginning", "middle", "end"],
        "min_scenes": settings.STORY_MIN_SCENES,
    },
    ContentType.QUIZ: {
        "min_question_count": settings.QUIZ_MIN_QUESTIONS,
        "min_explanation_length": 30,
        "required_question_types": ["multiple_choice", "short_answer"],
        "min_difficulty_levels": 2,
    },
    ContentType.WORKSHEET: {
        "min_activity_count": settings.WORKSHEET_MIN_ACTIVITIES,
        "required_activity_types": ["knowledge", "application", "creative"],
        "min_sections": 3,
    },
    ContentType.EXERCISE: {
        "min_exercise_count": settings.EXERCISE_MIN_EXERCISES,
        "required_safety_check": True,
        "required_materials_list": True,
        "min_activity_types": 3,
    },
}
