"""Tests for the analyze CLI command (TASK-093).

Tests the --all flag behavior:
- Finding logs without post_game_analysis
- Skipping logs with existing analysis
- Summary output
- Empty games folder handling
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.analyze import (
    analyze_all_games,
    analyze_single_game,
    get_game_id_from_path,
    has_post_game_analysis,
)


class TestHasPostGameAnalysis:
    """Tests for has_post_game_analysis function."""

    def test_returns_true_when_analysis_exists(self, tmp_path):
        game_file = tmp_path / "test_game.json"
        game_data = {
            "id": "test-id",
            "post_game_analysis": {"status": "completed"}
        }
        game_file.write_text(json.dumps(game_data))

        assert has_post_game_analysis(game_file) is True

    def test_returns_false_when_no_analysis(self, tmp_path):
        game_file = tmp_path / "test_game.json"
        game_data = {"id": "test-id"}
        game_file.write_text(json.dumps(game_data))

        assert has_post_game_analysis(game_file) is False

    def test_returns_false_for_invalid_json(self, tmp_path):
        game_file = tmp_path / "test_game.json"
        game_file.write_text("invalid json {")

        assert has_post_game_analysis(game_file) is False

    def test_returns_false_for_nonexistent_file(self, tmp_path):
        game_file = tmp_path / "nonexistent.json"

        assert has_post_game_analysis(game_file) is False


class TestGetGameIdFromPath:
    """Tests for get_game_id_from_path function."""

    def test_extracts_uuid_from_standard_filename(self):
        path = Path("games/2026-04-21_08-30-01_bf13d21c-3017-41de-9b0c-8fcb45ddf55b.json")
        result = get_game_id_from_path(path)
        assert result == "bf13d21c-3017-41de-9b0c-8fcb45ddf55b"

    def test_handles_simple_filename(self):
        path = Path("games/simple_name.json")
        result = get_game_id_from_path(path)
        assert result == "simple_name"


class TestAnalyzeSingleGame:
    """Tests for analyze_single_game function."""

    def test_skips_when_no_overwrite_and_analysis_exists(self, tmp_path):
        game_file = tmp_path / "2026-01-01_00-00-00_test-id.json"
        game_data = {
            "id": "test-id",
            "post_game_analysis": {"status": "completed"}
        }
        game_file.write_text(json.dumps(game_data))

        success, message = asyncio.run(
            analyze_single_game(game_file, no_overwrite=True)
        )

        assert success is True
        assert "Skipped (analysis exists)" in message
        assert "test-id" in message


class TestAnalyzeAllGames:
    """Tests for analyze_all_games function."""

    def test_empty_folder_returns_zeros(self, capsys):
        with patch("src.analyze.list_games", return_value=[]):
            analyzed, skipped, errors = asyncio.run(
                analyze_all_games(no_overwrite=True)
            )

        assert analyzed == 0
        assert skipped == 0
        assert errors == 0

        captured = capsys.readouterr()
        assert "No games found" in captured.out

    def test_skips_games_with_existing_analysis(self, tmp_path, capsys):
        games_dir = tmp_path / "games"
        games_dir.mkdir()

        game1 = games_dir / "2026-01-01_00-00-00_game1.json"
        game2 = games_dir / "2026-01-01_00-00-01_game2.json"

        game1.write_text(json.dumps({
            "id": "game1",
            "post_game_analysis": {"status": "completed"}
        }))
        game2.write_text(json.dumps({
            "id": "game2",
            "post_game_analysis": {"status": "completed"}
        }))

        with patch("src.analyze.list_games", return_value=[game1, game2]):
            analyzed, skipped, errors = asyncio.run(
                analyze_all_games(no_overwrite=True)
            )

        assert analyzed == 0
        assert skipped == 2
        assert errors == 0

        captured = capsys.readouterr()
        assert "Skipped" in captured.out

    def test_summary_counts_are_correct(self, tmp_path, capsys):
        games_dir = tmp_path / "games"
        games_dir.mkdir()

        game_with_analysis = games_dir / "2026-01-01_00-00-00_with-analysis.json"
        game_without_analysis = games_dir / "2026-01-01_00-00-01_without-analysis.json"

        game_with_analysis.write_text(json.dumps({
            "id": "with-analysis",
            "post_game_analysis": {"status": "completed"}
        }))
        game_without_analysis.write_text(json.dumps({
            "id": "without-analysis",
            "players": []
        }))

        mock_analysis = MagicMock()
        mock_analysis.status.value = "completed"
        mock_analysis.error = None

        with patch("src.analyze.list_games", return_value=[game_with_analysis, game_without_analysis]):
            with patch("src.analyze.PostGameAnalyzer") as MockAnalyzer:
                analyzer_instance = MockAnalyzer.return_value
                analyzer_instance.analyze = AsyncMock(return_value=mock_analysis)
                analyzer_instance.save_analysis = MagicMock()

                analyzed, skipped, errors = asyncio.run(
                    analyze_all_games(no_overwrite=True)
                )

        assert skipped == 1
        assert analyzed == 1
        assert errors == 0


class TestSummaryOutput:
    """Tests for summary output format."""

    def test_summary_format_matches_spec(self, tmp_path, capsys):
        games_dir = tmp_path / "games"
        games_dir.mkdir()

        game = games_dir / "2026-01-01_00-00-00_test.json"
        game.write_text(json.dumps({
            "id": "test",
            "post_game_analysis": {"status": "completed"}
        }))

        with patch("src.analyze.list_games", return_value=[game]):
            analyzed, skipped, errors = asyncio.run(
                analyze_all_games(no_overwrite=True)
            )

        assert analyzed == 0
        assert skipped == 1
        assert errors == 0


class TestRerunSkipsAllAnalyzed:
    """Test that rerunning skips all previously analyzed games."""

    def test_second_run_skips_all(self, tmp_path, capsys):
        games_dir = tmp_path / "games"
        games_dir.mkdir()

        games = []
        for i in range(5):
            game = games_dir / f"2026-01-01_00-00-0{i}_game{i}.json"
            game.write_text(json.dumps({
                "id": f"game{i}",
                "post_game_analysis": {"status": "completed"}
            }))
            games.append(game)

        with patch("src.analyze.list_games", return_value=games):
            analyzed, skipped, errors = asyncio.run(
                analyze_all_games(no_overwrite=True)
            )

        assert analyzed == 0
        assert skipped == 5
        assert errors == 0

        captured = capsys.readouterr()
        assert captured.out.count("Skipped") == 5
