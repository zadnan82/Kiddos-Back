"""
Initialize Fixed Content Database Tables
"""

import logging
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.fixed_content.models import Base as FixedContentBase

logger = logging.getLogger(__name__)


def create_fixed_content_tables():
    """Create all fixed content tables"""
    try:
        # Create all tables
        FixedContentBase.metadata.create_all(bind=engine)
        logger.info("Fixed content tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create fixed content tables: {e}")
        raise


def init_sample_data():
    """Initialize with sample data for testing"""
    db = SessionLocal()
    try:
        from app.fixed_content.models import (
            Subject,
            Course,
            Lesson,
            SubjectCategory,
            DifficultyLevel,
            LessonType,
        )
        import uuid
        from datetime import datetime

        # Check if we already have data
        existing_subjects = db.query(Subject).count()
        if existing_subjects > 0:
            logger.info("Sample data already exists, skipping initialization")
            return

        # Create sample subject
        science_subject = Subject(
            id=uuid.uuid4(),
            name="science",
            category=SubjectCategory.SCIENCE,
            display_name_en="Science",
            display_name_ar="العلوم",
            description_en="Learn about the world around us through fun science topics",
            description_ar="تعلم عن العالم من حولنا من خلال مواضيع علمية ممتعة",
            icon_name="🔬",
            color_code="#10B981",
            is_active=True,
            sort_order=1,
        )

        db.add(science_subject)
        db.flush()  # Get the ID

        # Create sample course
        animals_course = Course(
            id=uuid.uuid4(),
            subject_id=science_subject.id,
            name="animals-around-us",
            slug="animals-around-us",
            title_en="Animals Around Us",
            title_ar="الحيوانات من حولنا",
            description_en="Learn about different animals and their habitats",
            description_ar="تعلم عن الحيوانات المختلفة وبيئاتها",
            age_group_min=2,
            age_group_max=4,
            difficulty_level=DifficultyLevel.BEGINNER,
            estimated_duration_minutes=120,
            lesson_count=8,
            credit_reward=0.5,
            xp_reward=100,
            is_published=True,
            is_featured=True,
            sort_order=1,
            published_at=datetime.utcnow(),
        )

        db.add(animals_course)
        db.flush()  # Get the ID

        # Create sample lesson
        farm_lesson = Lesson(
            id=uuid.uuid4(),
            course_id=animals_course.id,
            lesson_order=1,
            name="farm-animals",
            slug="farm-animals",
            title_en="Farm Animals",
            title_ar="حيوانات المزرعة",
            description_en="Learn about animals that live on farms",
            description_ar="تعلم عن الحيوانات التي تعيش في المزارع",
            lesson_type=LessonType.STORY,
            estimated_duration_minutes=15,
            content_data={
                "title": "A Day at Grandpa's Farm",
                "content": "Today, Noor and her little brother Sami are visiting Grandpa's farm...",
                "learning_objectives": [
                    "Recognize and name common farm animals",
                    "Identify animal sounds",
                    "Understand role of farm animals in daily life",
                ],
                "activities": [
                    {
                        "title": "Animal Sound Shakers",
                        "type": "sensory",
                        "materials": ["Empty bottles", "rice", "beans", "stickers"],
                        "instructions": "Fill bottles with different items and match to animal sounds",
                    }
                ],
                "questions": [
                    {
                        "question": "What sound does a cow make?",
                        "type": "multiple_choice",
                        "options": ["Moo", "Woof", "Meow", "Oink"],
                        "answer": "Moo",
                    }
                ],
            },
            xp_reward=20,
            is_required=True,
            is_published=True,
        )

        db.add(farm_lesson)
        db.commit()

        logger.info("Sample fixed content data created successfully")

    except Exception as e:
        logger.error(f"Failed to create sample data: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_fixed_content_tables()
    init_sample_data()
