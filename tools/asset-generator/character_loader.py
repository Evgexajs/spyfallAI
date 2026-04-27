"""Character configuration loader for Asset Generator."""

import json
from pathlib import Path


class CharacterNotFoundError(Exception):
    """Raised when a character is not found in configuration."""
    pass


def _get_config_path() -> Path:
    """Return path to characters.json config file."""
    return Path(__file__).parent / "config" / "characters.json"


def _load_config() -> dict:
    """Load and parse the characters.json configuration."""
    config_path = _get_config_path()
    if not config_path.exists():
        raise FileNotFoundError(f"Character config not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_characters() -> list[str]:
    """Return list of all character IDs available in configuration."""
    config = _load_config()
    return list(config.keys())


def load_character(character_id: str) -> dict:
    """
    Load character configuration by ID.

    Args:
        character_id: The character identifier (e.g., 'boris_molot', 'aurora')

    Returns:
        Dictionary with character configuration fields:
        - display_name, archetype, color_accent, visual_description, pose_notes

    Raises:
        CharacterNotFoundError: If character_id is not in configuration
    """
    config = _load_config()

    if character_id not in config:
        available = ", ".join(sorted(config.keys()))
        raise CharacterNotFoundError(
            f"Character '{character_id}' not found. Available characters: {available}"
        )

    return config[character_id]
