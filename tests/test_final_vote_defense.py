"""Tests for final vote with defense phase integration (TASK-061)."""

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


from src.orchestrator.game_engine import run_final_vote
from src.agents import build_final_vote_with_defense_prompt, SecretInfo
from src.models import (
    Game,
    GameConfig,
    GamePhase,
    Player,
    Turn,
    TurnType,
    DefenseSpeech,
    VoteChange,
    TokenUsage,
    PhaseEntry,
    Location,
    Role,
)
from src.llm import LLMResponse


def create_test_game(players_data: list[dict]) -> Game:
    """Create a test game with given players."""
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
            duration_minutes=5,
            players_count=len(players_data),
            max_questions=10,
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


def create_test_character(char_id: str):
    """Create a minimal mock character."""
    char = MagicMock()
    char.id = char_id
    char.display_name = char_id.capitalize()
    char.archetype = "test"
    char.backstory = "Test character backstory."
    char.voice_style = "Test voice style."
    char.must_directives = ["Test directive 1"]
    char.must_not_directives = ["Test prohibition 1"]
    char.intervention_priority = 5
    char.intervention_threshold = 0.5
    return char


def create_test_location():
    """Create a test location with roles."""
    return Location(
        id="hospital",
        display_name="Больница",
        description="Медицинское учреждение",
        roles=[
            Role(id="surgeon", display_name="Хирург", description="Выполняет операции"),
            Role(id="nurse", display_name="Медсестра", description="Ухаживает за пациентами"),
            Role(id="patient", display_name="Пациент", description="Получает лечение"),
        ],
    )


class TestDefenseSkippedCopyVotes:
    """Test that when defense is skipped, preliminary votes are copied."""

    def test_copies_preliminary_votes_when_defense_skipped(self):
        """Final votes should match preliminary when defense was skipped."""
        game = create_test_game([
            {"id": "alice", "role_id": "surgeon", "is_spy": False},
            {"id": "bob", "role_id": "nurse", "is_spy": True},
            {"id": "carol", "role_id": "patient", "is_spy": False},
        ])
        game.preliminary_vote_result = {
            "alice": "bob",
            "bob": "carol",
            "carol": "bob",
        }

        characters = [create_test_character(p.character_id) for p in game.players]

        result = run_async(run_final_vote(
            game=game,
            characters=characters,
            provider=None,  # Should not be called
            defense_was_executed=False,
        ))

        assert result.final_vote_result == {
            "alice": "bob",
            "bob": "carol",
            "carol": "bob",
        }
        assert result.vote_changes == []

    def test_no_llm_calls_when_defense_skipped(self):
        """No LLM calls should be made when defense is skipped."""
        game = create_test_game([
            {"id": "alice", "role_id": "surgeon", "is_spy": False},
            {"id": "bob", "role_id": "nurse", "is_spy": True},
            {"id": "carol", "role_id": "patient", "is_spy": False},
        ])
        game.preliminary_vote_result = {"alice": "bob", "bob": "carol", "carol": "bob"}

        characters = [create_test_character(p.character_id) for p in game.players]
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock()

        result = run_async(run_final_vote(
            game=game,
            characters=characters,
            provider=mock_provider,
            defense_was_executed=False,
        ))

        mock_provider.complete.assert_not_called()

    def test_phase_transition_status_when_defense_skipped(self):
        """Phase transition should have 'skipped_copied_from_preliminary' status."""
        game = create_test_game([
            {"id": "alice", "role_id": "surgeon", "is_spy": False},
            {"id": "bob", "role_id": "nurse", "is_spy": True},
            {"id": "carol", "role_id": "patient", "is_spy": False},
        ])
        game.preliminary_vote_result = {"alice": "bob", "bob": "alice", "carol": "bob"}

        characters = [create_test_character(p.character_id) for p in game.players]

        result = run_async(run_final_vote(
            game=game,
            characters=characters,
            provider=None,
            defense_was_executed=False,
        ))

        final_vote_transition = None
        for pt in result.phase_transitions:
            if pt.to_phase == GamePhase.FINAL_VOTE:
                final_vote_transition = pt
                break

        assert final_vote_transition is not None
        assert final_vote_transition.status == "skipped_copied_from_preliminary"

    def test_turns_recorded_when_defense_skipped(self):
        """Vote turns should be recorded even when defense is skipped."""
        game = create_test_game([
            {"id": "alice", "role_id": "surgeon", "is_spy": False},
            {"id": "bob", "role_id": "nurse", "is_spy": True},
            {"id": "carol", "role_id": "patient", "is_spy": False},
        ])
        game.preliminary_vote_result = {"alice": "bob", "bob": "carol", "carol": "bob"}

        characters = [create_test_character(p.character_id) for p in game.players]

        result = run_async(run_final_vote(
            game=game,
            characters=characters,
            provider=None,
            defense_was_executed=False,
        ))

        final_vote_turns = [t for t in result.turns if t.type == TurnType.FINAL_VOTE]
        assert len(final_vote_turns) == 3
        for turn in final_vote_turns:
            assert "подтверждаю" in turn.content.lower()


