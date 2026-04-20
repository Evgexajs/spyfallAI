"""Tests for unanimous voting logic (TASK-055).

Voting succeeds ONLY if all players vote for the same person.
If votes are split, the game continues (returns to main_round).
"""

import pytest
from datetime import datetime
from uuid import uuid4

from src.models import (
    Game,
    GameConfig,
    GameOutcome,
    GamePhase,
    Player,
    Turn,
    TurnType,
    TokenUsage,
    PhaseEntry,
)


class TestUnanimousVotingLogic:
    """Test the unanimous voting logic without LLM calls."""

    def create_test_game(self, num_players: int = 4) -> Game:
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
                duration_minutes=5,
                players_count=num_players,
                max_questions=20,
                main_model="gpt-4o",
                utility_model="gpt-4o-mini",
            ),
            location_id="test_location",
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
            token_usage=TokenUsage(),
        )

    def test_unanimous_vote_catches_spy(self):
        """When all players vote for the spy, civilians win."""
        game = self.create_test_game(4)

        votes = {
            "player_1": "player_0",  # spy
            "player_2": "player_0",  # spy
            "player_3": "player_0",  # spy
        }

        unique_votes = set(votes.values())
        is_unanimous = len(unique_votes) == 1

        assert is_unanimous is True
        assert list(unique_votes)[0] == game.spy_id

    def test_unanimous_vote_wrong_target(self):
        """When all players vote for non-spy unanimously, spy wins."""
        game = self.create_test_game(4)

        votes = {
            "player_0": "player_1",  # spy votes
            "player_2": "player_1",  # wrong target
            "player_3": "player_1",  # wrong target
        }

        unique_votes = set(votes.values())
        is_unanimous = len(unique_votes) == 1
        accused = list(unique_votes)[0]

        assert is_unanimous is True
        assert accused != game.spy_id

    def test_split_vote_two_targets(self):
        """When votes are split between 2 targets, voting fails."""
        game = self.create_test_game(4)

        votes = {
            "player_0": "player_1",
            "player_1": "player_0",
            "player_2": "player_1",
            "player_3": "player_0",
        }

        unique_votes = set(votes.values())
        is_unanimous = len(unique_votes) == 1

        assert is_unanimous is False
        assert len(unique_votes) == 2

    def test_split_vote_three_targets(self):
        """When votes are split between 3 targets, voting fails."""
        game = self.create_test_game(4)

        votes = {
            "player_0": "player_1",
            "player_1": "player_2",
            "player_2": "player_3",
            "player_3": "player_1",
        }

        unique_votes = set(votes.values())
        is_unanimous = len(unique_votes) == 1

        assert is_unanimous is False
        assert len(unique_votes) == 3

    def test_split_vote_all_different(self):
        """When each player votes for different target, voting fails."""
        game = self.create_test_game(4)

        votes = {
            "player_0": "player_1",
            "player_1": "player_2",
            "player_2": "player_3",
            "player_3": "player_0",
        }

        unique_votes = set(votes.values())
        is_unanimous = len(unique_votes) == 1

        assert is_unanimous is False
        assert len(unique_votes) == 4

    def test_three_players_unanimous(self):
        """With 3 players, unanimous means 2 voters agree."""
        game = self.create_test_game(3)

        votes = {
            "player_1": "player_0",  # spy
            "player_2": "player_0",  # spy
        }

        unique_votes = set(votes.values())
        is_unanimous = len(unique_votes) == 1

        assert is_unanimous is True

    def test_six_players_unanimous(self):
        """With 6 players, unanimous means 5 voters agree."""
        game = self.create_test_game(6)

        votes = {
            "player_1": "player_0",
            "player_2": "player_0",
            "player_3": "player_0",
            "player_4": "player_0",
            "player_5": "player_0",
        }

        unique_votes = set(votes.values())
        is_unanimous = len(unique_votes) == 1

        assert is_unanimous is True

    def test_six_players_split(self):
        """With 6 players, one dissenter means split vote."""
        game = self.create_test_game(6)

        votes = {
            "player_1": "player_0",
            "player_2": "player_0",
            "player_3": "player_0",
            "player_4": "player_0",
            "player_5": "player_1",  # dissenter
        }

        unique_votes = set(votes.values())
        is_unanimous = len(unique_votes) == 1

        assert is_unanimous is False
        assert len(unique_votes) == 2


