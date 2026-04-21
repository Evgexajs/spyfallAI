"""Tests for post-game analyzer edge cases (TASK-085).

Tests the following edge cases:
1. Character without turns (no_replies)
2. Character without detectable_markers in profile (no_markers_in_profile)
3. Character without must_directives in profile (no_must_in_profile)
4. LLM returns hallucinated markers (not in profile) - should be ignored with warning
5. LLM misses markers from profile - should be marked as NOT_ANALYZED
"""

import asyncio
from datetime import datetime
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.character import Character, Marker
from src.models.game import Turn, TurnType
from src.models.post_game_analysis import AnalysisStatus
from src.post_game.analyzer import PostGameAnalyzer

MOCK_MUST_ONLY_RESPONSE = (
    '{"character_id": "test_char", "must_compliance": {"per_directive": '
    '[{"directive": "Must do something", "satisfied": true, '
    '"evidence_turns": [1], "reasoning": "Done"}]}}'
)

MOCK_MARKERS_ONLY_RESPONSE = (
    '{"character_id": "test_char", "markers": {"per_marker": '
    '[{"marker_id": "marker1", "triggered_count": 1, '
    '"total_relevant_replies": 1, "rate": 1.0, '
    '"per_turn": [{"turn_number": 1, "triggered": true, '
    '"reasoning": "Found marker"}]}]}}'
)


def create_minimal_character(
    character_id: str = "test_char",
    markers: Optional[List[Marker]] = None,
    must_directives: Optional[List[str]] = None,
) -> Character:
    """Create a minimal character for testing.

    Uses MagicMock to bypass Pydantic validation for edge case testing.
    """
    char = MagicMock(spec=Character)
    char.id = character_id
    char.display_name = "Test Character"
    char.archetype = "tester"
    char.voice_style = "test voice style for testing purposes"
    char.detectable_markers = markers or []
    char.must_directives = must_directives or []
    char.must_not_directives = []
    return char


def create_turn(
    turn_number: int,
    speaker_id: str = "test_char",
    content: str = "Test message",
    turn_type: TurnType = TurnType.ANSWER,
) -> Turn:
    """Create a Turn for testing."""
    return Turn(
        turn_number=turn_number,
        timestamp=datetime.now(),
        speaker_id=speaker_id,
        addressee_id="other_player",
        type=turn_type,
        content=content,
        display_delay_ms=100,
    )


def create_marker(marker_id: str, description: str = "Test marker") -> Marker:
    """Create a Marker for testing."""
    return Marker(
        id=marker_id,
        method="binary_llm",
        description=description,
        check_question=f"Does this contain {marker_id}?"
    )


class TestEdgeCaseNoReplies:
    """Test case: character has no turns/replies."""

    def test_no_turns_returns_skipped(self):
        """When character has no turns, analysis should be skipped."""
        analyzer = PostGameAnalyzer()
        character = create_minimal_character(
            markers=[create_marker("marker1")],
            must_directives=["Must do something"]
        )

        result = asyncio.run(analyzer._analyze_character(character, turns=[]))

        assert result.status == AnalysisStatus.SKIPPED
        assert result.reason == "no_replies"
        assert result.markers.status == AnalysisStatus.SKIPPED
        assert result.must_compliance.status == AnalysisStatus.SKIPPED

    def test_no_turns_no_llm_call(self):
        """When character has no turns, LLM should not be called."""
        analyzer = PostGameAnalyzer()
        character = create_minimal_character(
            markers=[create_marker("marker1")],
            must_directives=["Must do something"]
        )

        with patch.object(analyzer, '_failed_analysis') as mock_failed:
            result = asyncio.run(analyzer._analyze_character(character, turns=[]))
            mock_failed.assert_not_called()
            assert result.status == AnalysisStatus.SKIPPED


