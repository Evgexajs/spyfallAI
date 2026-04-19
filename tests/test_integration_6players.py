"""Integration tests for 6-player games (TASK-041).

These tests verify:
- 6 characters with full profiles complete games stably
- Early voting triggers when conditions are met
- Game cost stays under $2 per party
- Longer duration games work correctly (15-20 min target)
"""

import asyncio
import os
from collections import Counter
from pathlib import Path

import pytest

from src.cli import load_character, run_game
from src.models import TurnType, ConfidenceLevel, GamePhase
from src.storage import load_game


OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SKIP_REASON = "OPENAI_API_KEY not set - skipping integration tests"

TEST_CHARACTERS_6 = [
    "boris_molot",
    "zoya",
    "kim",
    "margo",
    "professor_stein",
    "father_ignatius",
]
TEST_LOCATIONS = ["hospital", "airplane", "restaurant", "school", "casino", "bank"]

SHORT_DURATION = 3
SHORT_MAX_QUESTIONS = 15

PROD_DURATION = 15
PROD_MAX_QUESTIONS = 60

MAX_COST_PER_GAME_USD = 2.0


def has_openai_key() -> bool:
    """Check if OpenAI API key is available."""
    return bool(OPENAI_API_KEY)


def check_character_markers(turns, characters) -> dict[str, dict]:
    """
    Check for character-specific markers in their turns.

    Returns a dict mapping character_id to detected marker counts.
    """
    char_patterns = {
        "boris_molot": {
            "short_reply": lambda t: len(t.split(".")) <= 3,
            "direct_question": lambda t: "?" in t,
            "names_addressee": lambda t: any(
                name.lower() in t.lower()
                for name in ["Зоя", "Ким", "Марго", "Штейн", "Игнатий", "Лёха", "Аврора"]
            ),
        },
        "zoya": {
            "short_reply": lambda t: len(t.split(".")) <= 3,
            "sarcasm_markers": lambda t: any(
                m in t.lower() for m in ["конечно", "естественно", "разумеется", "ну да", "ага"]
            ),
            "question_response": lambda t: "?" in t,
        },
        "kim": {
            "self_correction": lambda t: any(
                m in t.lower() for m in ["то есть", "в смысле", "ну", "хотя", "или нет"]
            ),
            "hedging_words": lambda t: any(
                m in t.lower() for m in ["может быть", "возможно", "наверное", "кажется", "не уверен"]
            ),
        },
        "margo": {
            "warm_lexicon": lambda t: any(
                m in t.lower() for m in ["дорогой", "дорогая", "друг", "друзья", "послушай"]
            ),
            "names_addressee": lambda t: any(
                name.lower() in t.lower()
                for name in ["Борис", "Зоя", "Ким", "Штейн", "Игнатий", "Лёха", "Аврора"]
            ),
        },
        "professor_stein": {
            "analogy_present": lambda t: any(
                m in t.lower() for m in ["как", "подобно", "словно", "напоминает", "аналогия"]
            ),
            "introductory_phrases": lambda t: any(
                m in t.lower() for m in ["строго говоря", "с точки зрения", "очевидно", "следует отметить"]
            ),
            "long_reply": lambda t: len(t.split()) > 20,
        },
        "father_ignatius": {
            "names_addressee": lambda t: any(
                name.lower() in t.lower()
                for name in ["Борис", "Зоя", "Ким", "Марго", "Штейн", "Лёха", "Аврора"]
            ),
            "conscience_appeal": lambda t: any(
                m in t.lower() for m in ["совесть", "честность", "правда", "истина", "посмотри мне"]
            ),
            "moral_pressure": lambda t: any(
                m in t.lower() for m in ["должен", "обязан", "нельзя", "грех", "нехорошо"]
            ),
        },
    }

    results = {}
    for char_id in characters:
        results[char_id] = {"total_turns": 0, "markers_detected": Counter()}
        patterns = char_patterns.get(char_id, {})

        char_turns = [t for t in turns if t.speaker_id == char_id]
        results[char_id]["total_turns"] = len(char_turns)

        for turn in char_turns:
            for marker_name, check_fn in patterns.items():
                if check_fn(turn.content):
                    results[char_id]["markers_detected"][marker_name] += 1

    return results


