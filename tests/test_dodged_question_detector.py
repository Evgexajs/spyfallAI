"""Tests for TASK-073: dodged_direct_question detector."""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.llm.adapter import LLMResponse
from src.models.character import Character
from src.models.game import Game, GameConfig, Player, Turn, TurnType
from src.triggers.checker import TriggerChecker


def load_character(character_id: str) -> Character:
    """Load a character from JSON file."""
    path = Path(__file__).parent.parent / "characters" / f"{character_id}.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Character(**data)


@pytest.fixture
def boris():
    """Boris character."""
    return load_character("boris_molot")


@pytest.fixture
def kim():
    """Kim character."""
    return load_character("kim")


@pytest.fixture
def question_turn():
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
def direct_answer_turn():
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
def evasive_answer_turn():
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
    ]
    return Game(
        id=uuid4(),
        started_at=datetime.now(),
        config=GameConfig(
            duration_minutes=10,
            players_count=2,
            max_questions=20,
            main_model="gpt-4o",
            utility_model="gpt-4o-mini",
        ),
        location_id="hospital",
        players=players,
        spy_id="boris_molot",
        turns=[],
    )


class TestDodgedQuestionDetector:
    """Tests for check_dodged_question async method."""

    def test_evasive_answer_returns_true(
        self, boris, kim, question_turn, evasive_answer_turn, mock_provider
    ):
        """TASK-073 Step 1: Evasive answer should trigger (return True)."""
        checker = TriggerChecker(characters=[boris, kim])

        # Mock LLM response: "нет" means player did NOT answer substantively
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
        """TASK-073 Step 2: Direct answer should not trigger (return False)."""
        checker = TriggerChecker(characters=[boris, kim])

        # Mock LLM response: "да" means player answered substantively
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
        """TASK-073 Step 3: Invalid LLM response should return False and log warning."""
        checker = TriggerChecker(characters=[boris, kim])

        # Mock LLM response with invalid content
        mock_provider.complete.return_value = LLMResponse(
            content="может быть",  # Invalid - not yes/no
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

        # Mock LLM to raise exception
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

    def test_response_with_whitespace_is_normalized(
        self, boris, kim, question_turn, direct_answer_turn, mock_provider
    ):
        """Response with extra whitespace should be normalized."""
        checker = TriggerChecker(characters=[boris, kim])

        mock_provider.complete.return_value = LLMResponse(
            content="  Да  \n",  # With whitespace
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

        # Check that the prompt was called with correct parameters
        call_args = mock_provider.complete.call_args
        messages = call_args.kwargs.get("messages", call_args.args[0] if call_args.args else None)

        assert messages is not None
        prompt_content = messages[0]["content"]

        # Verify question and answer are in the prompt
        assert question_turn.content in prompt_content
        assert direct_answer_turn.content in prompt_content

    def test_uses_specified_model(
        self, boris, kim, question_turn, direct_answer_turn, mock_provider
    ):
        """Should use the specified model parameter."""
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
                model="custom-utility-model",
            )
        )

        call_args = mock_provider.complete.call_args
        assert call_args.kwargs.get("model") == "custom-utility-model"
