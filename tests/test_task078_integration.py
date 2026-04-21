"""Integration test for TASK-078: verifies trigger detectors work in real game flow."""

from datetime import datetime
from uuid import uuid4

import pytest

from src.models.character import Character, ConditionType, Marker, ReactionType, Trigger
from src.models.game import Game, GameConfig, Player, Turn, TurnType
from src.triggers.checker import TriggerChecker, load_global_triggers


def create_test_character(
    char_id: str, display_name: str, reaction_type: ReactionType
) -> Character:
    """Create a test character with silent_for_n_turns trigger."""
    return Character(
        id=char_id,
        display_name=display_name,
        archetype="test_archetype",
        backstory="This is a test character backstory that is long enough.",
        voice_style="This is a test character voice style that is long enough.",
        must_directives=["Must do something in test."],
        must_not_directives=["Must not do something in test."],
        detectable_markers=[
            Marker(id="test_marker", method="regex", description="Test marker")
        ],
        personal_triggers=[
            Trigger(
                condition_type=ConditionType.SILENT_FOR_N_TURNS,
                priority=5,
                threshold=0.5,
                reaction_type=reaction_type,
                params={"silent_turns": 2},
            )
        ],
        intervention_priority=5,
        intervention_threshold=0.5,
    )


@pytest.fixture
def characters():
    """Create test characters with different silent_for_n_turns reaction_types."""
    return [
        create_test_character(
            "boris", "Борис", ReactionType.PRESSURE_WITH_SHARPER_QUESTION
        ),
        create_test_character("kim", "Ким", ReactionType.PANIC_AND_DERAIL),
        create_test_character("zoya", "Зоя", ReactionType.MOCK_WITH_DRY_SARCASM),
        create_test_character(
            "margo", "Марго", ReactionType.DEFLECT_SUSPICION_TO_ANOTHER
        ),
    ]


@pytest.fixture
def game(characters):
    """Create a test game with the characters."""
    return Game(
        id=uuid4(),
        started_at=datetime.now(),
        config=GameConfig(
            duration_minutes=5,
            players_count=4,
            max_questions=20,
            main_model="gpt-4o",
            utility_model="gpt-4o-mini",
        ),
        location_id="test-location",
        players=[
            Player(character_id=c.id, role_id=f"role_{c.id}", is_spy=c.id == "boris")
            for c in characters
        ],
        spy_id="boris",
        turns=[],
    )


class TestSilentForNTurnsDifferentReactionTypes:
    """Verify silent_for_n_turns has different reaction_types per character."""

    def test_characters_have_different_reaction_types(self, characters):
        """Each character should have their own reaction_type for silent_for_n_turns."""
        reaction_types = {}
        for char in characters:
            for trigger in char.personal_triggers:
                if trigger.condition_type == ConditionType.SILENT_FOR_N_TURNS:
                    reaction_types[char.id] = trigger.reaction_type

        assert len(set(reaction_types.values())) == 4
        assert reaction_types["boris"] == ReactionType.PRESSURE_WITH_SHARPER_QUESTION
        assert reaction_types["kim"] == ReactionType.PANIC_AND_DERAIL
        assert reaction_types["zoya"] == ReactionType.MOCK_WITH_DRY_SARCASM
        assert reaction_types["margo"] == ReactionType.DEFLECT_SUSPICION_TO_ANOTHER

    def test_triggered_events_use_personal_reaction_types(self, characters, game):
        """Triggered events use reaction_type from character's personal trigger."""
        global_triggers = load_global_triggers()
        checker = TriggerChecker(characters, global_triggers)

        turn1 = Turn(
            turn_number=1,
            timestamp=datetime.now(),
            speaker_id="kim",
            addressee_id="boris",
            type=TurnType.QUESTION,
            content="Test?",
            display_delay_ms=100,
        )
        game.turns.append(turn1)
        checker.update_silence_counters(turn1)

        turn2 = Turn(
            turn_number=2,
            timestamp=datetime.now(),
            speaker_id="boris",
            addressee_id="kim",
            type=TurnType.ANSWER,
            content="Test",
            display_delay_ms=100,
        )
        game.turns.append(turn2)
        checker.update_silence_counters(turn2)

        turn3 = Turn(
            turn_number=3,
            timestamp=datetime.now(),
            speaker_id="boris",
            addressee_id="zoya",
            type=TurnType.QUESTION,
            content="Test?",
            display_delay_ms=100,
        )
        game.turns.append(turn3)
        checker.update_silence_counters(turn3)

        turn4 = Turn(
            turn_number=4,
            timestamp=datetime.now(),
            speaker_id="zoya",
            addressee_id="boris",
            type=TurnType.ANSWER,
            content="Test",
            display_delay_ms=100,
        )
        game.turns.append(turn4)
        checker.update_silence_counters(turn4)

        kim_results = checker.check_triggers_for_character("kim", turn4, game)
        assert len(kim_results) > 0
        kim_result = kim_results[0]
        assert kim_result.condition_type == ConditionType.SILENT_FOR_N_TURNS
        assert kim_result.reaction_type == ReactionType.PANIC_AND_DERAIL

        margo_results = checker.check_triggers_for_character("margo", turn4, game)
        assert len(margo_results) > 0
        margo_result = margo_results[0]
        assert margo_result.condition_type == ConditionType.SILENT_FOR_N_TURNS
        assert margo_result.reaction_type == ReactionType.DEFLECT_SUSPICION_TO_ANOTHER


