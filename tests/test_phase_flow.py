"""Tests for TASK-062: Updated phase flow in orchestrator.

Tests verify:
1. Normal flow: main_round → preliminary_vote → defense → final_vote → resolution
2. Early voting flow: main_round → optional_vote → preliminary_vote → defense → final_vote
3. Phase transitions are correctly recorded
"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.models.game import (
    Game, GameConfig, GamePhase, GameOutcome, Player, Turn, TurnType,
    PhaseEntry, DefenseSpeech, VoteChange,
)
from src.models.character import Character, Marker, MarkerMethod
from src.models.location import Location, Role
from src.orchestrator.game_engine import (
    setup_game, run_main_round, run_preliminary_vote,
    run_defense_speeches, run_final_vote, _transition_phase,
)
from src.llm.adapter import LLMResponse


def run_async(coro):
    """Run an async coroutine in a new event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def create_mock_characters():
    """Create minimal mock characters for testing."""
    chars = []
    for i, (name, archetype) in enumerate([
        ("Boris", "aggressor"),
        ("Zoya", "cynic"),
        ("Kim", "paranoid"),
        ("Margo", "manipulator"),
    ]):
        char = Character(
            id=f"char_{i}",
            display_name=name,
            archetype=archetype,
            backstory=f"{name} backstory - a character with a detailed history and motivations",
            voice_style=f"{name} voice style - distinctive speech patterns and vocabulary",
            must_directives=["Test directive for must"],
            must_not_directives=["Test directive for must not"],
            detectable_markers=[
                Marker(
                    id="test_marker",
                    method=MarkerMethod.REGEX,
                    pattern="test",
                    description="Test marker description",
                )
            ],
            personal_triggers=[],
            intervention_priority=5,
            intervention_threshold=0.5,
        )
        chars.append(char)
    return chars


def create_mock_game(characters, location_id="hospital"):
    """Create a mock game with given characters."""
    players = [
        Player(character_id=c.id, role_id=f"role_{i}", is_spy=(i == 0))
        for i, c in enumerate(characters)
    ]

    return Game(
        id=uuid4(),
        started_at=datetime.now(),
        config=GameConfig(
            duration_minutes=1,
            max_questions=5,
            players_count=len(characters),
            main_model="gpt-4o",
            utility_model="gpt-4o-mini",
        ),
        location_id=location_id,
        players=players,
        spy_id=characters[0].id,
        turns=[],
        spy_confidence_log=[],
        triggered_events=[],
        phase_transitions=[
            PhaseEntry(
                timestamp=datetime.now(),
                from_phase=None,
                to_phase=GamePhase.SETUP,
                reason="Game setup",
            )
        ],
    )


class TestGamePhaseEnum:
    """Test that GamePhase enum contains all required phases."""

    def test_preliminary_vote_phase_exists(self):
        """GamePhase enum should contain PRELIMINARY_VOTE."""
        assert hasattr(GamePhase, "PRELIMINARY_VOTE")
        assert GamePhase.PRELIMINARY_VOTE.value == "preliminary_vote"

    def test_pre_final_vote_defense_phase_exists(self):
        """GamePhase enum should contain PRE_FINAL_VOTE_DEFENSE."""
        assert hasattr(GamePhase, "PRE_FINAL_VOTE_DEFENSE")
        assert GamePhase.PRE_FINAL_VOTE_DEFENSE.value == "pre_final_vote_defense"

    def test_all_phases_exist(self):
        """All required phases should exist in GamePhase enum."""
        required_phases = [
            "SETUP",
            "MAIN_ROUND",
            "OPTIONAL_VOTE",
            "PRELIMINARY_VOTE",
            "PRE_FINAL_VOTE_DEFENSE",
            "FINAL_VOTE",
            "RESOLUTION",
        ]
        for phase in required_phases:
            assert hasattr(GamePhase, phase), f"Missing phase: {phase}"


