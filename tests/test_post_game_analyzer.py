"""Unit tests for PostGameAnalyzer (TASK-091).

Tests cover the following acceptance criteria:
1. Valid LLM response parses correctly
2. Invalid JSON -> status='failed'
3. Missing required fields -> status='failed', error='missing_required_fields'
4. Player without replies -> status='skipped'
5. Player without markers in profile -> markers.status='skipped'

All tests use mocks for LLM calls.
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.models.character import Character, Marker
from src.models.game import Game, GameConfig, Player, Turn, TurnType
from src.models.post_game_analysis import AnalysisStatus
from src.post_game.analyzer import PostGameAnalyzer


@pytest.fixture
def sample_character() -> Character:
    """Create a sample character with markers and must_directives."""
    return Character(
        id="test_char",
        display_name="Test Character",
        archetype="tester",
        backstory="A test character for unit tests.",
        voice_style="Technical and precise.",
        must_directives=["Must do test action", "Must verify results"],
        must_not_directives=["Must not skip tests"],
        detectable_markers=[
            Marker(
                id="marker_a",
                method="binary_llm",
                description="Test marker A",
                check_question="Does this contain marker A?"
            ),
            Marker(
                id="marker_b",
                method="counter",
                rule="sentences <= 2",
                description="Test marker B"
            ),
        ],
        personal_triggers=[],
        intervention_priority=5,
        intervention_threshold=0.5,
    )


@pytest.fixture
def sample_character_no_markers():
    """Create a character without detectable_markers using MagicMock.

    Uses MagicMock to bypass Pydantic validation constraints that require
    at least 1 detectable_marker in real Character models.
    """
    char = MagicMock(spec=Character)
    char.id = "no_markers_char"
    char.display_name = "No Markers Character"
    char.archetype = "plain"
    char.voice_style = "Simple test voice style."
    char.detectable_markers = []
    char.must_directives = ["Must do something"]
    char.must_not_directives = ["Must not fail"]
    return char


@pytest.fixture
def sample_turn() -> Turn:
    """Create a sample turn."""
    return Turn(
        turn_number=1,
        timestamp=datetime.now(timezone.utc),
        speaker_id="test_char",
        addressee_id="other_char",
        type=TurnType.ANSWER,
        content="This is a test response.",
        display_delay_ms=100,
    )


@pytest.fixture
def valid_llm_response() -> dict:
    """Create a valid LLM response for character analysis."""
    return {
        "character_id": "test_char",
        "markers": {
            "per_marker": [
                {
                    "marker_id": "marker_a",
                    "triggered_count": 1,
                    "total_relevant_replies": 1,
                    "rate": 1.0,
                    "per_turn": [
                        {
                            "turn_number": 1,
                            "triggered": True,
                            "reasoning": "Found marker A in the response."
                        }
                    ]
                },
                {
                    "marker_id": "marker_b",
                    "triggered_count": 0,
                    "total_relevant_replies": 1,
                    "rate": 0.0,
                    "per_turn": [
                        {
                            "turn_number": 1,
                            "triggered": False,
                            "reasoning": "Response has more than 2 sentences."
                        }
                    ]
                }
            ]
        },
        "must_compliance": {
            "per_directive": [
                {
                    "directive": "Must do test action",
                    "satisfied": True,
                    "evidence_turns": [1],
                    "reasoning": "Test action was performed."
                },
                {
                    "directive": "Must verify results",
                    "satisfied": True,
                    "evidence_turns": [],
                    "reasoning": "No verification needed in this context."
                }
            ]
        }
    }


class TestValidResponseParsing:
    """Test: valid LLM response parses correctly."""

    def test_valid_response_creates_correct_analysis(
        self, sample_character, sample_turn, valid_llm_response
    ):
        """Valid JSON response should be parsed into CharacterAnalysis.

        Note: When parsing succeeds, CharacterAnalysis.status is None
        (indicating no error/skip). The actual completion status is
        determined by markers.status and must_compliance.status.
        """
        analyzer = PostGameAnalyzer()

        with patch('src.post_game.analyzer.OpenAIProvider') as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(
                return_value=MagicMock(content=json.dumps(valid_llm_response))
            )
            mock_provider_class.return_value = mock_provider

            with patch('src.post_game.analyzer.LLMConfig') as mock_config:
                mock_config.return_value.get_model_for_role.return_value = (
                    "openai", "gpt-4o-mini"
                )
                result = asyncio.run(
                    analyzer._analyze_character(sample_character, [sample_turn])
                )

        assert result.status is None
        assert result.character_id == "test_char"
        assert result.error is None
        assert result.markers.status == AnalysisStatus.COMPLETED
        assert result.must_compliance.status == AnalysisStatus.COMPLETED

    def test_valid_response_parses_markers_correctly(
        self, sample_character, sample_turn, valid_llm_response
    ):
        """Markers in valid response should be parsed with correct values."""
        analyzer = PostGameAnalyzer()

        with patch('src.post_game.analyzer.OpenAIProvider') as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(
                return_value=MagicMock(content=json.dumps(valid_llm_response))
            )
            mock_provider_class.return_value = mock_provider

            with patch('src.post_game.analyzer.LLMConfig') as mock_config:
                mock_config.return_value.get_model_for_role.return_value = (
                    "openai", "gpt-4o-mini"
                )
                result = asyncio.run(
                    analyzer._analyze_character(sample_character, [sample_turn])
                )

        assert result.markers.status == AnalysisStatus.COMPLETED
        assert len(result.markers.per_marker) == 2

        marker_a = next(m for m in result.markers.per_marker if m.marker_id == "marker_a")
        assert marker_a.triggered_count == 1
        assert marker_a.rate == 1.0

        marker_b = next(m for m in result.markers.per_marker if m.marker_id == "marker_b")
        assert marker_b.triggered_count == 0
        assert marker_b.rate == 0.0

    def test_valid_response_parses_must_compliance_correctly(
        self, sample_character, sample_turn, valid_llm_response
    ):
        """Must compliance in valid response should be parsed correctly."""
        analyzer = PostGameAnalyzer()

        with patch('src.post_game.analyzer.OpenAIProvider') as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(
                return_value=MagicMock(content=json.dumps(valid_llm_response))
            )
            mock_provider_class.return_value = mock_provider

            with patch('src.post_game.analyzer.LLMConfig') as mock_config:
                mock_config.return_value.get_model_for_role.return_value = (
                    "openai", "gpt-4o-mini"
                )
                result = asyncio.run(
                    analyzer._analyze_character(sample_character, [sample_turn])
                )

        assert result.must_compliance.status == AnalysisStatus.COMPLETED
        assert len(result.must_compliance.per_directive) == 2
        assert all(d.satisfied for d in result.must_compliance.per_directive)


class TestInvalidJsonResponse:
    """Test: invalid JSON -> status='failed'."""

    def test_invalid_json_returns_failed_status(self, sample_character, sample_turn):
        """When LLM returns invalid JSON, analysis should fail."""
        analyzer = PostGameAnalyzer()
        invalid_json = "This is not valid JSON { broken }"

        with patch('src.post_game.analyzer.OpenAIProvider') as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(
                return_value=MagicMock(content=invalid_json)
            )
            mock_provider_class.return_value = mock_provider

            with patch('src.post_game.analyzer.LLMConfig') as mock_config:
                mock_config.return_value.get_model_for_role.return_value = (
                    "openai", "gpt-4o-mini"
                )
                result = asyncio.run(
                    analyzer._analyze_character(sample_character, [sample_turn])
                )

        assert result.status == AnalysisStatus.FAILED
        assert result.error == "invalid_json"

    def test_invalid_json_markers_also_failed(self, sample_character, sample_turn):
        """When JSON is invalid, markers and must_compliance also have failed status."""
        analyzer = PostGameAnalyzer()
        invalid_json = "not json at all"

        with patch('src.post_game.analyzer.OpenAIProvider') as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(
                return_value=MagicMock(content=invalid_json)
            )
            mock_provider_class.return_value = mock_provider

            with patch('src.post_game.analyzer.LLMConfig') as mock_config:
                mock_config.return_value.get_model_for_role.return_value = (
                    "openai", "gpt-4o-mini"
                )
                result = asyncio.run(
                    analyzer._analyze_character(sample_character, [sample_turn])
                )

        assert result.markers.status == AnalysisStatus.FAILED
        assert result.must_compliance.status == AnalysisStatus.FAILED

    def test_empty_response_returns_failed(self, sample_character, sample_turn):
        """Empty response from LLM should result in failed status."""
        analyzer = PostGameAnalyzer()

        with patch('src.post_game.analyzer.OpenAIProvider') as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(
                return_value=MagicMock(content="")
            )
            mock_provider_class.return_value = mock_provider

            with patch('src.post_game.analyzer.LLMConfig') as mock_config:
                mock_config.return_value.get_model_for_role.return_value = (
                    "openai", "gpt-4o-mini"
                )
                result = asyncio.run(
                    analyzer._analyze_character(sample_character, [sample_turn])
                )

        assert result.status == AnalysisStatus.FAILED
        assert result.error == "invalid_json"


class TestMissingRequiredFields:
    """Test: missing required fields -> status='failed', error='missing_required_fields'."""

    def test_missing_markers_field_returns_failed(self, sample_character, sample_turn):
        """When 'markers' field is missing, analysis should fail."""
        analyzer = PostGameAnalyzer()
        response_without_markers = {
            "character_id": "test_char",
            "must_compliance": {
                "per_directive": []
            }
        }

        with patch('src.post_game.analyzer.OpenAIProvider') as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(
                return_value=MagicMock(content=json.dumps(response_without_markers))
            )
            mock_provider_class.return_value = mock_provider

            with patch('src.post_game.analyzer.LLMConfig') as mock_config:
                mock_config.return_value.get_model_for_role.return_value = (
                    "openai", "gpt-4o-mini"
                )
                result = asyncio.run(
                    analyzer._analyze_character(sample_character, [sample_turn])
                )

        assert result.status == AnalysisStatus.FAILED
        assert result.error == "missing_required_fields"

    def test_missing_must_compliance_field_returns_failed(
        self, sample_character, sample_turn
    ):
        """When 'must_compliance' field is missing, analysis should fail."""
        analyzer = PostGameAnalyzer()
        response_without_must = {
            "character_id": "test_char",
            "markers": {
                "per_marker": []
            }
        }

        with patch('src.post_game.analyzer.OpenAIProvider') as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(
                return_value=MagicMock(content=json.dumps(response_without_must))
            )
            mock_provider_class.return_value = mock_provider

            with patch('src.post_game.analyzer.LLMConfig') as mock_config:
                mock_config.return_value.get_model_for_role.return_value = (
                    "openai", "gpt-4o-mini"
                )
                result = asyncio.run(
                    analyzer._analyze_character(sample_character, [sample_turn])
                )

        assert result.status == AnalysisStatus.FAILED
        assert result.error == "missing_required_fields"

    def test_missing_character_id_returns_failed(self, sample_character, sample_turn):
        """When 'character_id' field is missing, analysis should fail."""
        analyzer = PostGameAnalyzer()
        response_without_id = {
            "markers": {"per_marker": []},
            "must_compliance": {"per_directive": []}
        }

        with patch('src.post_game.analyzer.OpenAIProvider') as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(
                return_value=MagicMock(content=json.dumps(response_without_id))
            )
            mock_provider_class.return_value = mock_provider

            with patch('src.post_game.analyzer.LLMConfig') as mock_config:
                mock_config.return_value.get_model_for_role.return_value = (
                    "openai", "gpt-4o-mini"
                )
                result = asyncio.run(
                    analyzer._analyze_character(sample_character, [sample_turn])
                )

        assert result.status == AnalysisStatus.FAILED
        assert result.error == "missing_required_fields"


class TestNoReplies:
    """Test: player without replies -> status='skipped'."""

    def test_no_turns_returns_skipped(self, sample_character):
        """When character has no turns, analysis should be skipped."""
        analyzer = PostGameAnalyzer()

        result = asyncio.run(analyzer._analyze_character(sample_character, turns=[]))

        assert result.status == AnalysisStatus.SKIPPED
        assert result.reason == "no_replies"

    def test_no_turns_markers_also_skipped(self, sample_character):
        """When no turns, markers analysis should also be skipped."""
        analyzer = PostGameAnalyzer()

        result = asyncio.run(analyzer._analyze_character(sample_character, turns=[]))

        assert result.markers.status == AnalysisStatus.SKIPPED
        assert result.markers.reason == "no_replies"

    def test_no_turns_must_compliance_also_skipped(self, sample_character):
        """When no turns, must_compliance analysis should also be skipped."""
        analyzer = PostGameAnalyzer()

        result = asyncio.run(analyzer._analyze_character(sample_character, turns=[]))

        assert result.must_compliance.status == AnalysisStatus.SKIPPED
        assert result.must_compliance.reason == "no_replies"

    def test_no_turns_no_llm_call(self, sample_character):
        """When no turns, LLM should not be called."""
        analyzer = PostGameAnalyzer()

        with patch('src.post_game.analyzer.OpenAIProvider') as mock_provider_class:
            result = asyncio.run(
                analyzer._analyze_character(sample_character, turns=[])
            )
            mock_provider_class.assert_not_called()

        assert result.status == AnalysisStatus.SKIPPED


class TestNoMarkersInProfile:
    """Test: player without markers in profile -> markers.status='skipped'."""

    def test_no_markers_skips_marker_analysis(
        self, sample_character_no_markers, sample_turn
    ):
        """When character has no markers, markers analysis should be skipped."""
        analyzer = PostGameAnalyzer()
        llm_response = {
            "character_id": "no_markers_char",
            "must_compliance": {
                "per_directive": [
                    {
                        "directive": "Must do something",
                        "satisfied": True,
                        "evidence_turns": [1],
                        "reasoning": "Done"
                    }
                ]
            }
        }

        with patch('src.post_game.analyzer.OpenAIProvider') as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(
                return_value=MagicMock(content=json.dumps(llm_response))
            )
            mock_provider_class.return_value = mock_provider

            with patch('src.post_game.analyzer.LLMConfig') as mock_config:
                mock_config.return_value.get_model_for_role.return_value = (
                    "openai", "gpt-4o-mini"
                )
                sample_turn.speaker_id = "no_markers_char"
                result = asyncio.run(
                    analyzer._analyze_character(sample_character_no_markers, [sample_turn])
                )

        assert result.markers.status == AnalysisStatus.SKIPPED
        assert result.markers.reason == "no_markers_in_profile"
        assert result.markers.per_marker == []

    def test_no_markers_still_analyzes_must_directives(
        self, sample_character_no_markers, sample_turn
    ):
        """When no markers but has must_directives, must should be analyzed."""
        analyzer = PostGameAnalyzer()
        llm_response = {
            "character_id": "no_markers_char",
            "must_compliance": {
                "per_directive": [
                    {
                        "directive": "Must do something",
                        "satisfied": True,
                        "evidence_turns": [1],
                        "reasoning": "Done"
                    }
                ]
            }
        }

        with patch('src.post_game.analyzer.OpenAIProvider') as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(
                return_value=MagicMock(content=json.dumps(llm_response))
            )
            mock_provider_class.return_value = mock_provider

            with patch('src.post_game.analyzer.LLMConfig') as mock_config:
                mock_config.return_value.get_model_for_role.return_value = (
                    "openai", "gpt-4o-mini"
                )
                sample_turn.speaker_id = "no_markers_char"
                result = asyncio.run(
                    analyzer._analyze_character(sample_character_no_markers, [sample_turn])
                )

        assert result.must_compliance.status == AnalysisStatus.COMPLETED
        assert len(result.must_compliance.per_directive) == 1
        assert result.must_compliance.per_directive[0].satisfied is True


class TestLLMMocking:
    """Verify all tests properly mock LLM calls."""

    def test_llm_is_mocked_in_valid_response_test(
        self, sample_character, sample_turn, valid_llm_response
    ):
        """Confirm LLM provider is mocked and no real API calls are made."""
        analyzer = PostGameAnalyzer()

        with patch('src.post_game.analyzer.OpenAIProvider') as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(
                return_value=MagicMock(content=json.dumps(valid_llm_response))
            )
            mock_provider_class.return_value = mock_provider

            with patch('src.post_game.analyzer.LLMConfig') as mock_config:
                mock_config.return_value.get_model_for_role.return_value = (
                    "openai", "gpt-4o-mini"
                )
                asyncio.run(
                    analyzer._analyze_character(sample_character, [sample_turn])
                )

            mock_provider_class.assert_called_once()
            mock_provider.complete.assert_called_once()

    def test_timeout_returns_failed_with_timeout_error(
        self, sample_character, sample_turn
    ):
        """When LLM times out, analysis should fail with timeout error."""
        from src.llm.adapter import LLMTimeoutError

        analyzer = PostGameAnalyzer()

        with patch('src.post_game.analyzer.OpenAIProvider') as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(
                side_effect=LLMTimeoutError("Request timed out")
            )
            mock_provider_class.return_value = mock_provider

            with patch('src.post_game.analyzer.LLMConfig') as mock_config:
                mock_config.return_value.get_model_for_role.return_value = (
                    "openai", "gpt-4o-mini"
                )
                result = asyncio.run(
                    analyzer._analyze_character(sample_character, [sample_turn])
                )

        assert result.status == AnalysisStatus.FAILED
        assert result.error == "timeout"

    def test_llm_error_returns_failed(self, sample_character, sample_turn):
        """When LLM raises an error, analysis should fail."""
        analyzer = PostGameAnalyzer()

        with patch('src.post_game.analyzer.OpenAIProvider') as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(
                side_effect=Exception("API Error")
            )
            mock_provider_class.return_value = mock_provider

            with patch('src.post_game.analyzer.LLMConfig') as mock_config:
                mock_config.return_value.get_model_for_role.return_value = (
                    "openai", "gpt-4o-mini"
                )
                result = asyncio.run(
                    analyzer._analyze_character(sample_character, [sample_turn])
                )

        assert result.status == AnalysisStatus.FAILED
        assert "llm_error" in result.error
