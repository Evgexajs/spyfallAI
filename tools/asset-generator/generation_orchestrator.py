"""Generation orchestrator with approach handling and fallback logic."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Literal

from image_client import (
    generate_image_text_only,
    generate_image_with_reference,
    ReferenceFlowError,
)


Approach = Literal["auto", "reference", "text-only"]
ActualApproach = Literal["reference", "text_only"]


@dataclass
class GenerationResult:
    """Result of image generation with metadata."""
    image_bytes: bytes
    actual_approach: ActualApproach
    fallback_triggered: bool
    fallback_reason: Optional[str] = None


def generate_image(
    prompt: str,
    approach: Approach,
    reference_path: Optional[Path] = None,
    model: str = "gpt-image-1",
    size: str = "1024x1536",
    quality: str = "high",
    api_key: Optional[str] = None,
) -> GenerationResult:
    """
    Generate an image using the specified approach.

    Approach semantics:
    - auto: Try reference-flow first, fallback to text-only ONLY on ReferenceFlowError.
            Other errors (429, network, auth, 5xx) propagate without fallback.
    - reference: Use reference-flow only. Any error propagates without fallback.
    - text-only: Use text-only directly, no reference needed.

    Args:
        prompt: Text prompt for image generation
        approach: Generation approach - "auto", "reference", or "text-only"
        reference_path: Path to reference image (required for auto/reference)
        model: OpenAI image model
        size: Image dimensions
        quality: Image quality
        api_key: OpenAI API key

    Returns:
        GenerationResult with image bytes and metadata about actual approach used

    Raises:
        ReferenceFlowError: In 'reference' mode if reference-flow fails
        Other ImageGenerationError subclasses: For API errors that don't trigger fallback
    """
    if approach == "text-only":
        image_bytes = generate_image_text_only(
            prompt=prompt,
            model=model,
            size=size,
            quality=quality,
            api_key=api_key,
        )
        return GenerationResult(
            image_bytes=image_bytes,
            actual_approach="text_only",
            fallback_triggered=False,
        )

    if approach == "reference":
        image_bytes = generate_image_with_reference(
            prompt=prompt,
            reference_path=reference_path,
            model=model,
            size=size,
            quality=quality,
            api_key=api_key,
        )
        return GenerationResult(
            image_bytes=image_bytes,
            actual_approach="reference",
            fallback_triggered=False,
        )

    # approach == "auto": try reference-flow, fallback on ReferenceFlowError only
    try:
        image_bytes = generate_image_with_reference(
            prompt=prompt,
            reference_path=reference_path,
            model=model,
            size=size,
            quality=quality,
            api_key=api_key,
        )
        return GenerationResult(
            image_bytes=image_bytes,
            actual_approach="reference",
            fallback_triggered=False,
        )
    except ReferenceFlowError as e:
        fallback_reason = str(e)
        image_bytes = generate_image_text_only(
            prompt=prompt,
            model=model,
            size=size,
            quality=quality,
            api_key=api_key,
        )
        return GenerationResult(
            image_bytes=image_bytes,
            actual_approach="text_only",
            fallback_triggered=True,
            fallback_reason=fallback_reason,
        )