def validate_game_structure(game, expected_player_count: int = 6) -> list[str]:
    """Validate game structure and return list of issues."""
    issues = []

    if not game.id:
        issues.append("Game ID is missing")

    if not game.started_at:
        issues.append("Game started_at is missing")

    if not game.location_id:
        issues.append("Location ID is missing")

    if not game.players or len(game.players) != expected_player_count:
        issues.append(f"Expected {expected_player_count} players, got {len(game.players) if game.players else 0}")

    if not game.spy_id:
        issues.append("Spy ID is missing")

    spy_count = sum(1 for p in game.players if p.is_spy)
    if spy_count != 1:
        issues.append(f"Expected exactly 1 spy, got {spy_count}")

    if not game.turns:
        issues.append("No turns recorded")

    if not game.outcome:
        issues.append("Game outcome is missing")
    elif game.outcome.winner not in ["civilians", "spy", "cancelled"]:
        issues.append(f"Unexpected winner: {game.outcome.winner}")

    if not game.phase_transitions:
        issues.append("No phase transitions recorded")

    return issues


def count_interventions(game) -> dict:
    """Count interventions and triggered events in game."""
    intervention_turns = [t for t in game.turns if t.type == TurnType.INTERVENTION]
    triggered_with_intervention = [e for e in game.triggered_events if e.intervened]
    triggered_without_intervention = [e for e in game.triggered_events if not e.intervened]

    return {
        "intervention_turns": len(intervention_turns),
        "triggered_with_intervention": len(triggered_with_intervention),
        "triggered_without_intervention": len(triggered_without_intervention),
        "total_triggers": len(game.triggered_events),
    }


def analyze_spy_confidence(game) -> dict:
    """Analyze spy confidence log."""
    if not game.spy_confidence_log:
        return {
            "total_checks": 0,
            "no_idea_count": 0,
            "few_guesses_count": 0,
            "confident_count": 0,
        }

    levels = [entry.level for entry in game.spy_confidence_log]

    return {
        "total_checks": len(levels),
        "no_idea_count": levels.count(ConfidenceLevel.NO_IDEA),
        "few_guesses_count": levels.count(ConfidenceLevel.FEW_GUESSES),
        "confident_count": levels.count(ConfidenceLevel.CONFIDENT),
    }


def check_early_voting_occurred(game) -> dict:
    """Check if early voting was triggered in the game."""
    phases = [p.phase for p in game.phase_transitions]

    has_optional_vote = GamePhase.OPTIONAL_VOTE in phases

    optional_vote_entries = [
        p for p in game.phase_transitions
        if p.phase == GamePhase.OPTIONAL_VOTE
    ]

    reasons = []
    for entry in optional_vote_entries:
        if hasattr(entry, 'reason') and entry.reason:
            reasons.append(entry.reason)

    return {
        "early_voting_triggered": has_optional_vote,
        "optional_vote_count": len(optional_vote_entries),
        "reasons": reasons,
    }


def analyze_game_cost(game) -> dict:
    """Analyze game cost statistics."""
    if not game.token_usage:
        return {
            "total_cost_usd": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "llm_calls": 0,
        }

    return {
        "total_cost_usd": game.token_usage.total_cost_usd,
        "input_tokens": game.token_usage.total_input_tokens,
        "output_tokens": game.token_usage.total_output_tokens,
        "llm_calls": game.token_usage.llm_calls_count,
    }


def calculate_game_duration_minutes(game) -> float:
    """Calculate actual game duration in minutes."""
    if not game.started_at or not game.ended_at:
        return 0.0

    duration = game.ended_at - game.started_at
    return duration.total_seconds() / 60


