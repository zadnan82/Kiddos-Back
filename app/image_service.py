"""
Enhanced Claude Service with Image Generation - CORRECTED VERSION
"""

import asyncio
import base64
import logging
from typing import List, Dict, Any, Optional
import httpx
from openai import OpenAI

from app.claude_service import ClaudeService
from app.config import settings
from app.models import ContentType

logger = logging.getLogger(__name__)


class ImageGenerationService:
    """Service for generating images for educational stories"""

    def __init__(self):
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.image_style = (
            "child-friendly illustration, colorful, educational, cartoon style"
        )

    async def generate_story_images(
        self, story_content: Dict[str, Any], age_group: int
    ) -> Dict[str, Any]:
        """Generate images for story content"""

        if not story_content.get("image_descriptions"):
            logger.info("🖼️ No image descriptions found in story content")
            return story_content

        try:
            logger.info(
                f"🖼️ Starting image generation for {len(story_content['image_descriptions'])} scenes"
            )

            # Generate images for each scene
            generated_images = []

            for i, img_desc in enumerate(story_content["image_descriptions"]):
                logger.info(f"🖼️ Generating image {i + 1}: {img_desc['scene']}")

                image_url = await self._generate_single_image(
                    description=img_desc["description"],
                    style=img_desc.get("style", "child-friendly illustration"),
                    age_group=age_group,
                )

                if image_url:
                    generated_images.append(
                        {
                            "scene": img_desc["scene"],
                            "description": img_desc["description"],
                            "image_url": image_url,
                            "style": img_desc["style"],
                        }
                    )
                    logger.info(f"🖼️ Successfully generated image {i + 1}")
                else:
                    logger.warning(f"⚠️ Failed to generate image {i + 1}")

                # Add delay to respect rate limits
                await asyncio.sleep(2)

            # Add images to content
            story_content["generated_images"] = generated_images
            story_content["has_images"] = len(generated_images) > 0

            logger.info(
                f"🖼️ Image generation completed: {len(generated_images)} images generated"
            )
            return story_content

        except Exception as e:
            logger.error(f"❌ Image generation failed: {e}")
            # Return story without images rather than failing
            story_content["generated_images"] = []
            story_content["has_images"] = False
            return story_content

    async def _generate_single_image(
        self, description: str, style: str, age_group: int
    ) -> Optional[str]:
        """Generate a single image using DALL-E"""

        try:
            # Enhance prompt for child safety and educational value
            enhanced_prompt = self._enhance_image_prompt(description, style, age_group)

            logger.info(f"🖼️ DALL-E prompt: {enhanced_prompt[:100]}...")

            response = await asyncio.to_thread(
                self.openai_client.images.generate,
                model="dall-e-3",
                prompt=enhanced_prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )

            image_url = response.data[0].url
            logger.info(f"✅ DALL-E generated image successfully")
            return image_url

        except Exception as e:
            logger.error(f"❌ DALL-E image generation failed: {e}")
            return None

    def _enhance_image_prompt(
        self, description: str, style: str, age_group: int
    ) -> str:
        """Enhance image prompt for better results"""

        # Age-appropriate style adjustments
        if age_group <= 5:
            style_addition = "very simple, bright colors, large shapes, minimal detail"
        elif age_group <= 8:
            style_addition = "colorful, clear details, friendly characters, engaging"
        else:
            style_addition = "detailed illustration, rich colors, educational accuracy"

        # Safety and educational enhancements
        safety_additions = [
            "safe for children",
            "educational",
            "positive and uplifting",
            "diverse and inclusive",
            "no scary or frightening elements",
        ]

        enhanced_prompt = f"""
        {description}
        
        Style: {style}, {style_addition}
        Requirements: {", ".join(safety_additions)}
        Art style: children's book illustration, digital art, clean and professional
        Mood: happy, educational, wonder and discovery
        """

        return enhanced_prompt.strip()


class EnhancedClaudeWithImages(ClaudeService):
    """Enhanced Claude service with image generation"""

    def __init__(self):
        super().__init__()
        self.image_service = ImageGenerationService()
        logger.info("🖼️ Enhanced Claude service initialized with image generation")

    async def generate_content(self, **kwargs) -> Dict[str, Any]:
        """Enhanced content generation with images for stories"""

        # Generate base content using parent class
        logger.info("🤖 Generating base content with Claude...")
        content = await super().generate_content(**kwargs)

        logger.info(f"✅ Base content generated: {content.get('title', 'No title')}")

        # Add images for stories only
        if kwargs.get("content_type") == ContentType.STORY:
            logger.info("🖼️ Story detected - attempting image generation...")

            # Check if we have image descriptions
            if content.get("image_descriptions"):
                logger.info(
                    f"🖼️ Found {len(content['image_descriptions'])} image descriptions"
                )

                # Check if image generation is enabled
                if settings.images_enabled:
                    logger.info("🖼️ Image generation is enabled - proceeding...")
                    content = await self.image_service.generate_story_images(
                        content, kwargs.get("age_group", 6)
                    )
                else:
                    logger.warning("⚠️ Image generation is disabled in settings")
                    content["generated_images"] = []
                    content["has_images"] = False
            else:
                logger.warning("⚠️ No image descriptions found in content")
                content["generated_images"] = []
                content["has_images"] = False
        else:
            logger.info(
                f"📝 Content type is {kwargs.get('content_type', 'unknown')} - no images needed"
            )
            content["generated_images"] = []
            content["has_images"] = False

        return content
