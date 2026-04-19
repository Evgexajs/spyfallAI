"""Spy win rate statistics module for SpyfallAI."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from ..models.game import Game, TurnType
from ..storage.game_repository import list_games, load_game


class VictoryType(str, Enum):
    """Types of spy victories."""

    SPY_GUESSED_LOCATION = "spy_guessed_location"
    CIVILIANS_VOTED_WRONG = "civilians_voted_wrong"
    CIVILIANS_VOTED_CORRECTLY = "civilians_voted_correctly"
    SPY_GUESS_INCORRECT = "spy_guess_incorrect"
    SPY_LEAKED_LOCATION = "spy_leaked_location"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass
class GameResult:
    """Result of a single game for statistics."""

    game_id: str
    spy_won: bool
    victory_type: VictoryType
    spy_id: str
    location_id: str
    players_count: int
    duration_seconds: Optional[float] = None
    spy_confidence_reached: bool = False
    total_turns: int = 0


@dataclass
class SpyStatistics:
    """Aggregated spy statistics from multiple games."""

    total_games: int = 0
    spy_wins: int = 0
    civilian_wins: int = 0
    cancelled_games: int = 0

    spy_guessed_location: int = 0
    civilians_voted_wrong: int = 0
    civilians_voted_correctly: int = 0
    spy_guess_incorrect: int = 0
    spy_leaked_location: int = 0

    by_player_count: dict[int, "SpyStatistics"] = field(default_factory=dict)
    by_location: dict[str, "SpyStatistics"] = field(default_factory=dict)
    game_results: list[GameResult] = field(default_factory=list)

    @property
    def spy_win_rate(self) -> float:
        """Calculate spy win rate as percentage."""
        completed = self.total_games - self.cancelled_games
        if completed == 0:
            return 0.0
        return (self.spy_wins / completed) * 100

    @property
    def is_balanced(self) -> bool:
        """Check if win rate is in target range 30-50%."""
        return 30.0 <= self.spy_win_rate <= 50.0


def determine_victory_type(game: Game) -> VictoryType:
    """Determine the type of victory from game outcome."""
    if game.outcome is None:
        return VictoryType.UNKNOWN

    winner = game.outcome.winner

    if winner == "cancelled":
        return VictoryType.CANCELLED

    if winner == "spy":
        if game.outcome.spy_guess_correct is True:
            return VictoryType.SPY_GUESSED_LOCATION
        else:
            return VictoryType.CIVILIANS_VOTED_WRONG

    if winner == "civilians":
        if game.outcome.spy_guess_correct is False:
            return VictoryType.SPY_GUESS_INCORRECT

        for turn in game.turns:
            if turn.type == TurnType.SPY_LEAK:
                return VictoryType.SPY_LEAKED_LOCATION

        return VictoryType.CIVILIANS_VOTED_CORRECTLY

    return VictoryType.UNKNOWN


def analyze_game_for_spy_stats(game: Game) -> GameResult:
    """Analyze a single game and extract spy statistics."""
    victory_type = determine_victory_type(game)

    spy_won = victory_type in (
        VictoryType.SPY_GUESSED_LOCATION,
        VictoryType.CIVILIANS_VOTED_WRONG,
    )

    duration = None
    if game.ended_at and game.started_at:
        duration = (game.ended_at - game.started_at).total_seconds()

    spy_confidence_reached = any(
        entry.level.value == "confident" for entry in game.spy_confidence_log
    )

    return GameResult(
        game_id=str(game.id),
        spy_won=spy_won,
        victory_type=victory_type,
        spy_id=game.spy_id,
        location_id=game.location_id,
        players_count=len(game.players),
        duration_seconds=duration,
        spy_confidence_reached=spy_confidence_reached,
        total_turns=len(game.turns),
    )


def analyze_games_for_spy_stats(
    games: list[Game],
    group_by_player_count: bool = True,
    group_by_location: bool = True,
) -> SpyStatistics:
    """Analyze multiple games and return aggregated spy statistics."""
    stats = SpyStatistics()

    for game in games:
        if game.outcome is None:
            continue

        result = analyze_game_for_spy_stats(game)
        stats.game_results.append(result)
        stats.total_games += 1

        if result.victory_type == VictoryType.CANCELLED:
            stats.cancelled_games += 1
            continue

        if result.spy_won:
            stats.spy_wins += 1
        else:
            stats.civilian_wins += 1

        if result.victory_type == VictoryType.SPY_GUESSED_LOCATION:
            stats.spy_guessed_location += 1
        elif result.victory_type == VictoryType.CIVILIANS_VOTED_WRONG:
            stats.civilians_voted_wrong += 1
        elif result.victory_type == VictoryType.CIVILIANS_VOTED_CORRECTLY:
            stats.civilians_voted_correctly += 1
        elif result.victory_type == VictoryType.SPY_GUESS_INCORRECT:
            stats.spy_guess_incorrect += 1
        elif result.victory_type == VictoryType.SPY_LEAKED_LOCATION:
            stats.spy_leaked_location += 1

        if group_by_player_count:
            pc = result.players_count
            if pc not in stats.by_player_count:
                stats.by_player_count[pc] = SpyStatistics()
            _update_stats(stats.by_player_count[pc], result)

        if group_by_location:
            loc = result.location_id
            if loc not in stats.by_location:
                stats.by_location[loc] = SpyStatistics()
            _update_stats(stats.by_location[loc], result)

    return stats


def _update_stats(stats: SpyStatistics, result: GameResult) -> None:
    """Update statistics with a game result."""
    stats.total_games += 1

    if result.victory_type == VictoryType.CANCELLED:
        stats.cancelled_games += 1
        return

    if result.spy_won:
        stats.spy_wins += 1
    else:
        stats.civilian_wins += 1

    if result.victory_type == VictoryType.SPY_GUESSED_LOCATION:
        stats.spy_guessed_location += 1
    elif result.victory_type == VictoryType.CIVILIANS_VOTED_WRONG:
        stats.civilians_voted_wrong += 1
    elif result.victory_type == VictoryType.CIVILIANS_VOTED_CORRECTLY:
        stats.civilians_voted_correctly += 1
    elif result.victory_type == VictoryType.SPY_GUESS_INCORRECT:
        stats.spy_guess_incorrect += 1
    elif result.victory_type == VictoryType.SPY_LEAKED_LOCATION:
        stats.spy_leaked_location += 1


def load_and_analyze_games(games_dir: Optional[Path] = None) -> SpyStatistics:
    """Load all games from directory and analyze spy statistics."""
    game_files = list_games(games_dir)
    games = [load_game(f) for f in game_files]
    return analyze_games_for_spy_stats(games)


def generate_spy_report(stats: SpyStatistics) -> str:
    """Generate a human-readable calibration report."""
    lines = [
        "=" * 60,
        "СПYFALL AI — СТАТИСТИКА ПОБЕД ШПИОНА",
        "=" * 60,
        "",
    ]

    completed = stats.total_games - stats.cancelled_games

    lines.extend(
        [
            "ОБЩАЯ СТАТИСТИКА",
            "-" * 40,
            f"Всего партий:        {stats.total_games}",
            f"Завершённых:         {completed}",
            f"Отменённых:          {stats.cancelled_games}",
            "",
            f"Победы шпиона:       {stats.spy_wins} ({stats.spy_win_rate:.1f}%)",
            f"Победы мирных:       {stats.civilian_wins}",
            "",
        ]
    )

    if stats.is_balanced:
        lines.append("✓ Win rate в целевом диапазоне (30-50%)")
    else:
        if stats.spy_win_rate < 30:
            lines.append("⚠ Win rate НИЖЕ целевого (< 30%) — шпион слишком слаб")
        else:
            lines.append("⚠ Win rate ВЫШЕ целевого (> 50%) — шпион слишком силён")

    lines.extend(
        [
            "",
            "РАЗБИВКА ПО ТИПУ ПОБЕДЫ",
            "-" * 40,
            "Победы шпиона:",
            f"  • Угадал локацию:           {stats.spy_guessed_location}",
            f"  • Мирные ошиблись:          {stats.civilians_voted_wrong}",
            "",
            "Победы мирных:",
            f"  • Нашли шпиона голосованием: {stats.civilians_voted_correctly}",
            f"  • Шпион ошибся в угадывании: {stats.spy_guess_incorrect}",
            f"  • Шпион выдал локацию:       {stats.spy_leaked_location}",
            "",
        ]
    )

    if stats.by_player_count:
        lines.extend(
            [
                "ПО КОЛИЧЕСТВУ ИГРОКОВ",
                "-" * 40,
            ]
        )
        for pc in sorted(stats.by_player_count.keys()):
            pc_stats = stats.by_player_count[pc]
            lines.append(
                f"  {pc} игроков: {pc_stats.spy_wins}/{pc_stats.total_games - pc_stats.cancelled_games} "
                f"({pc_stats.spy_win_rate:.1f}%)"
            )
        lines.append("")

    if stats.by_location:
        lines.extend(
            [
                "ПО ЛОКАЦИЯМ",
                "-" * 40,
            ]
        )
        for loc in sorted(stats.by_location.keys()):
            loc_stats = stats.by_location[loc]
            lines.append(
                f"  {loc}: {loc_stats.spy_wins}/{loc_stats.total_games - loc_stats.cancelled_games} "
                f"({loc_stats.spy_win_rate:.1f}%)"
            )
        lines.append("")

    lines.extend(
        [
            "РЕКОМЕНДАЦИИ ПО КАЛИБРОВКЕ",
            "-" * 40,
        ]
    )

    if completed < 20:
        lines.append(f"• Недостаточно данных ({completed} игр). Нужно 20+ для статистики.")
    elif stats.is_balanced:
        lines.append("• Баланс в норме. Изменения не требуются.")
    else:
        if stats.spy_win_rate < 30:
            lines.extend(
                [
                    "• Увеличить SPY_CONFIDENCE_CHECK_EVERY_N (реже проверять шпиона)",
                    "• Уменьшить точность детекции прямых вопросов",
                    "• Усложнить роли для мирных (более общие описания)",
                ]
            )
        else:
            lines.extend(
                [
                    "• Уменьшить SPY_CONFIDENCE_CHECK_EVERY_N (чаще проверять шпиона)",
                    "• Улучшить качество вопросов мирных (few-shot примеры)",
                    "• Добавить больше ролей в локации для разнообразия",
                ]
            )

    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)
