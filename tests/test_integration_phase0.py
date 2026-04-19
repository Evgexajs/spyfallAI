"""Integration tests for Phase 0: Full game with 3 characters.

These tests require OPENAI_API_KEY to run real LLM calls.
They verify the complete game flow from setup to resolution.
"""

import asyncio
import os
from collections import Counter
from pathlib import Path

import pytest

from src.cli import load_character, run_game
from src.models import TurnType
from src.storage import load_game


OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SKIP_REASON = "OPENAI_API_KEY not set - skipping integration tests"

TEST_CHARACTERS = ["boris_molot", "zoya", "kim"]
TEST_LOCATIONS = ["hospital", "airplane"]

SHORT_DURATION = 1
SHORT_MAX_QUESTIONS = 6


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
                m in t.lower() for m in ["подобно", "как ", "словно", "аналогия", "сравни"]
            ),
            "introductory_phrases": lambda t: any(
                m in t.lower() for m in ["строго говоря", "следует отметить", "очевидно", "разумеется"]
            ),
            "long_reply": lambda t: len(t.split(".")) >= 3,
        },
        "father_ignatius": {
            "conscience_appeal": lambda t: any(
                m in t.lower() for m in ["совесть", "честность", "правда", "искренн"]
            ),
            "names_addressee": lambda t: any(
                name.lower() in t.lower()
                for name in ["Борис", "Зоя", "Ким", "Марго", "Штейн", "Лёха", "Аврора"]
            ),
        },
        "lyokha": {
            "short_reply": lambda t: len(t.split(".")) <= 2,
            "colloquial_speech": lambda t: any(
                m in t.lower() for m in ["чё", "ну", "да ладно", "не гони", "блин", "короче"]
            ),
        },
        "aurora": {
            "long_reply": lambda t: len(t.split(".")) >= 3,
            "exclamation_present": lambda t: "!" in t,
            "theatrical_pauses": lambda t: "..." in t,
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


def validate_game_structure(game) -> list[str]:
    """Validate game structure and return list of issues."""
    issues = []

    if not game.id:
        issues.append("Game ID is missing")

    if not game.started_at:
        issues.append("Game started_at is missing")

    if not game.location_id:
        issues.append("Location ID is missing")

    if not game.players or len(game.players) < 3:
        issues.append(f"Expected at least 3 players, got {len(game.players) if game.players else 0}")

    if not game.spy_id:
        issues.append("Spy ID is missing")

    spy_count = sum(1 for p in game.players if p.is_spy)
    if spy_count != 1:
        issues.append(f"Expected exactly 1 spy, got {spy_count}")

    if not game.turns:
        issues.append("No turns recorded")

    if not game.outcome:
        issues.append("Game outcome is missing")
    elif game.outcome.winner not in ["civilians", "spy"]:
        issues.append(f"Unexpected winner: {game.outcome.winner}")

    if not game.phase_transitions:
        issues.append("No phase transitions recorded")

    return issues


@pytest.mark.skipif(not has_openai_key(), reason=SKIP_REASON)
class TestIntegrationPhase0:
    """Integration tests for Phase 0 functionality."""

    def test_single_game_completes(self):
        """Test that a single game completes successfully."""
        async def _run():
            filepath = await run_game(
                character_ids=TEST_CHARACTERS,
                location_id=TEST_LOCATIONS[0],
                duration_minutes=SHORT_DURATION,
                max_questions=SHORT_MAX_QUESTIONS,
            )

            assert filepath.exists(), f"Game log not created: {filepath}"

            game = load_game(filepath)
            issues = validate_game_structure(game)
            assert not issues, f"Game structure issues: {issues}"

            filepath.unlink()

        asyncio.run(_run())

    def test_three_games_complete_without_errors(self):
        """
        Run 3 games and verify all complete without errors.

        This is the main acceptance criterion for TASK-039.
        """
        async def _run():
            game_files = []
            errors = []

            for i in range(3):
                try:
                    location = TEST_LOCATIONS[i % len(TEST_LOCATIONS)]
                    filepath = await run_game(
                        character_ids=TEST_CHARACTERS,
                        location_id=location,
                        duration_minutes=SHORT_DURATION,
                        max_questions=SHORT_MAX_QUESTIONS,
                    )
                    game_files.append(filepath)
                except Exception as e:
                    errors.append(f"Game {i+1} failed: {e}")

            assert not errors, f"Some games failed: {errors}"
            assert len(game_files) == 3, f"Expected 3 games, got {len(game_files)}"

            for i, filepath in enumerate(game_files):
                assert filepath.exists(), f"Game {i+1} log not found"
                game = load_game(filepath)
                issues = validate_game_structure(game)
                assert not issues, f"Game {i+1} structure issues: {issues}"

                assert game.outcome is not None, f"Game {i+1} has no outcome"
                assert game.outcome.winner in ["civilians", "spy"], \
                    f"Game {i+1} unexpected winner: {game.outcome.winner}"

            for filepath in game_files:
                filepath.unlink()

        asyncio.run(_run())

    def test_characters_are_distinguishable(self):
        """
        Verify that character voices are distinguishable in their turns.

        Checks that each character exhibits their defining markers.
        """
        async def _run():
            filepath = await run_game(
                character_ids=TEST_CHARACTERS,
                location_id=TEST_LOCATIONS[0],
                duration_minutes=SHORT_DURATION,
                max_questions=SHORT_MAX_QUESTIONS,
            )

            game = load_game(filepath)

            conversational_turns = [
                t for t in game.turns
                if t.type in [TurnType.QUESTION, TurnType.ANSWER, TurnType.INTERVENTION]
            ]

            marker_results = check_character_markers(conversational_turns, TEST_CHARACTERS)

            for char_id in TEST_CHARACTERS:
                result = marker_results[char_id]
                total_markers = sum(result["markers_detected"].values())

                if result["total_turns"] > 0:
                    assert total_markers > 0, \
                        f"{char_id} had {result['total_turns']} turns but no markers detected"

            filepath.unlink()

        asyncio.run(_run())

    def test_game_log_is_valid_and_complete(self):
        """Verify the game log contains all required data."""
        async def _run():
            filepath = await run_game(
                character_ids=TEST_CHARACTERS,
                location_id=TEST_LOCATIONS[0],
                duration_minutes=SHORT_DURATION,
                max_questions=SHORT_MAX_QUESTIONS,
            )

            game = load_game(filepath)

            assert game.config is not None, "Game config missing"
            assert game.config.duration_minutes == SHORT_DURATION
            assert game.config.max_questions == SHORT_MAX_QUESTIONS

            assert game.token_usage is not None, "Token usage missing"
            assert game.token_usage.total_cost_usd >= 0
            assert game.token_usage.llm_calls_count > 0

            for player in game.players:
                assert player.character_id in TEST_CHARACTERS
                if player.is_spy:
                    assert player.role_id is None
                else:
                    assert player.role_id is not None

            question_turns = [t for t in game.turns if t.type == TurnType.QUESTION]
            answer_turns = [t for t in game.turns if t.type == TurnType.ANSWER]

            assert len(question_turns) > 0, "No questions in game"
            assert len(answer_turns) > 0, "No answers in game"

            assert "SETUP" in [p.phase for p in game.phase_transitions]

            filepath.unlink()

        asyncio.run(_run())


def run_sync_test():
    """Helper to run a single game synchronously for manual testing."""
    if not has_openai_key():
        print(f"Skipping: {SKIP_REASON}")
        return

    async def _run():
        filepath = await run_game(
            character_ids=TEST_CHARACTERS,
            location_id=TEST_LOCATIONS[0],
            duration_minutes=SHORT_DURATION,
            max_questions=SHORT_MAX_QUESTIONS,
        )
        print(f"Game saved to: {filepath}")

        game = load_game(filepath)
        print(f"Winner: {game.outcome.winner if game.outcome else 'N/A'}")
        print(f"Turns: {len(game.turns)}")
        print(f"Cost: ${game.token_usage.total_cost_usd:.4f}")

        return filepath

    return asyncio.run(_run())


if __name__ == "__main__":
    run_sync_test()
