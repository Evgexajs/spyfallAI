"""Tests for preliminary voting phase (TASK-059, CR-001 F11)."""

import asyncio
import pytest
from datetime import datetime
from uuid import uuid4
from unittest.mock import MagicMock, patch


def run_async(coro):
    """Run an async coroutine in a new event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

from src.models import (
    Character,
    Game,
    GameConfig,
    GamePhase,
    Marker,
    MarkerMethod,
    PhaseEntry,
    Player,
    Turn,
    TurnType,
)
from src.orchestrator.game_engine import (
    run_preliminary_vote,
)


def create_test_character(char_id: str, display_name: str) -> Character:
    """Create a minimal test character."""
    return Character(
        id=char_id,
        display_name=display_name,
        archetype="test",
        backstory="Test backstory",
        voice_style="Test voice",
        must_directives=["Test directive"],
        must_not_directives=["Test prohibition"],
        detectable_markers=[
            Marker(
                id="test_marker",
                method=MarkerMethod.REGEX,
                pattern="test",
                description="Test marker",
            )
        ],
        personal_triggers=[],
        intervention_priority=5,
        intervention_threshold=0.5,
    )


def create_test_game(num_players: int = 3) -> Game:
    """Create a test game with specified number of players."""
    players = [
        Player(
            character_id=f"player_{i}",
            role_id=f"role_{i}" if i != 0 else None,
            is_spy=(i == 0),
        )
        for i in range(num_players)
    ]

    return Game(
        id=uuid4(),
        started_at=datetime.now(),
        config=GameConfig(
            duration_minutes=10,
            players_count=num_players,
            max_questions=20,
            main_model="gpt-4o",
            utility_model="gpt-4o-mini",
        ),
        location_id="hospital",
        players=players,
        spy_id="player_0",
        turns=[],
        spy_confidence_log=[],
        triggered_events=[],
        phase_transitions=[
            PhaseEntry(
                timestamp=datetime.now(),
                to_phase=GamePhase.SETUP,
                reason="Test game setup",
            )
        ],
    )


def create_test_characters(num: int = 3) -> list[Character]:
    """Create test characters."""
    return [
        create_test_character(f"player_{i}", f"Player {i}")
        for i in range(num)
    ]


def create_mock_llm_response(content: str) -> MagicMock:
    """Create a mock LLM response with all required attributes."""
    mock_response = MagicMock()
    mock_response.content = content
    mock_response.input_tokens = 100
    mock_response.output_tokens = 10
    mock_response.model = "gpt-4o-mini"
    mock_response.calculate_cost = MagicMock(return_value=0.001)
    return mock_response


class TestRunPreliminaryVoteBasics:
    """Tests for run_preliminary_vote function basics."""

    def test_basic_preliminary_vote(self):
        """Should collect votes from all players."""
        game = create_test_game(3)
        characters = create_test_characters(3)

        mock_provider = MagicMock()
        mock_response = create_mock_llm_response("player_1")

        async def mock_complete(*args, **kwargs):
            return mock_response

        mock_provider.complete = mock_complete

        updated_game, vote_counts = run_async(
            run_preliminary_vote(game, characters, provider=mock_provider)
        )

        assert updated_game.preliminary_vote_result is not None
        assert len(updated_game.preliminary_vote_result) == 3
        assert "player_0" in updated_game.preliminary_vote_result
        assert "player_1" in updated_game.preliminary_vote_result
        assert "player_2" in updated_game.preliminary_vote_result

    def test_preliminary_vote_creates_turns(self):
        """Should create PRELIMINARY_VOTE turns for each player."""
        game = create_test_game(3)
        characters = create_test_characters(3)

        mock_provider = MagicMock()
        mock_response = create_mock_llm_response("player_0")

        async def mock_complete(*args, **kwargs):
            return mock_response

        mock_provider.complete = mock_complete

        updated_game, _ = run_async(
            run_preliminary_vote(game, characters, provider=mock_provider)
        )

        vote_turns = [t for t in updated_game.turns if t.type == TurnType.PRELIMINARY_VOTE]
        assert len(vote_turns) == 3
        for turn in vote_turns:
            assert turn.addressee_id == "all"
            assert turn.display_delay_ms > 0

    def test_preliminary_vote_transitions_phase(self):
        """Should transition to PRELIMINARY_VOTE phase."""
        game = create_test_game(3)
        characters = create_test_characters(3)

        mock_provider = MagicMock()
        mock_response = create_mock_llm_response("player_2")

        async def mock_complete(*args, **kwargs):
            return mock_response

        mock_provider.complete = mock_complete

        updated_game, _ = run_async(
            run_preliminary_vote(game, characters, provider=mock_provider)
        )

        assert any(
            p.to_phase == GamePhase.PRELIMINARY_VOTE
            for p in updated_game.phase_transitions
        )


class TestVoteCounts:
    """Tests for vote counting logic."""

    def test_vote_counts_aggregate(self):
        """Should return correct vote counts aggregate."""
        game = create_test_game(3)
        characters = create_test_characters(3)

        mock_provider = MagicMock()
        responses = ["player_2", "player_2", "player_1"]
        call_count = [0]

        async def mock_complete(*args, **kwargs):
            idx = call_count[0] % len(responses)
            call_count[0] += 1
            return create_mock_llm_response(responses[idx])

        mock_provider.complete = mock_complete

        _, vote_counts = run_async(
            run_preliminary_vote(game, characters, provider=mock_provider)
        )

        assert vote_counts.get("player_2", 0) == 2
        assert vote_counts.get("player_1", 0) == 1
        assert vote_counts.get("player_0", 0) == 0

    def test_abstention_excluded_from_counts(self):
        """Should exclude abstentions from vote counts."""
        game = create_test_game(3)
        characters = create_test_characters(3)

        mock_provider = MagicMock()
        responses = ["player_1", "воздержусь", "player_1"]
        call_count = [0]

        async def mock_complete(*args, **kwargs):
            idx = call_count[0] % len(responses)
            call_count[0] += 1
            return create_mock_llm_response(responses[idx])

        mock_provider.complete = mock_complete

        with patch("src.orchestrator.game_engine.DEFENSE_ALLOW_ABSTAIN", True):
            updated_game, vote_counts = run_async(
                run_preliminary_vote(game, characters, provider=mock_provider)
            )

        total_votes = sum(vote_counts.values())
        assert total_votes == 2
        assert vote_counts.get("player_1", 0) == 2
        assert updated_game.preliminary_vote_result["player_1"] is None

    def test_all_abstentions_empty_counts(self):
        """When all abstain, vote counts should be empty."""
        game = create_test_game(3)
        characters = create_test_characters(3)

        mock_provider = MagicMock()
        mock_response = create_mock_llm_response("воздержусь")

        async def mock_complete(*args, **kwargs):
            return mock_response

        mock_provider.complete = mock_complete

        with patch("src.orchestrator.game_engine.DEFENSE_ALLOW_ABSTAIN", True):
            _, vote_counts = run_async(
                run_preliminary_vote(game, characters, provider=mock_provider)
            )

        assert len(vote_counts) == 0


class TestAbstainBehavior:
    """Tests for abstain behavior based on DEFENSE_ALLOW_ABSTAIN setting."""

    def test_abstain_allowed_stores_none(self):
        """When abstain allowed, should store None in votes."""
        game = create_test_game(3)
        characters = create_test_characters(3)

        mock_provider = MagicMock()
        mock_response = create_mock_llm_response("воздержусь")

        async def mock_complete(*args, **kwargs):
            return mock_response

        mock_provider.complete = mock_complete

        with patch("src.orchestrator.game_engine.DEFENSE_ALLOW_ABSTAIN", True):
            updated_game, _ = run_async(
                run_preliminary_vote(game, characters, provider=mock_provider)
            )

        for vote in updated_game.preliminary_vote_result.values():
            assert vote is None

    def test_abstain_not_allowed_retries_once(self):
        """When abstain not allowed, should retry once then pick random."""
        game = create_test_game(3)
        characters = create_test_characters(3)

        mock_provider = MagicMock()
        call_count = [0]

        async def mock_complete(*args, **kwargs):
            call_count[0] += 1
            return create_mock_llm_response("воздержусь")

        mock_provider.complete = mock_complete

        with patch("src.orchestrator.game_engine.DEFENSE_ALLOW_ABSTAIN", False):
            updated_game, _ = run_async(
                run_preliminary_vote(game, characters, provider=mock_provider)
            )

        assert call_count[0] == 6  # 3 initial + 3 retries

        for vote in updated_game.preliminary_vote_result.values():
            assert vote is not None

    def test_abstain_not_allowed_uses_valid_vote(self):
        """When abstain not allowed and valid vote on retry, should use it."""
        game = create_test_game(3)
        characters = create_test_characters(3)

        mock_provider = MagicMock()
        responses = []

        async def mock_complete(*args, **kwargs):
            if len(responses) == 0:
                responses.append(1)
                return create_mock_llm_response("воздержусь")
            elif len(responses) == 1:
                responses.append(2)
                return create_mock_llm_response("player_2")
            else:
                return create_mock_llm_response("player_1")

        mock_provider.complete = mock_complete

        with patch("src.orchestrator.game_engine.DEFENSE_ALLOW_ABSTAIN", False):
            updated_game, vote_counts = run_async(
                run_preliminary_vote(game, characters, provider=mock_provider)
            )

        assert updated_game.preliminary_vote_result["player_0"] == "player_2"


class TestVoteTurnContent:
    """Tests for vote turn content."""

    def test_vote_turn_content_shows_target(self):
        """Vote turn should contain vote target name."""
        game = create_test_game(3)
        characters = create_test_characters(3)

        mock_provider = MagicMock()
        mock_response = create_mock_llm_response("player_2")

        async def mock_complete(*args, **kwargs):
            return mock_response

        mock_provider.complete = mock_complete

        updated_game, _ = run_async(
            run_preliminary_vote(game, characters, provider=mock_provider)
        )

        vote_turns = [t for t in updated_game.turns if t.type == TurnType.PRELIMINARY_VOTE]
        valid_vote_turns = [t for t in vote_turns if "против" in t.content.lower()]
        assert len(valid_vote_turns) >= 2
        for turn in valid_vote_turns:
            assert "player_2" in turn.content.lower()

    def test_abstain_turn_shows_abstention(self):
        """Abstain turn should indicate abstention."""
        game = create_test_game(3)
        characters = create_test_characters(3)

        mock_provider = MagicMock()
        mock_response = create_mock_llm_response("воздержусь")

        async def mock_complete(*args, **kwargs):
            return mock_response

        mock_provider.complete = mock_complete

        with patch("src.orchestrator.game_engine.DEFENSE_ALLOW_ABSTAIN", True):
            updated_game, _ = run_async(
                run_preliminary_vote(game, characters, provider=mock_provider)
            )

        vote_turns = [t for t in updated_game.turns if t.type == TurnType.PRELIMINARY_VOTE]
        for turn in vote_turns:
            assert "воздерж" in turn.content.lower()


class TestCallbacks:
    """Tests for callback invocations."""

    def test_on_turn_callback_called(self):
        """Should call on_turn callback for each vote."""
        game = create_test_game(3)
        characters = create_test_characters(3)

        mock_provider = MagicMock()
        mock_response = create_mock_llm_response("player_1")

        async def mock_complete(*args, **kwargs):
            return mock_response

        mock_provider.complete = mock_complete

        callback_calls = []

        def on_turn_sync(turn, game):
            callback_calls.append(turn)

        run_async(
            run_preliminary_vote(
                game, characters, provider=mock_provider, on_turn=on_turn_sync
            )
        )

        assert len(callback_calls) == 3

    def test_on_typing_callback_called(self):
        """Should call on_typing callback before each LLM call."""
        game = create_test_game(3)
        characters = create_test_characters(3)

        mock_provider = MagicMock()
        mock_response = create_mock_llm_response("player_0")

        async def mock_complete(*args, **kwargs):
            return mock_response

        mock_provider.complete = mock_complete

        typing_calls = []

        def on_typing_sync(speaker_id):
            typing_calls.append(speaker_id)

        run_async(
            run_preliminary_vote(
                game, characters, provider=mock_provider, on_typing=on_typing_sync
            )
        )

        assert len(typing_calls) == 3
        assert "player_0" in typing_calls
        assert "player_1" in typing_calls
        assert "player_2" in typing_calls


class TestPromptContent:
    """Tests for prompt content based on settings."""

    def test_prompt_includes_abstain_when_allowed(self):
        """Prompt should mention abstain option when allowed."""
        game = create_test_game(3)
        characters = create_test_characters(3)

        mock_provider = MagicMock()
        mock_response = create_mock_llm_response("player_1")

        captured_messages = []

        async def mock_complete(messages, **kwargs):
            captured_messages.append(messages)
            return mock_response

        mock_provider.complete = mock_complete

        with patch("src.orchestrator.game_engine.DEFENSE_ALLOW_ABSTAIN", True):
            run_async(
                run_preliminary_vote(game, characters, provider=mock_provider)
            )

        user_message = captured_messages[0][-1]["content"]
        assert "воздерж" in user_message.lower()

    def test_prompt_excludes_abstain_when_not_allowed(self):
        """Prompt should not mention abstain option when not allowed."""
        game = create_test_game(3)
        characters = create_test_characters(3)

        mock_provider = MagicMock()
        mock_response = create_mock_llm_response("player_1")

        captured_messages = []

        async def mock_complete(messages, **kwargs):
            captured_messages.append(messages)
            return mock_response

        mock_provider.complete = mock_complete

        with patch("src.orchestrator.game_engine.DEFENSE_ALLOW_ABSTAIN", False):
            run_async(
                run_preliminary_vote(game, characters, provider=mock_provider)
            )

        user_message = captured_messages[0][-1]["content"]
        assert "воздерж" not in user_message.lower()
