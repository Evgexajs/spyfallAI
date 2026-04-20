"""Tests for GET /games API endpoint."""

import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.models.game import Game, GameConfig, GameOutcome, GamePhase, PhaseEntry, Player
from src.storage import save_game
from src.web.app import GameListItem, app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def temp_games_dir(monkeypatch):
    """Create a temporary games directory and patch the games directory path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        monkeypatch.setattr("src.storage.game_repository._get_games_dir", lambda: tmpdir_path)

        yield tmpdir_path


def create_test_game(
    location_id: str = "hospital",
    winner: str = "civilians",
    started_at: datetime = None,
) -> Game:
    """Create a test game object."""
    if started_at is None:
        started_at = datetime.now()

    return Game(
        id=uuid4(),
        started_at=started_at,
        ended_at=datetime.now(),
        config=GameConfig(
            duration_minutes=3,
            players_count=3,
            max_questions=10,
            main_model="gpt-4o",
            utility_model="gpt-4o-mini",
        ),
        location_id=location_id,
        players=[
            Player(character_id="boris_molot", role_id="surgeon", is_spy=False),
            Player(character_id="zoya", role_id="nurse", is_spy=False),
            Player(character_id="kim", role_id=None, is_spy=True),
        ],
        spy_id="kim",
        turns=[],
        spy_confidence_log=[],
        triggered_events=[],
        phase_transitions=[
            PhaseEntry(to_phase=GamePhase.SETUP, timestamp=started_at),
        ],
        outcome=GameOutcome(winner=winner, reason="Test game"),
    )


def test_get_games_returns_json_array(client, temp_games_dir):
    """Test that GET /games returns a JSON array."""
    response = client.get("/games")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_games_empty_when_no_games(client, temp_games_dir):
    """Test that GET /games returns empty list when no games exist."""
    response = client.get("/games")
    assert response.status_code == 200
    assert response.json() == []


def test_get_games_returns_game_fields(client, temp_games_dir):
    """Test that each game item contains required fields."""
    game = create_test_game(location_id="hospital", winner="civilians")
    save_game(game, temp_games_dir)

    response = client.get("/games")
    assert response.status_code == 200

    games = response.json()
    assert len(games) == 1

    game_item = games[0]
    assert "id" in game_item
    assert "started_at" in game_item
    assert "location_id" in game_item
    assert "winner" in game_item

    assert game_item["id"] == str(game.id)
    assert game_item["location_id"] == "hospital"
    assert game_item["winner"] == "civilians"


def test_get_games_sorted_newest_first(client, temp_games_dir):
    """Test that games are sorted by date (newest first)."""
    import time

    game1 = create_test_game(location_id="hospital", winner="spy")
    save_game(game1, temp_games_dir)

    time.sleep(0.1)

    game2 = create_test_game(location_id="airplane", winner="civilians")
    save_game(game2, temp_games_dir)

    response = client.get("/games")
    assert response.status_code == 200

    games = response.json()
    assert len(games) == 2

    assert games[0]["id"] == str(game2.id)
    assert games[1]["id"] == str(game1.id)


def test_get_games_handles_missing_outcome(client, temp_games_dir):
    """Test that games without outcome have null winner."""
    game = create_test_game()
    game.outcome = None
    save_game(game, temp_games_dir)

    response = client.get("/games")
    assert response.status_code == 200

    games = response.json()
    assert len(games) == 1
    assert games[0]["winner"] is None


def test_game_list_item_model():
    """Test GameListItem model validation."""
    item = GameListItem(
        id="test-id",
        started_at="2026-04-20T10:00:00",
        location_id="hospital",
        winner="civilians",
    )
    assert item.id == "test-id"
    assert item.location_id == "hospital"
    assert item.winner == "civilians"

    item_no_winner = GameListItem(
        id="test-id-2",
        started_at="2026-04-20T10:00:00",
        location_id="airplane",
        winner=None,
    )
    assert item_no_winner.winner is None


class TestGetGameById:
    """Tests for GET /games/{id} endpoint."""

    def test_get_game_by_id_returns_full_game(self, client, temp_games_dir):
        """Test that GET /games/{id} returns full game data."""
        game = create_test_game(location_id="hospital", winner="civilians")
        save_game(game, temp_games_dir)

        response = client.get(f"/games/{game.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == str(game.id)
        assert data["location_id"] == "hospital"
        assert "turns" in data
        assert "players" in data
        assert "outcome" in data
        assert "token_usage" in data

    def test_get_game_by_id_returns_404_when_not_found(self, client, temp_games_dir):
        """Test that GET /games/{id} returns 404 for non-existent game."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.get(f"/games/{fake_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_game_by_id_includes_players(self, client, temp_games_dir):
        """Test that returned game includes players with correct fields."""
        game = create_test_game()
        save_game(game, temp_games_dir)

        response = client.get(f"/games/{game.id}")
        assert response.status_code == 200

        data = response.json()
        players = data["players"]
        assert len(players) == 3

        for player in players:
            assert "character_id" in player
            assert "is_spy" in player
            assert "role_id" in player

    def test_get_game_by_id_includes_turns(self, client, temp_games_dir):
        """Test that returned game includes turns array."""
        game = create_test_game()
        save_game(game, temp_games_dir)

        response = client.get(f"/games/{game.id}")
        assert response.status_code == 200

        data = response.json()
        assert "turns" in data
        assert isinstance(data["turns"], list)

    def test_get_game_by_id_includes_outcome(self, client, temp_games_dir):
        """Test that returned game includes outcome."""
        game = create_test_game(winner="spy")
        save_game(game, temp_games_dir)

        response = client.get(f"/games/{game.id}")
        assert response.status_code == 200

        data = response.json()
        outcome = data["outcome"]
        assert outcome["winner"] == "spy"
        assert "reason" in outcome

    def test_get_game_by_id_includes_token_usage(self, client, temp_games_dir):
        """Test that returned game includes token_usage."""
        game = create_test_game()
        save_game(game, temp_games_dir)

        response = client.get(f"/games/{game.id}")
        assert response.status_code == 200

        data = response.json()
        token_usage = data["token_usage"]
        assert "total_input_tokens" in token_usage
        assert "total_output_tokens" in token_usage
        assert "total_cost_usd" in token_usage
        assert "llm_calls_count" in token_usage
