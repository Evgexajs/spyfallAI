"""Tests for spy statistics module."""

from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

import pytest

from src.analysis.spy_statistics import (
    GameResult,
    SpyStatistics,
    VictoryType,
    analyze_game_for_spy_stats,
    analyze_games_for_spy_stats,
    determine_victory_type,
    generate_spy_report,
)
from src.models.game import (
    ConfidenceEntry,
    ConfidenceLevel,
    Game,
    GameConfig,
    GameOutcome,
    GamePhase,
    PhaseEntry,
    Player,
    Turn,
    TurnType,
)


def create_test_game(
    winner: str = "spy",
    spy_guess_correct: Optional[bool] = None,
    include_spy_leak: bool = False,
    accused_id: Optional[str] = None,
    players_count: int = 4,
    location_id: str = "hospital",
    spy_reached_confident: bool = False,
) -> Game:
    """Create a test game with configurable outcome."""
    game_id = uuid4()
    started_at = datetime.now()
    ended_at = started_at + timedelta(minutes=10)

    players = []
    spy_char_id = f"char_{players_count - 1}"

    for i in range(players_count):
        char_id = f"char_{i}"
        is_spy = char_id == spy_char_id
        players.append(
            Player(
                character_id=char_id,
                role_id=None if is_spy else f"role_{i}",
                is_spy=is_spy,
            )
        )

    spy_id = spy_char_id

    turns = [
        Turn(
            turn_number=1,
            timestamp=started_at,
            speaker_id="player_0",
            addressee_id="player_1",
            type=TurnType.QUESTION,
            content="Test question?",
            display_delay_ms=1000,
        ),
        Turn(
            turn_number=2,
            timestamp=started_at + timedelta(seconds=30),
            speaker_id="player_1",
            addressee_id="player_0",
            type=TurnType.ANSWER,
            content="Test answer.",
            display_delay_ms=1000,
        ),
    ]

    if include_spy_leak:
        turns.append(
            Turn(
                turn_number=3,
                timestamp=started_at + timedelta(seconds=60),
                speaker_id=spy_id,
                addressee_id="all",
                type=TurnType.SPY_LEAK,
                content="I mentioned hospital accidentally!",
                display_delay_ms=1000,
            )
        )

    spy_confidence_log = []
    if spy_reached_confident:
        spy_confidence_log.append(
            ConfidenceEntry(
                turn_number=5,
                timestamp=started_at + timedelta(seconds=90),
                level=ConfidenceLevel.CONFIDENT,
            )
        )

    reason = "Test outcome"
    if winner == "spy" and spy_guess_correct:
        reason = f"Шпион ({spy_id}) угадал локацию: {location_id}"
    elif winner == "civilians":
        if spy_guess_correct is False:
            reason = f"Шпион ({spy_id}) ошибся в угадывании"
        elif include_spy_leak:
            reason = f"Шпион ({spy_id}) случайно назвал локацию"
        else:
            reason = f"Шпион ({spy_id}) был разоблачён голосованием"

    outcome = GameOutcome(
        winner=winner,
        reason=reason,
        votes={"char_0": spy_id, "char_1": spy_id} if accused_id else None,
        spy_guess=location_id if spy_guess_correct is not None else None,
        spy_guess_correct=spy_guess_correct,
        accused_id=accused_id or spy_id,
    )

    return Game(
        id=game_id,
        started_at=started_at,
        ended_at=ended_at,
        config=GameConfig(
            players_count=players_count,
            duration_minutes=10,
            max_questions=50,
            main_model="gpt-4o",
            utility_model="gpt-4o-mini",
        ),
        location_id=location_id,
        players=players,
        spy_id=spy_id,
        turns=turns,
        spy_confidence_log=spy_confidence_log,
        triggered_events=[],
        phase_transitions=[
            PhaseEntry(to_phase=GamePhase.SETUP, timestamp=started_at),
            PhaseEntry(to_phase=GamePhase.RESOLUTION, timestamp=ended_at),
        ],
        outcome=outcome,
    )


class TestDetermineVictoryType:
    """Tests for determine_victory_type function."""

    def test_spy_guessed_location(self):
        game = create_test_game(winner="spy", spy_guess_correct=True)
        assert determine_victory_type(game) == VictoryType.SPY_GUESSED_LOCATION

    def test_civilians_voted_wrong(self):
        game = create_test_game(winner="spy", accused_id="player_0")
        assert determine_victory_type(game) == VictoryType.CIVILIANS_VOTED_WRONG

    def test_civilians_voted_correctly(self):
        game = create_test_game(winner="civilians")
        assert determine_victory_type(game) == VictoryType.CIVILIANS_VOTED_CORRECTLY

    def test_spy_guess_incorrect(self):
        game = create_test_game(winner="civilians", spy_guess_correct=False)
        assert determine_victory_type(game) == VictoryType.SPY_GUESS_INCORRECT

    def test_spy_leaked_location(self):
        game = create_test_game(winner="civilians", include_spy_leak=True)
        assert determine_victory_type(game) == VictoryType.SPY_LEAKED_LOCATION

    def test_cancelled(self):
        game = create_test_game(winner="cancelled")
        assert determine_victory_type(game) == VictoryType.CANCELLED

    def test_no_outcome(self):
        game = create_test_game()
        game.outcome = None
        assert determine_victory_type(game) == VictoryType.UNKNOWN