class TestPhaseTransitions:
    """Test phase transition recording."""

    def test_transition_phase_records_correctly(self):
        """_transition_phase should record transition with correct from/to phases."""
        characters = create_mock_characters()
        game = create_mock_game(characters)

        initial_count = len(game.phase_transitions)
        _transition_phase(game, GamePhase.MAIN_ROUND, "Test transition")

        assert len(game.phase_transitions) == initial_count + 1
        last_transition = game.phase_transitions[-1]
        assert last_transition.from_phase == GamePhase.SETUP
        assert last_transition.to_phase == GamePhase.MAIN_ROUND
        assert last_transition.reason == "Test transition"

    def test_transition_chain_records_all_phases(self):
        """Multiple transitions should chain correctly."""
        characters = create_mock_characters()
        game = create_mock_game(characters)

        _transition_phase(game, GamePhase.MAIN_ROUND, "Start main round")
        _transition_phase(game, GamePhase.PRELIMINARY_VOTE, "Start voting")
        _transition_phase(game, GamePhase.PRE_FINAL_VOTE_DEFENSE, "Start defense")
        _transition_phase(game, GamePhase.FINAL_VOTE, "Final vote")
        _transition_phase(game, GamePhase.RESOLUTION, "Resolution")

        assert len(game.phase_transitions) == 6  # SETUP + 5 transitions

        phases = [t.to_phase for t in game.phase_transitions]
        expected = [
            GamePhase.SETUP,
            GamePhase.MAIN_ROUND,
            GamePhase.PRELIMINARY_VOTE,
            GamePhase.PRE_FINAL_VOTE_DEFENSE,
            GamePhase.FINAL_VOTE,
            GamePhase.RESOLUTION,
        ]
        assert phases == expected


class TestNormalPhaseFlow:
    """Test normal game flow without early voting."""

    def test_preliminary_vote_transitions_from_main_round(self):
        """run_preliminary_vote should transition to PRELIMINARY_VOTE phase."""
        async def _test():
            characters = create_mock_characters()
            game = create_mock_game(characters)
            _transition_phase(game, GamePhase.MAIN_ROUND, "Main round started")

            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(return_value=LLMResponse(
                content=f"Голосую за {characters[1].id}",
                input_tokens=10,
                output_tokens=5,
                model="gpt-4o-mini",
            ))

            result_game, vote_counts = await run_preliminary_vote(
                game, characters, mock_provider
            )

            phases = [t.to_phase for t in result_game.phase_transitions]
            assert GamePhase.PRELIMINARY_VOTE in phases

        run_async(_test())

    def test_defense_speeches_transitions_to_defense_phase(self):
        """run_defense_speeches should transition to PRE_FINAL_VOTE_DEFENSE."""
        async def _test():
            characters = create_mock_characters()
            game = create_mock_game(characters)
            _transition_phase(game, GamePhase.MAIN_ROUND, "Main round")
            _transition_phase(game, GamePhase.PRELIMINARY_VOTE, "Preliminary vote")

            vote_counts = {characters[1].id: 3}

            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(return_value=LLMResponse(
                content="Я невиновен!",
                input_tokens=10,
                output_tokens=5,
                model="gpt-4o",
            ))

            result_game, defense_executed = await run_defense_speeches(
                game, characters, vote_counts, mock_provider
            )

            phases = [t.to_phase for t in result_game.phase_transitions]
            assert GamePhase.PRE_FINAL_VOTE_DEFENSE in phases

        run_async(_test())

    def test_final_vote_transitions_to_final_vote_phase(self):
        """run_final_vote should transition to FINAL_VOTE phase."""
        async def _test():
            characters = create_mock_characters()
            game = create_mock_game(characters)
            _transition_phase(game, GamePhase.MAIN_ROUND, "Main round")
            _transition_phase(game, GamePhase.PRELIMINARY_VOTE, "Preliminary vote")
            _transition_phase(game, GamePhase.PRE_FINAL_VOTE_DEFENSE, "Defense")

            game.preliminary_vote_result = {
                c.id: characters[1].id for c in characters
            }

            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(return_value=LLMResponse(
                content=f"Подтверждаю голос за {characters[1].id}",
                input_tokens=10,
                output_tokens=5,
                model="gpt-4o",
            ))

            result_game = await run_final_vote(
                game, characters, mock_provider,
                defense_was_executed=True,
            )

            phases = [t.to_phase for t in result_game.phase_transitions]
            assert GamePhase.FINAL_VOTE in phases

        run_async(_test())