class TestDefenseExecutedVoteChanges:
    """Test vote changes when defense was executed."""

    def test_allows_vote_changes_after_defense(self):
        """Voters should be able to change their votes after hearing defense."""
        game = create_test_game([
            {"id": "alice", "role_id": "surgeon", "is_spy": False},
            {"id": "bob", "role_id": "nurse", "is_spy": True},
            {"id": "carol", "role_id": "patient", "is_spy": False},
        ])
        game.preliminary_vote_result = {
            "alice": "bob",
            "bob": "carol",
            "carol": "bob",
        }
        game.defense_speeches = [
            DefenseSpeech(
                defender_id="bob",
                votes_received=2,
                content="I am not the spy!",
                timestamp=datetime.now(),
            )
        ]

        characters = [create_test_character(p.character_id) for p in game.players]

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(side_effect=[
            LLMResponse(content="bob", input_tokens=10, output_tokens=5, model="test"),  # alice confirms
            LLMResponse(content="alice", input_tokens=10, output_tokens=5, model="test"),  # bob changes
            LLMResponse(content="alice", input_tokens=10, output_tokens=5, model="test"),  # carol changes
        ])

        result = run_async(run_final_vote(
            game=game,
            characters=characters,
            provider=mock_provider,
            defense_was_executed=True,
        ))

        assert result.final_vote_result["alice"] == "bob"  # unchanged
        assert result.final_vote_result["bob"] == "alice"  # changed from carol
        assert result.final_vote_result["carol"] == "alice"  # changed from bob to alice

    def test_tracks_vote_changes(self):
        """Changed votes should be tracked in vote_changes."""
        game = create_test_game([
            {"id": "alice", "role_id": "surgeon", "is_spy": False},
            {"id": "bob", "role_id": "nurse", "is_spy": True},
            {"id": "carol", "role_id": "patient", "is_spy": False},
        ])
        game.preliminary_vote_result = {
            "alice": "bob",
            "bob": "carol",
            "carol": "bob",
        }
        game.defense_speeches = []

        characters = [create_test_character(p.character_id) for p in game.players]

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(side_effect=[
            LLMResponse(content="carol", input_tokens=10, output_tokens=5, model="test"),  # alice changes
            LLMResponse(content="carol", input_tokens=10, output_tokens=5, model="test"),  # bob confirms
            LLMResponse(content="alice", input_tokens=10, output_tokens=5, model="test"),  # carol changes
        ])

        result = run_async(run_final_vote(
            game=game,
            characters=characters,
            provider=mock_provider,
            defense_was_executed=True,
        ))

        assert len(result.vote_changes) == 2

        alice_change = next((vc for vc in result.vote_changes if vc.voter_id == "alice"), None)
        assert alice_change is not None
        assert alice_change.from_target == "bob"
        assert alice_change.to_target == "carol"

        carol_change = next((vc for vc in result.vote_changes if vc.voter_id == "carol"), None)
        assert carol_change is not None
        assert carol_change.from_target == "bob"
        assert carol_change.to_target == "alice"

    def test_abstainer_can_vote_in_final(self):
        """Voters who abstained in preliminary can vote in final."""
        game = create_test_game([
            {"id": "alice", "role_id": "surgeon", "is_spy": False},
            {"id": "bob", "role_id": "nurse", "is_spy": True},
            {"id": "carol", "role_id": "patient", "is_spy": False},
        ])
        game.preliminary_vote_result = {
            "alice": None,  # abstained
            "bob": "carol",
            "carol": "bob",
        }
        game.defense_speeches = [
            DefenseSpeech(
                defender_id="bob",
                votes_received=1,
                content="Defense speech",
                timestamp=datetime.now(),
            )
        ]

        characters = [create_test_character(p.character_id) for p in game.players]

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(side_effect=[
            LLMResponse(content="bob", input_tokens=10, output_tokens=5, model="test"),  # alice now votes
            LLMResponse(content="carol", input_tokens=10, output_tokens=5, model="test"),
            LLMResponse(content="bob", input_tokens=10, output_tokens=5, model="test"),
        ])

        result = run_async(run_final_vote(
            game=game,
            characters=characters,
            provider=mock_provider,
            defense_was_executed=True,
        ))

        assert result.final_vote_result["alice"] == "bob"

        alice_change = next((vc for vc in result.vote_changes if vc.voter_id == "alice"), None)
        assert alice_change is not None
        assert alice_change.from_target is None
        assert alice_change.to_target == "bob"


