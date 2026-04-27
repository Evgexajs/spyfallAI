"""Reference image loader for Asset Generator."""

from pathlib import Path
from typing import Optional


class ReferenceImageMissingError(Exception):
    """Raised when reference image is required but not found."""
    pass


def _get_reference_dir() -> Path:
    """Return path to reference directory."""
    return Path(__file__).parent / "reference"


def get_reference_path(text_only: bool = False) -> Optional[Path]:
    """
    Get path to the style reference image.

    Args:
        text_only: If True, missing reference produces a warning instead of error

    Returns:
        Path to style_reference.png, or None in text_only mode if file is missing

    Raises:
        ReferenceImageMissingError: If file is missing and text_only is False
    """
    reference_path = _get_reference_dir() / "style_reference.png"

    if not reference_path.exists():
        if text_only:
            return None
        else:
            raise ReferenceImageMissingError(
                f"Reference image not found: {reference_path}\n"
                "Place your style reference image at:\n"
                f"  {reference_path}\n"
                "Or use --approach text-only to generate without reference."
            )

    return reference_path
