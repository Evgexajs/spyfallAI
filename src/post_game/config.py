"""Environment configuration for post-game analysis module."""

import os

# Whether to auto-run analyzer after each game
POST_GAME_ANALYSIS_ENABLED: bool = os.environ.get(
    "POST_GAME_ANALYSIS_ENABLED", "true"
).lower() in ("true", "1", "yes")

# Timeout in seconds for each LLM call during analysis
POST_GAME_ANALYSIS_TIMEOUT_SECONDS: int = int(
    os.environ.get("POST_GAME_ANALYSIS_TIMEOUT_SECONDS", "90")
)

# LLM role from llm_config.json to use for analysis (main/utility)
POST_GAME_ANALYSIS_MODEL_ROLE: str = os.environ.get(
    "POST_GAME_ANALYSIS_MODEL_ROLE", "utility"
)