class TestStrictMajorityWinner:
    """Test strict majority winner determination."""

    def test_strict_majority_catches_spy(self):
        """If spy gets strict majority votes, civilians win."""
        game = create_test_game([
            {"id": "alice", "role_id": "surgeon", "is_spy": False},
            {"id": "bob", "role_id": "nurse", "is_spy": True},
            {"id": "carol", "role_id": "patient", "is_spy": False},
        ])
        game.preliminary_vote_result = {
            "alice": "bob",
            "bob": "carol",
            "carol": "bob",
        }

        characters = [create_test_character(p.character_id) for p in game.players]

        result = run_async(run_final_vote(
            game=game,
            characters=characters,
            provider=None,
            defense_was_executed=False,
        ))

        assert result.outcome is not None
        assert result.outcome.winner == "civilians"
        assert "bob" in result.outcome.reason.lower() or "шпион" in result.outcome.reason.lower()

    def test_strict_majority_wrong_target_spy_wins(self):
        """If majority votes for non-spy, spy wins."""
        game = create_test_game([
            {"id": "alice", "role_id": "surgeon", "is_spy": True},
            {"id": "bob", "role_id": "nurse", "is_spy": False},
            {"id": "carol", "role_id": "patient", "is_spy": False},
        ])
        game.preliminary_vote_result = {
            "alice": "bob",
            "bob": "carol",
            "carol": "bob",  # majority for bob who is not spy
        }

        characters = [create_test_character(p.character_id) for p in game.players]

        result = run_async(run_final_vote(
            game=game,
            characters=characters,
            provider=None,
            defense_was_executed=False,
        ))

        assert result.outcome is not None
        assert result.outcome.winner == "spy"

    def test_no_majority_spy_wins(self):
        """If no strict majority, spy wins."""
        game = create_test_game([
            {"id": "alice", "role_id": "surgeon", "is_spy": False},
            {"id": "bob", "role_id": "nurse", "is_spy": True},
            {"id": "carol", "role_id": "patient", "is_spy": False},
            {"id": "dave", "role_id": "receptionist", "is_spy": False},
        ])
        game.preliminary_vote_result = {
            "alice": "bob",
            "bob": "carol",
            "carol": "dave",
            "dave": "alice",  # 1-1-1-1 split
        }

        characters = [create_test_character(p.character_id) for p in game.players]

        result = run_async(run_final_vote(
            game=game,
            characters=characters,
            provider=None,
            defense_was_executed=False,
        ))

        assert result.outcome is not None
        assert result.outcome.winner == "spy"
        assert "раздел" in result.outcome.reason.lower() or "большинств" in result.outcome.reason.lower()

    def test_all_abstain_spy_wins(self):
        """If all voters abstain, spy wins."""
        game = create_test_game([
            {"id": "alice", "role_id": "surgeon", "is_spy": False},
            {"id": "bob", "role_id": "nurse", "is_spy": True},
            {"id": "carol", "role_id": "patient", "is_spy": False},
        ])
        game.preliminary_vote_result = {
            "alice": None,
            "bob": None,
            "carol": None,
        }

        characters = [create_test_character(p.character_id) for p in game.players]

        result = run_async(run_final_vote(
            game=game,
            characters=characters,
            provider=None,
            defense_was_executed=False,
        ))

        assert result.outcome is not None
        assert result.outcome.winner == "spy"
        assert "воздерж" in result.outcome.reason.lower()


