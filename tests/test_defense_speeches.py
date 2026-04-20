"""Tests for defense speeches phase (TASK-060)."""

import asyncio
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("DEFENSE_MIN_VOTES_TO_QUALIFY", "2")
os.environ.setdefault("DEFENSE_SPEECH_MAX_SENTENCES", "2")
os.environ.setdefault("DEFENSE_ALLOW_ABSTAIN", "true")


def run_async(coro):
    """Run an async coroutine in a new event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


from src.orchestrator.game_engine import (
    run_defense_speeches,
    _count_sentences,
    _truncate_to_sentences,
    DEFENSE_MIN_VOTES_TO_QUALIFY,
    DEFENSE_SPEECH_MAX_SENTENCES,
)
from src.agents import build_defense_speech_prompt, SecretInfo
from src.models import (
    Game,
    GameConfig,
    GamePhase,
    Player,
    Turn,
    TurnType,
    DefenseSpeech,
    TokenUsage,
    PhaseEntry,
)
from src.llm import LLMResponse


def create_test_game(players_data: list[dict]) -> Game:
    """Create a test game with given players.

    Note: Game requires at least 3 players and exactly 1 spy.
    If fewer players are provided, dummy players are added.
    If no spy is designated, the first player becomes the spy.
    """
    has_spy = any(p.get("is_spy", False) for p in players_data)
    if not has_spy and players_data:
        players_data[0]["is_spy"] = True
        players_data[0]["role_id"] = None

    while len(players_data) < 3:
        players_data.append({
            "id": f"dummy_{len(players_data)}",
            "role_id": f"role_{len(players_data)}",
            "is_spy": False,
        })

    players = [
        Player(
            character_id=p["id"],
            role_id=p.get("role_id"),
            is_spy=p.get("is_spy", False),
        )
        for p in players_data
    ]
    spy_id = next((p["id"] for p in players_data if p.get("is_spy")), players_data[0]["id"])

    return Game(
        id=uuid4(),
        started_at=datetime.now(),
        config=GameConfig(
            duration_minutes=10,
            players_count=len(players_data),
            max_questions=20,
            main_model="gpt-4o",
            utility_model="gpt-4o-mini",
        ),
        location_id="hospital",
        players=players,
        spy_id=spy_id,
        turns=[],
        spy_confidence_log=[],
        triggered_events=[],
        phase_transitions=[
            PhaseEntry(
                timestamp=datetime.now(),
                from_phase=None,
                to_phase=GamePhase.SETUP,
            )
        ],
        token_usage=TokenUsage(),
    )


def create_mock_character(char_id: str, display_name: str, archetype: str):
    """Create a mock character object."""
    char = MagicMock()
    char.id = char_id
    char.display_name = display_name
    char.archetype = archetype
    char.must_directives = ["MUST directive 1"]
    char.must_not_directives = ["MUST NOT directive 1"]
    char.backstory = "Test backstory for the character."
    char.voice_style = "Test voice style"
    return char


def create_mock_llm_response(content: str) -> MagicMock:
    """Create a mock LLM response with all required attributes."""
    mock_response = MagicMock()
    mock_response.content = content
    mock_response.input_tokens = 100
    mock_response.output_tokens = 20
    mock_response.model = "gpt-4o"
    mock_response.calculate_cost = MagicMock(return_value=0.01)
    return mock_response


class TestCountSentences:
    """Tests for _count_sentences helper function."""

    def test_single_sentence(self):
        assert _count_sentences("Это одно предложение.") == 1

    def test_multiple_sentences(self):
        assert _count_sentences("Первое предложение. Второе предложение!") == 2

    def test_question_mark(self):
        assert _count_sentences("Это вопрос? Да, это вопрос.") == 2

    def test_exclamation(self):
        assert _count_sentences("Привет! Как дела? Всё хорошо.") == 3

    def test_empty_string(self):
        assert _count_sentences("") == 0

    def test_no_punctuation(self):
        assert _count_sentences("Текст без знаков препинания") == 1


class TestTruncateToSentences:
    """Tests for _truncate_to_sentences helper function."""

    def test_no_truncation_needed(self):
        text = "Первое предложение. Второе предложение."
        result, truncated = _truncate_to_sentences(text, 3)
        assert truncated is False
        assert result == text

    def test_truncation_to_two(self):
        text = "Первое. Второе. Третье. Четвёртое."
        result, truncated = _truncate_to_sentences(text, 2)
        assert truncated is True
        assert "Первое." in result
        assert "Второе." in result
        assert "Третье" not in result

    def test_truncation_to_one(self):
        text = "Первое! Второе! Третье!"
        result, truncated = _truncate_to_sentences(text, 1)
        assert truncated is True
        assert "Первое!" in result
        assert "Второе" not in result

    def test_exact_match_no_truncation(self):
        text = "Одно предложение. Два."
        result, truncated = _truncate_to_sentences(text, 2)
        assert truncated is False


class TestDefensePhaseSkipping:
    """Tests for defense phase skipping conditions."""

    def test_skip_when_no_votes(self):
        """Defense phase should be skipped when no votes were cast."""
        game = create_test_game([
            {"id": "boris", "role_id": "surgeon", "is_spy": False},
            {"id": "zoya", "role_id": "nurse", "is_spy": True},
        ])
        characters = [
            create_mock_character("boris", "Борис", "агрессор"),
            create_mock_character("zoya", "Зоя", "дерзкий циник"),
        ]

        vote_counts = {}

        game, executed = run_async(run_defense_speeches(
            game, characters, vote_counts
        ))

        assert executed is False
        assert game.defense_speeches == []
        assert any(
            "skipped" in str(p.reason).lower()
            for p in game.phase_transitions
            if p.to_phase == GamePhase.PRE_FINAL_VOTE_DEFENSE
        )

    def test_skip_when_below_threshold(self):
        """Defense phase should be skipped when max votes < threshold."""
        game = create_test_game([
            {"id": "boris", "role_id": "surgeon", "is_spy": False},
            {"id": "zoya", "role_id": "nurse", "is_spy": True},
            {"id": "kim", "role_id": "patient", "is_spy": False},
        ])
        characters = [
            create_mock_character("boris", "Борис", "агрессор"),
            create_mock_character("zoya", "Зоя", "дерзкий циник"),
            create_mock_character("kim", "Ким", "параноик"),
        ]

        vote_counts = {"boris": 1, "zoya": 1}

        game, executed = run_async(run_defense_speeches(
            game, characters, vote_counts
        ))

        assert executed is False
        assert game.defense_speeches == []


class TestDefensePhaseExecution:
    """Tests for defense phase execution."""

    def test_single_defender_gets_speech(self):
        """One player with max votes should get a defense speech."""
        game = create_test_game([
            {"id": "boris", "role_id": "surgeon", "is_spy": False},
            {"id": "zoya", "role_id": "nurse", "is_spy": True},
            {"id": "kim", "role_id": "patient", "is_spy": False},
        ])
        characters = [
            create_mock_character("boris", "Борис", "агрессор"),
            create_mock_character("zoya", "Зоя", "дерзкий циник"),
            create_mock_character("kim", "Ким", "параноик"),
        ]

        vote_counts = {"boris": 3, "zoya": 0, "kim": 0}

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=create_mock_llm_response(
            "Я не шпион! Это очевидно."
        ))

        game, executed = run_async(run_defense_speeches(
            game, characters, vote_counts, provider=mock_provider
        ))

        assert executed is True
        assert len(game.defense_speeches) == 1
        assert game.defense_speeches[0].defender_id == "boris"
        assert game.defense_speeches[0].votes_received == 3

    def test_multiple_defenders_with_tie(self):
        """Multiple players with same max votes should all get speeches (2-2-2)."""
        game = create_test_game([
            {"id": "boris", "role_id": "surgeon", "is_spy": False},
            {"id": "zoya", "role_id": "nurse", "is_spy": True},
            {"id": "kim", "role_id": "patient", "is_spy": False},
        ])
        game.preliminary_vote_result = {
            "boris": "kim",
            "zoya": "boris",
            "kim": "zoya",
        }
        characters = [
            create_mock_character("boris", "Борис", "агрессор"),
            create_mock_character("zoya", "Зоя", "дерзкий циник"),
            create_mock_character("kim", "Ким", "параноик"),
        ]

        vote_counts = {"boris": 2, "zoya": 2, "kim": 2}

        mock_provider = MagicMock()
        call_count = [0]

        async def mock_complete(*args, **kwargs):
            call_count[0] += 1
            return create_mock_llm_response(
                f"Защитная речь номер {call_count[0]}."
            )

        mock_provider.complete = mock_complete

        game, executed = run_async(run_defense_speeches(
            game, characters, vote_counts, provider=mock_provider
        ))

        assert executed is True
        assert len(game.defense_speeches) == 3
        defender_ids = {ds.defender_id for ds in game.defense_speeches}
        assert defender_ids == {"boris", "zoya", "kim"}

    def test_defense_turn_created(self):
        """Defense speech should create a Turn with correct type."""
        game = create_test_game([
            {"id": "boris", "role_id": "surgeon", "is_spy": False},
            {"id": "zoya", "role_id": "nurse", "is_spy": True},
        ])
        characters = [
            create_mock_character("boris", "Борис", "агрессор"),
            create_mock_character("zoya", "Зоя", "дерзкий циник"),
        ]

        vote_counts = {"boris": 2}

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=create_mock_llm_response(
            "Моя защита!"
        ))

        game, executed = run_async(run_defense_speeches(
            game, characters, vote_counts, provider=mock_provider
        ))

        assert executed is True
        defense_turns = [t for t in game.turns if t.type == TurnType.DEFENSE_SPEECH]
        assert len(defense_turns) == 1
        assert defense_turns[0].speaker_id == "boris"
        assert defense_turns[0].addressee_id == "all"
        assert defense_turns[0].display_delay_ms > 0

    def test_on_turn_callback_called(self):
        """on_turn callback should be called for each defense speech."""
        game = create_test_game([
            {"id": "boris", "role_id": "surgeon", "is_spy": False},
            {"id": "zoya", "role_id": "nurse", "is_spy": True},
        ])
        characters = [
            create_mock_character("boris", "Борис", "агрессор"),
            create_mock_character("zoya", "Зоя", "дерзкий циник"),
        ]

        vote_counts = {"boris": 2}

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=create_mock_llm_response(
            "Защита!"
        ))

        on_turn_calls = []

        def mock_on_turn(turn, game):
            on_turn_calls.append((turn.speaker_id, turn.type))

        game, executed = run_async(run_defense_speeches(
            game, characters, vote_counts,
            provider=mock_provider,
            on_turn=mock_on_turn,
        ))

        assert len(on_turn_calls) == 1
        assert on_turn_calls[0] == ("boris", TurnType.DEFENSE_SPEECH)

    def test_on_typing_callback_called(self):
        """on_typing callback should be called before LLM generation."""
        game = create_test_game([
            {"id": "boris", "role_id": "surgeon", "is_spy": False},
            {"id": "zoya", "role_id": "nurse", "is_spy": True},
        ])
        characters = [
            create_mock_character("boris", "Борис", "агрессор"),
            create_mock_character("zoya", "Зоя", "дерзкий циник"),
        ]

        vote_counts = {"boris": 2}

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=create_mock_llm_response(
            "Защита!"
        ))

        typing_calls = []

        def mock_on_typing(speaker_id):
            typing_calls.append(speaker_id)

        game, executed = run_async(run_defense_speeches(
            game, characters, vote_counts,
            provider=mock_provider,
            on_typing=mock_on_typing,
        ))

        assert typing_calls == ["boris"]


class TestSentenceTruncation:
    """Tests for sentence truncation in defense speeches."""

    def test_long_speech_truncated(self):
        """Speech with too many sentences should be truncated."""
        game = create_test_game([
            {"id": "boris", "role_id": "surgeon", "is_spy": False},
            {"id": "zoya", "role_id": "nurse", "is_spy": True},
        ])
        characters = [
            create_mock_character("boris", "Борис", "агрессор"),
            create_mock_character("zoya", "Зоя", "дерзкий циник"),
        ]

        vote_counts = {"boris": 2}

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=create_mock_llm_response(
            "Первое предложение. Второе предложение. Третье предложение. Четвёртое предложение."
        ))

        with patch("src.orchestrator.game_engine.logger") as mock_logger:
            game, executed = run_async(run_defense_speeches(
                game, characters, vote_counts, provider=mock_provider
            ))

            mock_logger.warning.assert_called()
            warning_call = str(mock_logger.warning.call_args)
            assert "truncated" in warning_call.lower()

        assert executed is True
        assert len(game.defense_speeches) == 1
        content = game.defense_speeches[0].content
        assert _count_sentences(content) <= DEFENSE_SPEECH_MAX_SENTENCES


class TestDefensePromptBuilder:
    """Tests for build_defense_speech_prompt function."""

    def test_prompt_includes_character_identity(self):
        """Prompt should include character display name."""
        char = create_mock_character("boris", "Борис", "агрессор")
        game = create_test_game([
            {"id": "boris", "role_id": "surgeon", "is_spy": False},
        ])
        secret_info = SecretInfo(is_spy=False)

        prompt = build_defense_speech_prompt(char, game, secret_info, votes_received=3)

        assert "Борис" in prompt
        assert "агрессор" in prompt

    def test_prompt_includes_votes_info(self):
        """Prompt should include votes received information."""
        char = create_mock_character("boris", "Борис", "агрессор")
        game = create_test_game([
            {"id": "boris", "role_id": "surgeon", "is_spy": False},
        ])
        game.preliminary_vote_result = {"zoya": "boris", "kim": "boris"}
        secret_info = SecretInfo(is_spy=False)

        prompt = build_defense_speech_prompt(char, game, secret_info, votes_received=2)

        assert "2" in prompt
        assert "zoya" in prompt.lower() or "kim" in prompt.lower()

    def test_prompt_includes_sentence_limit(self):
        """Prompt should mention sentence limit."""
        char = create_mock_character("boris", "Борис", "агрессор")
        game = create_test_game([
            {"id": "boris", "role_id": "surgeon", "is_spy": False},
        ])
        secret_info = SecretInfo(is_spy=False)

        prompt = build_defense_speech_prompt(
            char, game, secret_info, votes_received=2, max_sentences=3
        )

        assert "3" in prompt
        assert "предложен" in prompt.lower()


class TestPhaseTransitions:
    """Tests for phase transitions during defense phase."""

    def test_phase_transition_recorded_on_execution(self):
        """Phase transition should be recorded when defense phase executes."""
        game = create_test_game([
            {"id": "boris", "role_id": "surgeon", "is_spy": False},
            {"id": "zoya", "role_id": "nurse", "is_spy": True},
        ])
        characters = [
            create_mock_character("boris", "Борис", "агрессор"),
            create_mock_character("zoya", "Зоя", "дерзкий циник"),
        ]

        vote_counts = {"boris": 2}

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=create_mock_llm_response(
            "Защита!"
        ))

        game, executed = run_async(run_defense_speeches(
            game, characters, vote_counts, provider=mock_provider
        ))

        defense_transitions = [
            p for p in game.phase_transitions
            if p.to_phase == GamePhase.PRE_FINAL_VOTE_DEFENSE
        ]
        assert len(defense_transitions) == 1
        assert "defense" in defense_transitions[0].reason.lower()

    def test_skipped_status_recorded(self):
        """Skipped status should be recorded when defense phase is skipped."""
        game = create_test_game([
            {"id": "boris", "role_id": "surgeon", "is_spy": False},
            {"id": "zoya", "role_id": "nurse", "is_spy": True},
        ])
        characters = [
            create_mock_character("boris", "Борис", "агрессор"),
            create_mock_character("zoya", "Зоя", "дерзкий циник"),
        ]

        vote_counts = {"boris": 1}

        game, executed = run_async(run_defense_speeches(
            game, characters, vote_counts
        ))

        defense_transitions = [
            p for p in game.phase_transitions
            if p.to_phase == GamePhase.PRE_FINAL_VOTE_DEFENSE
        ]
        assert len(defense_transitions) == 1
        assert defense_transitions[0].status is not None
        assert "skipped" in defense_transitions[0].status


class TestTokenUsageTracking:
    """Tests for token usage tracking during defense phase."""

    def test_token_usage_tracked(self):
        """Token usage should be tracked after LLM calls."""
        game = create_test_game([
            {"id": "boris", "role_id": "surgeon", "is_spy": False},
            {"id": "zoya", "role_id": "nurse", "is_spy": True},
        ])
        characters = [
            create_mock_character("boris", "Борис", "агрессор"),
            create_mock_character("zoya", "Зоя", "дерзкий циник"),
        ]

        vote_counts = {"boris": 2}

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=create_mock_llm_response(
            "Защита!"
        ))

        initial_calls = game.token_usage.llm_calls_count

        game, executed = run_async(run_defense_speeches(
            game, characters, vote_counts, provider=mock_provider
        ))

        assert game.token_usage.llm_calls_count > initial_calls
        assert game.token_usage.total_input_tokens >= 100
        assert game.token_usage.total_output_tokens >= 20


class TestDefenseOrder:
    """Tests for random defense order."""

    def test_defense_order_is_randomized(self):
        """Defense speeches should be given in random order."""
        game = create_test_game([
            {"id": "boris", "role_id": "surgeon", "is_spy": False},
            {"id": "zoya", "role_id": "nurse", "is_spy": True},
            {"id": "kim", "role_id": "patient", "is_spy": False},
        ])
        characters = [
            create_mock_character("boris", "Борис", "агрессор"),
            create_mock_character("zoya", "Зоя", "дерзкий циник"),
            create_mock_character("kim", "Ким", "параноик"),
        ]

        vote_counts = {"boris": 2, "zoya": 2, "kim": 2}

        mock_provider = MagicMock()
        call_order = []

        async def mock_complete(*args, **kwargs):
            return create_mock_llm_response("Защита!")

        mock_provider.complete = mock_complete

        orders = set()
        for _ in range(10):
            test_game = create_test_game([
                {"id": "boris", "role_id": "surgeon", "is_spy": False},
                {"id": "zoya", "role_id": "nurse", "is_spy": True},
                {"id": "kim", "role_id": "patient", "is_spy": False},
            ])
            test_game, _ = run_async(run_defense_speeches(
                test_game, characters, vote_counts, provider=mock_provider
            ))
            order = tuple(ds.defender_id for ds in test_game.defense_speeches)
            orders.add(order)

        assert len(orders) > 1


class TestNoTriggersOrInterventions:
    """Tests that triggers and interventions are NOT triggered during defense."""

    def test_no_trigger_check_during_defense(self):
        """Trigger checks should not run during defense speeches."""
        game = create_test_game([
            {"id": "boris", "role_id": "surgeon", "is_spy": False},
            {"id": "zoya", "role_id": "nurse", "is_spy": True},
        ])
        characters = [
            create_mock_character("boris", "Борис", "агрессор"),
            create_mock_character("zoya", "Зоя", "дерзкий циник"),
        ]

        vote_counts = {"boris": 2}

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value=create_mock_llm_response(
            "Это обвинение против Зои! Она шпион!"
        ))

        with patch("src.orchestrator.game_engine.TriggerChecker") as mock_checker:
            game, executed = run_async(run_defense_speeches(
                game, characters, vote_counts, provider=mock_provider
            ))

            mock_checker.assert_not_called()

        assert executed is True
        intervention_turns = [t for t in game.turns if t.type == TurnType.INTERVENTION]
        assert len(intervention_turns) == 0
