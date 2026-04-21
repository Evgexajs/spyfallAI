"""Tests for TASK-070: Trigger reaction_type selection from personal triggers."""

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from src.models.character import Character, ConditionType, ReactionType
from src.models.game import Game, GameConfig, Player, Turn, TurnType
from src.triggers.checker import TriggerChecker, load_global_triggers


def load_character(character_id: str) -> Character:
    """Load a character from JSON file."""
    path = Path(__file__).parent.parent / "characters" / f"{character_id}.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Character(**data)


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
def sample_turn():
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


@pytest.fixture
def accusation_turn_against_kim():
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
def accusation_turn_against_boris():
    """A turn with direct accusation against Boris (who has NO direct_accusation trigger)."""
    return Turn(
        turn_number=5,
        timestamp=datetime.now(),
        speaker_id="kim",
        addressee_id="boris_molot",
        type=TurnType.QUESTION,
        content="Борис, ты шпион! Я не верю тебе!",
        display_delay_ms=1000,
    )


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


class TestSilentForNTurnsReactionTypes:
    """Test that silent_for_n_turns triggers use personal reaction_types."""

    def test_boris_silent_trigger_uses_pressure_reaction(
        self, boris, kim, sample_turn, sample_game
    ):
        """Boris should use pressure_with_sharper_question when silent too long."""
        checker = TriggerChecker(characters=[boris, kim])

        # Simulate Boris being silent for 3 turns (his threshold is 2)
        checker._silence_counters["boris_molot"] = 3

        results = checker.check_triggers_for_character(
            "boris_molot", sample_turn, sample_game
        )

        # Find the silent_for_n_turns result
        silent_results = [
            r for r in results
            if r.condition_type == ConditionType.SILENT_FOR_N_TURNS
        ]

        assert len(silent_results) == 1
        result = silent_results[0]

        assert result.reaction_type == ReactionType.PRESSURE_WITH_SHARPER_QUESTION
        assert result.priority == 9  # Boris's personal trigger priority
        assert result.threshold == 0.3  # Boris's personal trigger threshold

    def test_kim_silent_trigger_uses_panic_reaction(
        self, boris, kim, sample_turn, sample_game
    ):
        """Kim should use panic_and_derail when silent too long."""
        checker = TriggerChecker(characters=[boris, kim])

        # Simulate Kim being silent for 3 turns (his threshold is 2)
        checker._silence_counters["kim"] = 3

        results = checker.check_triggers_for_character("kim", sample_turn, sample_game)

        # Find the silent_for_n_turns result
        silent_results = [
            r for r in results
            if r.condition_type == ConditionType.SILENT_FOR_N_TURNS
        ]

        assert len(silent_results) == 1
        result = silent_results[0]

        assert result.reaction_type == ReactionType.PANIC_AND_DERAIL
        assert result.priority == 4  # Kim's personal trigger priority
        assert result.threshold == 0.4  # Kim's personal trigger threshold

    def test_different_characters_different_reactions_same_condition(
        self, boris, kim, sample_turn, sample_game
    ):
        """Different characters should have different reaction_types for same condition."""
        checker = TriggerChecker(characters=[boris, kim])

        # Both silent for long enough
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

        # Same condition type, different reaction types
        assert boris_silent.condition_type == kim_silent.condition_type
        assert boris_silent.reaction_type != kim_silent.reaction_type
        assert boris_silent.reaction_type == ReactionType.PRESSURE_WITH_SHARPER_QUESTION
        assert kim_silent.reaction_type == ReactionType.PANIC_AND_DERAIL


class TestGlobalTriggerPersonalTriggerRequirement:
    """Test that global triggers only fire when character has matching personal trigger."""

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

        # Should use Kim's personal trigger values
        assert result.reaction_type == ReactionType.PANIC_AND_DERAIL
        assert result.priority == 7  # Kim's personal trigger priority
        assert result.threshold == 0.3  # Kim's personal trigger threshold

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

        # Should be empty - Boris doesn't have direct_accusation personal trigger
        assert len(accusation_results) == 0

    def test_margo_accusation_uses_deflect_reaction(
        self, margo, boris, sample_game
    ):
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
        assert result.priority == 8  # Margo's personal trigger priority


class TestNoDuplicateTriggers:
    """Test that we don't get duplicate triggers for the same condition."""

    def test_no_duplicate_silent_triggers(self, boris, kim, sample_turn, sample_game):
        """Should only get one trigger result per condition_type."""
        checker = TriggerChecker(characters=[boris, kim])
        checker._silence_counters["boris_molot"] = 3

        results = checker.check_triggers_for_character(
            "boris_molot", sample_turn, sample_game
        )

        # Count results by condition_type
        condition_counts = {}
        for r in results:
            condition_counts[r.condition_type] = condition_counts.get(r.condition_type, 0) + 1

        # Each condition_type should appear at most once
        for ct, count in condition_counts.items():
            assert count == 1, f"Duplicate results for {ct}"


