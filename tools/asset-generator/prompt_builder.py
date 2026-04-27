"""Prompt builder for Asset Generator."""

from pathlib import Path


def _get_template_path() -> Path:
    """Return path to character_template.txt template file."""
    return Path(__file__).parent / "prompts" / "character_template.txt"


def _load_template() -> str:
    """Load the character prompt template."""
    template_path = _get_template_path()
    if not template_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {template_path}")

    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def build_prompt(character_config: dict) -> str:
    """
    Build a complete prompt from template and character configuration.

    Args:
        character_config: Dictionary with character fields including
                          'visual_description' and 'pose_notes'

    Returns:
        Complete prompt string ready for API submission

    Raises:
        FileNotFoundError: If template file doesn't exist
        KeyError: If required fields are missing from character_config
    """
    template = _load_template()

    required_fields = ["visual_description", "pose_notes"]
    for field in required_fields:
        if field not in character_config:
            raise KeyError(f"Character config missing required field: '{field}'")

    return template.format(
        visual_description=character_config["visual_description"],
        pose_notes=character_config["pose_notes"]
    )