class TestFinalVotePromptContent:
    """Test that final vote prompt contains required information."""

    def test_prompt_contains_preliminary_vote(self):
        """Prompt should mention the voter's preliminary vote."""
        char = create_test_character("alice")
        game = create_test_game([
            {"id": "alice", "role_id": "surgeon", "is_spy": False},
            {"id": "bob", "role_id": "nurse", "is_spy": True},
            {"id": "carol", "role_id": "patient", "is_spy": False},
        ])

        location = create_test_location()
        role = location.roles[0]
        secret = SecretInfo(is_spy=False, location=location, role=role)
        defense_speeches = [
            DefenseSpeech(defender_id="bob", votes_received=2, content="I am innocent!", timestamp=datetime.now())
        ]

        prompt = build_final_vote_with_defense_prompt(
            character=char,
            game=game,
            secret_info=secret,
            preliminary_vote="bob",
            defense_speeches=defense_speeches,
            candidates=["bob", "carol"],
            allow_abstain=True,
        )

        assert "bob" in prompt.lower()
        assert "предварительн" in prompt.lower()

    def test_prompt_contains_defense_speeches(self):
        """Prompt should include all defense speeches."""
        char = create_test_character("alice")
        game = create_test_game([
            {"id": "alice", "role_id": "surgeon", "is_spy": False},
            {"id": "bob", "role_id": "nurse", "is_spy": True},
            {"id": "carol", "role_id": "patient", "is_spy": False},
        ])

        location = create_test_location()
        role = location.roles[0]
        secret = SecretInfo(is_spy=False, location=location, role=role)
        defense_speeches = [
            DefenseSpeech(defender_id="bob", votes_received=2, content="I am innocent!", timestamp=datetime.now()),
            DefenseSpeech(defender_id="carol", votes_received=2, content="Trust me!", timestamp=datetime.now()),
        ]

        prompt = build_final_vote_with_defense_prompt(
            character=char,
            game=game,
            secret_info=secret,
            preliminary_vote="bob",
            defense_speeches=defense_speeches,
            candidates=["bob", "carol"],
            allow_abstain=True,
        )

        assert "I am innocent!" in prompt
        assert "Trust me!" in prompt

    def test_prompt_contains_strict_majority_rule(self):
        """Prompt should explain strict majority rule."""
        char = create_test_character("alice")
        game = create_test_game([
            {"id": "alice", "role_id": "surgeon", "is_spy": False},
            {"id": "bob", "role_id": "nurse", "is_spy": True},
            {"id": "carol", "role_id": "patient", "is_spy": False},
        ])

        location = create_test_location()
        role = location.roles[0]
        secret = SecretInfo(is_spy=False, location=location, role=role)

        prompt = build_final_vote_with_defense_prompt(
            character=char,
            game=game,
            secret_info=secret,
            preliminary_vote="bob",
            defense_speeches=[],
            candidates=["bob", "carol"],
            allow_abstain=True,
        )

        assert "большинств" in prompt.lower()
        assert "шпион" in prompt.lower()

    def test_prompt_shows_abstain_option_when_allowed(self):
        """Prompt should show abstain option when allowed."""
        char = create_test_character("alice")
        game = create_test_game([
            {"id": "alice", "role_id": "surgeon", "is_spy": False},
            {"id": "bob", "role_id": "nurse", "is_spy": True},
            {"id": "carol", "role_id": "patient", "is_spy": False},
        ])

        location = create_test_location()
        role = location.roles[0]
        secret = SecretInfo(is_spy=False, location=location, role=role)

        prompt = build_final_vote_with_defense_prompt(
            character=char,
            game=game,
            secret_info=secret,
            preliminary_vote="bob",
            defense_speeches=[],
            candidates=["bob", "carol"],
            allow_abstain=True,
        )

        assert "воздерж" in prompt.lower()


