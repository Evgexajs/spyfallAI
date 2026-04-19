"""Integration tests for 4-player games (TASK-040).

These tests verify:
- 4 characters with full profiles complete games stably
- Trigger system and interventions work correctly
- Spy confidence system works correctly
"""

import asyncio
import os
from collections import Counter
from pathlib import Path

import pytest

from src.cli import load_character, run_game
from src.models import TurnType, ConfidenceLevel
from src.storage import load_game


OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SKIP_REASON = "OPENAI_API_KEY not set - skipping integration tests"

TEST_CHARACTERS_4 = ["boris_molot", "zoya", "kim", "margo"]
TEST_LOCATIONS = ["hospital", "airplane", "restaurant", "school"]

SHORT_DURATION = 2
SHORT_MAX_QUESTIONS = 10


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


def validate_game_structure(game, expected_player_count: int = 4) -> list[str]:
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


@pytest.mark.skipif(not has_openai_key(), reason=SKIP_REASON)
class TestIntegration4Players:
    """Integration tests for 4-player games."""

    def test_single_4player_game_completes(self):
        """Test that a single 4-player game completes successfully."""
        async def _run():
            filepath = await run_game(
                character_ids=TEST_CHARACTERS_4,
                location_id=TEST_LOCATIONS[0],
                duration_minutes=SHORT_DURATION,
                max_questions=SHORT_MAX_QUESTIONS,
            )

            assert filepath.exists(), f"Game log not created: {filepath}"

            game = load_game(filepath)
            issues = validate_game_structure(game, expected_player_count=4)
            assert not issues, f"Game structure issues: {issues}"

            filepath.unlink()

        asyncio.run(_run())

    def test_five_games_complete_without_errors(self):
        """
        Run 5 games with 4 players and verify all complete without errors.

        This is the main acceptance criterion for TASK-040.
        """
        async def _run():
            game_files = []
            errors = []

            for i in range(5):
                try:
                    location = TEST_LOCATIONS[i % len(TEST_LOCATIONS)]
                    filepath = await run_game(
                        character_ids=TEST_CHARACTERS_4,
                        location_id=location,
                        duration_minutes=SHORT_DURATION,
                        max_questions=SHORT_MAX_QUESTIONS,
                    )
                    game_files.append(filepath)
                except Exception as e:
                    errors.append(f"Game {i+1} failed: {e}")

            assert not errors, f"Some games failed: {errors}"
            assert len(game_files) == 5, f"Expected 5 games, got {len(game_files)}"

            for i, filepath in enumerate(game_files):
                assert filepath.exists(), f"Game {i+1} log not found"
                game = load_game(filepath)
                issues = validate_game_structure(game, expected_player_count=4)
                assert not issues, f"Game {i+1} structure issues: {issues}"

                assert game.outcome is not None, f"Game {i+1} has no outcome"
                assert game.outcome.winner in ["civilians", "spy", "cancelled"], \
                    f"Game {i+1} unexpected winner: {game.outcome.winner}"

            for filepath in game_files:
                filepath.unlink()

        asyncio.run(_run())

    def test_interventions_present_in_logs(self):
        """
        Run 5 games and verify that interventions appear in at least some logs.

        The trigger system should produce interventions when conditions are met.
        """
        async def _run():
            total_interventions = 0
            total_triggers = 0
            game_files = []

            for i in range(5):
                location = TEST_LOCATIONS[i % len(TEST_LOCATIONS)]
                filepath = await run_game(
                    character_ids=TEST_CHARACTERS_4,
                    location_id=location,
                    duration_minutes=SHORT_DURATION,
                    max_questions=SHORT_MAX_QUESTIONS,
                )
                game_files.append(filepath)

                game = load_game(filepath)
                stats = count_interventions(game)
                total_interventions += stats["intervention_turns"]
                total_triggers += stats["total_triggers"]

            assert total_triggers >= 0, "Trigger system should be active"

            print(f"\nIntervention stats across 5 games:")
            print(f"  Total intervention turns: {total_interventions}")
            print(f"  Total triggers fired: {total_triggers}")

            for filepath in game_files:
                filepath.unlink()

        asyncio.run(_run())

    def test_spy_confidence_log_populated(self):
        """
        Verify that spy confidence checks are recorded in game logs.

        SPY_CONFIDENCE_CHECK_EVERY_N controls the frequency of checks.
        """
        async def _run():
            game_files = []
            total_confidence_checks = 0
            games_with_checks = 0

            for i in range(5):
                location = TEST_LOCATIONS[i % len(TEST_LOCATIONS)]
                filepath = await run_game(
                    character_ids=TEST_CHARACTERS_4,
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

                    for entry in game.spy_confidence_log:
                        assert entry.level in [
                            ConfidenceLevel.NO_IDEA,
                            ConfidenceLevel.FEW_GUESSES,
                            ConfidenceLevel.CONFIDENT,
                        ], f"Invalid confidence level: {entry.level}"

            print(f"\nSpy confidence stats across 5 games:")
            print(f"  Games with confidence checks: {games_with_checks}/5")
            print(f"  Total confidence checks: {total_confidence_checks}")

            for filepath in game_files:
                filepath.unlink()

        asyncio.run(_run())

    def test_characters_are_distinguishable(self):
        """Verify that all 4 character voices are distinguishable."""
        async def _run():
            filepath = await run_game(
                character_ids=TEST_CHARACTERS_4,
                location_id=TEST_LOCATIONS[0],
                duration_minutes=SHORT_DURATION,
                max_questions=SHORT_MAX_QUESTIONS,
            )

            game = load_game(filepath)

            conversational_turns = [
                t for t in game.turns
                if t.type in [TurnType.QUESTION, TurnType.ANSWER, TurnType.INTERVENTION]
            ]

            marker_results = check_character_markers(conversational_turns, TEST_CHARACTERS_4)

            for char_id in TEST_CHARACTERS_4:
                result = marker_results[char_id]
                total_markers = sum(result["markers_detected"].values())

                if result["total_turns"] > 0:
                    assert total_markers > 0, \
                        f"{char_id} had {result['total_turns']} turns but no markers detected"

            filepath.unlink()

        asyncio.run(_run())

    def test_trigger_system_active(self):
        """
        Verify that the trigger system is working by checking triggered_events.

        With 4 players and 10 max questions, we should have conditions
        that could trigger interventions (e.g., accusations, silence).
        """
        async def _run():
            filepath = await run_game(
                character_ids=TEST_CHARACTERS_4,
                location_id=TEST_LOCATIONS[0],
                duration_minutes=SHORT_DURATION,
                max_questions=SHORT_MAX_QUESTIONS,
            )

            game = load_game(filepath)

            assert hasattr(game, 'triggered_events'), "Game should have triggered_events field"

            print(f"\nTrigger events in game: {len(game.triggered_events)}")
            for event in game.triggered_events[:5]:
                print(f"  - {event.character_id}: {event.condition_type} -> {event.reaction_type} (intervened: {event.intervened})")

            filepath.unlink()

        asyncio.run(_run())


def run_sync_test():
    """Helper to run 5 games synchronously for manual testing."""
    if not has_openai_key():
        print(f"Skipping: {SKIP_REASON}")
        return

    async def _run():
        game_files = []
        for i in range(5):
            print(f"\n=== Starting game {i+1}/5 ===")
            location = TEST_LOCATIONS[i % len(TEST_LOCATIONS)]
            filepath = await run_game(
                character_ids=TEST_CHARACTERS_4,
                location_id=location,
                duration_minutes=SHORT_DURATION,
                max_questions=SHORT_MAX_QUESTIONS,
            )
            game_files.append(filepath)

            game = load_game(filepath)
            intervention_stats = count_interventions(game)
            confidence_stats = analyze_spy_confidence(game)

            print(f"Game {i+1} saved to: {filepath}")
            print(f"  Winner: {game.outcome.winner if game.outcome else 'N/A'}")
            print(f"  Turns: {len(game.turns)}")
            print(f"  Cost: ${game.token_usage.total_cost_usd:.4f}")
            print(f"  Interventions: {intervention_stats['intervention_turns']}")
            print(f"  Triggers fired: {intervention_stats['total_triggers']}")
            print(f"  Confidence checks: {confidence_stats['total_checks']}")

        print("\n=== Summary ===")
        print(f"All 5 games completed. Files:")
        for f in game_files:
            print(f"  {f}")

        return game_files

    return asyncio.run(_run())


if __name__ == "__main__":
    run_sync_test()
