"""Analysis module for SpyfallAI - character metrics and spy statistics."""

from .character_metrics import (
    CharacterMetrics,
    GameAnalysis,
    MarkerResult,
    ReplyAnalysis,
    analyze_game,
    analyze_games,
    count_sentences,
    detect_marker,
    detect_markers,
    generate_report,
)
from .spy_statistics import (
    GameResult,
    SpyStatistics,
    VictoryType,
    analyze_game_for_spy_stats,
    analyze_games_for_spy_stats,
    determine_victory_type,
    generate_spy_report,
    load_and_analyze_games,
)

__all__ = [
    # Character metrics
    "CharacterMetrics",
    "GameAnalysis",
    "MarkerResult",
    "ReplyAnalysis",
    "analyze_game",
    "analyze_games",
    "count_sentences",
    "detect_marker",
    "detect_markers",
    "generate_report",
    # Spy statistics
    "GameResult",
    "SpyStatistics",
    "VictoryType",
    "analyze_game_for_spy_stats",
    "analyze_games_for_spy_stats",
    "determine_victory_type",
    "generate_spy_report",
    "load_and_analyze_games",
]