class TestAnalyzeGameForSpyStats:
    """Tests for analyze_game_for_spy_stats function."""

    def test_spy_win_by_guess(self):
        game = create_test_game(winner="spy", spy_guess_correct=True)
        result = analyze_game_for_spy_stats(game)

        assert result.spy_won is True
        assert result.victory_type == VictoryType.SPY_GUESSED_LOCATION
        assert result.players_count == 4
        assert result.location_id == "hospital"
        assert result.total_turns == 2

    def test_spy_loss_by_vote(self):
        game = create_test_game(winner="civilians")
        result = analyze_game_for_spy_stats(game)

        assert result.spy_won is False
        assert result.victory_type == VictoryType.CIVILIANS_VOTED_CORRECTLY

    def test_duration_calculated(self):
        game = create_test_game()
        result = analyze_game_for_spy_stats(game)

        assert result.duration_seconds is not None
        assert result.duration_seconds == 600.0  # 10 minutes

    def test_confidence_reached(self):
        game = create_test_game(spy_reached_confident=True)
        result = analyze_game_for_spy_stats(game)

        assert result.spy_confidence_reached is True


class TestAnalyzeGamesForSpyStats:
    """Tests for analyze_games_for_spy_stats function."""

    def test_empty_games(self):
        stats = analyze_games_for_spy_stats([])

        assert stats.total_games == 0
        assert stats.spy_win_rate == 0.0

    def test_single_spy_win(self):
        games = [create_test_game(winner="spy", spy_guess_correct=True)]
        stats = analyze_games_for_spy_stats(games)

        assert stats.total_games == 1
        assert stats.spy_wins == 1
        assert stats.civilian_wins == 0
        assert stats.spy_win_rate == 100.0

    def test_single_civilian_win(self):
        games = [create_test_game(winner="civilians")]
        stats = analyze_games_for_spy_stats(games)

        assert stats.total_games == 1
        assert stats.spy_wins == 0
        assert stats.civilian_wins == 1
        assert stats.spy_win_rate == 0.0

    def test_multiple_games(self):
        games = [
            create_test_game(winner="spy", spy_guess_correct=True),
            create_test_game(winner="spy", accused_id="player_0"),
            create_test_game(winner="civilians"),
            create_test_game(winner="civilians", spy_guess_correct=False),
            create_test_game(winner="civilians", include_spy_leak=True),
        ]
        stats = analyze_games_for_spy_stats(games)

        assert stats.total_games == 5
        assert stats.spy_wins == 2
        assert stats.civilian_wins == 3
        assert stats.spy_win_rate == 40.0
        assert stats.spy_guessed_location == 1
        assert stats.civilians_voted_wrong == 1
        assert stats.civilians_voted_correctly == 1
        assert stats.spy_guess_incorrect == 1
        assert stats.spy_leaked_location == 1

    def test_cancelled_excluded_from_rate(self):
        games = [
            create_test_game(winner="spy", spy_guess_correct=True),
            create_test_game(winner="cancelled"),
        ]
        stats = analyze_games_for_spy_stats(games)

        assert stats.total_games == 2
        assert stats.cancelled_games == 1
        assert stats.spy_wins == 1
        assert stats.spy_win_rate == 100.0  # 1 spy win / 1 completed

    def test_group_by_player_count(self):
        games = [
            create_test_game(winner="spy", players_count=4),
            create_test_game(winner="civilians", players_count=4),
            create_test_game(winner="spy", players_count=6),
        ]
        stats = analyze_games_for_spy_stats(games, group_by_player_count=True)

        assert 4 in stats.by_player_count
        assert 6 in stats.by_player_count
        assert stats.by_player_count[4].total_games == 2
        assert stats.by_player_count[4].spy_win_rate == 50.0
        assert stats.by_player_count[6].total_games == 1
        assert stats.by_player_count[6].spy_win_rate == 100.0

    def test_group_by_location(self):
        games = [
            create_test_game(winner="spy", location_id="hospital"),
            create_test_game(winner="civilians", location_id="hospital"),
            create_test_game(winner="civilians", location_id="airplane"),
        ]
        stats = analyze_games_for_spy_stats(games, group_by_location=True)

        assert "hospital" in stats.by_location
        assert "airplane" in stats.by_location
        assert stats.by_location["hospital"].spy_win_rate == 50.0
        assert stats.by_location["airplane"].spy_win_rate == 0.0