class TestEdgeCaseNoMarkers:
    """Test case: character has no detectable_markers in profile."""

    def test_no_markers_skips_marker_analysis(self):
        """When character has no markers, markers analysis should be skipped."""
        analyzer = PostGameAnalyzer()
        character = create_minimal_character(
            markers=[],  # No markers
            must_directives=["Must do something"]
        )
        turns = [create_turn(1)]

        with patch('src.post_game.analyzer.OpenAIProvider') as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(
                return_value=MagicMock(content=MOCK_MUST_ONLY_RESPONSE)
            )
            mock_provider_class.return_value = mock_provider

            with patch('src.post_game.analyzer.LLMConfig') as mock_config:
                mock_config.return_value.get_model_for_role.return_value = (
                    "openai", "gpt-4o-mini"
                )
                result = asyncio.run(analyzer._analyze_character(character, turns))

        assert result.markers.status == AnalysisStatus.SKIPPED
        assert result.markers.reason == "no_markers_in_profile"
        assert result.markers.per_marker == []

    def test_no_markers_still_analyzes_must(self):
        """When character has no markers but has must_directives, must should be analyzed."""
        analyzer = PostGameAnalyzer()
        character = create_minimal_character(
            markers=[],
            must_directives=["Must do something"]
        )
        turns = [create_turn(1)]

        with patch('src.post_game.analyzer.OpenAIProvider') as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.complete = AsyncMock(
                return_value=MagicMock(content=MOCK_MUST_ONLY_RESPONSE)
            )
            mock_provider_class.return_value = mock_provider

            with patch('src.post_game.analyzer.LLMConfig') as mock_config:
                mock_config.return_value.get_model_for_role.return_value = (
                    "openai", "gpt-4o-mini"
                )
                result = asyncio.run(analyzer._analyze_character(character, turns))

        assert result.must_compliance.status == AnalysisStatus.COMPLETED
        assert len(result.must_compliance.per_directive) == 1


class TestEdgeCaseNoMustDirectives:
    """Test case: character has no must_directives in profile."""

    def test_no_must_skips_compliance_analysis(self):
        """When character has no must_directives, must_compliance should be skipped."""
        async def run_test():
            analyzer = PostGameAnalyzer()
            character = create_minimal_character(
                markers=[create_marker("marker1")],
                must_directives=[]  # No must directives
            )
            turns = [create_turn(1)]

            with patch('src.post_game.analyzer.OpenAIProvider') as mock_cls:
                mock_provider = MagicMock()
                mock_provider.complete = AsyncMock(
                    return_value=MagicMock(content=MOCK_MARKERS_ONLY_RESPONSE)
                )
                mock_cls.return_value = mock_provider

                with patch('src.post_game.analyzer.LLMConfig') as mock_config:
                    mock_config.return_value.get_model_for_role.return_value = (
                        "openai", "gpt-4o-mini"
                    )
                    result = await analyzer._analyze_character(character, turns)

            return result

        result = asyncio.run(run_test())
        assert result.must_compliance.status == AnalysisStatus.SKIPPED
        assert result.must_compliance.reason == "no_must_in_profile"
        assert result.must_compliance.per_directive == []

    def test_no_must_still_analyzes_markers(self):
        """When character has no must_directives but has markers, markers should be analyzed."""
        async def run_test():
            analyzer = PostGameAnalyzer()
            character = create_minimal_character(
                markers=[create_marker("marker1")],
                must_directives=[]
            )
            turns = [create_turn(1)]

            with patch('src.post_game.analyzer.OpenAIProvider') as mock_cls:
                mock_provider = MagicMock()
                mock_provider.complete = AsyncMock(
                    return_value=MagicMock(content=MOCK_MARKERS_ONLY_RESPONSE)
                )
                mock_cls.return_value = mock_provider

                with patch('src.post_game.analyzer.LLMConfig') as mock_config:
                    mock_config.return_value.get_model_for_role.return_value = (
                        "openai", "gpt-4o-mini"
                    )
                    result = await analyzer._analyze_character(character, turns)

            return result

        result = asyncio.run(run_test())
        assert result.markers.status == AnalysisStatus.COMPLETED
        assert len(result.markers.per_marker) == 1


class TestEdgeCaseNoMarkersAndNoMust:
    """Test case: character has neither markers nor must_directives."""

    def test_no_markers_no_must_returns_skipped(self):
        """When character has no markers and no must_directives, skip entirely."""
        analyzer = PostGameAnalyzer()
        character = create_minimal_character(
            markers=[],
            must_directives=[]
        )
        turns = [create_turn(1)]

        result = asyncio.run(analyzer._analyze_character(character, turns))

        assert result.status == AnalysisStatus.SKIPPED
        assert "no_markers_in_profile_and_no_must_in_profile" in result.reason


