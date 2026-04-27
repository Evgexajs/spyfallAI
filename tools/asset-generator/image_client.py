"""OpenAI Image API client for Asset Generator."""

import base64
from typing import Optional

from openai import OpenAI, AuthenticationError, APIStatusError


class ImageGenerationError(Exception):
    """Base exception for image generation errors."""
    pass


class AuthenticationFailedError(ImageGenerationError):
    """Raised when API authentication fails (401)."""
    pass


class ServerError(ImageGenerationError):
    """Raised when API returns a server error (5xx)."""
    pass


def generate_image_text_only(
    prompt: str,
    model: str = "gpt-image-1",
    size: str = "1024x1536",
    quality: str = "high",
    api_key: Optional[str] = None,
) -> bytes:
    """
    Generate an image using OpenAI Image Generation API (text-only mode).

    Args:
        prompt: Text prompt describing the image to generate
        model: OpenAI image model to use (default: gpt-image-1)
        size: Image dimensions as "WxH" (default: 1024x1536 portrait)
        quality: Image quality - "low", "medium", "high" (default: high)
        api_key: OpenAI API key (uses env OPENAI_API_KEY if not provided)

    Returns:
        PNG image data as bytes

    Raises:
        AuthenticationFailedError: If API key is invalid (401)
        ServerError: If API returns a server error (5xx)
        ImageGenerationError: For other API errors
    """
    client = OpenAI(api_key=api_key)

    try:
        response = client.images.generate(
            model=model,
            prompt=prompt,
            n=1,
            size=size,
            quality=quality,
            response_format="b64_json",
        )

        b64_data = response.data[0].b64_json
        return base64.b64decode(b64_data)

    except AuthenticationError as e:
        raise AuthenticationFailedError(
            f"OpenAI API authentication failed (401). "
            f"Check your OPENAI_API_KEY.\nDetails: {e.message}"
        ) from e

    except APIStatusError as e:
        if 500 <= e.status_code < 600:
            raise ServerError(
                f"OpenAI API server error ({e.status_code}). "
                f"Try again later.\nDetails: {e.message}"
            ) from e
        else:
            raise ImageGenerationError(
                f"OpenAI API error ({e.status_code}): {e.message}"
            ) from e
