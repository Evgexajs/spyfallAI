"""OpenAI Image API client for Asset Generator."""

import base64
import time
import random
from pathlib import Path
from typing import Optional, Union

from openai import (
    OpenAI,
    AuthenticationError,
    APIStatusError,
    BadRequestError,
    RateLimitError,
    APIConnectionError,
    APITimeoutError,
)


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


class RateLimitExceededError(ImageGenerationError):
    """Raised when rate limit (429) is exceeded after all retry attempts."""
    pass


class NetworkError(ImageGenerationError):
    """Raised when network/timeout errors persist after all retry attempts."""
    pass


MAX_RETRY_ATTEMPTS = 3
BASE_RETRY_DELAY = 1.0
MIN_REQUEST_INTERVAL = 2.0  # Minimum pause between requests in batch mode (--all-characters)


def _map_quality_for_model(quality: str, model: str) -> str:
    """Map quality value to model-specific equivalent."""
    if model.startswith("dall-e"):
        return "hd" if quality == "high" else "standard"
    return quality


def _map_size_for_model(size: str, model: str) -> str:
    """Map size to model-specific supported size."""
    if model.startswith("dall-e-3"):
        w, h = map(int, size.split("x"))
        if h > w:
            return "1024x1792"
        elif w > h:
            return "1792x1024"
        else:
            return "1024x1024"
    return size


def _retry_on_transient_errors(api_call, max_attempts: int = MAX_RETRY_ATTEMPTS):
    """Execute API call with retry logic for rate limits and network errors.

    Retries up to max_attempts times with exponential backoff + jitter.
    Does NOT retry on auth errors, server errors, or reference-flow errors.
    """
    last_error = None

    for attempt in range(max_attempts):
        try:
            return api_call()
        except RateLimitError as e:
            last_error = e
            if attempt < max_attempts - 1:
                delay = BASE_RETRY_DELAY * (2 ** attempt) + random.uniform(0, 1)
                time.sleep(delay)
        except (APIConnectionError, APITimeoutError) as e:
            last_error = e
            if attempt < max_attempts - 1:
                delay = BASE_RETRY_DELAY * (2 ** attempt) + random.uniform(0, 1)
                time.sleep(delay)

    if isinstance(last_error, RateLimitError):
        raise RateLimitExceededError(
            f"Rate limit exceeded after {max_attempts} attempts. "
            f"Please wait and try again.\nLast error: {last_error}"
        ) from last_error
    else:
        raise NetworkError(
            f"Network error after {max_attempts} attempts. "
            f"Check your connection.\nLast error: {last_error}"
        ) from last_error


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
        RateLimitExceededError: If rate limit exceeded after retries
        NetworkError: If network errors persist after retries
        ImageGenerationError: For other API errors
    """
    client = OpenAI(api_key=api_key)
    mapped_quality = _map_quality_for_model(quality, model)
    mapped_size = _map_size_for_model(size, model)

    def _make_request():
        return client.images.generate(
            model=model,
            prompt=prompt,
            n=1,
            size=mapped_size,
            quality=mapped_quality,
        )

    try:
        response = _retry_on_transient_errors(_make_request)
        if response.data[0].b64_json:
            return base64.b64decode(response.data[0].b64_json)
        elif response.data[0].url:
            import urllib.request
            with urllib.request.urlopen(response.data[0].url) as resp:
                return resp.read()
        else:
            raise ImageGenerationError("API returned no image data")

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
        RateLimitExceededError: If rate limit exceeded after retries
        NetworkError: If network errors persist after retries
        ImageGenerationError: For other API errors
    """
    client = OpenAI(api_key=api_key)
    reference_path = Path(reference_path)
    mapped_size = _map_size_for_model(size, model)

    try:
        with open(reference_path, "rb") as image_file:
            image_data = image_file.read()

        def _make_request_with_data():
            import io
            return client.images.edit(
                model=model,
                image=io.BytesIO(image_data),
                prompt=prompt,
                n=1,
                size=mapped_size,
            )

        response = _retry_on_transient_errors(_make_request_with_data)

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
