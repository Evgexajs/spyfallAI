"""Tests for defense voting phase models (TASK-058, TASK-065)."""

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from src.models import (
    DefenseSpeech,
    Game,
    GameConfig,
    GameOutcome,
    GamePhase,
    PhaseEntry,
    Player,
    TurnType,
    VoteChange,
)
from src.storage.game_repository import load_game


class TestDefenseSpeechModel:
    """Tests for DefenseSpeech model."""

    def test_create_defense_speech(self):
        """Test creating a valid DefenseSpeech."""
        speech = DefenseSpeech(
            defender_id="boris_molot",
            votes_received=3,
            content="Вы все ошибаетесь!",
            timestamp=datetime.now(),
        )
        assert speech.defender_id == "boris_molot"
        assert speech.votes_received == 3
        assert speech.content == "Вы все ошибаетесь!"

    def test_defense_speech_requires_defender_id(self):
        """Test that defender_id is required and non-empty."""
        with pytest.raises(ValueError):
            DefenseSpeech(
                defender_id="",
                votes_received=2,
                content="Test",
                timestamp=datetime.now(),
            )

    def test_defense_speech_requires_content(self):
        """Test that content is required and non-empty."""
        with pytest.raises(ValueError):
            DefenseSpeech(
                defender_id="boris",
                votes_received=2,
                content="",
                timestamp=datetime.now(),
            )

    def test_defense_speech_votes_non_negative(self):
        """Test that votes_received must be >= 0."""
        with pytest.raises(ValueError):
            DefenseSpeech(
                defender_id="boris",
                votes_received=-1,
                content="Test",
                timestamp=datetime.now(),
            )

    def test_defense_speech_serialization(self):
        """Test JSON serialization/deserialization."""
        speech = DefenseSpeech(
            defender_id="zoya",
            votes_received=2,
            content="Серьезно? Это всё что у вас есть?",
            timestamp=datetime(2026, 4, 20, 12, 0, 0),
        )
        json_str = speech.model_dump_json()
        parsed = DefenseSpeech.model_validate_json(json_str)
        assert parsed.defender_id == speech.defender_id
        assert parsed.votes_received == speech.votes_received
        assert parsed.content == speech.content


class TestVoteChangeModel:
    """Tests for VoteChange model."""

    def test_create_vote_change(self):
        """Test creating a valid VoteChange."""
        change = VoteChange(
            voter_id="kim",
            from_target="boris_molot",
            to_target="zoya",
        )
        assert change.voter_id == "kim"
        assert change.from_target == "boris_molot"
        assert change.to_target == "zoya"

    def test_vote_change_with_abstain(self):
        """Test VoteChange with null targets (abstain)."""
        change = VoteChange(
            voter_id="kim",
            from_target=None,
            to_target="boris_molot",
        )
        assert change.from_target is None
        assert change.to_target == "boris_molot"

    def test_vote_change_to_abstain(self):
        """Test VoteChange where player changes to abstain."""
        change = VoteChange(
            voter_id="kim",
            from_target="boris_molot",
            to_target=None,
        )
        assert change.from_target == "boris_molot"
        assert change.to_target is None

    def test_vote_change_requires_voter_id(self):
        """Test that voter_id is required and non-empty."""
        with pytest.raises(ValueError):
            VoteChange(
                voter_id="",
                from_target="boris",
                to_target="zoya",
            )

    def test_vote_change_serialization(self):
        """Test JSON serialization/deserialization."""
        change = VoteChange(
            voter_id="margo",
            from_target="kim",
            to_target="boris_molot",
        )
        json_str = change.model_dump_json()
        parsed = VoteChange.model_validate_json(json_str)
        assert parsed.voter_id == change.voter_id
        assert parsed.from_target == change.from_target
        assert parsed.to_target == change.to_target


