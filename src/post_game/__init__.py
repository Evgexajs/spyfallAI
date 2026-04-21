"""Post-game analysis module for SpyfallAI.

This module provides automated character analysis after game completion.
"""

from .analyzer import PostGameAnalyzer
from .config import (
    POST_GAME_ANALYSIS_ENABLED,
    POST_GAME_ANALYSIS_MODEL_ROLE,
    POST_GAME_ANALYSIS_TIMEOUT_SECONDS,
)

__all__ = [
    "POST_GAME_ANALYSIS_ENABLED",
    "POST_GAME_ANALYSIS_MODEL_ROLE",
    "POST_GAME_ANALYSIS_TIMEOUT_SECONDS",
    "PostGameAnalyzer",
]