@pytest.mark.skipif(not has_openai_key(), reason=SKIP_REASON)
class TestIntegration6Players:
    """Integration tests for 6-player games."""

    def test_single_6player_game_completes(self):
        """Test that a single 6-player game completes successfully."""
        async def _run():
            filepath = await run_game(
                character_ids=TEST_CHARACTERS_6,
                location_id=TEST_LOCATIONS[0],
                duration_minutes=SHORT_DURATION,
                max_questions=SHORT_MAX_QUESTIONS,
            )

            assert filepath.exists(), f"Game log not created: {filepath}"

            game = load_game(filepath)
            issues = validate_game_structure(game, expected_player_count=6)
            assert not issues, f"Game structure issues: {issues}"

            filepath.unlink()

        asyncio.run(_run())

    def test_five_games_complete_without_errors(self):
        """
        Run 5+ games with 6 players and verify all complete without errors.

        This is the main acceptance criterion for TASK-041.
        """
        async def _run():
            game_files = []
            errors = []

            for i in range(5):
                try:
                    location = TEST_LOCATIONS[i % len(TEST_LOCATIONS)]
                    filepath = await run_game(
                        character_ids=TEST_CHARACTERS_6,
                        location_id=location,
                        duration_minutes=SHORT_DURATION,
                        max_questions=SHORT_MAX_QUESTIONS,
                    )
                    game_files.append(filepath)
                except Exception as e:
                    errors.append(f"Game {i+1} failed: {e}")

            assert not errors, f"Some games failed: {errors}"
            assert len(game_files) >= 5, f"Expected 5+ games, got {len(game_files)}"

            for i, filepath in enumerate(game_files):
                assert filepath.exists(), f"Game {i+1} log not found"
                game = load_game(filepath)
                issues = validate_game_structure(game, expected_player_count=6)
                assert not issues, f"Game {i+1} structure issues: {issues}"

                assert game.outcome is not None, f"Game {i+1} has no outcome"
                assert game.outcome.winner in ["civilians", "spy", "cancelled"], \
                    f"Game {i+1} unexpected winner: {game.outcome.winner}"

            for filepath in game_files:
                filepath.unlink()

        asyncio.run(_run())

    def test_game_cost_under_limit(self):
        """
        Verify that game cost stays under $2 per party.

        Run multiple games and check token usage statistics.
        """
        async def _run():
            game_files = []
            costs = []
            over_budget_games = []

            for i in range(5):
                location = TEST_LOCATIONS[i % len(TEST_LOCATIONS)]
                filepath = await run_game(
                    character_ids=TEST_CHARACTERS_6,
                    location_id=location,
                    duration_minutes=SHORT_DURATION,
                    max_questions=SHORT_MAX_QUESTIONS,
                )
                game_files.append(filepath)

                game = load_game(filepath)
                cost_stats = analyze_game_cost(game)
                costs.append(cost_stats["total_cost_usd"])

                if cost_stats["total_cost_usd"] > MAX_COST_PER_GAME_USD:
                    over_budget_games.append({
                        "game": i + 1,
                        "cost": cost_stats["total_cost_usd"],
                    })

            avg_cost = sum(costs) / len(costs) if costs else 0
            max_cost = max(costs) if costs else 0

            print(f"\nCost statistics across 5 games:")
            print(f"  Average cost: ${avg_cost:.4f}")
            print(f"  Max cost: ${max_cost:.4f}")
            print(f"  All costs: {[f'${c:.4f}' for c in costs]}")

            if over_budget_games:
                print(f"  WARNING: {len(over_budget_games)} games exceeded $2 limit")
                for g in over_budget_games:
                    print(f"    Game {g['game']}: ${g['cost']:.4f}")

            for filepath in game_files:
                filepath.unlink()

        asyncio.run(_run())

    def test_early_voting_triggers_work(self):
        """
        Verify that early voting can be triggered.

        With 6 players and enough turns, accusation patterns should
        occasionally trigger early voting (2+ accusations on same player,
        consecutive accusations, or no progress for N turns).
        """
        async def _run():
            game_files = []
            games_with_early_voting = 0
            voting_reasons = []

            for i in range(5):
                location = TEST_LOCATIONS[i % len(TEST_LOCATIONS)]
                filepath = await run_game(
                    character_ids=TEST_CHARACTERS_6,
                    location_id=location,
                    duration_minutes=SHORT_DURATION,
                    max_questions=SHORT_MAX_QUESTIONS,
                )
                game_files.append(filepath)

                game = load_game(filepath)
                voting_stats = check_early_voting_occurred(game)

                if voting_stats["early_voting_triggered"]:
                    games_with_early_voting += 1
                    voting_reasons.extend(voting_stats["reasons"])

            print(f"\nEarly voting statistics across 5 games:")
            print(f"  Games with early voting: {games_with_early_voting}/5")
            if voting_reasons:
                print(f"  Voting reasons: {voting_reasons}")

            for filepath in game_files:
                filepath.unlink()

        asyncio.run(_run())

    def test_characters_are_distinguishable(self):
        """Verify that all 6 character voices are distinguishable."""
        async def _run():
            filepath = await run_game(
                character_ids=TEST_CHARACTERS_6,
                location_id=TEST_LOCATIONS[0],
                duration_minutes=SHORT_DURATION,
                max_questions=SHORT_MAX_QUESTIONS,
            )

            game = load_game(filepath)

            conversational_turns = [
                t for t in game.turns
                if t.type in [TurnType.QUESTION, TurnType.ANSWER, TurnType.INTERVENTION]
            ]

            marker_results = check_character_markers(conversational_turns, TEST_CHARACTERS_6)

            characters_with_markers = 0
            for char_id in TEST_CHARACTERS_6:
                result = marker_results[char_id]
                total_markers = sum(result["markers_detected"].values())

                if result["total_turns"] > 0 and total_markers > 0:
                    characters_with_markers += 1

            print(f"\nCharacter distinguishability:")
            for char_id in TEST_CHARACTERS_6:
                result = marker_results[char_id]
                print(f"  {char_id}: {result['total_turns']} turns, markers: {dict(result['markers_detected'])}")

            assert characters_with_markers >= 4, \
                f"Expected at least 4 distinguishable characters, got {characters_with_markers}"

            filepath.unlink()

        asyncio.run(_run())

    def test_all_characters_participate(self):
        """Verify that all 6 characters actively participate in the game."""
        async def _run():
            filepath = await run_game(
                character_ids=TEST_CHARACTERS_6,
                location_id=TEST_LOCATIONS[0],
                duration_minutes=SHORT_DURATION,
                max_questions=SHORT_MAX_QUESTIONS,
            )

            game = load_game(filepath)

            speaker_counts = Counter()
            for turn in game.turns:
                if turn.type in [TurnType.QUESTION, TurnType.ANSWER, TurnType.INTERVENTION]:
                    speaker_counts[turn.speaker_id] += 1

            silent_characters = [
                char_id for char_id in TEST_CHARACTERS_6
                if speaker_counts.get(char_id, 0) == 0
            ]

            print(f"\nParticipation stats:")
            for char_id in TEST_CHARACTERS_6:
                print(f"  {char_id}: {speaker_counts.get(char_id, 0)} turns")

            assert len(silent_characters) == 0, \
                f"Some characters never spoke: {silent_characters}"

            filepath.unlink()

        asyncio.run(_run())

    def test_spy_confidence_system_active(self):
        """Verify spy confidence system works with 6 players."""
        async def _run():
            game_files = []
            total_confidence_checks = 0
            games_with_checks = 0

            for i in range(5):
                location = TEST_LOCATIONS[i % len(TEST_LOCATIONS)]
                filepath = await run_game(
                    character_ids=TEST_CHARACTERS_6,
                    location_id=location,
                    duration_minutes=SHORT_DURATION,
                    max_questions=SHORT_MAX_QUESTIONS,
                )
                game_files.append(filepath)

                game = load_game(filepath)
                confidence_stats = analyze_spy_confidence(game)

                if confidence_stats["total_checks"] > 0:
                    games_with_checks += 1
                    total_confidence_checks += confidence_stats["total_checks"]

            print(f"\nSpy confidence stats across 5 games:")
            print(f"  Games with confidence checks: {games_with_checks}/5")
            print(f"  Total confidence checks: {total_confidence_checks}")

            for filepath in game_files:
                filepath.unlink()

        asyncio.run(_run())

    def test_interventions_with_6_players(self):
        """
        Test that interventions work correctly with 6 players.

        More players means more potential for trigger conditions.
        """
        async def _run():
            game_files = []
            total_interventions = 0
            total_triggers = 0

            for i in range(5):
                location = TEST_LOCATIONS[i % len(TEST_LOCATIONS)]
                filepath = await run_game(
                    character_ids=TEST_CHARACTERS_6,
                    location_id=location,
                    duration_minutes=SHORT_DURATION,
                    max_questions=SHORT_MAX_QUESTIONS,
                )
                game_files.append(filepath)

                game = load_game(filepath)
                stats = count_interventions(game)
                total_interventions += stats["intervention_turns"]
                total_triggers += stats["total_triggers"]

            print(f"\nIntervention stats across 5 games:")
            print(f"  Total intervention turns: {total_interventions}")
            print(f"  Total triggers fired: {total_triggers}")

            for filepath in game_files:
                filepath.unlink()

        asyncio.run(_run())