class TestPhaseEntryStatus:
    """Tests for PhaseEntry status field."""

    def test_phase_entry_with_status(self):
        """Test PhaseEntry with status field."""
        entry = PhaseEntry(
            timestamp=datetime.now(),
            from_phase=GamePhase.MAIN_ROUND,
            to_phase=GamePhase.FINAL_VOTE,
            reason="Defense phase skipped",
            status="skipped_copied_from_preliminary",
        )
        assert entry.status == "skipped_copied_from_preliminary"

    def test_phase_entry_status_optional(self):
        """Test that status is optional and defaults to None."""
        entry = PhaseEntry(
            timestamp=datetime.now(),
            to_phase=GamePhase.SETUP,
        )
        assert entry.status is None


class TestGameWithNewFields:
    """Tests for Game model with new defense voting fields."""

    def _create_base_game(self) -> Game:
        """Create a valid base Game for testing."""
        return Game(
            id=uuid4(),
            started_at=datetime.now(),
            config=GameConfig(
                duration_minutes=10,
                players_count=4,
                max_questions=20,
                main_model="gpt-4o",
                utility_model="gpt-4o-mini",
            ),
            location_id="hospital",
            players=[
                Player(character_id="boris_molot", role_id="surgeon", is_spy=False),
                Player(character_id="zoya", role_id="nurse", is_spy=True),
                Player(character_id="kim", role_id="patient", is_spy=False),
                Player(character_id="margo", role_id="receptionist", is_spy=False),
            ],
            spy_id="zoya",
        )

    def test_game_with_preliminary_vote_result(self):
        """Test Game with preliminary_vote_result field."""
        game = self._create_base_game()
        game.preliminary_vote_result = {
            "boris_molot": "zoya",
            "zoya": "kim",
            "kim": "boris_molot",
            "margo": None,  # abstained
        }
        assert game.preliminary_vote_result["boris_molot"] == "zoya"
        assert game.preliminary_vote_result["margo"] is None

    def test_game_with_defense_speeches(self):
        """Test Game with defense_speeches field."""
        game = self._create_base_game()
        game.defense_speeches = [
            DefenseSpeech(
                defender_id="boris_molot",
                votes_received=2,
                content="Я невиновен!",
                timestamp=datetime.now(),
            ),
            DefenseSpeech(
                defender_id="zoya",
                votes_received=2,
                content="Ну да, конечно.",
                timestamp=datetime.now(),
            ),
        ]
        assert len(game.defense_speeches) == 2
        assert game.defense_speeches[0].defender_id == "boris_molot"

    def test_game_with_final_vote_result(self):
        """Test Game with final_vote_result field."""
        game = self._create_base_game()
        game.final_vote_result = {
            "boris_molot": "zoya",
            "zoya": "kim",
            "kim": "zoya",  # changed vote
            "margo": "zoya",  # voted after abstaining
        }
        assert game.final_vote_result["kim"] == "zoya"

    def test_game_with_vote_changes(self):
        """Test Game with vote_changes field."""
        game = self._create_base_game()
        game.vote_changes = [
            VoteChange(voter_id="kim", from_target="boris_molot", to_target="zoya"),
            VoteChange(voter_id="margo", from_target=None, to_target="zoya"),
        ]
        assert len(game.vote_changes) == 2
        assert game.vote_changes[0].voter_id == "kim"

    def test_game_full_serialization(self):
        """Test full Game serialization with all new fields."""
        game = self._create_base_game()
        game.preliminary_vote_result = {
            "boris_molot": "zoya",
            "zoya": "kim",
            "kim": "boris_molot",
            "margo": None,
        }
        game.defense_speeches = [
            DefenseSpeech(
                defender_id="boris_molot",
                votes_received=2,
                content="Это недоразумение!",
                timestamp=datetime(2026, 4, 20, 12, 0, 0),
            ),
        ]
        game.final_vote_result = {
            "boris_molot": "zoya",
            "zoya": "kim",
            "kim": "zoya",
            "margo": "zoya",
        }
        game.vote_changes = [
            VoteChange(voter_id="kim", from_target="boris_molot", to_target="zoya"),
        ]
        game.outcome = GameOutcome(
            winner="civilians",
            reason="Spy was correctly identified",
            votes=game.final_vote_result,
            accused_id="zoya",
        )

        json_str = game.model_dump_json()
        parsed = Game.model_validate_json(json_str)

        assert parsed.preliminary_vote_result == game.preliminary_vote_result
        assert len(parsed.defense_speeches) == 1
        assert parsed.defense_speeches[0].defender_id == "boris_molot"
        assert parsed.final_vote_result == game.final_vote_result
        assert len(parsed.vote_changes) == 1
        assert parsed.vote_changes[0].voter_id == "kim"