class TestEarlyVotingFlow:
    """Test early voting (optional_vote) goes through new phases."""

    def test_optional_vote_phase_exists(self):
        """OPTIONAL_VOTE phase should be defined."""
        assert GamePhase.OPTIONAL_VOTE.value == "optional_vote"

    def test_early_voting_triggers_optional_vote_transition(self):
        """When early voting triggers, should transition to OPTIONAL_VOTE."""
        characters = create_mock_characters()
        game = create_mock_game(characters)
        _transition_phase(game, GamePhase.MAIN_ROUND, "Main round started")

        for i, char in enumerate(characters):
            turn = Turn(
                turn_number=i * 2 + 1,
                timestamp=datetime.now(),
                speaker_id=characters[(i + 1) % len(characters)].id,
                addressee_id=char.id,
                type=TurnType.QUESTION,
                content=f"{char.display_name}, ты шпион!",
                display_delay_ms=100,
            )
            game.turns.append(turn)

            turn2 = Turn(
                turn_number=i * 2 + 2,
                timestamp=datetime.now(),
                speaker_id=char.id,
                addressee_id=characters[(i + 1) % len(characters)].id,
                type=TurnType.ANSWER,
                content="Нет, это не я!",
                display_delay_ms=100,
            )
            game.turns.append(turn2)

        _transition_phase(game, GamePhase.OPTIONAL_VOTE, "Early voting triggered")

        phases = [t.to_phase for t in game.phase_transitions]
        assert GamePhase.OPTIONAL_VOTE in phases

    def test_after_optional_vote_goes_to_preliminary(self):
        """After OPTIONAL_VOTE, should transition to PRELIMINARY_VOTE."""
        async def _test():
            characters = create_mock_characters()
            game = create_mock_game(characters)
            _transition_phase(game, GamePhase.MAIN_ROUND, "Main round")
            _transition_phase(game, GamePhase.OPTIONAL_VOTE, "Early voting triggered")

            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(return_value=LLMResponse(
                content=f"Голосую за {characters[1].id}",
                input_tokens=10,
                output_tokens=5,
                model="gpt-4o-mini",
            ))

            result_game, vote_counts = await run_preliminary_vote(
                game, characters, mock_provider
            )

            transitions = result_game.phase_transitions
            optional_vote_idx = None
            preliminary_idx = None

            for i, t in enumerate(transitions):
                if t.to_phase == GamePhase.OPTIONAL_VOTE:
                    optional_vote_idx = i
                if t.to_phase == GamePhase.PRELIMINARY_VOTE:
                    preliminary_idx = i

            assert optional_vote_idx is not None
            assert preliminary_idx is not None
            assert preliminary_idx > optional_vote_idx

            preliminary_transition = transitions[preliminary_idx]
            assert preliminary_transition.from_phase == GamePhase.OPTIONAL_VOTE

        run_async(_test())


class TestFullPhaseFlowIntegration:
    """Integration tests for complete phase flow."""

    def test_normal_flow_phases_order(self):
        """Normal flow should have phases in correct order."""
        characters = create_mock_characters()
        game = create_mock_game(characters)

        _transition_phase(game, GamePhase.MAIN_ROUND, "Main round started")
        _transition_phase(game, GamePhase.PRELIMINARY_VOTE, "Preliminary voting")
        _transition_phase(game, GamePhase.PRE_FINAL_VOTE_DEFENSE, "Defense speeches")
        _transition_phase(game, GamePhase.FINAL_VOTE, "Final voting")
        _transition_phase(game, GamePhase.RESOLUTION, "Game ended")

        phases = [t.to_phase for t in game.phase_transitions]
        expected_order = [
            GamePhase.SETUP,
            GamePhase.MAIN_ROUND,
            GamePhase.PRELIMINARY_VOTE,
            GamePhase.PRE_FINAL_VOTE_DEFENSE,
            GamePhase.FINAL_VOTE,
            GamePhase.RESOLUTION,
        ]
        assert phases == expected_order

    def test_early_voting_flow_phases_order(self):
        """Early voting flow should include OPTIONAL_VOTE before PRELIMINARY_VOTE."""
        characters = create_mock_characters()
        game = create_mock_game(characters)

        _transition_phase(game, GamePhase.MAIN_ROUND, "Main round started")
        _transition_phase(game, GamePhase.OPTIONAL_VOTE, "Early voting triggered")
        _transition_phase(game, GamePhase.PRELIMINARY_VOTE, "Preliminary voting")
        _transition_phase(game, GamePhase.PRE_FINAL_VOTE_DEFENSE, "Defense speeches")
        _transition_phase(game, GamePhase.FINAL_VOTE, "Final voting")
        _transition_phase(game, GamePhase.RESOLUTION, "Game ended")

        phases = [t.to_phase for t in game.phase_transitions]
        expected_order = [
            GamePhase.SETUP,
            GamePhase.MAIN_ROUND,
            GamePhase.OPTIONAL_VOTE,
            GamePhase.PRELIMINARY_VOTE,
            GamePhase.PRE_FINAL_VOTE_DEFENSE,
            GamePhase.FINAL_VOTE,
            GamePhase.RESOLUTION,
        ]
        assert phases == expected_order

    def test_phase_transition_timestamps_increase(self):
        """Phase transition timestamps should be monotonically increasing."""
        import time

        characters = create_mock_characters()
        game = create_mock_game(characters)

        time.sleep(0.01)
        _transition_phase(game, GamePhase.MAIN_ROUND, "1")
        time.sleep(0.01)
        _transition_phase(game, GamePhase.PRELIMINARY_VOTE, "2")
        time.sleep(0.01)
        _transition_phase(game, GamePhase.FINAL_VOTE, "3")

        timestamps = [t.timestamp for t in game.phase_transitions]
        for i in range(1, len(timestamps)):
            assert timestamps[i] > timestamps[i-1]