class TestVoteResultCallback:
    """Test vote result callback functionality."""

    def test_callback_receives_vote_result(self):
        """on_vote_result callback should receive majority status and votes."""
        game = create_test_game([
            {"id": "alice", "role_id": "surgeon", "is_spy": False},
            {"id": "bob", "role_id": "nurse", "is_spy": True},
            {"id": "carol", "role_id": "patient", "is_spy": False},
        ])
        game.preliminary_vote_result = {"alice": "bob", "bob": "carol", "carol": "bob"}

        characters = [create_test_character(p.character_id) for p in game.players]

        callback_results = []

        async def callback(has_majority, votes):
            callback_results.append((has_majority, votes))

        result = run_async(run_final_vote(
            game=game,
            characters=characters,
            provider=None,
            defense_was_executed=False,
            on_vote_result=callback,
        ))

        assert len(callback_results) == 1
        has_majority, votes = callback_results[0]
        assert has_majority is True
        assert votes["alice"] == "bob"


class TestTurnContent:
    """Test turn content formatting."""

    def test_turn_shows_confirmed_when_unchanged(self):
        """Turn content should show 'confirmed' for unchanged votes."""
        game = create_test_game([
            {"id": "alice", "role_id": "surgeon", "is_spy": False},
            {"id": "bob", "role_id": "nurse", "is_spy": True},
            {"id": "carol", "role_id": "patient", "is_spy": False},
        ])
        game.preliminary_vote_result = {"alice": "bob", "bob": "carol", "carol": "bob"}
        game.defense_speeches = []

        characters = [create_test_character(p.character_id) for p in game.players]

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(side_effect=[
            LLMResponse(content="bob", input_tokens=10, output_tokens=5, model="test"),
            LLMResponse(content="carol", input_tokens=10, output_tokens=5, model="test"),
            LLMResponse(content="bob", input_tokens=10, output_tokens=5, model="test"),
        ])

        result = run_async(run_final_vote(
            game=game,
            characters=characters,
            provider=mock_provider,
            defense_was_executed=True,
        ))

        alice_turn = next((t for t in result.turns if t.type == TurnType.FINAL_VOTE and t.speaker_id == "alice"), None)
        assert alice_turn is not None
        assert "подтверждаю" in alice_turn.content.lower()

    def test_turn_shows_change_when_vote_changed(self):
        """Turn content should indicate when vote was changed."""
        game = create_test_game([
            {"id": "alice", "role_id": "surgeon", "is_spy": False},
            {"id": "bob", "role_id": "nurse", "is_spy": True},
            {"id": "carol", "role_id": "patient", "is_spy": False},
        ])
        game.preliminary_vote_result = {"alice": "bob", "bob": "carol", "carol": "bob"}
        game.defense_speeches = []

        characters = [create_test_character(p.character_id) for p in game.players]

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(side_effect=[
            LLMResponse(content="carol", input_tokens=10, output_tokens=5, model="test"),  # alice changes
            LLMResponse(content="carol", input_tokens=10, output_tokens=5, model="test"),
            LLMResponse(content="bob", input_tokens=10, output_tokens=5, model="test"),
        ])

        result = run_async(run_final_vote(
            game=game,
            characters=characters,
            provider=mock_provider,
            defense_was_executed=True,
        ))

        alice_turn = next((t for t in result.turns if t.type == TurnType.FINAL_VOTE and t.speaker_id == "alice"), None)
        assert alice_turn is not None
        assert "меняю" in alice_turn.content.lower()