class TestBackwardCompatibility:
    """Tests for backward compatibility with old game logs."""

    def test_load_game_without_new_fields(self):
        """Test loading a Game JSON without the new fields."""
        old_game_json = {
            "id": "12345678-1234-1234-1234-123456789abc",
            "started_at": "2026-04-19T10:00:00",
            "config": {
                "duration_minutes": 10,
                "players_count": 3,
                "max_questions": 20,
                "main_model": "gpt-4o",
                "utility_model": "gpt-4o-mini",
            },
            "location_id": "hospital",
            "players": [
                {"character_id": "boris_molot", "role_id": "surgeon", "is_spy": False},
                {"character_id": "zoya", "role_id": "nurse", "is_spy": True},
                {"character_id": "kim", "role_id": "patient", "is_spy": False},
            ],
            "spy_id": "zoya",
            "turns": [],
            "spy_confidence_log": [],
            "triggered_events": [],
            "phase_transitions": [],
            "outcome": {
                "winner": "spy",
                "reason": "Civilians voted wrong",
                "votes": {"boris_molot": "kim", "zoya": "kim", "kim": "boris_molot"},
            },
        }

        game = Game.model_validate(old_game_json)

        assert game.preliminary_vote_result is None
        assert game.defense_speeches == []
        assert game.final_vote_result is None
        assert game.vote_changes == []

    def test_load_game_with_partial_new_fields(self):
        """Test loading a Game with only some new fields."""
        partial_json = {
            "id": "12345678-1234-1234-1234-123456789abc",
            "started_at": "2026-04-19T10:00:00",
            "config": {
                "duration_minutes": 10,
                "players_count": 3,
                "max_questions": 20,
                "main_model": "gpt-4o",
                "utility_model": "gpt-4o-mini",
            },
            "location_id": "hospital",
            "players": [
                {"character_id": "boris_molot", "role_id": "surgeon", "is_spy": False},
                {"character_id": "zoya", "role_id": "nurse", "is_spy": True},
                {"character_id": "kim", "role_id": "patient", "is_spy": False},
            ],
            "spy_id": "zoya",
            "preliminary_vote_result": {
                "boris_molot": "zoya",
                "zoya": "kim",
                "kim": "boris_molot",
            },
        }

        game = Game.model_validate(partial_json)

        assert game.preliminary_vote_result is not None
        assert game.defense_speeches == []
        assert game.final_vote_result is None
        assert game.vote_changes == []

    def test_round_trip_preserves_data(self):
        """Test that JSON round-trip preserves all data."""
        original = {
            "id": "12345678-1234-1234-1234-123456789abc",
            "started_at": "2026-04-19T10:00:00",
            "config": {
                "duration_minutes": 10,
                "players_count": 4,
                "max_questions": 20,
                "main_model": "gpt-4o",
                "utility_model": "gpt-4o-mini",
            },
            "location_id": "hospital",
            "players": [
                {"character_id": "boris_molot", "role_id": "surgeon", "is_spy": False},
                {"character_id": "zoya", "role_id": "nurse", "is_spy": True},
                {"character_id": "kim", "role_id": "patient", "is_spy": False},
                {"character_id": "margo", "role_id": "receptionist", "is_spy": False},
            ],
            "spy_id": "zoya",
            "preliminary_vote_result": {
                "boris_molot": "zoya",
                "zoya": "kim",
                "kim": "boris_molot",
                "margo": None,
            },
            "defense_speeches": [
                {
                    "defender_id": "boris_molot",
                    "votes_received": 1,
                    "content": "Test",
                    "timestamp": "2026-04-19T10:30:00",
                }
            ],
            "final_vote_result": {
                "boris_molot": "zoya",
                "zoya": "kim",
                "kim": "zoya",
                "margo": "zoya",
            },
            "vote_changes": [
                {"voter_id": "kim", "from_target": "boris_molot", "to_target": "zoya"}
            ],
        }

        game = Game.model_validate(original)
        exported = json.loads(game.model_dump_json())

        assert exported["preliminary_vote_result"] == original["preliminary_vote_result"]
        assert len(exported["defense_speeches"]) == 1
        assert exported["vote_changes"][0]["voter_id"] == "kim"


