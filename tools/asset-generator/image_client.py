"""OpenAI Image API client for Asset Generator."""

import base64
from pathlib import Path
from typing import Optional, Union

from openai import OpenAI, AuthenticationError, APIStatusError, BadRequestError


class ImageGenerationError(Exception):
    """Base exception for image generation errors."""
    pass


class AuthenticationFailedError(ImageGenerationError):
    """Raised when API authentication fails (401)."""
    pass


class ServerError(ImageGenerationError):
    """Raised when API returns a server error (5xx)."""
    pass


class ReferenceFlowError(ImageGenerationError):
    """Raised when reference-flow is not supported or fails due to reference-specific issues.

    This error triggers fallback to text-only in 'auto' mode.
    It should only be raised for errors specifically related to reference image handling,
    NOT for general API errors like rate limits, auth, or server errors.
    """
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


def generate_image_with_reference(
    prompt: str,
    reference_path: Union[str, Path],
    model: str = "gpt-image-1",
    size: str = "1024x1536",
    quality: str = "high",
    api_key: Optional[str] = None,
) -> bytes:
    """
    Generate an image using OpenAI Images Edit API with a reference image.

    Uses the reference image as a style guide for generation.

    Args:
        prompt: Text prompt describing the image to generate
        reference_path: Path to the reference image (PNG)
        model: OpenAI image model to use (default: gpt-image-1)
        size: Image dimensions as "WxH" (default: 1024x1536 portrait)
        quality: Image quality - "low", "medium", "high" (default: high)
        api_key: OpenAI API key (uses env OPENAI_API_KEY if not provided)

    Returns:
        PNG image data as bytes

    Raises:
        ReferenceFlowError: If reference-flow is not supported by the model/endpoint
        AuthenticationFailedError: If API key is invalid (401)
        ServerError: If API returns a server error (5xx)
        ImageGenerationError: For other API errors
    """
    client = OpenAI(api_key=api_key)
    reference_path = Path(reference_path)

    try:
        with open(reference_path, "rb") as image_file:
            response = client.images.edit(
                model=model,
                image=image_file,
                prompt=prompt,
                n=1,
                size=size,
            )

        if response.data[0].b64_json:
            return base64.b64decode(response.data[0].b64_json)
        elif response.data[0].url:
            import urllib.request
            with urllib.request.urlopen(response.data[0].url) as resp:
                return resp.read()
        else:
            raise ImageGenerationError("API returned no image data")

    except BadRequestError as e:
        error_msg = str(e.message).lower() if hasattr(e, 'message') else str(e).lower()
        if any(keyword in error_msg for keyword in [
            "image", "reference", "not supported", "invalid image",
            "unsupported", "edit", "format"
        ]):
            raise ReferenceFlowError(
                f"Reference-flow not supported for this model/endpoint. "
                f"Details: {e.message if hasattr(e, 'message') else str(e)}"
            ) from e
        raise ImageGenerationError(
            f"OpenAI API error (400): {e.message if hasattr(e, 'message') else str(e)}"
        ) from e

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