class TestSpyStatistics:
    """Tests for SpyStatistics class properties."""

    def test_is_balanced_in_range(self):
        stats = SpyStatistics(total_games=10, spy_wins=4, civilian_wins=6)
        assert stats.spy_win_rate == 40.0
        assert stats.is_balanced is True

    def test_is_balanced_too_low(self):
        stats = SpyStatistics(total_games=10, spy_wins=2, civilian_wins=8)
        assert stats.spy_win_rate == 20.0
        assert stats.is_balanced is False

    def test_is_balanced_too_high(self):
        stats = SpyStatistics(total_games=10, spy_wins=6, civilian_wins=4)
        assert stats.spy_win_rate == 60.0
        assert stats.is_balanced is False

    def test_is_balanced_at_boundaries(self):
        stats_low = SpyStatistics(total_games=10, spy_wins=3, civilian_wins=7)
        assert stats_low.spy_win_rate == 30.0
        assert stats_low.is_balanced is True

        stats_high = SpyStatistics(total_games=10, spy_wins=5, civilian_wins=5)
        assert stats_high.spy_win_rate == 50.0
        assert stats_high.is_balanced is True


class TestGenerateSpyReport:
    """Tests for generate_spy_report function."""

    def test_report_contains_header(self):
        stats = SpyStatistics(total_games=5, spy_wins=2, civilian_wins=3)
        report = generate_spy_report(stats)

        assert "СТАТИСТИКА ПОБЕД ШПИОНА" in report

    def test_report_contains_totals(self):
        stats = SpyStatistics(
            total_games=10,
            spy_wins=4,
            civilian_wins=5,
            cancelled_games=1,
        )
        report = generate_spy_report(stats)

        assert "Всего партий:        10" in report
        assert "Завершённых:         9" in report
        assert "Отменённых:          1" in report
        assert "Победы шпиона:       4" in report

    def test_report_shows_balanced(self):
        stats = SpyStatistics(total_games=10, spy_wins=4, civilian_wins=6)
        report = generate_spy_report(stats)

        assert "✓ Win rate в целевом диапазоне (30-50%)" in report

    def test_report_shows_too_low(self):
        stats = SpyStatistics(total_games=10, spy_wins=2, civilian_wins=8)
        report = generate_spy_report(stats)

        assert "шпион слишком слаб" in report

    def test_report_shows_too_high(self):
        stats = SpyStatistics(total_games=10, spy_wins=6, civilian_wins=4)
        report = generate_spy_report(stats)

        assert "шпион слишком силён" in report

    def test_report_shows_victory_breakdown(self):
        stats = SpyStatistics(
            total_games=5,
            spy_wins=2,
            civilian_wins=3,
            spy_guessed_location=1,
            civilians_voted_wrong=1,
            civilians_voted_correctly=2,
            spy_leaked_location=1,
        )
        report = generate_spy_report(stats)

        assert "Угадал локацию:           1" in report
        assert "Мирные ошиблись:          1" in report
        assert "Нашли шпиона голосованием: 2" in report
        assert "Шпион выдал локацию:       1" in report

    def test_report_shows_player_count_breakdown(self):
        stats = SpyStatistics(total_games=3, spy_wins=2, civilian_wins=1)
        stats.by_player_count = {
            4: SpyStatistics(total_games=2, spy_wins=1, civilian_wins=1),
            6: SpyStatistics(total_games=1, spy_wins=1, civilian_wins=0),
        }
        report = generate_spy_report(stats)

        assert "4 игроков:" in report
        assert "6 игроков:" in report

    def test_report_shows_insufficient_data_warning(self):
        stats = SpyStatistics(total_games=5, spy_wins=2, civilian_wins=3)
        report = generate_spy_report(stats)

        assert "Недостаточно данных" in report


class TestVictoryType:
    """Tests for VictoryType enum."""

    def test_all_types_defined(self):
        assert VictoryType.SPY_GUESSED_LOCATION.value == "spy_guessed_location"
        assert VictoryType.CIVILIANS_VOTED_WRONG.value == "civilians_voted_wrong"
        assert VictoryType.CIVILIANS_VOTED_CORRECTLY.value == "civilians_voted_correctly"
        assert VictoryType.SPY_GUESS_INCORRECT.value == "spy_guess_incorrect"
        assert VictoryType.SPY_LEAKED_LOCATION.value == "spy_leaked_location"
        assert VictoryType.CANCELLED.value == "cancelled"
        assert VictoryType.UNKNOWN.value == "unknown"