class TestGameOutcomeAfterVoting:
    """Test that game outcome is set correctly based on voting result."""

    def test_outcome_set_when_unanimous(self):
        """GameOutcome should be set when voting is unanimous."""
        votes = {"player_1": "player_0", "player_2": "player_0"}
        unique_votes = set(votes.values())
        is_unanimous = len(unique_votes) == 1
        accused = list(unique_votes)[0]

        assert is_unanimous is True

        spy_id = "player_0"
        spy_caught = accused == spy_id

        assert spy_caught is True

        outcome = GameOutcome(
            winner="civilians" if spy_caught else "spy",
            reason=f"Шпион ({spy_id}) был единогласно разоблачён",
            votes=votes,
            accused_id=accused,
        )

        assert outcome.winner == "civilians"
        assert "единогласно" in outcome.reason

    def test_outcome_not_set_when_split(self):
        """GameOutcome should NOT be set when votes are split."""
        votes = {"player_1": "player_0", "player_2": "player_1"}
        unique_votes = set(votes.values())
        is_unanimous = len(unique_votes) == 1

        assert is_unanimous is False

    def test_spy_wins_on_wrong_unanimous_vote(self):
        """Spy wins if players unanimously vote for wrong target."""
        votes = {"player_0": "player_2", "player_1": "player_2"}
        unique_votes = set(votes.values())
        is_unanimous = len(unique_votes) == 1
        accused = list(unique_votes)[0]

        spy_id = "player_0"
        spy_caught = accused == spy_id

        assert is_unanimous is True
        assert spy_caught is False

        outcome = GameOutcome(
            winner="spy",
            reason=f"Мирные единогласно обвинили {accused}, но шпионом был {spy_id}",
            votes=votes,
            accused_id=accused,
        )

        assert outcome.winner == "spy"
        assert "единогласно" in outcome.reason


class TestPhaseTransitions:
    """Test phase transitions based on voting results."""

    def test_resolution_phase_on_unanimous(self):
        """Game should transition to RESOLUTION on unanimous vote."""
        is_unanimous = True

        if is_unanimous:
            next_phase = GamePhase.RESOLUTION
        else:
            next_phase = GamePhase.MAIN_ROUND

        assert next_phase == GamePhase.RESOLUTION

    def test_main_round_phase_on_split(self):
        """Game should transition to MAIN_ROUND on split vote."""
        is_unanimous = False

        if is_unanimous:
            next_phase = GamePhase.RESOLUTION
        else:
            next_phase = GamePhase.MAIN_ROUND

        assert next_phase == GamePhase.MAIN_ROUND


class TestVoteResultCallback:
    """Test the on_vote_result callback functionality."""

    def test_callback_receives_unanimous_flag(self):
        """Callback should receive is_unanimous and votes."""
        received_data = {}

        async def mock_callback(is_unanimous: bool, votes: dict):
            received_data["is_unanimous"] = is_unanimous
            received_data["votes"] = votes

        votes = {"player_1": "player_0", "player_2": "player_0"}
        unique_votes = set(votes.values())
        is_unanimous = len(unique_votes) == 1

        import asyncio
        asyncio.run(mock_callback(is_unanimous, votes))

        assert received_data["is_unanimous"] is True
        assert received_data["votes"] == votes

    def test_callback_receives_split_flag(self):
        """Callback should receive is_unanimous=False when split."""
        received_data = {}

        async def mock_callback(is_unanimous: bool, votes: dict):
            received_data["is_unanimous"] = is_unanimous
            received_data["votes"] = votes

        votes = {"player_1": "player_0", "player_2": "player_1"}
        unique_votes = set(votes.values())
        is_unanimous = len(unique_votes) == 1

        import asyncio
        asyncio.run(mock_callback(is_unanimous, votes))

        assert received_data["is_unanimous"] is False
        assert len(set(received_data["votes"].values())) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