class TestRepeatedAccusationOnSameTarget:
    """Tests for TASK-072: repeated_accusation_on_same_target detector."""

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

    @pytest.fixture
    def accusation_turn_late(self):
        """Accusation turn against Kim at turn 12 (outside window)."""
        return Turn(
            turn_number=12,
            timestamp=datetime.now(),
            speaker_id="boris_molot",
            addressee_id="zoya",
            type=TurnType.ANSWER,
            content="Ким, ты шпион! Вернёмся к этому!",
            display_delay_ms=1000,
        )

    @pytest.fixture
    def accusation_turn_against_different_target(self):
        """Accusation turn against Boris (different target)."""
        return Turn(
            turn_number=2,
            timestamp=datetime.now(),
            speaker_id="zoya",
            addressee_id="kim",
            type=TurnType.ANSWER,
            content="Борис, ты шпион! Ты слишком агрессивен!",
            display_delay_ms=1000,
        )

    def test_two_accusations_in_row_triggers(
        self, margo, boris, kim, accusation_turn_1, accusation_turn_2, sample_game
    ):
        """TASK-072 Step 1: 2 accusations in a row should trigger."""
        checker = TriggerChecker(characters=[margo, boris, kim])

        # Track first accusation against Kim at turn 1
        accused_1 = checker.detect_accusation_target(accusation_turn_1)
        assert accused_1 == "kim"
        checker.track_accusation(accused_1, accusation_turn_1.turn_number)

        # Track second accusation against Kim at turn 2
        accused_2 = checker.detect_accusation_target(accusation_turn_2)
        assert accused_2 == "kim"
        checker.track_accusation(accused_2, accusation_turn_2.turn_number)

        # Check repeated accusation - should trigger (2 in window of 5)
        assert checker.check_repeated_accusation("kim", current_turn=2, window=5) is True

    def test_accusations_spread_over_10_turns_does_not_trigger(
        self, margo, boris, kim, accusation_turn_1, accusation_turn_late, sample_game
    ):
        """TASK-072 Step 2: Accusations spread over 10 turns should not trigger."""
        checker = TriggerChecker(characters=[margo, boris, kim])

        # Track first accusation against Kim at turn 1
        checker.track_accusation("kim", turn_number=1)

        # Track second accusation against Kim at turn 12 (11 turns later)
        checker.track_accusation("kim", turn_number=12)

        # Check repeated accusation at turn 12 with window of 5
        # Turn 1 is outside window (12 - 5 = 7, turn 1 < 7)
        assert checker.check_repeated_accusation("kim", current_turn=12, window=5) is False

    def test_accusations_on_different_targets_does_not_trigger(
        self, margo, boris, kim, accusation_turn_1, accusation_turn_against_different_target, sample_game
    ):
        """TASK-072 Step 3: Accusations on different targets should not trigger."""
        checker = TriggerChecker(characters=[margo, boris, kim])

        # Track accusation against Kim at turn 1
        accused_1 = checker.detect_accusation_target(accusation_turn_1)
        assert accused_1 == "kim"
        checker.track_accusation(accused_1, accusation_turn_1.turn_number)

        # Track accusation against Boris at turn 2
        accused_2 = checker.detect_accusation_target(accusation_turn_against_different_target)
        assert accused_2 == "boris_molot"
        checker.track_accusation(accused_2, accusation_turn_against_different_target.turn_number)

        # Neither target should trigger repeated accusation (only 1 each)
        assert checker.check_repeated_accusation("kim", current_turn=2, window=5) is False
        assert checker.check_repeated_accusation("boris_molot", current_turn=2, window=5) is False

    def test_trigger_event_includes_target_id_in_params(self, margo, boris, kim, sample_game):
        """TriggerEvent should include target_id in params for repeated_accusation."""
        checker = TriggerChecker(characters=[margo, boris, kim])

        # Pre-populate tracker with accusations against Kim
        checker.track_accusation("kim", turn_number=1)
        checker.track_accusation("kim", turn_number=2)

        # Create a turn with accusation against Kim
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

        # Check triggers for Margo (she has repeated_accusation_on_same_target personal trigger)
        results = checker.check_triggers_for_character("margo", turn, sample_game)

        repeated_results = [
            r for r in results
            if r.condition_type == ConditionType.REPEATED_ACCUSATION_ON_SAME_TARGET
        ]

        assert len(repeated_results) == 1
        result = repeated_results[0]

        # Verify target_character_id is set
        assert result.target_character_id == "kim"

        # Create TriggerEvent and verify params
        event = checker.create_trigger_event(result, turn_number=3, intervened=True)
        assert event.params is not None
        assert event.params.get("target_id") == "kim"

    def test_margo_repeated_accusation_uses_correct_reaction_type(
        self, margo, boris, kim, sample_game
    ):
        """Margo should use deflect_suspicion_to_another for repeated_accusation."""
        checker = TriggerChecker(characters=[margo, boris, kim])

        # Pre-populate tracker with accusations against Kim
        checker.track_accusation("kim", turn_number=1)
        checker.track_accusation("kim", turn_number=2)

        # Create a turn with accusation against Kim
        turn = Turn(
            turn_number=3,
            timestamp=datetime.now(),
            speaker_id="boris_molot",
            addressee_id="zoya",
            type=TurnType.ANSWER,
            content="Ким, ты шпион! Это очевидно!",
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

        # Margo's personal trigger values
        assert result.reaction_type == ReactionType.DEFLECT_SUSPICION_TO_ANOTHER
        assert result.priority == 6  # Margo's personal trigger priority
        assert result.threshold == 0.5  # Margo's personal trigger threshold
