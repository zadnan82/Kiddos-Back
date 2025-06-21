"""
Kiddos - System Router
Health checks, webhooks, and system endpoints
"""

import logging
import time
import stripe
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db, health_check_database, health_check_redis
from ..schemas import HealthCheck
from ..claude_service import claude_service
from ..worker import process_credit_purchase

# Configure logging
logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# Create router
router = APIRouter()


@router.get("/health", response_model=HealthCheck)
async def health_check():
    """System health check"""
    try:
        # Check database
        db_health = await health_check_database()

        # Check Redis
        redis_health = await health_check_redis()

        # Check Claude API
        claude_health = await claude_service.get_service_health()

        # Determine overall status
        services = {
            "database": db_health,
            "redis": redis_health,
            "claude_api": claude_health,
        }

        overall_status = "healthy"
        if any(service.get("status") != "healthy" for service in services.values()):
            overall_status = "degraded"

        return HealthCheck(
            status=overall_status,
            timestamp=datetime.utcnow(),
            version=settings.VERSION,
            environment=settings.ENVIRONMENT,
            services=services,
            uptime_seconds=int(time.time()),  # Simplified uptime
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheck(
            status="unhealthy",
            timestamp=datetime.utcnow(),
            version=settings.VERSION,
            environment=settings.ENVIRONMENT,
            services={"error": {"status": "unhealthy", "details": str(e)}},
            uptime_seconds=0,
        )


@router.get("/ping")
async def ping():
    """Simple ping endpoint"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events"""
    try:
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe.error.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid signature")

        # Handle the event
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]

            # Process successful payment
            user_id = session["metadata"]["user_id"]
            credits = int(session["metadata"]["credits"])

            # Queue background task to add credits
            process_credit_purchase.delay(
                user_id=user_id,
                amount=credits,
                stripe_payment_id=session["payment_intent"],
            )

            logger.info(
                f"Stripe payment completed for user {user_id}: {credits} credits"
            )

        elif event["type"] == "payment_intent.payment_failed":
            # Handle failed payment
            payment_intent = event["data"]["object"]
            logger.warning(f"Stripe payment failed: {payment_intent['id']}")

        return {"status": "success"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stripe webhook failed: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


@router.get("/version")
async def get_version():
    """Get application version info"""
    return {
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
    }
