"""Tests for PostGameAnalyzer.analyze() method (TASK-086)."""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from src.models.character import Character, Marker
from src.models.game import Game, GameConfig, Player, Turn, TurnType
from src.models.post_game_analysis import AnalysisStatus, PostGameAnalysis
from src.post_game.analyzer import PostGameAnalyzer


@pytest.fixture
def sample_game() -> Game:
    """Create a sample game for testing."""
    return Game(
        id=uuid4(),
        started_at=datetime.now(timezone.utc),
        config=GameConfig(
            duration_minutes=5,
            players_count=3,
            max_questions=30,
            main_model="gpt-4o",
            utility_model="gpt-4o-mini",
        ),
        location_id="hospital",
        players=[
            Player(character_id="boris_molot", role_id="surgeon", is_spy=False),
            Player(character_id="zoya", role_id="nurse", is_spy=False),
            Player(character_id="kim", role_id=None, is_spy=True),
        ],
        spy_id="kim",
        turns=[
            Turn(
                turn_number=1,
                timestamp=datetime.now(timezone.utc),
                speaker_id="boris_molot",
                addressee_id="zoya",
                type=TurnType.QUESTION,
                content="Что ты делала сегодня?",
                display_delay_ms=100,
            ),
            Turn(
                turn_number=2,
                timestamp=datetime.now(timezone.utc),
                speaker_id="zoya",
                addressee_id="boris_molot",
                type=TurnType.ANSWER,
                content="Работала, как обычно.",
                display_delay_ms=100,
            ),
            Turn(
                turn_number=3,
                timestamp=datetime.now(timezone.utc),
                speaker_id="kim",
                addressee_id="boris_molot",
                type=TurnType.QUESTION,
                content="А ты чем занимался?",
                display_delay_ms=100,
            ),
        ],
    )


@pytest.fixture
def sample_character() -> Character:
    """Create a sample character for testing."""
    return Character(
        id="boris_molot",
        display_name="Борис",
        archetype="агрессор",
        backstory="Бывший следователь.",
        voice_style="Короткие рубленые фразы.",
        must_directives=["При обвинении — контратака"],
        must_not_directives=["Длинные оправдания"],
        detectable_markers=[
            Marker(
                id="short_sentences",
                method="counter",
                rule="sentences <= 2",
                description="Короткие предложения",
            )
        ],
        personal_triggers=[],
        intervention_priority=9,
        intervention_threshold=0.3,
    )


@pytest.fixture
def mock_llm_response() -> dict:
    """Sample LLM response for character analysis."""
    return {
        "character_id": "boris_molot",
        "markers": {
            "per_marker": [
                {
                    "marker_id": "short_sentences",
                    "triggered_count": 1,
                    "total_relevant_replies": 1,
                    "rate": 1.0,
                    "per_turn": [
                        {
                            "turn_number": 1,
                            "triggered": True,
                            "reasoning": "Короткий вопрос в 3 слова.",
                        }
                    ],
                }
            ]
        },
        "must_compliance": {
            "per_directive": [
                {
                    "directive": "При обвинении — контратака",
                    "satisfied": True,
                    "evidence_turns": [],
                    "reasoning": "Не было обвинений в данной партии.",
                }
            ]
        },
    }


