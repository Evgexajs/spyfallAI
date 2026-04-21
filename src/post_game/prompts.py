"""LLM prompts for post-game character analysis."""

from src.models.character import Character
from src.models.game import Turn


def build_analysis_prompt(character: Character, turns: list[Turn]) -> str:
    """Build the LLM prompt for character analysis.

    Args:
        character: The character profile with detectable_markers and must_directives.
        turns: List of turns (with context) for this character in the game.

    Returns:
        Complete prompt string for the analysis LLM call.
    """
    raise NotImplementedError("Will be implemented in TASK-083")
