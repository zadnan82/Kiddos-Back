"""
Kiddos - Content Generation Router
AI content creation, approval, and management
"""

import logging
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..schemas import (
    ContentRequest,
    ContentResponse,
    GeneratedContent,
    ContentApproval,
    ContentRegenerate,
    ContentHistory,
    FilterParams,
    PaginationParams,
    SuccessResponse,
)
from ..auth import get_current_active_user, field_encryption
from ..rate_limiter import rate_limit
from ..claude_service import check_topic_safety
from ..models import (
    User,
    Child,
    ContentSession,
    ContentStatus,
    ContentType,
    calculate_content_cost,
)
from ..worker import generate_content_task
from ..config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.post("/generate", response_model=ContentResponse)
async def generate_content(
    content_request: ContentRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Generate educational content with optional images"""
    try:
        # Validate topic safety first
        is_safe, safety_reason = await check_topic_safety(
            content_request.topic, content_request.age_group
        )

        if not is_safe:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Topic not appropriate: {safety_reason}",
            )

        # Calculate credit cost with image option
        credit_cost = calculate_content_cost(
            content_request.content_type,
            current_user.tier,
            content_request.include_images,  # NEW: Include image cost
        )

        # Check if user has enough credits
        if current_user.credits < credit_cost:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Insufficient credits. Required: {credit_cost}, Available: {current_user.credits}",
            )

        # Create content session with image option
        session = ContentSession(
            user_id=current_user.id,
            child_id=content_request.child_id,
            content_type=content_request.content_type,
            prompt_text=content_request.specific_requirements or "",
            topic=content_request.topic,
            age_group=content_request.age_group,
            language=content_request.language,
            difficulty_level=content_request.difficulty_level,
            include_images=content_request.include_images,  # NEW FIELD
            credits_cost=credit_cost,
            status=ContentStatus.PENDING,
        )

        db.add(session)
        db.commit()
        db.refresh(session)

        # Queue background task for content generation
        task = generate_content_task.delay(str(session.id))

        logger.info(
            f"Content generation queued for user {current_user.id}, session {session.id}, images: {content_request.include_images}"
        )

        return ContentResponse(
            session_id=str(session.id),
            status=ContentStatus.PENDING,
            estimated_completion_time=60
            if content_request.include_images
            else 30,  # Longer for images
            credits_cost=credit_cost,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Content generation failed: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start content generation",
        )


# ADD: Simple debug endpoint to check your ContentSession model fields
@router.get("/debug-model/{session_id}")
async def debug_content_session_model(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Debug what fields actually exist in ContentSession"""
    try:
        session = (
            db.query(ContentSession)
            .filter(
                ContentSession.id == session_id,
                ContentSession.user_id == current_user.id,
            )
            .first()
        )

        if not session:
            return {"error": "Session not found"}

        # Get all attributes of the session object
        session_attrs = []
        for attr in dir(session):
            if not attr.startswith("_") and not callable(getattr(session, attr, None)):
                try:
                    value = getattr(session, attr)
                    # Convert complex types to string for JSON serialization
                    if hasattr(value, "isoformat"):
                        value = value.isoformat()
                    elif hasattr(value, "value"):
                        value = value.value
                    elif isinstance(value, bytes):
                        value = f"<bytes: {len(value)} bytes>"

                    session_attrs.append(
                        {
                            "field": attr,
                            "type": str(type(getattr(session, attr))),
                            "value": str(value)[:100]
                            if value
                            else None,  # Limit to 100 chars
                        }
                    )
                except Exception as e:
                    session_attrs.append(
                        {
                            "field": attr,
                            "type": "error",
                            "value": f"Error accessing: {str(e)}",
                        }
                    )

        return {
            "session_id": session_id,
            "available_fields": session_attrs,
            "status": session.status.value,
            "has_content": bool(session.generated_content),
        }

    except Exception as e:
        return {"error": str(e)}


# ALSO ADD: A separate endpoint specifically for getting content
@router.get("/content/{session_id}")
async def get_session_content(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get the actual content for a completed session - FIXED"""
    try:
        session = (
            db.query(ContentSession)
            .filter(
                ContentSession.id == session_id,
                ContentSession.user_id == current_user.id,
            )
            .first()
        )

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if not session.generated_content:
            raise HTTPException(
                status_code=404, detail="No content available for this session"
            )

        if (
            session.status not in [ContentStatus.COMPLETED]
            and not session.parent_approved
        ):
            raise HTTPException(
                status_code=400, detail="Content is not ready or approved"
            )

        # FIXED: Handle both bytes and string from decryption
        try:
            from app.auth import field_encryption

            decrypted_content = field_encryption.decrypt(session.generated_content)

            # FIXED: Check if decrypted_content is bytes or string
            if isinstance(decrypted_content, bytes):
                content_text = decrypted_content.decode("utf-8")
            elif isinstance(decrypted_content, str):
                content_text = decrypted_content
            else:
                logger.error(
                    f"Unexpected decrypted content type: {type(decrypted_content)}"
                )
                raise HTTPException(status_code=500, detail="Failed to decrypt content")

            logger.info(f"Content decrypted successfully for session {session_id}")

        except Exception as decrypt_error:
            logger.error(
                f"Decryption failed for session {session_id}: {str(decrypt_error)}"
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to decrypt content: {str(decrypt_error)}",
            )

        # FIXED: Parse JSON with better error handling
        try:
            content_dict = json.loads(content_text)
        except json.JSONDecodeError as json_error:
            logger.error(
                f"JSON parsing failed for session {session_id}: {str(json_error)}"
            )
            logger.error(f"Content preview: {content_text[:200]}...")
            raise HTTPException(status_code=500, detail="Failed to parse content JSON")

        # Add metadata
        content_dict.update(
            {
                "session_id": session_id,
                "content_type": session.content_type.value,
                "age_group": session.age_group,
                "language": session.language,
                "topic": session.topic,
                "difficulty_level": session.difficulty_level,
                "credits_used": session.credits_cost,
                "generation_time": session.generation_duration_seconds,
                "safety_approved": session.safety_approved,
                "parent_approved": session.parent_approved,
                "created_at": session.created_at.isoformat(),
                "expires_at": session.expires_at.isoformat()
                if session.expires_at
                else None,
            }
        )

        logger.info(f"Content successfully returned for session {session_id}")
        return content_dict

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error getting content for session {session_id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=f"Failed to load content: {str(e)}")


# ALSO FIX: The status endpoint to include content directly
@router.get("/status/{session_id}")
async def get_content_status(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get content generation status - FIXED to include content when completed"""
    try:
        session = (
            db.query(ContentSession)
            .filter(
                ContentSession.id == session_id,
                ContentSession.user_id == current_user.id,
            )
            .first()
        )

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Base response
        response_data = {
            "session_id": session_id,
            "status": session.status.value.lower(),
            "progress_percentage": getattr(session, "progress_percentage", 0),
            "estimated_completion": getattr(session, "estimated_completion_time", None),
            "error_message": None,
        }

        # Add error messages for rejected/failed sessions
        if session.status.value == "FAILED":
            response_data["error_message"] = (
                session.moderation_notes or "Content generation failed"
            )

        elif session.status.value == "REJECTED":
            error_msg = (
                session.moderation_notes or "Content was rejected by safety filters"
            )
            if "inappropriate terms" in error_msg.lower():
                if ":" in error_msg:
                    flagged_terms = error_msg.split(":")[-1].strip()
                    response_data["error_message"] = (
                        f"Our safety filter flagged some words ({flagged_terms}). "
                        f"Try rephrasing your topic."
                    )
                else:
                    response_data["error_message"] = error_msg
            else:
                response_data["error_message"] = error_msg

        # FIXED: Include content directly in status response when completed
        elif session.status.value == "COMPLETED" and session.generated_content:
            try:
                from app.auth import field_encryption

                # FIXED: Same decryption logic as above
                decrypted_content = field_encryption.decrypt(session.generated_content)

                if isinstance(decrypted_content, bytes):
                    content_text = decrypted_content.decode("utf-8")
                elif isinstance(decrypted_content, str):
                    content_text = decrypted_content
                else:
                    logger.error(
                        f"Unexpected decrypted content type in status: {type(decrypted_content)}"
                    )
                    content_text = str(decrypted_content)

                content_dict = json.loads(content_text)

                # Add session metadata to the content
                content_dict.update(
                    {
                        "session_id": session_id,
                        "content_type": session.content_type.value,
                        "age_group": session.age_group,
                        "language": session.language,
                        "topic": session.topic,
                        "difficulty_level": session.difficulty_level,
                        "credits_used": session.credits_cost,
                        "generation_time": session.generation_duration_seconds,
                        "safety_approved": session.safety_approved,
                        "parent_approved": session.parent_approved,
                        "created_at": session.created_at.isoformat(),
                        "expires_at": session.expires_at.isoformat()
                        if session.expires_at
                        else None,
                    }
                )

                response_data["content"] = content_dict
                logger.info(
                    f"✅ Content included in status response for session {session_id}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to include content in status for session {session_id}: {str(e)}"
                )
                response_data["error_message"] = (
                    "Content was generated but couldn't be loaded"
                )

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting status for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/debug/image-config")
async def debug_image_config(
    current_user: User = Depends(get_current_active_user),
):
    """Debug image generation configuration"""
    from app.config import settings

    return {
        "image_generation_enabled": settings.IMAGE_GENERATION_ENABLED,
        "image_service": settings.IMAGE_SERVICE,
        "openai_api_key_configured": bool(
            settings.OPENAI_API_KEY
            and settings.OPENAI_API_KEY != "your-openai-api-key-here"
        ),
        "images_enabled_property": settings.images_enabled,
        "image_settings": {
            "max_images_per_story": settings.MAX_IMAGES_PER_STORY,
            "image_size": settings.IMAGE_SIZE,
            "image_quality": settings.IMAGE_QUALITY,
            "style_preset": settings.IMAGE_STYLE_PRESET,
        },
    }


# DEBUGGING: Add this endpoint to see what's in the database
@router.get("/debug/{session_id}")
async def debug_session_detailed(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Debug endpoint to see exactly what's in the database"""
    try:
        session = (
            db.query(ContentSession)
            .filter(
                ContentSession.id == session_id,
                ContentSession.user_id == current_user.id,
            )
            .first()
        )

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        debug_info = {
            "session_id": session_id,
            "status": session.status.value,
            "content_type": session.content_type.value,
            "topic": session.topic,
            "age_group": session.age_group,
            "language": session.language,
            "safety_approved": session.safety_approved,
            "parent_approved": session.parent_approved,
            "credits_charged": session.credits_charged,
            "moderation_notes": session.moderation_notes,
            "has_generated_content": bool(session.generated_content),
            "content_size_bytes": len(session.generated_content)
            if session.generated_content
            else 0,
            "created_at": session.created_at.isoformat(),
            "generation_completed_at": session.generation_completed_at.isoformat()
            if session.generation_completed_at
            else None,
        }

        # Try to preview content if it exists
        if session.generated_content:
            try:
                from app.auth import field_encryption

                decrypted = field_encryption.decrypt(session.generated_content)
                content_text = decrypted.decode("utf-8")

                # Show first 200 characters
                debug_info["content_preview"] = (
                    content_text[:200] + "..."
                    if len(content_text) > 200
                    else content_text
                )

                # Try to parse as JSON
                content_dict = json.loads(content_text)
                debug_info["content_structure"] = {
                    "keys": list(content_dict.keys()),
                    "title": content_dict.get("title"),
                    "questions_count": len(content_dict.get("questions", [])),
                    "content_length": len(content_dict.get("content", "")),
                }

            except Exception as e:
                debug_info["content_error"] = str(e)

        return debug_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Debug error for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Debug failed: {str(e)}")


# Add this to your content.py router for debugging


@router.get("/debug/image-config")
async def debug_image_config(
    current_user: User = Depends(get_current_active_user),
):
    """Debug image generation configuration"""
    from app.config import settings

    # Check if OpenAI is available
    openai_available = False
    openai_error = None
    try:
        import openai

        openai_available = True
    except ImportError as e:
        openai_error = str(e)

    # Check if enhanced service is available
    enhanced_service_available = False
    enhanced_error = None
    try:
        from app.image_service import EnhancedClaudeWithImages

        enhanced_service_available = True
    except ImportError as e:
        enhanced_error = str(e)

    return {
        "openai_available": openai_available,
        "openai_error": openai_error,
        "enhanced_service_available": enhanced_service_available,
        "enhanced_service_error": enhanced_error,
        "image_generation_enabled": settings.IMAGE_GENERATION_ENABLED,
        "image_service": settings.IMAGE_SERVICE,
        "openai_api_key_configured": bool(
            settings.OPENAI_API_KEY
            and settings.OPENAI_API_KEY != "your-openai-api-key-here"
        ),
        "images_enabled_property": settings.images_enabled,
        "image_settings": {
            "max_images_per_story": settings.MAX_IMAGES_PER_STORY,
            "image_size": settings.IMAGE_SIZE,
            "image_quality": settings.IMAGE_QUALITY,
            "style_preset": settings.IMAGE_STYLE_PRESET,
        },
        "current_config": {
            "IMAGE_GENERATION_ENABLED": settings.IMAGE_GENERATION_ENABLED,
            "IMAGE_SERVICE": settings.IMAGE_SERVICE,
            "OPENAI_API_KEY": "***" + settings.OPENAI_API_KEY[-4:]
            if settings.OPENAI_API_KEY
            else "Not set",
        },
    }


@router.post("/{session_id}/approve", response_model=SuccessResponse)
async def approve_content(
    session_id: str,
    approval: ContentApproval,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Approve or reject generated content"""
    try:
        session = (
            db.query(ContentSession)
            .filter(
                ContentSession.id == session_id,
                ContentSession.user_id == current_user.id,
                ContentSession.status == ContentStatus.COMPLETED,
            )
            .first()
        )

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content session not found or not ready for approval",
            )

        # Update approval status
        session.parent_approved = approval.approved

        if approval.feedback:
            existing_notes = session.moderation_notes or ""
            session.moderation_notes = (
                f"{existing_notes}\nParent feedback: {approval.feedback}"
            )

        if approval.approved:
            session.status = ContentStatus.APPROVED

            # Update child's last_used timestamp if child specified
            if session.child_id:
                child = db.query(Child).filter(Child.id == session.child_id).first()
                if child:
                    child.last_used = datetime.utcnow()
        else:
            session.status = ContentStatus.REJECTED

        db.commit()

        status_text = "approved" if approval.approved else "rejected"
        logger.info(f"Content {status_text} by parent for session {session_id}")

        return SuccessResponse(message=f"Content {status_text} successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Content approval failed: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process content approval",
        )


@router.get("/debug/{session_id}")
async def debug_content_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Debug endpoint to check content session details"""
    try:
        session = (
            db.query(ContentSession)
            .filter(
                ContentSession.id == session_id,
                ContentSession.user_id == current_user.id,
            )
            .first()
        )

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content session not found",
            )

        return {
            "session_id": str(session.id),
            "user_id": str(session.user_id),
            "status": session.status.value,
            "parent_approved": session.parent_approved,
            "safety_approved": session.safety_approved,
            "generated_title": session.generated_title,
            "has_generated_content": session.generated_content is not None,
            "content_length": len(session.generated_content)
            if session.generated_content
            else 0,
            "content_metadata": session.content_metadata,
            "topic": session.topic,
            "age_group": session.age_group,
            "language": session.language,
            "credits_cost": session.credits_cost,
            "credits_charged": session.credits_charged,
            "created_at": session.created_at.isoformat(),
            "generation_started_at": session.generation_started_at.isoformat()
            if session.generation_started_at
            else None,
            "generation_completed_at": session.generation_completed_at.isoformat()
            if session.generation_completed_at
            else None,
            "expires_at": session.expires_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Debug content session failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to debug content session",
        )


@router.post("/{session_id}/regenerate", response_model=ContentResponse)
@rate_limit("content")
async def regenerate_content(
    session_id: str,
    regenerate_request: ContentRegenerate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Regenerate content with feedback"""
    try:
        session = (
            db.query(ContentSession)
            .filter(
                ContentSession.id == session_id,
                ContentSession.user_id == current_user.id,
            )
            .first()
        )

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content session not found",
            )

        if not session.can_regenerate():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Content cannot be regenerated",
            )

        # Check regeneration limit
        regeneration_count = session.content_metadata.get("regeneration_count", 0)
        if regeneration_count >= settings.MAX_REGENERATIONS_PER_CONTENT:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Maximum regenerations reached ({settings.MAX_REGENERATIONS_PER_CONTENT})",
            )

        # Check credits again
        if current_user.credits < session.credits_cost:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Insufficient credits for regeneration",
            )

        # Update session with feedback
        if regenerate_request.feedback:
            feedback_text = f"Regeneration feedback: {regenerate_request.feedback}"
            if regenerate_request.adjust_difficulty:
                feedback_text += f" (Make it {regenerate_request.adjust_difficulty})"
            if regenerate_request.change_focus:
                feedback_text += f" (Focus on: {regenerate_request.change_focus})"

            session.prompt_text = f"{session.prompt_text}\n\n{feedback_text}"

        # Reset session for regeneration
        session.status = ContentStatus.PENDING
        session.generated_content = None
        session.generated_title = None
        session.safety_approved = None
        session.parent_approved = None
        session.generation_started_at = None
        session.generation_completed_at = None
        session.credits_charged = False

        # Update metadata
        metadata = session.content_metadata.copy()
        metadata["regeneration_count"] = regeneration_count + 1
        metadata["last_regeneration"] = datetime.utcnow().isoformat()
        session.content_metadata = metadata

        db.commit()

        # Queue new generation task
        task = generate_content_task.delay(str(session.id))

        logger.info(f"Content regeneration queued for session {session_id}")

        return ContentResponse(
            session_id=session_id,
            status=ContentStatus.PENDING,
            estimated_completion_time=30,
            credits_cost=session.credits_cost,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Content regeneration failed: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to regenerate content",
        )


@router.get("/history", response_model=List[ContentHistory])
async def get_content_history(
    current_user: User = Depends(get_current_active_user),
    pagination: PaginationParams = Depends(),
    filters: FilterParams = Depends(),
    db: Session = Depends(get_db),
):
    """Get content generation history"""
    try:
        # Build query
        query = db.query(ContentSession).filter(
            ContentSession.user_id == current_user.id
        )

        # Apply filters
        if filters.language:
            query = query.filter(ContentSession.language == filters.language)
        if filters.content_type:
            query = query.filter(ContentSession.content_type == filters.content_type)
        if filters.age_group:
            query = query.filter(ContentSession.age_group == filters.age_group)
        if filters.date_from:
            query = query.filter(ContentSession.created_at >= filters.date_from)
        if filters.date_to:
            query = query.filter(ContentSession.created_at <= filters.date_to)

        # Get paginated results
        content_sessions = (
            query.order_by(ContentSession.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.per_page)
            .all()
        )

        # Build response
        history = []
        for session in content_sessions:
            child_name = None
            if session.child_id:
                child = db.query(Child).filter(Child.id == session.child_id).first()
                if child and child.nickname_encrypted:
                    child_name = field_encryption.decrypt(child.nickname_encrypted)

            history.append(
                ContentHistory(
                    session_id=str(session.id),
                    content_type=session.content_type,
                    title=session.generated_title or session.topic,
                    topic=session.topic,
                    child_name=child_name,
                    age_group=session.age_group,
                    language=session.language,
                    status=session.status,
                    parent_approved=session.parent_approved,
                    created_at=session.created_at,
                    expires_at=session.expires_at,
                )
            )

        return history

    except Exception as e:
        logger.error(f"Get content history failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get content history",
        )


@router.delete("/{session_id}", response_model=SuccessResponse)
async def delete_content(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Delete content session"""
    try:
        session = (
            db.query(ContentSession)
            .filter(
                ContentSession.id == session_id,
                ContentSession.user_id == current_user.id,
            )
            .first()
        )

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Content session not found",
            )

        # Clear content data but keep session record for analytics
        session.generated_content = None
        session.content_metadata = {}
        session.status = ContentStatus.PENDING  # Mark as cleaned

        db.commit()

        logger.info(f"Content deleted for session {session_id}")

        return SuccessResponse(message="Content deleted successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Content deletion failed: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete content",
        )


@router.get("/debug/rate-limit")
async def debug_rate_limit(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Debug rate limiting status"""
    try:
        from ..rate_limiter import rate_limiter, RATE_LIMITS

        user_id = str(current_user.id)
        tier = current_user.tier.value

        # Get all rate limit types for this tier
        debug_info = {
            "user_id": user_id,
            "tier": tier,
            "rate_limits_config": RATE_LIMITS.get(tier, {}),
            "current_usage": {},
        }

        # Check each rate limit type
        for limit_type in RATE_LIMITS.get(tier, {}):
            max_requests, window_seconds = RATE_LIMITS[tier][limit_type]

            # Get Redis key and check current state
            key = f"rate_limit:{tier}:{limit_type}:{user_id}"

            try:
                # Check Redis directly
                import time

                now = time.time()

                # Get all entries in the key
                all_entries = await rate_limiter.redis.zrange(
                    key, 0, -1, withscores=True
                )

                # Count entries in current window
                valid_entries = [
                    entry for entry in all_entries if entry[1] > now - window_seconds
                ]

                debug_info["current_usage"][limit_type] = {
                    "limit": max_requests,
                    "window_seconds": window_seconds,
                    "redis_key": key,
                    "total_entries": len(all_entries),
                    "valid_entries": len(valid_entries),
                    "entries_detail": [
                        {
                            "timestamp": entry[1],
                            "age_seconds": now - entry[1],
                            "is_valid": entry[1] > now - window_seconds,
                        }
                        for entry in all_entries
                    ],
                    "is_over_limit": len(valid_entries) >= max_requests,
                }

            except Exception as redis_error:
                debug_info["current_usage"][limit_type] = {
                    "error": str(redis_error),
                    "redis_key": key,
                }

        # Also test Redis connectivity
        try:
            start_time = time.time()
            await rate_limiter.redis.ping()
            redis_latency = time.time() - start_time
            debug_info["redis_status"] = {
                "connected": True,
                "latency_ms": round(redis_latency * 1000, 2),
            }
        except Exception as redis_error:
            debug_info["redis_status"] = {"connected": False, "error": str(redis_error)}

        return debug_info

    except Exception as e:
        logger.error(f"Rate limit debug failed: {e}")
        return {
            "error": str(e),
            "user_id": str(current_user.id),
            "tier": current_user.tier.value,
        }