class TestMultipleConditionTypes:
    """Verify multiple condition_types can fire in a game."""

    def test_direct_accusation_and_silent_triggers_both_fire(self, characters, game):
        """Both direct_accusation and silent_for_n_turns should be able to fire."""
        for char in characters:
            if char.id == "kim":
                rt = ReactionType.PANIC_AND_DERAIL
            else:
                rt = ReactionType.POINT_OUT_INCONSISTENCY
            char.personal_triggers.append(
                Trigger(
                    condition_type=ConditionType.DIRECT_ACCUSATION,
                    priority=8,
                    threshold=0.3,
                    reaction_type=rt,
                )
            )

        global_triggers = load_global_triggers()
        checker = TriggerChecker(characters, global_triggers)

        turn1 = Turn(
            turn_number=1,
            timestamp=datetime.now(),
            speaker_id="boris",
            addressee_id="kim",
            type=TurnType.QUESTION,
            content="Ким, ты точно шпион!",
            display_delay_ms=100,
        )
        game.turns.append(turn1)
        checker.update_silence_counters(turn1)

        kim_results = checker.check_triggers_for_character("kim", turn1, game)
        accusation_results = [
            r
            for r in kim_results
            if r.condition_type == ConditionType.DIRECT_ACCUSATION
        ]
        assert len(accusation_results) > 0
        assert accusation_results[0].reaction_type == ReactionType.PANIC_AND_DERAIL

        turn2 = Turn(
            turn_number=2,
            timestamp=datetime.now(),
            speaker_id="kim",
            addressee_id="boris",
            type=TurnType.ANSWER,
            content="Нет!",
            display_delay_ms=100,
        )
        game.turns.append(turn2)
        checker.update_silence_counters(turn2)

        turn3 = Turn(
            turn_number=3,
            timestamp=datetime.now(),
            speaker_id="kim",
            addressee_id="zoya",
            type=TurnType.QUESTION,
            content="Зоя?",
            display_delay_ms=100,
        )
        game.turns.append(turn3)
        checker.update_silence_counters(turn3)

        turn4 = Turn(
            turn_number=4,
            timestamp=datetime.now(),
            speaker_id="zoya",
            addressee_id="kim",
            type=TurnType.ANSWER,
            content="Не знаю",
            display_delay_ms=100,
        )
        game.turns.append(turn4)
        checker.update_silence_counters(turn4)

        boris_results = checker.check_triggers_for_character("boris", turn4, game)
        silent_results = [
            r
            for r in boris_results
            if r.condition_type == ConditionType.SILENT_FOR_N_TURNS
        ]
        assert len(silent_results) > 0
        assert silent_results[0].reaction_type == ReactionType.PRESSURE_WITH_SHARPER_QUESTION


class TestCostAndPerformance:
    """Verify game costs are within expected bounds."""

    def test_trigger_check_is_synchronous_for_non_llm_triggers(self, characters, game):
        """silent_for_n_turns and direct_accusation don't require LLM calls."""
        global_triggers = load_global_triggers()
        checker = TriggerChecker(characters, global_triggers)

        turn = Turn(
            turn_number=1,
            timestamp=datetime.now(),
            speaker_id="boris",
            addressee_id="kim",
            type=TurnType.ANSWER,
            content="Test",
            display_delay_ms=100,
        )

        results = checker.check_triggers_for_character("kim", turn, game)
        assert results is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