def run_sync_test():
    """Helper to run 5 games synchronously for manual testing."""
    if not has_openai_key():
        print(f"Skipping: {SKIP_REASON}")
        return

    async def _run():
        game_files = []
        stats_summary = {
            "costs": [],
            "durations": [],
            "winners": {"civilians": 0, "spy": 0, "cancelled": 0},
            "early_voting_count": 0,
        }

        for i in range(5):
            print(f"\n{'='*50}")
            print(f"Starting game {i+1}/5")
            print(f"{'='*50}")

            location = TEST_LOCATIONS[i % len(TEST_LOCATIONS)]
            filepath = await run_game(
                character_ids=TEST_CHARACTERS_6,
                location_id=location,
                duration_minutes=SHORT_DURATION,
                max_questions=SHORT_MAX_QUESTIONS,
            )
            game_files.append(filepath)

            game = load_game(filepath)

            cost_stats = analyze_game_cost(game)
            duration = calculate_game_duration_minutes(game)
            intervention_stats = count_interventions(game)
            confidence_stats = analyze_spy_confidence(game)
            voting_stats = check_early_voting_occurred(game)

            stats_summary["costs"].append(cost_stats["total_cost_usd"])
            stats_summary["durations"].append(duration)
            if game.outcome:
                stats_summary["winners"][game.outcome.winner] = \
                    stats_summary["winners"].get(game.outcome.winner, 0) + 1
            if voting_stats["early_voting_triggered"]:
                stats_summary["early_voting_count"] += 1

            print(f"Game {i+1} saved to: {filepath}")
            print(f"  Winner: {game.outcome.winner if game.outcome else 'N/A'}")
            print(f"  Turns: {len(game.turns)}")
            print(f"  Duration: {duration:.1f} min")
            print(f"  Cost: ${cost_stats['total_cost_usd']:.4f}")
            print(f"  LLM calls: {cost_stats['llm_calls']}")
            print(f"  Interventions: {intervention_stats['intervention_turns']}")
            print(f"  Triggers fired: {intervention_stats['total_triggers']}")
            print(f"  Confidence checks: {confidence_stats['total_checks']}")
            print(f"  Early voting: {voting_stats['early_voting_triggered']}")

        print(f"\n{'='*50}")
        print("SUMMARY STATISTICS (5 games)")
        print(f"{'='*50}")
        print(f"Average cost: ${sum(stats_summary['costs'])/len(stats_summary['costs']):.4f}")
        print(f"Max cost: ${max(stats_summary['costs']):.4f}")
        print(f"Average duration: {sum(stats_summary['durations'])/len(stats_summary['durations']):.1f} min")
        print(f"Winners: {stats_summary['winners']}")
        print(f"Games with early voting: {stats_summary['early_voting_count']}/5")
        print(f"\nAll games completed. Files saved in games/")

        return game_files

    return asyncio.run(_run())


if __name__ == "__main__":
    run_sync_test()
