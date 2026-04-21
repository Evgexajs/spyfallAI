"""Post-game analysis module for SpyfallAI.

This module provides automated character analysis after game completion.
"""

from .config import (
    POST_GAME_ANALYSIS_ENABLED,
    POST_GAME_ANALYSIS_TIMEOUT_SECONDS,
    POST_GAME_ANALYSIS_MODEL_ROLE,
)

__all__ = [
    "POST_GAME_ANALYSIS_ENABLED",
    "POST_GAME_ANALYSIS_TIMEOUT_SECONDS",
    "POST_GAME_ANALYSIS_MODEL_ROLE",
]