class TestAnalyzeMethod:
    """Tests for analyze() method."""

    def test_analyze_loads_game_and_returns_analysis(
        self, sample_game, sample_character, mock_llm_response, tmp_path
    ):
        """Test that analyze loads game and returns PostGameAnalysis."""
        game_path = tmp_path / "test_game.json"
        with open(game_path, "w") as f:
            json.dump(sample_game.model_dump(mode="json"), f, default=str)

        analyzer = PostGameAnalyzer()

        with patch.object(
            analyzer, "_load_character_profile", return_value=sample_character
        ), patch.object(
            analyzer,
            "_analyze_character",
            new_callable=AsyncMock,
            return_value=analyzer._skipped_analysis("test", "test"),
        ):
            result = asyncio.run(analyzer.analyze(game_path))

        assert isinstance(result, PostGameAnalysis)
        assert result.analyzed_at is not None
        assert result.analyzer_model is not None
        assert len(result.per_character) == 3

    def test_analyze_returns_analysis_for_all_players(
        self, sample_game, sample_character, tmp_path
    ):
        """Test that result contains analysis for all players."""
        game_path = tmp_path / "test_game.json"
        with open(game_path, "w") as f:
            json.dump(sample_game.model_dump(mode="json"), f, default=str)

        analyzer = PostGameAnalyzer()

        with patch.object(
            analyzer, "_load_character_profile", return_value=sample_character
        ), patch.object(
            analyzer,
            "_analyze_character",
            new_callable=AsyncMock,
            return_value=analyzer._skipped_analysis("test", "no_replies"),
        ):
            result = asyncio.run(analyzer.analyze(game_path))

        player_ids = {p.character_id for p in sample_game.players}
        result_ids = set(result.per_character.keys())
        assert player_ids == result_ids

    def test_analyze_one_failure_doesnt_break_others(
        self, sample_game, sample_character, tmp_path
    ):
        """Test that one character failure doesn't break analysis of others."""
        game_path = tmp_path / "test_game.json"
        with open(game_path, "w") as f:
            json.dump(sample_game.model_dump(mode="json"), f, default=str)

        analyzer = PostGameAnalyzer()

        def load_profile_side_effect(char_id):
            if char_id == "kim":
                return None
            return sample_character

        with patch.object(
            analyzer,
            "_load_character_profile",
            side_effect=load_profile_side_effect,
        ), patch.object(
            analyzer,
            "_analyze_character",
            new_callable=AsyncMock,
            return_value=analyzer._skipped_analysis("test", "test"),
        ):
            result = asyncio.run(analyzer.analyze(game_path))

        assert result.status == AnalysisStatus.COMPLETED
        assert "kim" in result.per_character
        assert result.per_character["kim"].status == AnalysisStatus.FAILED
        assert result.per_character["kim"].error == "profile_not_found"
        assert "boris_molot" in result.per_character
        assert "zoya" in result.per_character

    def test_analyze_all_failures_returns_failed_status(
        self, sample_game, tmp_path
    ):
        """Test that if all characters fail, overall status is failed."""
        game_path = tmp_path / "test_game.json"
        with open(game_path, "w") as f:
            json.dump(sample_game.model_dump(mode="json"), f, default=str)

        analyzer = PostGameAnalyzer()

        with patch.object(
            analyzer, "_load_character_profile", return_value=None
        ):
            result = asyncio.run(analyzer.analyze(game_path))

        assert result.status == AnalysisStatus.FAILED
        assert result.error == "all_characters_failed"

    def test_analyze_game_not_found_returns_failed(self, tmp_path):
        """Test that missing game file returns failed status."""
        game_path = tmp_path / "nonexistent.json"

        analyzer = PostGameAnalyzer()
        result = asyncio.run(analyzer.analyze(game_path))

        assert result.status == AnalysisStatus.FAILED
        assert "failed_to_load_game" in result.error


class TestLoadCharacterProfile:
    """Tests for _load_character_profile() method."""

    def test_load_existing_character(self):
        """Test loading an existing character profile."""
        analyzer = PostGameAnalyzer()
        character = analyzer._load_character_profile("boris_molot")

        assert character is not None
        assert character.id == "boris_molot"
        assert character.display_name == "Борис"

    def test_load_nonexistent_character_returns_none(self):
        """Test that nonexistent character returns None."""
        analyzer = PostGameAnalyzer()
        character = analyzer._load_character_profile("nonexistent_char")

        assert character is None

    def test_load_all_characters(self):
        """Test that all standard characters can be loaded."""
        analyzer = PostGameAnalyzer()
        character_ids = [
            "boris_molot",
            "zoya",
            "kim",
            "margo",
            "professor_stein",
            "father_ignatius",
            "lyokha",
            "aurora",
        ]

        for char_id in character_ids:
            character = analyzer._load_character_profile(char_id)
            assert character is not None, f"Failed to load {char_id}"
            assert character.id == char_id
