"""Tests for TASK-077: All trigger detectors.

This file consolidates tests for:
- dodged_direct_question detector (TASK-073)
- repeated_accusation_on_same_target detector (TASK-072)
- contradiction_with_previous_answer detector (TASK-074)
- silent_for_n_turns with personal reaction_types (TASK-070)

All LLM calls are mocked.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.llm.adapter import LLMResponse
from src.models.character import Character, ConditionType, ReactionType
from src.models.game import Game, GameConfig, Player, Turn, TurnType
from src.triggers.checker import TriggerChecker, TriggerResult


def load_character(character_id: str) -> Character:
    """Load a character from JSON file."""
    path = Path(__file__).parent.parent / "characters" / f"{character_id}.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Character(**data)


# ==============================================================================
# Shared Fixtures
# ==============================================================================


@pytest.fixture
def boris():
    """Boris character - has silent_for_n_turns with pressure_with_sharper_question."""
    return load_character("boris_molot")


@pytest.fixture
def kim():
    """Kim character - has silent_for_n_turns with panic_and_derail."""
    return load_character("kim")


@pytest.fixture
def margo():
    """Margo character - has direct_accusation with deflect_suspicion_to_another."""
    return load_character("margo")


@pytest.fixture
def zoya():
    """Zoya character - has dodged_direct_question with mock_with_dry_sarcasm."""
    return load_character("zoya")


@pytest.fixture
def mock_provider():
    """Create a mock LLM provider."""
    provider = MagicMock()
    provider.complete = AsyncMock()
    return provider


@pytest.fixture
def sample_game():
    """A minimal game for testing."""
    players = [
        Player(character_id="boris_molot", role_id="doctor", is_spy=False),
        Player(character_id="kim", role_id="nurse", is_spy=False),
        Player(character_id="zoya", role_id=None, is_spy=True),
    ]
    return Game(
        id=uuid4(),
        started_at=datetime.now(),
        config=GameConfig(
            duration_minutes=10,
            players_count=3,
            max_questions=20,
            main_model="gpt-4o",
            utility_model="gpt-4o-mini",
        ),
        location_id="hospital",
        players=players,
        spy_id="zoya",
        turns=[],
    )


# ==============================================================================
# Tests for dodged_direct_question detector (TASK-073)
# ==============================================================================


class TestDodgedDirectQuestionDetector:
    """Tests for check_dodged_question async method."""

    @pytest.fixture
    def question_turn(self):
        """A direct question turn."""
        return Turn(
            turn_number=3,
            timestamp=datetime.now(),
            speaker_id="boris_molot",
            addressee_id="kim",
            type=TurnType.QUESTION,
            content="Ким, какая твоя роль в этом месте?",
            display_delay_ms=1000,
        )

    @pytest.fixture
    def direct_answer_turn(self):
        """An answer that directly addresses the question."""
        return Turn(
            turn_number=4,
            timestamp=datetime.now(),
            speaker_id="kim",
            addressee_id="boris_molot",
            type=TurnType.ANSWER,
            content="Я работаю здесь врачом, помогаю пациентам.",
            display_delay_ms=1000,
        )

    @pytest.fixture
    def evasive_answer_turn(self):
        """An answer that dodges the question."""
        return Turn(
            turn_number=4,
            timestamp=datetime.now(),
            speaker_id="kim",
            addressee_id="boris_molot",
            type=TurnType.ANSWER,
            content="А почему ты так интересуешься? Что у тебя за роль?",
            display_delay_ms=1000,
        )

    def test_evasive_answer_returns_true(
        self, boris, kim, question_turn, evasive_answer_turn, mock_provider
    ):
        """Evasive answer should trigger (return True)."""
        checker = TriggerChecker(characters=[boris, kim])

        mock_provider.complete.return_value = LLMResponse(
            content="нет",
            input_tokens=50,
            output_tokens=1,
            model="gpt-4o-mini",
        )

        result = asyncio.run(
            checker.check_dodged_question(
                question_turn=question_turn,
                answer_turn=evasive_answer_turn,
                provider=mock_provider,
                model="gpt-4o-mini",
            )
        )

        assert result is True
        mock_provider.complete.assert_called_once()

    def test_direct_answer_returns_false(
        self, boris, kim, question_turn, direct_answer_turn, mock_provider
    ):
        """Direct answer should not trigger (return False)."""
        checker = TriggerChecker(characters=[boris, kim])

        mock_provider.complete.return_value = LLMResponse(
            content="да",
            input_tokens=50,
            output_tokens=1,
            model="gpt-4o-mini",
        )

        result = asyncio.run(
            checker.check_dodged_question(
                question_turn=question_turn,
                answer_turn=direct_answer_turn,
                provider=mock_provider,
                model="gpt-4o-mini",
            )
        )

        assert result is False
        mock_provider.complete.assert_called_once()

    def test_invalid_llm_response_returns_false_with_warning(
        self, boris, kim, question_turn, evasive_answer_turn, mock_provider, caplog
    ):
        """Invalid LLM response should return False and log warning."""
        checker = TriggerChecker(characters=[boris, kim])

        mock_provider.complete.return_value = LLMResponse(
            content="может быть",
            input_tokens=50,
            output_tokens=3,
            model="gpt-4o-mini",
        )

        with caplog.at_level(logging.WARNING):
            result = asyncio.run(
                checker.check_dodged_question(
                    question_turn=question_turn,
                    answer_turn=evasive_answer_turn,
                    provider=mock_provider,
                    model="gpt-4o-mini",
                )
            )

        assert result is False
        assert "Invalid LLM response for dodged_question check" in caplog.text

    def test_llm_exception_returns_false_with_warning(
        self, boris, kim, question_turn, evasive_answer_turn, mock_provider, caplog
    ):
        """LLM exception should return False and log warning."""
        checker = TriggerChecker(characters=[boris, kim])
        mock_provider.complete.side_effect = Exception("API timeout")

        with caplog.at_level(logging.WARNING):
            result = asyncio.run(
                checker.check_dodged_question(
                    question_turn=question_turn,
                    answer_turn=evasive_answer_turn,
                    provider=mock_provider,
                    model="gpt-4o-mini",
                )
            )

        assert result is False
        assert "Error checking dodged question" in caplog.text

    def test_yes_english_returns_false(
        self, boris, kim, question_turn, direct_answer_turn, mock_provider
    ):
        """English 'yes' should be recognized as valid response."""
        checker = TriggerChecker(characters=[boris, kim])

        mock_provider.complete.return_value = LLMResponse(
            content="yes",
            input_tokens=50,
            output_tokens=1,
            model="gpt-4o-mini",
        )

        result = asyncio.run(
            checker.check_dodged_question(
                question_turn=question_turn,
                answer_turn=direct_answer_turn,
                provider=mock_provider,
                model="gpt-4o-mini",
            )
        )

        assert result is False

    def test_no_english_returns_true(
        self, boris, kim, question_turn, evasive_answer_turn, mock_provider
    ):
        """English 'no' should be recognized as valid response."""
        checker = TriggerChecker(characters=[boris, kim])

        mock_provider.complete.return_value = LLMResponse(
            content="no",
            input_tokens=50,
            output_tokens=1,
            model="gpt-4o-mini",
        )

        result = asyncio.run(
            checker.check_dodged_question(
                question_turn=question_turn,
                answer_turn=evasive_answer_turn,
                provider=mock_provider,
                model="gpt-4o-mini",
            )
        )

        assert result is True

    def test_prompt_includes_question_and_answer_content(
        self, boris, kim, question_turn, direct_answer_turn, mock_provider
    ):
        """Prompt should include both question and answer content."""
        checker = TriggerChecker(characters=[boris, kim])

        mock_provider.complete.return_value = LLMResponse(
            content="да",
            input_tokens=50,
            output_tokens=1,
            model="gpt-4o-mini",
        )

        asyncio.run(
            checker.check_dodged_question(
                question_turn=question_turn,
                answer_turn=direct_answer_turn,
                provider=mock_provider,
                model="gpt-4o-mini",
            )
        )

        call_args = mock_provider.complete.call_args
        messages = call_args.kwargs.get("messages", call_args.args[0] if call_args.args else None)

        assert messages is not None
        prompt_content = messages[0]["content"]
        assert question_turn.content in prompt_content
        assert direct_answer_turn.content in prompt_content


# ==============================================================================
# Tests for repeated_accusation_on_same_target detector (TASK-072)
# ==============================================================================


class TestRepeatedAccusationDetector:
    """Tests for repeated_accusation_on_same_target detector."""

    @pytest.fixture
    def accusation_turn_1(self):
        """First accusation turn against Kim at turn 1."""
        return Turn(
            turn_number=1,
            timestamp=datetime.now(),
            speaker_id="boris_molot",
            addressee_id="zoya",
            type=TurnType.ANSWER,
            content="Ким, ты шпион! Я уверен в этом!",
            display_delay_ms=1000,
        )

    @pytest.fixture
    def accusation_turn_2(self):
        """Second accusation turn against Kim at turn 2."""
        return Turn(
            turn_number=2,
            timestamp=datetime.now(),
            speaker_id="zoya",
            addressee_id="boris_molot",
            type=TurnType.ANSWER,
            content="Согласна, Ким точно шпион! Он всё время молчит!",
            display_delay_ms=1000,
        )

    def test_two_accusations_in_row_triggers(
        self, margo, boris, kim, accusation_turn_1, accusation_turn_2
    ):
        """2 accusations in a row should trigger."""
        checker = TriggerChecker(characters=[margo, boris, kim])

        accused_1 = checker.detect_accusation_target(accusation_turn_1)
        assert accused_1 == "kim"
        checker.track_accusation(accused_1, accusation_turn_1.turn_number)

        accused_2 = checker.detect_accusation_target(accusation_turn_2)
        assert accused_2 == "kim"
        checker.track_accusation(accused_2, accusation_turn_2.turn_number)

        assert checker.check_repeated_accusation("kim", current_turn=2, window=5) is True

    def test_accusations_spread_over_10_turns_does_not_trigger(self, margo, boris, kim):
        """Accusations spread over 10 turns should not trigger."""
        checker = TriggerChecker(characters=[margo, boris, kim])

        checker.track_accusation("kim", turn_number=1)
        checker.track_accusation("kim", turn_number=12)

        assert checker.check_repeated_accusation("kim", current_turn=12, window=5) is False

    def test_accusations_on_different_targets_does_not_trigger(
        self, margo, boris, kim, accusation_turn_1
    ):
        """Accusations on different targets should not trigger."""
        accusation_against_boris = Turn(
            turn_number=2,
            timestamp=datetime.now(),
            speaker_id="zoya",
            addressee_id="kim",
            type=TurnType.ANSWER,
            content="Борис, ты шпион! Ты слишком агрессивен!",
            display_delay_ms=1000,
        )

        checker = TriggerChecker(characters=[margo, boris, kim])

        accused_1 = checker.detect_accusation_target(accusation_turn_1)
        assert accused_1 == "kim"
        checker.track_accusation(accused_1, accusation_turn_1.turn_number)

        accused_2 = checker.detect_accusation_target(accusation_against_boris)
        assert accused_2 == "boris_molot"
        checker.track_accusation(accused_2, accusation_against_boris.turn_number)

        assert checker.check_repeated_accusation("kim", current_turn=2, window=5) is False
        assert checker.check_repeated_accusation("boris_molot", current_turn=2, window=5) is False

    def test_trigger_event_includes_target_id_in_params(self, margo, boris, kim, sample_game):
        """TriggerEvent should include target_id in params for repeated_accusation."""
        checker = TriggerChecker(characters=[margo, boris, kim])

        checker.track_accusation("kim", turn_number=1)
        checker.track_accusation("kim", turn_number=2)

        turn = Turn(
            turn_number=3,
            timestamp=datetime.now(),
            speaker_id="boris_molot",
            addressee_id="zoya",
            type=TurnType.ANSWER,
            content="Ким, ты шпион! Третий раз говорю!",
            display_delay_ms=1000,
        )
        checker.track_accusation("kim", turn.turn_number)

        results = checker.check_triggers_for_character("margo", turn, sample_game)

        repeated_results = [
            r for r in results
            if r.condition_type == ConditionType.REPEATED_ACCUSATION_ON_SAME_TARGET
        ]

        assert len(repeated_results) == 1
        result = repeated_results[0]
        assert result.target_character_id == "kim"

        event = checker.create_trigger_event(result, turn_number=3, intervened=True)
        assert event.params is not None
        assert event.params.get("target_id") == "kim"


# ==============================================================================
# Tests for contradiction_with_previous_answer detector (TASK-074)
# ==============================================================================


class TestContradictionDetector:
    """Tests for contradiction_with_previous_answer detector."""

    @pytest.fixture
    def game_with_turns(self, sample_game):
        """Game with previous answer turns."""
        sample_game.turns = [
            Turn(
                turn_number=1,
                timestamp=datetime.now(),
                speaker_id="kim",
                addressee_id="boris_molot",
                type=TurnType.ANSWER,
                content="Я работаю здесь уже пять лет.",
                display_delay_ms=1000,
            ),
            Turn(
                turn_number=2,
                timestamp=datetime.now(),
                speaker_id="boris_molot",
                addressee_id="zoya",
                type=TurnType.ANSWER,
                content="Это моя первая смена.",
                display_delay_ms=1000,
            ),
            Turn(
                turn_number=3,
                timestamp=datetime.now(),
                speaker_id="kim",
                addressee_id="zoya",
                type=TurnType.ANSWER,
                content="Я точно знаю всех здесь.",
                display_delay_ms=1000,
            ),
        ]
        return sample_game

    def test_explicit_contradiction_triggers(
        self, boris, kim, game_with_turns, mock_provider
    ):
        """Explicit contradiction should trigger."""
        checker = TriggerChecker(characters=[boris, kim])

        current_answer = Turn(
            turn_number=4,
            timestamp=datetime.now(),
            speaker_id="kim",
            addressee_id="boris_molot",
            type=TurnType.ANSWER,
            content="Вообще-то я никого здесь не знаю, это мой первый день.",
            display_delay_ms=1000,
        )
        game_with_turns.turns.append(current_answer)

        mock_response = MagicMock()
        mock_response.content = "да"
        mock_provider.complete.return_value = mock_response

        triggered, reasoning, turn_numbers = asyncio.run(checker.check_contradiction(
            speaker_id="kim",
            current_answer=current_answer,
            game=game_with_turns,
            provider=mock_provider,
            model="gpt-4o-mini",
        ))

        assert triggered is True
        assert reasoning is not None
        assert turn_numbers is not None
        assert 1 in turn_numbers
        assert 3 in turn_numbers

    def test_rephrasing_does_not_trigger(
        self, boris, kim, game_with_turns, mock_provider
    ):
        """Rephrasing should NOT trigger."""
        checker = TriggerChecker(characters=[boris, kim])

        current_answer = Turn(
            turn_number=4,
            timestamp=datetime.now(),
            speaker_id="kim",
            addressee_id="boris_molot",
            type=TurnType.ANSWER,
            content="Как я уже говорил, работаю тут давно и знаю всех коллег.",
            display_delay_ms=1000,
        )
        game_with_turns.turns.append(current_answer)

        mock_response = MagicMock()
        mock_response.content = "нет"
        mock_provider.complete.return_value = mock_response

        triggered, reasoning, turn_numbers = asyncio.run(checker.check_contradiction(
            speaker_id="kim",
            current_answer=current_answer,
            game=game_with_turns,
            provider=mock_provider,
            model="gpt-4o-mini",
        ))

        assert triggered is False
        assert reasoning is None
        assert turn_numbers is None

    def test_topic_change_does_not_trigger(
        self, boris, kim, game_with_turns, mock_provider
    ):
        """Topic change should NOT trigger."""
        checker = TriggerChecker(characters=[boris, kim])

        current_answer = Turn(
            turn_number=4,
            timestamp=datetime.now(),
            speaker_id="kim",
            addressee_id="boris_molot",
            type=TurnType.ANSWER,
            content="Давайте лучше поговорим о погоде сегодня.",
            display_delay_ms=1000,
        )
        game_with_turns.turns.append(current_answer)

        mock_response = MagicMock()
        mock_response.content = "нет"
        mock_provider.complete.return_value = mock_response

        triggered, reasoning, turn_numbers = asyncio.run(checker.check_contradiction(
            speaker_id="kim",
            current_answer=current_answer,
            game=game_with_turns,
            provider=mock_provider,
            model="gpt-4o-mini",
        ))

        assert triggered is False
        assert reasoning is None
        assert turn_numbers is None

    def test_less_than_two_previous_answers_skips_check(
        self, boris, kim, sample_game, mock_provider
    ):
        """Detector should not run if speaker has < 2 previous answers."""
        checker = TriggerChecker(characters=[boris, kim])

        sample_game.turns = [
            Turn(
                turn_number=1,
                timestamp=datetime.now(),
                speaker_id="kim",
                addressee_id="boris_molot",
                type=TurnType.ANSWER,
                content="Я работаю здесь.",
                display_delay_ms=1000,
            ),
        ]

        current_answer = Turn(
            turn_number=2,
            timestamp=datetime.now(),
            speaker_id="kim",
            addressee_id="boris_molot",
            type=TurnType.ANSWER,
            content="На самом деле я не работаю здесь.",
            display_delay_ms=1000,
        )
        sample_game.turns.append(current_answer)

        triggered, reasoning, turn_numbers = asyncio.run(checker.check_contradiction(
            speaker_id="kim",
            current_answer=current_answer,
            game=sample_game,
            provider=mock_provider,
            model="gpt-4o-mini",
        ))

        assert triggered is False
        assert reasoning is None
        assert turn_numbers is None
        mock_provider.complete.assert_not_called()

    def test_invalid_llm_response_does_not_trigger(
        self, boris, kim, game_with_turns, mock_provider
    ):
        """Invalid LLM response should not trigger."""
        checker = TriggerChecker(characters=[boris, kim])

        current_answer = Turn(
            turn_number=4,
            timestamp=datetime.now(),
            speaker_id="kim",
            addressee_id="boris_molot",
            type=TurnType.ANSWER,
            content="Что-то противоречивое.",
            display_delay_ms=1000,
        )
        game_with_turns.turns.append(current_answer)

        mock_response = MagicMock()
        mock_response.content = "maybe"
        mock_provider.complete.return_value = mock_response

        triggered, reasoning, turn_numbers = asyncio.run(checker.check_contradiction(
            speaker_id="kim",
            current_answer=current_answer,
            game=game_with_turns,
            provider=mock_provider,
            model="gpt-4o-mini",
        ))

        assert triggered is False
        assert reasoning is None
        assert turn_numbers is None

    def test_create_trigger_event_with_reasoning_and_params(self, boris, kim):
        """TriggerEvent should include reasoning and contradicting_turn_numbers."""
        checker = TriggerChecker(characters=[boris, kim])

        result = TriggerResult(
            triggered=True,
            character_id="zoya",
            condition_type=ConditionType.CONTRADICTION_WITH_PREVIOUS_ANSWER,
            reaction_type=ReactionType.MOCK_WITH_DRY_SARCASM,
            priority=7,
            threshold=0.4,
            target_character_id="kim",
        )

        reasoning = "LLM detected contradiction with previous statements from turns [1, 3]"
        params = {"contradicting_turn_numbers": [1, 3]}

        event = checker.create_trigger_event(
            result=result,
            turn_number=4,
            intervened=True,
            reasoning=reasoning,
            params=params,
        )

        assert event.condition_type == "contradiction_with_previous_answer"
        assert event.reasoning == reasoning
        assert event.params is not None
        assert event.params.get("contradicting_turn_numbers") == [1, 3]


# ==============================================================================
# Tests for silent_for_n_turns with personal reaction_types (TASK-070)
# ==============================================================================


class TestSilentForNTurnsReactionTypes:
    """Test that silent_for_n_turns triggers use personal reaction_types."""

    @pytest.fixture
    def sample_turn(self):
        """A sample turn for testing."""
        return Turn(
            turn_number=5,
            timestamp=datetime.now(),
            speaker_id="zoya",
            addressee_id="boris_molot",
            type=TurnType.ANSWER,
            content="Я просто отвечаю на вопрос.",
            display_delay_ms=1000,
        )

    def test_boris_silent_trigger_uses_pressure_reaction(
        self, boris, kim, sample_turn, sample_game
    ):
        """Boris should use pressure_with_sharper_question when silent too long."""
        checker = TriggerChecker(characters=[boris, kim])
        checker._silence_counters["boris_molot"] = 3

        results = checker.check_triggers_for_character(
            "boris_molot", sample_turn, sample_game
        )

        silent_results = [
            r for r in results
            if r.condition_type == ConditionType.SILENT_FOR_N_TURNS
        ]

        assert len(silent_results) == 1
        result = silent_results[0]

        assert result.reaction_type == ReactionType.PRESSURE_WITH_SHARPER_QUESTION
        assert result.priority == 9
        assert result.threshold == 0.3

    def test_kim_silent_trigger_uses_panic_reaction(
        self, boris, kim, sample_turn, sample_game
    ):
        """Kim should use panic_and_derail when silent too long."""
        checker = TriggerChecker(characters=[boris, kim])
        checker._silence_counters["kim"] = 3

        results = checker.check_triggers_for_character("kim", sample_turn, sample_game)

        silent_results = [
            r for r in results
            if r.condition_type == ConditionType.SILENT_FOR_N_TURNS
        ]

        assert len(silent_results) == 1
        result = silent_results[0]

        assert result.reaction_type == ReactionType.PANIC_AND_DERAIL
        assert result.priority == 4
        assert result.threshold == 0.4

    def test_different_characters_different_reactions_same_condition(
        self, boris, kim, sample_turn, sample_game
    ):
        """Different characters should have different reaction_types for same condition."""
        checker = TriggerChecker(characters=[boris, kim])

        checker._silence_counters["boris_molot"] = 3
        checker._silence_counters["kim"] = 3

        boris_results = checker.check_triggers_for_character(
            "boris_molot", sample_turn, sample_game
        )
        kim_results = checker.check_triggers_for_character(
            "kim", sample_turn, sample_game
        )

        boris_silent = next(
            r for r in boris_results
            if r.condition_type == ConditionType.SILENT_FOR_N_TURNS
        )
        kim_silent = next(
            r for r in kim_results
            if r.condition_type == ConditionType.SILENT_FOR_N_TURNS
        )

        assert boris_silent.condition_type == kim_silent.condition_type
        assert boris_silent.reaction_type != kim_silent.reaction_type
        assert boris_silent.reaction_type == ReactionType.PRESSURE_WITH_SHARPER_QUESTION
        assert kim_silent.reaction_type == ReactionType.PANIC_AND_DERAIL


class TestGlobalTriggerPersonalTriggerRequirement:
    """Test that global triggers only fire when character has matching personal trigger."""

    @pytest.fixture
    def accusation_turn_against_kim(self):
        """A turn with direct accusation against Kim."""
        return Turn(
            turn_number=5,
            timestamp=datetime.now(),
            speaker_id="boris_molot",
            addressee_id="kim",
            type=TurnType.QUESTION,
            content="Ким, ты шпион! Ты врёшь нам всё это время!",
            display_delay_ms=1000,
        )

    @pytest.fixture
    def accusation_turn_against_boris(self):
        """A turn with direct accusation against Boris."""
        return Turn(
            turn_number=5,
            timestamp=datetime.now(),
            speaker_id="kim",
            addressee_id="boris_molot",
            type=TurnType.QUESTION,
            content="Борис, ты шпион! Я не верю тебе!",
            display_delay_ms=1000,
        )

    def test_global_accusation_fires_for_character_with_personal_trigger(
        self, kim, boris, accusation_turn_against_kim, sample_game
    ):
        """Kim has direct_accusation personal trigger, so global should fire."""
        checker = TriggerChecker(characters=[boris, kim])

        results = checker.check_triggers_for_character(
            "kim", accusation_turn_against_kim, sample_game
        )

        accusation_results = [
            r for r in results
            if r.condition_type == ConditionType.DIRECT_ACCUSATION
        ]

        assert len(accusation_results) == 1
        result = accusation_results[0]

        assert result.reaction_type == ReactionType.PANIC_AND_DERAIL
        assert result.priority == 7
        assert result.threshold == 0.3

    def test_global_accusation_does_not_fire_for_character_without_personal_trigger(
        self, boris, kim, accusation_turn_against_boris, sample_game
    ):
        """Boris has NO direct_accusation personal trigger, so global should NOT fire."""
        checker = TriggerChecker(characters=[boris, kim])

        results = checker.check_triggers_for_character(
            "boris_molot", accusation_turn_against_boris, sample_game
        )

        accusation_results = [
            r for r in results
            if r.condition_type == ConditionType.DIRECT_ACCUSATION
        ]

        assert len(accusation_results) == 0

    def test_margo_accusation_uses_deflect_reaction(self, margo, boris, sample_game):
        """Margo has direct_accusation with deflect_suspicion_to_another."""
        accusation_turn = Turn(
            turn_number=5,
            timestamp=datetime.now(),
            speaker_id="boris_molot",
            addressee_id="margo",
            type=TurnType.QUESTION,
            content="Марго, ты шпион! Ты всё время уходишь от ответа!",
            display_delay_ms=1000,
        )

        checker = TriggerChecker(characters=[margo, boris])

        results = checker.check_triggers_for_character("margo", accusation_turn, sample_game)

        accusation_results = [
            r for r in results
            if r.condition_type == ConditionType.DIRECT_ACCUSATION
        ]

        assert len(accusation_results) == 1
        result = accusation_results[0]

        assert result.reaction_type == ReactionType.DEFLECT_SUSPICION_TO_ANOTHER
        assert result.priority == 8


class TestNoDuplicateTriggers:
    """Test that we don't get duplicate triggers for the same condition."""

    @pytest.fixture
    def sample_turn(self):
        """A sample turn for testing."""
        return Turn(
            turn_number=5,
            timestamp=datetime.now(),
            speaker_id="zoya",
            addressee_id="boris_molot",
            type=TurnType.ANSWER,
            content="Я просто отвечаю на вопрос.",
            display_delay_ms=1000,
        )

    def test_no_duplicate_silent_triggers(self, boris, kim, sample_turn, sample_game):
        """Should only get one trigger result per condition_type."""
        checker = TriggerChecker(characters=[boris, kim])
        checker._silence_counters["boris_molot"] = 3

        results = checker.check_triggers_for_character(
            "boris_molot", sample_turn, sample_game
        )

        condition_counts = {}
        for r in results:
            condition_counts[r.condition_type] = condition_counts.get(r.condition_type, 0) + 1

        for ct, count in condition_counts.items():
            assert count == 1, f"Duplicate results for {ct}"