class TestEdgeCaseHallucinatedMarkers:
    """Test case: LLM returns markers not in character profile."""

    def test_hallucinated_markers_are_removed(self):
        """LLM-returned markers not in profile should be removed with warning."""
        analyzer = PostGameAnalyzer()
        character = create_minimal_character(
            markers=[create_marker("real_marker")],
            must_directives=["Must do something"]
        )

        llm_data = {
            "character_id": character.id,
            "markers": {
                "per_marker": [
                    {
                        "marker_id": "real_marker",
                        "triggered_count": 1,
                        "total_relevant_replies": 1,
                        "rate": 1.0,
                        "per_turn": [{"turn_number": 1, "triggered": True, "reasoning": "Found"}]
                    },
                    {
                        "marker_id": "hallucinated_marker",
                        "triggered_count": 1,
                        "total_relevant_replies": 1,
                        "rate": 1.0,
                        "per_turn": [{"turn_number": 1, "triggered": True, "reasoning": "Imagined"}]
                    }
                ]
            },
            "must_compliance": {
                "per_directive": [{
                    "directive": "Must do something",
                    "satisfied": True,
                    "evidence_turns": [1],
                    "reasoning": "Done"
                }]
            }
        }

        result = analyzer._parse_llm_response(character, llm_data)

        marker_ids = [m.marker_id for m in result.markers.per_marker]
        assert "real_marker" in marker_ids
        assert "hallucinated_marker" not in marker_ids
        assert any("hallucinated_marker" in w for w in result._analyzer_warnings)


class TestEdgeCaseMissingMarkers:
    """Test case: LLM misses some markers from character profile."""

    def test_missing_markers_are_added_as_not_analyzed(self):
        """Markers from profile that LLM missed should be added with NOT_ANALYZED status."""
        analyzer = PostGameAnalyzer()
        character = create_minimal_character(
            markers=[create_marker("marker1"), create_marker("marker2")],
            must_directives=["Must do something"]
        )

        llm_data = {
            "character_id": character.id,
            "markers": {
                "per_marker": [
                    {
                        "marker_id": "marker1",
                        "triggered_count": 1,
                        "total_relevant_replies": 1,
                        "rate": 1.0,
                        "per_turn": [{"turn_number": 1, "triggered": True, "reasoning": "Found"}]
                    }
                    # marker2 is missing
                ]
            },
            "must_compliance": {
                "per_directive": [{
                    "directive": "Must do something",
                    "satisfied": True,
                    "evidence_turns": [1],
                    "reasoning": "Done"
                }]
            }
        }

        result = analyzer._parse_llm_response(character, llm_data)

        marker_ids = {m.marker_id for m in result.markers.per_marker}
        assert "marker1" in marker_ids
        assert "marker2" in marker_ids

        marker2_entry = next(m for m in result.markers.per_marker if m.marker_id == "marker2")
        assert marker2_entry.status == AnalysisStatus.NOT_ANALYZED
        assert any("marker2" in w for w in result._analyzer_warnings)


class TestSkippedAnalysisHelpers:
    """Test the helper methods for creating skipped analysis objects."""

    def test_skipped_analysis_creates_proper_structure(self):
        """_skipped_analysis should create properly structured CharacterAnalysis."""
        analyzer = PostGameAnalyzer()

        result = analyzer._skipped_analysis("test_char", "test_reason")

        assert result.character_id == "test_char"
        assert result.status == AnalysisStatus.SKIPPED
        assert result.reason == "test_reason"
        assert result.markers.status == AnalysisStatus.SKIPPED
        assert result.markers.reason == "test_reason"
        assert result.must_compliance.status == AnalysisStatus.SKIPPED
        assert result.must_compliance.reason == "test_reason"

    def test_skipped_markers_analysis(self):
        """_skipped_markers_analysis should create MarkerAnalysis with SKIPPED status."""
        analyzer = PostGameAnalyzer()

        result = analyzer._skipped_markers_analysis("no_markers_in_profile")

        assert result.status == AnalysisStatus.SKIPPED
        assert result.reason == "no_markers_in_profile"
        assert result.per_marker == []

    def test_skipped_must_analysis(self):
        """_skipped_must_analysis should create MustComplianceAnalysis with SKIPPED status."""
        analyzer = PostGameAnalyzer()

        result = analyzer._skipped_must_analysis("no_must_in_profile")

        assert result.status == AnalysisStatus.SKIPPED
        assert result.reason == "no_must_in_profile"
        assert result.per_directive == []
