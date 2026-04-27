"""Image saver for Asset Generator."""

from pathlib import Path
from typing import Tuple


class ImageAlreadyExistsError(Exception):
    """Raised when image exists and regenerate is False."""
    pass


def _get_output_dir() -> Path:
    """Return path to characters output directory."""
    return Path(__file__).parent / "output" / "characters"


def save_image(
    character_id: str,
    image_bytes: bytes,
    regenerate: bool = False
) -> Tuple[Path, bool]:
    """
    Save generated image to output directory.

    Args:
        character_id: Character identifier (used as filename)
        image_bytes: PNG image data as bytes
        regenerate: If True, overwrite existing file; if False, skip

    Returns:
        Tuple of (path to saved file, was_written flag)
        was_written is False if file existed and regenerate=False

    Raises:
        None - this function does not raise on existing files,
        it returns was_written=False instead
    """
    output_dir = _get_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{character_id}.png"

    if output_path.exists() and not regenerate:
        return output_path, False

    output_path.write_bytes(image_bytes)
    return output_path, True


def image_exists(character_id: str) -> bool:
    """
    Check if image for character already exists.

    Args:
        character_id: Character identifier

    Returns:
        True if image file exists, False otherwise
    """
    output_path = _get_output_dir() / f"{character_id}.png"
    return output_path.exists()


def get_image_path(character_id: str) -> Path:
    """
    Get the expected path for a character's image.

    Args:
        character_id: Character identifier

    Returns:
        Path where the image would be saved (may not exist yet)
    """
    return _get_output_dir() / f"{character_id}.png"
