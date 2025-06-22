"""
Fixed Content Service - Business Logic
Handles course enrollment, progress tracking, and credit earning
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from .models import (
    Subject,
    Course,
    Lesson,
    UserCourseProgress,
    UserLessonProgress,
    UserCreditEarning,
    CompletionStatus,
    get_monthly_credit_cap,
    get_or_create_monthly_earning,
)
from app.models import User, Child, CreditTransaction, TransactionType
from app.auth import field_encryption

# Configure logging
logger = logging.getLogger(__name__)


class FixedContentService:
    """Service for managing fixed content operations"""

    def __init__(self):
        pass

    # ===============================
    # Subject Operations
    # ===============================

    def get_subjects(
        self, db: Session, language: str = "en", include_course_count: bool = True
    ) -> List[Dict[str, Any]]:
        """Get all active subjects"""
        try:
            subjects = (
                db.query(Subject)
                .filter(Subject.is_active == True)
                .order_by(Subject.sort_order, Subject.created_at)
                .all()
            )

            result = []
            for subject in subjects:
                subject_data = subject.to_dict(language)

                if include_course_count:
                    course_count = (
                        db.query(Course)
                        .filter(
                            Course.subject_id == subject.id, Course.is_published == True
                        )
                        .count()
                    )
                    subject_data["course_count"] = course_count

                result.append(subject_data)

            return result

        except Exception as e:
            logger.error(f"Get subjects failed: {e}")
            raise

    def get_subject_by_id(
        self, subject_id: str, db: Session, language: str = "en"
    ) -> Optional[Dict[str, Any]]:
        """Get subject by ID"""
        try:
            subject = (
                db.query(Subject)
                .filter(Subject.id == subject_id, Subject.is_active == True)
                .first()
            )

            if not subject:
                return None

            return subject.to_dict(language)

        except Exception as e:
            logger.error(f"Get subject by ID failed: {e}")
            raise

    # ===============================
    # Course Operations
    # ===============================

    def get_courses(
        self,
        db: Session,
        subject_id: Optional[str] = None,
        age_group: Optional[int] = None,
        difficulty_level: Optional[str] = None,
        is_featured: Optional[bool] = None,
        search: Optional[str] = None,
        language: str = "en",
        page: int = 1,
        limit: int = 20,
        sort_by: str = "sort_order",
        sort_order: str = "asc",
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get courses with filtering and pagination"""
        try:
            # Build query
            query = db.query(Course).filter(Course.is_published == True)

            # Apply filters
            if subject_id:
                query = query.filter(Course.subject_id == subject_id)

            if age_group:
                query = query.filter(
                    and_(
                        Course.age_group_min <= age_group,
                        Course.age_group_max >= age_group,
                    )
                )

            if difficulty_level:
                query = query.filter(Course.difficulty_level == difficulty_level)

            if is_featured is not None:
                query = query.filter(Course.is_featured == is_featured)

            if search:
                # Search in title and description
                search_term = f"%{search}%"
                query = query.filter(
                    or_(
                        Course.title_en.ilike(search_term),
                        Course.title_ar.ilike(search_term),
                        Course.description_en.ilike(search_term),
                        Course.description_ar.ilike(search_term),
                    )
                )

            # Get total count
            total = query.count()

            # Apply sorting
            if sort_by == "title":
                order_column = Course.title_en if language == "en" else Course.title_ar
            elif sort_by == "created_at":
                order_column = Course.created_at
            elif sort_by == "difficulty_level":
                order_column = Course.difficulty_level
            elif sort_by == "duration":
                order_column = Course.estimated_duration_minutes
            else:
                order_column = Course.sort_order

            if sort_order == "desc":
                query = query.order_by(order_column.desc())
            else:
                query = query.order_by(order_column.asc())

            # Apply pagination
            offset = (page - 1) * limit
            courses = query.offset(offset).limit(limit).all()

            # Convert to response format
            result = []
            for course in courses:
                course_data = course.to_dict(language)
                result.append(course_data)

            return result, total

        except Exception as e:
            logger.error(f"Get courses failed: {e}")
            raise

    def get_course_by_id(
        self,
        course_id: str,
        db: Session,
        user_id: Optional[str] = None,
        child_id: Optional[str] = None,
        language: str = "en",
        include_lessons: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Get course by ID with optional progress information"""
        try:
            course = (
                db.query(Course)
                .filter(Course.id == course_id, Course.is_published == True)
                .first()
            )

            if not course:
                return None

            course_data = course.to_dict(language, include_lessons=include_lessons)

            # Add progress information if user is provided
            if user_id:
                progress = self.get_course_progress(
                    user_id=user_id, child_id=child_id, course_id=course_id, db=db
                )
                course_data["user_progress"] = progress

            # Add subject information
            if course.subject:
                course_data["subject"] = course.subject.to_dict(language)

            # Add prerequisite information
            if course.prerequisite:
                course_data["prerequisite"] = course.prerequisite.to_dict(language)

            return course_data

        except Exception as e:
            logger.error(f"Get course by ID failed: {e}")
            raise

    # ===============================
    # Lesson Operations
    # ===============================

    def get_lesson_by_id(
        self,
        lesson_id: str,
        db: Session,
        user_id: Optional[str] = None,
        child_id: Optional[str] = None,
        language: str = "en",
        include_content: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Get lesson by ID with optional progress information"""
        try:
            lesson = (
                db.query(Lesson)
                .filter(Lesson.id == lesson_id, Lesson.is_published == True)
                .first()
            )

            if not lesson:
                return None

            lesson_data = lesson.to_dict(language, include_content=include_content)

            # Add progress information if user is provided
            if user_id:
                progress = self.get_lesson_progress(
                    user_id=user_id, child_id=child_id, lesson_id=lesson_id, db=db
                )
                lesson_data["user_progress"] = progress

            return lesson_data

        except Exception as e:
            logger.error(f"Get lesson by ID failed: {e}")
            raise

    # ===============================
    # Enrollment & Progress Operations
    # ===============================

    def enroll_in_course(
        self, user_id: str, course_id: str, child_id: Optional[str], db: Session
    ) -> Dict[str, Any]:
        """Enroll user in a course"""
        try:
            # Check if course exists and is published
            course = (
                db.query(Course)
                .filter(Course.id == course_id, Course.is_published == True)
                .first()
            )

            if not course:
                raise ValueError("Course not found or not available")

            # Check if already enrolled
            existing_progress = (
                db.query(UserCourseProgress)
                .filter(
                    UserCourseProgress.user_id == user_id,
                    UserCourseProgress.child_id == child_id,
                    UserCourseProgress.course_id == course_id,
                )
                .first()
            )

            if existing_progress:
                return existing_progress.to_dict()

            # Create progress record
            progress = UserCourseProgress(
                user_id=user_id,
                child_id=child_id,
                course_id=course_id,
                total_lessons=course.lesson_count,
                status=CompletionStatus.NOT_STARTED,
            )

            db.add(progress)
            db.commit()
            db.refresh(progress)

            logger.info(f"User {user_id} enrolled in course {course_id}")
            return progress.to_dict()

        except Exception as e:
            logger.error(f"Course enrollment failed: {e}")
            db.rollback()
            raise

    def start_lesson(
        self, user_id: str, lesson_id: str, child_id: Optional[str], db: Session
    ) -> Dict[str, Any]:
        """Start a lesson"""
        try:
            # Get lesson and course
            lesson = (
                db.query(Lesson)
                .filter(Lesson.id == lesson_id, Lesson.is_published == True)
                .first()
            )

            if not lesson:
                raise ValueError("Lesson not found or not available")

            # Get or create course progress
            course_progress = (
                db.query(UserCourseProgress)
                .filter(
                    UserCourseProgress.user_id == user_id,
                    UserCourseProgress.child_id == child_id,
                    UserCourseProgress.course_id == lesson.course_id,
                )
                .first()
            )

            if not course_progress:
                # Auto-enroll in course
                course_progress_dict = self.enroll_in_course(
                    user_id=user_id,
                    course_id=lesson.course_id,
                    child_id=child_id,
                    db=db,
                )
                course_progress = (
                    db.query(UserCourseProgress)
                    .filter(UserCourseProgress.id == course_progress_dict["id"])
                    .first()
                )

            # Check if lesson progress exists
            lesson_progress = (
                db.query(UserLessonProgress)
                .filter(
                    UserLessonProgress.user_id == user_id,
                    UserLessonProgress.child_id == child_id,
                    UserLessonProgress.lesson_id == lesson_id,
                )
                .first()
            )

            if not lesson_progress:
                # Create lesson progress
                lesson_progress = UserLessonProgress(
                    user_id=user_id,
                    child_id=child_id,
                    lesson_id=lesson_id,
                    course_progress_id=course_progress.id,
                    status=CompletionStatus.IN_PROGRESS,
                    started_at=datetime.utcnow(),
                )
                db.add(lesson_progress)
            else:
                # Update existing progress
                if lesson_progress.status == CompletionStatus.NOT_STARTED:
                    lesson_progress.status = CompletionStatus.IN_PROGRESS
                    lesson_progress.started_at = datetime.utcnow()

            lesson_progress.last_accessed_at = datetime.utcnow()
            lesson_progress.attempts += 1

            # Update course progress if first lesson
            if course_progress.status == CompletionStatus.NOT_STARTED:
                course_progress.status = CompletionStatus.IN_PROGRESS
                course_progress.started_at = datetime.utcnow()

            course_progress.last_accessed_at = datetime.utcnow()

            db.commit()
            db.refresh(lesson_progress)

            logger.info(f"User {user_id} started lesson {lesson_id}")
            return lesson_progress.to_dict()

        except Exception as e:
            logger.error(f"Start lesson failed: {e}")
            db.rollback()
            raise

    def complete_lesson(
        self,
        user_id: str,
        lesson_id: str,
        child_id: Optional[str],
        score: Optional[float],
        time_spent_minutes: int,
        responses: Optional[Dict[str, Any]],
        db: Session,
    ) -> Dict[str, Any]:
        """Complete a lesson and update progress"""
        try:
            # Get lesson progress
            lesson_progress = (
                db.query(UserLessonProgress)
                .filter(
                    UserLessonProgress.user_id == user_id,
                    UserLessonProgress.child_id == child_id,
                    UserLessonProgress.lesson_id == lesson_id,
                )
                .first()
            )

            if not lesson_progress:
                # Start lesson first
                lesson_progress_dict = self.start_lesson(
                    user_id=user_id, lesson_id=lesson_id, child_id=child_id, db=db
                )
                lesson_progress = (
                    db.query(UserLessonProgress)
                    .filter(UserLessonProgress.id == lesson_progress_dict["id"])
                    .first()
                )

            # Get lesson and course progress
            lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()
            course_progress = (
                db.query(UserCourseProgress)
                .filter(UserCourseProgress.id == lesson_progress.course_progress_id)
                .first()
            )

            # Update lesson progress
            lesson_progress.status = CompletionStatus.COMPLETED
            lesson_progress.completed_at = datetime.utcnow()
            lesson_progress.last_accessed_at = datetime.utcnow()
            lesson_progress.time_spent_minutes += time_spent_minutes
            lesson_progress.xp_earned = lesson.xp_reward

            if score is not None:
                lesson_progress.score = score

            if responses:
                lesson_progress.responses = responses

            # Update course progress
            if lesson_progress.status == CompletionStatus.COMPLETED:
                # Count completed lessons
                completed_lessons = (
                    db.query(UserLessonProgress)
                    .filter(
                        UserLessonProgress.course_progress_id == course_progress.id,
                        UserLessonProgress.status == CompletionStatus.COMPLETED,
                    )
                    .count()
                )

                course_progress.lessons_completed = completed_lessons
                course_progress.total_time_spent_minutes += time_spent_minutes
                course_progress.xp_earned += lesson.xp_reward
                course_progress.update_progress()

                # Calculate average score
                scores = (
                    db.query(UserLessonProgress.score)
                    .filter(
                        UserLessonProgress.course_progress_id == course_progress.id,
                        UserLessonProgress.score.isnot(None),
                    )
                    .all()
                )

                if scores:
                    valid_scores = [s[0] for s in scores if s[0] is not None]
                    if valid_scores:
                        course_progress.average_score = sum(valid_scores) / len(
                            valid_scores
                        )

            db.commit()

            # Check if course is completed and award credits
            if (
                course_progress.status == CompletionStatus.COMPLETED
                and not course_progress.credits_earned
            ):
                credits_awarded = self._award_course_completion_credits(
                    user_id=user_id,
                    course_id=lesson.course_id,
                    course_progress=course_progress,
                    db=db,
                )

                if credits_awarded > 0:
                    course_progress.credits_earned = credits_awarded
                    db.commit()

            db.refresh(lesson_progress)
            logger.info(f"User {user_id} completed lesson {lesson_id}")

            return {
                "lesson_progress": lesson_progress.to_dict(),
                "course_progress": course_progress.to_dict(),
                "credits_awarded": course_progress.credits_earned
                if course_progress.status == CompletionStatus.COMPLETED
                else 0,
            }

        except Exception as e:
            logger.error(f"Complete lesson failed: {e}")
            db.rollback()
            raise

    # ===============================
    # Credit Management
    # ===============================

    def _award_course_completion_credits(
        self,
        user_id: str,
        course_id: str,
        course_progress: UserCourseProgress,
        db: Session,
    ) -> float:
        """Award credits for course completion"""
        try:
            # Get user and course
            user = db.query(User).filter(User.id == user_id).first()
            course = db.query(Course).filter(Course.id == course_id).first()

            if not user or not course:
                return 0.0

            # Check if user tier allows credit earning
            if user.tier.value == "free":
                logger.info(
                    f"Free tier user {user_id} completed course but cannot earn credits"
                )
                return 0.0

            # Get or create monthly earning record
            monthly_earning = get_or_create_monthly_earning(
                user_id=user_id, user_tier=user.tier.value, db_session=db
            )

            # Check if can earn credits
            credits_to_award = course.credit_reward
            if not monthly_earning.can_earn_credits(credits_to_award):
                # Award partial credits if possible
                credits_to_award = max(
                    0,
                    monthly_earning.monthly_cap - monthly_earning.credits_earned_total,
                )

            if credits_to_award <= 0:
                logger.info(
                    f"User {user_id} hit monthly credit cap, no credits awarded"
                )
                return 0.0

            # Award credits
            actual_credits = monthly_earning.add_credits(credits_to_award, "course")
            monthly_earning.courses_completed += 1

            # Add credits to user account
            user.credits += actual_credits

            # Create transaction record
            transaction = CreditTransaction(
                user_id=user.id,
                transaction_type=TransactionType.BONUS,
                amount=int(actual_credits),  # Convert to int for transaction
                description=f"Course completion reward: {course.name}",
                status="completed",
                content_type="course_completion",
                processed_at=datetime.utcnow(),
            )
            db.add(transaction)

            # Check for bonus awards
            bonus_credits = self._check_bonus_credit_awards(
                user_id=user_id,
                course=course,
                course_progress=course_progress,
                monthly_earning=monthly_earning,
                db=db,
            )

            if bonus_credits > 0:
                user.credits += bonus_credits
                actual_credits += bonus_credits

            db.commit()

            logger.info(
                f"Awarded {actual_credits} credits to user {user_id} for completing course {course_id}"
            )
            return actual_credits

        except Exception as e:
            logger.error(f"Credit award failed: {e}")
            db.rollback()
            return 0.0

    def _check_bonus_credit_awards(
        self,
        user_id: str,
        course: Course,
        course_progress: UserCourseProgress,
        monthly_earning: UserCreditEarning,
        db: Session,
    ) -> float:
        """Check and award bonus credits"""
        try:
            bonus_credits = 0.0

            # Perfect score bonus (if average score >= 95%)
            if course_progress.average_score and course_progress.average_score >= 95.0:
                if monthly_earning.can_earn_credits(0.2):
                    bonus_credits += monthly_earning.add_credits(0.2, "bonus")
                    monthly_earning.perfect_scores += 1

                    # Create transaction
                    transaction = CreditTransaction(
                        user_id=user_id,
                        transaction_type=TransactionType.BONUS,
                        amount=int(0.2),
                        description=f"Perfect score bonus: {course.name}",
                        status="completed",
                        content_type="perfect_score_bonus",
                        processed_at=datetime.utcnow(),
                    )
                    db.add(transaction)

            # Subject completion bonus
            subject_courses = (
                db.query(Course)
                .filter(
                    Course.subject_id == course.subject_id, Course.is_published == True
                )
                .count()
            )

            completed_in_subject = (
                db.query(UserCourseProgress)
                .join(Course)
                .filter(
                    UserCourseProgress.user_id == user_id,
                    Course.subject_id == course.subject_id,
                    UserCourseProgress.status == CompletionStatus.COMPLETED,
                )
                .count()
            )

            if completed_in_subject >= subject_courses and subject_courses > 0:
                if monthly_earning.can_earn_credits(0.5):
                    bonus_credits += monthly_earning.add_credits(0.5, "bonus")
                    monthly_earning.subjects_completed += 1

                    # Create transaction
                    transaction = CreditTransaction(
                        user_id=user_id,
                        transaction_type=TransactionType.BONUS,
                        amount=int(0.5),
                        description=f"Subject completion bonus: {course.subject.name}",
                        status="completed",
                        content_type="subject_completion_bonus",
                        processed_at=datetime.utcnow(),
                    )
                    db.add(transaction)

            return bonus_credits

        except Exception as e:
            logger.error(f"Bonus credit check failed: {e}")
            return 0.0

    # ===============================
    # Progress Tracking
    # ===============================

    def get_course_progress(
        self, user_id: str, course_id: str, child_id: Optional[str], db: Session
    ) -> Optional[Dict[str, Any]]:
        """Get course progress for user"""
        try:
            progress = (
                db.query(UserCourseProgress)
                .filter(
                    UserCourseProgress.user_id == user_id,
                    UserCourseProgress.child_id == child_id,
                    UserCourseProgress.course_id == course_id,
                )
                .first()
            )

            return progress.to_dict() if progress else None

        except Exception as e:
            logger.error(f"Get course progress failed: {e}")
            raise

    def get_lesson_progress(
        self, user_id: str, lesson_id: str, child_id: Optional[str], db: Session
    ) -> Optional[Dict[str, Any]]:
        """Get lesson progress for user"""
        try:
            progress = (
                db.query(UserLessonProgress)
                .filter(
                    UserLessonProgress.user_id == user_id,
                    UserLessonProgress.child_id == child_id,
                    UserLessonProgress.lesson_id == lesson_id,
                )
                .first()
            )

            return progress.to_dict() if progress else None

        except Exception as e:
            logger.error(f"Get lesson progress failed: {e}")
            raise

    def get_user_learning_stats(
        self, user_id: str, child_id: Optional[str], db: Session
    ) -> Dict[str, Any]:
        """Get comprehensive learning statistics for user"""
        try:
            # Get current month's credit earning
            now = datetime.utcnow()
            current_earning = (
                db.query(UserCreditEarning)
                .filter(
                    UserCreditEarning.user_id == user_id,
                    UserCreditEarning.year == now.year,
                    UserCreditEarning.month == now.month,
                )
                .first()
            )

            # Get course statistics
            enrolled_courses = (
                db.query(UserCourseProgress)
                .filter(
                    UserCourseProgress.user_id == user_id,
                    UserCourseProgress.child_id == child_id,
                )
                .count()
            )

            completed_courses = (
                db.query(UserCourseProgress)
                .filter(
                    UserCourseProgress.user_id == user_id,
                    UserCourseProgress.child_id == child_id,
                    UserCourseProgress.status == CompletionStatus.COMPLETED,
                )
                .count()
            )

            # Get lesson statistics
            completed_lessons = (
                db.query(UserLessonProgress)
                .filter(
                    UserLessonProgress.user_id == user_id,
                    UserLessonProgress.child_id == child_id,
                    UserLessonProgress.status == CompletionStatus.COMPLETED,
                )
                .count()
            )

            # Get total credits earned
            total_credits = (
                db.query(func.sum(UserCreditEarning.credits_earned_total))
                .filter(UserCreditEarning.user_id == user_id)
                .scalar()
                or 0.0
            )

            # Get total XP
            total_xp = (
                db.query(func.sum(UserCourseProgress.xp_earned))
                .filter(
                    UserCourseProgress.user_id == user_id,
                    UserCourseProgress.child_id == child_id,
                )
                .scalar()
                or 0
            )

            # Get average score
            avg_score = (
                db.query(func.avg(UserCourseProgress.average_score))
                .filter(
                    UserCourseProgress.user_id == user_id,
                    UserCourseProgress.child_id == child_id,
                    UserCourseProgress.average_score.isnot(None),
                )
                .scalar()
            )

            # Get total time spent (convert to hours)
            total_time_minutes = (
                db.query(func.sum(UserCourseProgress.total_time_spent_minutes))
                .filter(
                    UserCourseProgress.user_id == user_id,
                    UserCourseProgress.child_id == child_id,
                )
                .scalar()
                or 0
            )

            # Get subjects studied
            subjects_studied = (
                db.query(Course.subject_id)
                .distinct()
                .join(UserCourseProgress)
                .filter(
                    UserCourseProgress.user_id == user_id,
                    UserCourseProgress.child_id == child_id,
                    UserCourseProgress.status.in_(
                        [CompletionStatus.IN_PROGRESS, CompletionStatus.COMPLETED]
                    ),
                )
                .all()
            )

            # Calculate learning streak (simplified)
            recent_activity = (
                db.query(UserLessonProgress)
                .filter(
                    UserLessonProgress.user_id == user_id,
                    UserLessonProgress.child_id == child_id,
                    UserLessonProgress.last_accessed_at
                    >= datetime.utcnow() - timedelta(days=7),
                )
                .count()
            )

            return {
                "total_courses_enrolled": enrolled_courses,
                "total_courses_completed": completed_courses,
                "total_lessons_completed": completed_lessons,
                "total_credits_earned": total_credits,
                "total_xp_earned": total_xp,
                "current_month_credits": current_earning.credits_earned_total
                if current_earning
                else 0.0,
                "current_month_cap": current_earning.monthly_cap
                if current_earning
                else 0.0,
                "subjects_studied": [str(s[0]) for s in subjects_studied],
                "average_score": round(avg_score, 1) if avg_score else None,
                "total_time_spent_hours": round(total_time_minutes / 60, 1),
                "current_streak": min(recent_activity, 7),  # Max 7 days
                "cap_reached": current_earning.cap_reached
                if current_earning
                else False,
            }

        except Exception as e:
            logger.error(f"Get learning stats failed: {e}")
            raise

    def get_monthly_credit_status(self, user_id: str, db: Session) -> Dict[str, Any]:
        """Get current month's credit earning status"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")

            # Get current month's earning record
            now = datetime.utcnow()
            earning = (
                db.query(UserCreditEarning)
                .filter(
                    UserCreditEarning.user_id == user_id,
                    UserCreditEarning.year == now.year,
                    UserCreditEarning.month == now.month,
                )
                .first()
            )

            if not earning:
                # Create if doesn't exist
                earning = get_or_create_monthly_earning(
                    user_id=user_id, user_tier=user.tier.value, db_session=db
                )
                db.commit()

            return earning.to_dict()

        except Exception as e:
            logger.error(f"Get monthly credit status failed: {e}")
            raise

    # ===============================
    # Dashboard & Analytics
    # ===============================

    def get_user_dashboard(
        self, user_id: str, db: Session, language: str = "en"
    ) -> Dict[str, Any]:
        """Get complete user dashboard data"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")

            # Get children
            children = (
                db.query(Child)
                .filter(Child.user_id == user_id, Child.is_active == True)
                .all()
            )

            # Get overall user stats
            user_stats = self.get_user_learning_stats(
                user_id=user_id,
                child_id=None,  # All children combined
                db=db,
            )

            # Get stats for each child
            children_stats = []
            for child in children:
                try:
                    child_name = (
                        field_encryption.decrypt(child.nickname_encrypted)
                        if child.nickname_encrypted
                        else f"Child {child.age_group}"
                    )
                except:
                    child_name = f"Child {child.age_group}"

                child_stats = self.get_user_learning_stats(
                    user_id=user_id, child_id=str(child.id), db=db
                )
                child_stats.update(
                    {
                        "child_id": str(child.id),
                        "child_name": child_name,
                        "age_group": child.age_group,
                    }
                )
                children_stats.append(child_stats)

            # Get recent activity
            recent_progress = (
                db.query(UserLessonProgress)
                .filter(
                    UserLessonProgress.user_id == user_id,
                    UserLessonProgress.last_accessed_at
                    >= datetime.utcnow() - timedelta(days=7),
                )
                .order_by(UserLessonProgress.last_accessed_at.desc())
                .limit(10)
                .all()
            )

            recent_activity = []
            for progress in recent_progress:
                lesson = (
                    db.query(Lesson).filter(Lesson.id == progress.lesson_id).first()
                )
                if lesson:
                    activity = {
                        "lesson_title": lesson.title_en
                        if language == "en"
                        else lesson.title_ar,
                        "status": progress.status.value,
                        "timestamp": progress.last_accessed_at.isoformat(),
                        "score": progress.score,
                    }
                    recent_activity.append(activity)

            # Get recommended courses (simplified)
            # Find courses in subjects user hasn't completed
            recommended_courses, _ = self.get_courses(
                db=db, is_featured=True, language=language, limit=5
            )

            # Get monthly credit status
            credit_status = self.get_monthly_credit_status(user_id=user_id, db=db)

            return {
                "user_stats": user_stats,
                "children_stats": children_stats,
                "recent_activity": recent_activity,
                "recommended_courses": recommended_courses,
                "monthly_credits": credit_status,
            }

        except Exception as e:
            logger.error(f"Get user dashboard failed: {e}")
            raise


# Global service instance
fixed_content_service = FixedContentService()
