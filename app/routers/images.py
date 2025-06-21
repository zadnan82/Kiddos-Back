# 1. Create app/routers/images.py - Image Proxy Router

"""
Image Proxy Router - Bypass CORS for DALL-E images
"""

import logging
import httpx
import io
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from typing import Optional
import asyncio

from ..auth import get_current_active_user
from ..models import User

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/proxy")
async def proxy_dalle_image(
    url: str = Query(..., description="DALL-E image URL to proxy"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Proxy DALL-E images to bypass CORS restrictions
    """
    try:
        # Validate that this is a DALL-E URL for security
        allowed_domains = [
            "oaidalleapiprodscus.blob.core.windows.net",
            "cdn.openai.com",
            "files.oaiusercontent.com",
        ]

        if not any(domain in url for domain in allowed_domains):
            raise HTTPException(
                status_code=400, detail="Only OpenAI/DALL-E image URLs are allowed"
            )

        logger.info(f"🖼️ Proxying DALL-E image for user {current_user.id}")
        logger.debug(f"Image URL: {url[:100]}...")

        # Download the image from DALL-E with proper headers
        async with httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "image/png,image/jpeg,image/*,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
        ) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()

            # Get content type
            content_type = response.headers.get("content-type", "image/png")
            content_length = len(response.content)

            logger.info(
                f"✅ Successfully proxied image: {content_type}, {content_length} bytes"
            )

            # Return the image with CORS headers
            return StreamingResponse(
                io.BytesIO(response.content),
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=7200",  # Cache for 2 hours
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                    "Content-Length": str(content_length),
                },
            )

    except httpx.HTTPStatusError as e:
        logger.error(f"❌ HTTP error proxying image: {e.response.status_code}")
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Image not found or expired")
        elif e.response.status_code == 403:
            raise HTTPException(status_code=403, detail="Image access forbidden")
        else:
            raise HTTPException(
                status_code=e.response.status_code, detail="Failed to fetch image"
            )

    except httpx.TimeoutException:
        logger.error(f"❌ Timeout proxying image")
        raise HTTPException(status_code=408, detail="Image request timed out")

    except Exception as e:
        logger.error(f"❌ Error proxying image: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.options("/proxy")
async def options_proxy():
    """Handle CORS preflight requests"""
    return StreamingResponse(
        io.BytesIO(b""),
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        },
    )


@router.get("/test")
async def test_image_proxy(
    current_user: User = Depends(get_current_active_user),
):
    """Test endpoint to verify image proxy is working"""
    return {
        "status": "ready",
        "proxy_endpoint": "/api/images/proxy",
        "usage": "Add ?url=DALLE_IMAGE_URL to proxy images",
        "user_id": str(current_user.id),
    }