class TestPhaseStatusField:
    """Test PhaseEntry status field for special cases."""

    def test_defense_skipped_records_status(self):
        """When defense is skipped, PhaseEntry should have status field."""
        async def _test():
            characters = create_mock_characters()
            game = create_mock_game(characters)
            _transition_phase(game, GamePhase.MAIN_ROUND, "Main round")
            _transition_phase(game, GamePhase.PRELIMINARY_VOTE, "Preliminary vote")

            vote_counts = {characters[1].id: 1}

            with patch.dict('os.environ', {'DEFENSE_MIN_VOTES_TO_QUALIFY': '3'}):
                mock_provider = MagicMock()
                result_game, defense_executed = await run_defense_speeches(
                    game, characters, vote_counts, mock_provider
                )

            assert defense_executed is False

            defense_transitions = [
                t for t in result_game.phase_transitions
                if t.to_phase == GamePhase.PRE_FINAL_VOTE_DEFENSE
            ]
            assert len(defense_transitions) == 1
            assert "skipped" in (defense_transitions[0].status or "")

        run_async(_test())

    def test_final_vote_copied_records_status(self):
        """When final vote copies preliminary, PhaseEntry should have status."""
        async def _test():
            characters = create_mock_characters()
            game = create_mock_game(characters)
            _transition_phase(game, GamePhase.MAIN_ROUND, "Main round")
            _transition_phase(game, GamePhase.PRELIMINARY_VOTE, "Preliminary vote")
            _transition_phase(game, GamePhase.PRE_FINAL_VOTE_DEFENSE, "Defense skipped")

            game.preliminary_vote_result = {
                c.id: characters[1].id for c in characters
            }

            mock_provider = MagicMock()

            result_game = await run_final_vote(
                game, characters, mock_provider,
                defense_was_executed=False,
            )

            final_transitions = [
                t for t in result_game.phase_transitions
                if t.to_phase == GamePhase.FINAL_VOTE
            ]
            assert len(final_transitions) == 1
            assert final_transitions[0].status == "skipped_copied_from_preliminary"

        run_async(_test())


class TestVoteSplitBehavior:
    """Test behavior when votes split (no strict majority)."""

    def test_vote_split_spy_wins(self):
        """When votes split (no strict majority), spy should win."""
        async def _test():
            characters = create_mock_characters()
            game = create_mock_game(characters)
            _transition_phase(game, GamePhase.MAIN_ROUND, "Main round")
            _transition_phase(game, GamePhase.PRELIMINARY_VOTE, "Preliminary vote")
            _transition_phase(game, GamePhase.PRE_FINAL_VOTE_DEFENSE, "Defense")

            game.preliminary_vote_result = {
                characters[0].id: characters[1].id,
                characters[1].id: characters[2].id,
                characters[2].id: characters[0].id,
                characters[3].id: characters[1].id,
            }

            game.defense_speeches = [
                DefenseSpeech(
                    defender_id=characters[1].id,
                    votes_received=2,
                    content="Я невиновен!",
                    timestamp=datetime.now(),
                ),
            ]

            mock_provider = MagicMock()

            response_map = {
                characters[0].id: characters[2].id,
                characters[1].id: characters[0].id,
                characters[2].id: characters[1].id,
                characters[3].id: characters[3].id,
            }

            call_count = [0]
            async def mock_complete(messages, **kwargs):
                voter_idx = call_count[0] % len(characters)
                call_count[0] += 1
                voter_id = characters[voter_idx].id
                target = response_map.get(voter_id, characters[1].id)
                return LLMResponse(
                    content=f"Голосую за {target}",
                    input_tokens=10,
                    output_tokens=5,
                    model="gpt-4o",
                )

            mock_provider.complete = mock_complete

            result_game = await run_final_vote(
                game, characters, mock_provider,
                defense_was_executed=True,
            )

            assert result_game.outcome is not None
            assert result_game.outcome.winner == "spy"
            assert "разделились" in result_game.outcome.reason

        run_async(_test())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
