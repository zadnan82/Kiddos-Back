"""
Kiddos - Children Management Router (FIXED)
Child profiles, preferences, and settings - Fixed validation issues
"""

import logging
from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import ChildCreate, ChildUpdate, ChildProfile, SuccessResponse
from ..auth import get_current_active_user, field_encryption
from ..rate_limiter import rate_limit
from ..models import User, Child, ContentSession, ContentStatus

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.post("", response_model=ChildProfile)
@rate_limit("api")
async def create_child(
    child_data: ChildCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create child profile - FIXED with better validation"""
    try:
        logger.info(f"Creating child for user {current_user.id}")
        logger.info(f"Child data received: {child_data}")

        # Additional validation
        if not child_data.nickname or len(child_data.nickname.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Nickname is required and cannot be empty",
            )

        if child_data.age_group < 2 or child_data.age_group > 12:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Age must be between 2 and 12 years",
            )

        # Check if user has reached child limit (e.g., 5 children max)
        existing_children = (
            db.query(Child)
            .filter(Child.user_id == current_user.id, Child.is_active == True)
            .count()
        )

        if existing_children >= 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum number of children reached (5)",
            )

        # Validate interests
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

        if child_data.interests:
            invalid_interests = [
                i for i in child_data.interests if i not in valid_interests
            ]
            if invalid_interests:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid interests: {', '.join(invalid_interests)}",
                )

        # Validate avatar_id
        if child_data.avatar_id < 1 or child_data.avatar_id > 20:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Avatar ID must be between 1 and 20",
            )

        # FIXED: Handle empty preferred_language properly
        preferred_language = None
        if child_data.preferred_language and child_data.preferred_language.strip():
            preferred_language = child_data.preferred_language.strip()

        # Create child with proper encryption
        child = Child(
            user_id=current_user.id,
            nickname_encrypted=field_encryption.encrypt(child_data.nickname.strip()),
            full_name_encrypted=field_encryption.encrypt(child_data.full_name.strip())
            if child_data.full_name and child_data.full_name.strip()
            else None,
            age_group=child_data.age_group,
            learning_level=child_data.learning_level or "beginner",
            interests=child_data.interests or [],
            preferred_language=preferred_language,  # This can be None
            content_difficulty=child_data.content_difficulty or "age_appropriate",
            avatar_id=child_data.avatar_id or 1,
        )

        db.add(child)
        db.commit()
        db.refresh(child)

        logger.info(
            f"Child profile created successfully for user {current_user.id}, child ID: {child.id}"
        )

        # Return the created child profile
        return ChildProfile(
            id=str(child.id),
            nickname=field_encryption.decrypt(child.nickname_encrypted),
            age_group=child.age_group,
            learning_level=child.learning_level,
            interests=child.interests,
            preferred_language=child.get_effective_language(),
            content_difficulty=child.content_difficulty,
            avatar_id=child.avatar_id,
            created_at=child.created_at,
            last_used=child.last_used,
            content_count=0,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create child failed: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create child profile",
        )


@router.get("", response_model=List[ChildProfile])
async def get_children(
    current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    """Get user's children"""
    try:
        children = (
            db.query(Child)
            .filter(Child.user_id == current_user.id, Child.is_active == True)
            .order_by(Child.created_at.desc())
            .all()
        )

        result = []
        for child in children:
            # Get content count
            content_count = (
                db.query(ContentSession)
                .filter(
                    ContentSession.child_id == child.id,
                    ContentSession.status == ContentStatus.COMPLETED,
                )
                .count()
            )

            # Safely decrypt nickname
            nickname = None
            if child.nickname_encrypted:
                try:
                    nickname = field_encryption.decrypt(child.nickname_encrypted)
                except Exception as e:
                    logger.error(f"Failed to decrypt child nickname: {e}")
                    nickname = f"Child {child.age_group}"

            result.append(
                ChildProfile(
                    id=str(child.id),
                    nickname=nickname,
                    age_group=child.age_group,
                    learning_level=child.learning_level,
                    interests=child.interests,
                    preferred_language=child.get_effective_language(),
                    content_difficulty=child.content_difficulty,
                    avatar_id=child.avatar_id,
                    created_at=child.created_at,
                    last_used=child.last_used,
                    content_count=content_count,
                )
            )

        return result

    except Exception as e:
        logger.error(f"Get children failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get children",
        )


@router.get("/{child_id}", response_model=ChildProfile)
async def get_child(
    child_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get specific child profile"""
    try:
        child = (
            db.query(Child)
            .filter(
                Child.id == child_id,
                Child.user_id == current_user.id,
                Child.is_active == True,
            )
            .first()
        )

        if not child:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Child not found"
            )

        # Get content count
        content_count = (
            db.query(ContentSession)
            .filter(
                ContentSession.child_id == child.id,
                ContentSession.status == ContentStatus.COMPLETED,
            )
            .count()
        )

        # Safely decrypt nickname
        nickname = None
        if child.nickname_encrypted:
            try:
                nickname = field_encryption.decrypt(child.nickname_encrypted)
            except Exception as e:
                logger.error(f"Failed to decrypt child nickname: {e}")
                nickname = f"Child {child.age_group}"

        return ChildProfile(
            id=str(child.id),
            nickname=nickname,
            age_group=child.age_group,
            learning_level=child.learning_level,
            interests=child.interests,
            preferred_language=child.get_effective_language(),
            content_difficulty=child.content_difficulty,
            avatar_id=child.avatar_id,
            created_at=child.created_at,
            last_used=child.last_used,
            content_count=content_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get child failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get child",
        )


@router.put("/{child_id}", response_model=ChildProfile)
@rate_limit("api")
async def update_child(
    child_id: str,
    update_data: ChildUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update child profile - FIXED with better validation"""
    try:
        child = (
            db.query(Child)
            .filter(
                Child.id == child_id,
                Child.user_id == current_user.id,
                Child.is_active == True,
            )
            .first()
        )

        if not child:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Child not found"
            )

        # Validate update data
        if update_data.nickname is not None:
            if len(update_data.nickname.strip()) == 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Nickname cannot be empty",
                )
            child.nickname_encrypted = field_encryption.encrypt(
                update_data.nickname.strip()
            )

        if update_data.full_name is not None:
            child.full_name_encrypted = (
                field_encryption.encrypt(update_data.full_name.strip())
                if update_data.full_name.strip()
                else None
            )

        if update_data.age_group is not None:
            if update_data.age_group < 2 or update_data.age_group > 12:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Age must be between 2 and 12 years",
                )
            child.age_group = update_data.age_group

        if update_data.learning_level:
            if update_data.learning_level not in [
                "beginner",
                "intermediate",
                "advanced",
            ]:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Learning level must be beginner, intermediate, or advanced",
                )
            child.learning_level = update_data.learning_level

        if update_data.interests is not None:
            # Validate interests
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
            invalid_interests = [
                i for i in update_data.interests if i not in valid_interests
            ]
            if invalid_interests:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid interests: {', '.join(invalid_interests)}",
                )
            child.interests = update_data.interests

        if update_data.preferred_language:
            if update_data.preferred_language not in ["ar", "en", "fr", "de"]:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Language must be ar, en, fr, or de",
                )
            child.preferred_language = update_data.preferred_language

        if update_data.content_difficulty:
            if update_data.content_difficulty not in [
                "easy",
                "age_appropriate",
                "challenging",
            ]:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Content difficulty must be easy, age_appropriate, or challenging",
                )
            child.content_difficulty = update_data.content_difficulty

        if update_data.avatar_id is not None:
            if update_data.avatar_id < 1 or update_data.avatar_id > 20:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Avatar ID must be between 1 and 20",
                )
            child.avatar_id = update_data.avatar_id

        child.updated_at = datetime.utcnow()
        db.commit()

        # Return updated child
        content_count = (
            db.query(ContentSession)
            .filter(
                ContentSession.child_id == child.id,
                ContentSession.status == ContentStatus.COMPLETED,
            )
            .count()
        )

        # Safely decrypt nickname
        nickname = None
        if child.nickname_encrypted:
            try:
                nickname = field_encryption.decrypt(child.nickname_encrypted)
            except Exception as e:
                logger.error(f"Failed to decrypt child nickname: {e}")
                nickname = f"Child {child.age_group}"

        return ChildProfile(
            id=str(child.id),
            nickname=nickname,
            age_group=child.age_group,
            learning_level=child.learning_level,
            interests=child.interests,
            preferred_language=child.get_effective_language(),
            content_difficulty=child.content_difficulty,
            avatar_id=child.avatar_id,
            created_at=child.created_at,
            last_used=child.last_used,
            content_count=content_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update child failed: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update child",
        )


@router.delete("/{child_id}", response_model=SuccessResponse)
async def delete_child(
    child_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Delete child profile"""
    try:
        child = (
            db.query(Child)
            .filter(Child.id == child_id, Child.user_id == current_user.id)
            .first()
        )

        if not child:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Child not found"
            )

        # Soft delete - just mark as inactive
        child.is_active = False
        child.updated_at = datetime.utcnow()

        db.commit()

        return SuccessResponse(message="Child profile deleted successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete child failed: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete child",
        )
