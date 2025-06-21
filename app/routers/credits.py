"""
Kiddos - Credits Router
Credit management, packages, and transactions
"""

import logging
from typing import List, Dict
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import func
import stripe

from ..database import get_db
from ..schemas import CreditPurchase, CreditPackage, CreditBalance, TransactionHistory
from ..auth import get_current_active_user
from ..rate_limiter import rate_limit
from ..models import User, CreditTransaction, TransactionType
from ..config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# Create router
router = APIRouter()


@router.get("/packages", response_model=List[CreditPackage])
async def get_credit_packages():
    """Get available credit packages"""
    packages = [
        CreditPackage(
            package_type="mini",
            credits=30,
            price_usd=2.99,
            bonus_credits=0,
            description="Perfect for trying out Kiddos",
            popular=False,
        ),
        CreditPackage(
            package_type="basic",
            credits=100,
            price_usd=7.99,
            bonus_credits=10,
            description="Great for regular use",
            popular=True,
        ),
        CreditPackage(
            package_type="family",
            credits=250,
            price_usd=17.99,
            bonus_credits=50,
            description="Best value for families",
            popular=False,
        ),
        CreditPackage(
            package_type="bulk",
            credits=500,
            price_usd=29.99,
            bonus_credits=150,
            description="For heavy users and educators",
            popular=False,
        ),
    ]

    return packages


@router.post("/purchase", response_model=Dict[str, str])
@rate_limit("api")
async def purchase_credits(
    purchase_request: CreditPurchase,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Initiate credit purchase"""
    try:
        # Get package details
        packages = await get_credit_packages()
        package = next(
            (p for p in packages if p.package_type == purchase_request.package_type),
            None,
        )

        if not package:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid package type"
            )

        # Create Stripe checkout session
        try:
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": "usd",
                            "product_data": {
                                "name": f"Kiddos Credits - {package.credits + package.bonus_credits} credits",
                                "description": package.description,
                            },
                            "unit_amount": int(
                                package.price_usd * 100
                            ),  # Convert to cents
                        },
                        "quantity": 1,
                    }
                ],
                mode="payment",
                success_url=f"https://kiddos.app/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url="https://kiddos.app/payment/cancel",
                metadata={
                    "user_id": str(current_user.id),
                    "package_type": purchase_request.package_type,
                    "credits": package.credits + package.bonus_credits,
                },
            )

            return {
                "checkout_url": checkout_session.url,
                "session_id": checkout_session.id,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment processing error",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Credit purchase failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate credit purchase",
        )


@router.get("/balance", response_model=CreditBalance)
async def get_credit_balance(
    current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    """Get user credit balance and history"""
    try:
        # Calculate totals
        purchases = (
            db.query(func.sum(CreditTransaction.amount))
            .filter(
                CreditTransaction.user_id == current_user.id,
                CreditTransaction.transaction_type == TransactionType.PURCHASE,
                CreditTransaction.status == "completed",
            )
            .scalar()
            or 0
        )

        spent = abs(
            db.query(func.sum(CreditTransaction.amount))
            .filter(
                CreditTransaction.user_id == current_user.id,
                CreditTransaction.transaction_type == TransactionType.CONSUMPTION,
                CreditTransaction.status == "completed",
            )
            .scalar()
            or 0
        )

        pending = (
            db.query(func.count(CreditTransaction.id))
            .filter(
                CreditTransaction.user_id == current_user.id,
                CreditTransaction.status == "pending",
            )
            .scalar()
            or 0
        )

        # Get recent transactions
        recent_transactions = (
            db.query(CreditTransaction)
            .filter(CreditTransaction.user_id == current_user.id)
            .order_by(CreditTransaction.created_at.desc())
            .limit(10)
            .all()
        )

        transaction_history = [
            TransactionHistory(
                id=str(tx.id),
                transaction_type=tx.transaction_type,
                amount=tx.amount,
                cost_usd=tx.cost_usd / 100 if tx.cost_usd else None,
                description=tx.description,
                status=tx.status,
                created_at=tx.created_at,
            )
            for tx in recent_transactions
        ]

        return CreditBalance(
            current_balance=current_user.credits,
            total_purchased=purchases,
            total_spent=spent,
            pending_transactions=pending,
            recent_transactions=transaction_history,
        )

    except Exception as e:
        logger.error(f"Get credit balance failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get credit balance",
        )


@router.get("/transactions", response_model=List[TransactionHistory])
async def get_transaction_history(
    current_user: User = Depends(get_current_active_user),
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Get detailed transaction history"""
    try:
        transactions = (
            db.query(CreditTransaction)
            .filter(CreditTransaction.user_id == current_user.id)
            .order_by(CreditTransaction.created_at.desc())
            .limit(limit)
            .all()
        )

        return [
            TransactionHistory(
                id=str(tx.id),
                transaction_type=tx.transaction_type,
                amount=tx.amount,
                cost_usd=tx.cost_usd / 100 if tx.cost_usd else None,
                description=tx.description,
                status=tx.status,
                created_at=tx.created_at,
            )
            for tx in transactions
        ]

    except Exception as e:
        logger.error(f"Get transaction history failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get transaction history",
        )
