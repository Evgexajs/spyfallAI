"""Post-game character analysis module (CR-003).

This module provides automated analysis of character behavior after game completion.
It checks detectable_markers and must_directives compliance for each character.
"""

from pathlib import Path
from typing import Optional

from src.models.character import Character
from src.models.game import Game, Turn
from src.models.post_game_analysis import (
    CharacterAnalysis,
    PostGameAnalysis,
)


class PostGameAnalyzer:
    """Analyzer for post-game character behavior.

    Analyzes each character's performance in terms of:
    - detectable_markers: Did the character show their characteristic markers?
    - must_directives: Did the character comply with their MUST rules?
    """

    def __init__(self) -> None:
        """Initialize the analyzer."""
        pass

    async def analyze(self, game_path: Path) -> PostGameAnalysis:
        """Analyze a completed game and return analysis results.

        Args:
            game_path: Path to the game JSON log file.

        Returns:
            PostGameAnalysis with per-character analysis results.
        """
        raise NotImplementedError("Will be implemented in TASK-086")

    def _collect_character_turns(
        self, game: Game, character_id: str
    ) -> list[Turn]:
        """Collect all turns for a specific character with context.

        Args:
            game: The game to analyze.
            character_id: ID of the character to collect turns for.

        Returns:
            List of Turn objects for this character with context (previous turn, addressee).
        """
        raise NotImplementedError("Will be implemented in TASK-082")

    async def _analyze_character(
        self,
        character: Character,
        turns: list[Turn],
    ) -> CharacterAnalysis:
        """Analyze a single character's performance.

        Args:
            character: The character profile.
            turns: Character's turns with context.

        Returns:
            CharacterAnalysis with markers and must_compliance results.
        """
        raise NotImplementedError("Will be implemented in TASK-084")

    def save_analysis(
        self, game_path: Path, analysis: PostGameAnalysis
    ) -> None:
        """Save analysis results back to the game log file.

        Adds or overwrites the post_game_analysis field in the game JSON.

        Args:
            game_path: Path to the game JSON log file.
            analysis: Analysis results to save.
        """
        raise NotImplementedError("Will be implemented in TASK-087")

    def _load_character_profile(self, character_id: str) -> Optional[Character]:
        """Load a character profile from the characters/ directory.

        Args:
            character_id: ID of the character to load.

        Returns:
            Character model or None if not found.
        """
        raise NotImplementedError("Will be implemented in TASK-086")