class TestTurnTypeValues:
    """Verify TurnType enum values for defense voting."""

    def test_preliminary_vote_type_exists(self):
        """Test PRELIMINARY_VOTE type exists."""
        assert TurnType.PRELIMINARY_VOTE.value == "preliminary_vote"

    def test_defense_speech_type_exists(self):
        """Test DEFENSE_SPEECH type exists."""
        assert TurnType.DEFENSE_SPEECH.value == "defense_speech"

    def test_final_vote_type_exists(self):
        """Test FINAL_VOTE type exists."""
        assert TurnType.FINAL_VOTE.value == "final_vote"

    def test_vote_type_preserved(self):
        """Test old VOTE type still exists for backward compatibility."""
        assert TurnType.VOTE.value == "vote"


class TestRealGameFileBackwardCompatibility:
    """Tests for backward compatibility with real game log files (TASK-065)."""

    def test_load_existing_game_files(self):
        """Test loading all existing game files from games/ directory.

        Verifies that old game logs without CR-001 fields load without errors.
        """
        games_dir = Path(__file__).parent.parent / "games"
        if not games_dir.exists():
            pytest.skip("No games directory found")

        game_files = list(games_dir.glob("*.json"))
        if not game_files:
            pytest.skip("No game files found")

        for game_file in game_files:
            game = load_game(game_file)

            assert game.id is not None
            assert game.location_id is not None
            assert len(game.players) >= 3
            prelim_vote = game.preliminary_vote_result
            assert prelim_vote is None or isinstance(prelim_vote, dict)
            assert isinstance(game.defense_speeches, list)
            assert game.final_vote_result is None or isinstance(game.final_vote_result, dict)
            assert isinstance(game.vote_changes, list)

    def test_old_game_defaults_are_correct(self):
        """Test that old games get correct default values for new fields."""
        games_dir = Path(__file__).parent.parent / "games"
        if not games_dir.exists():
            pytest.skip("No games directory found")

        game_files = list(games_dir.glob("*.json"))
        if not game_files:
            pytest.skip("No game files found")

        for game_file in game_files:
            with open(game_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            game = load_game(game_file)

            if "preliminary_vote_result" not in raw_data:
                assert game.preliminary_vote_result is None
            if "defense_speeches" not in raw_data:
                assert game.defense_speeches == []
            if "final_vote_result" not in raw_data:
                assert game.final_vote_result is None
            if "vote_changes" not in raw_data:
                assert game.vote_changes == []

    def test_round_trip_preserves_existing_game_data(self):
        """Test that loading and re-serializing an old game preserves all original data."""
        games_dir = Path(__file__).parent.parent / "games"
        if not games_dir.exists():
            pytest.skip("No games directory found")

        game_files = list(games_dir.glob("*.json"))
        if not game_files:
            pytest.skip("No game files found")

        for game_file in game_files:
            with open(game_file, "r", encoding="utf-8") as f:
                original_data = json.load(f)

            game = load_game(game_file)
            reserialized = json.loads(game.model_dump_json())

            assert reserialized["id"] == original_data["id"]
            assert reserialized["location_id"] == original_data["location_id"]
            assert reserialized["spy_id"] == original_data["spy_id"]
            assert len(reserialized["players"]) == len(original_data["players"])
            assert len(reserialized["turns"]) == len(original_data.get("turns", []))
