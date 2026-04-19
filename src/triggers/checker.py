"""Trigger detection and checking system for SpyfallAI."""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.models.character import Character, ConditionType, ReactionType, Trigger
from src.models.game import Game, Turn, TurnType, TriggerEvent


@dataclass
class TriggerResult:
    """Result of a trigger check."""

    triggered: bool
    character_id: str
    condition_type: ConditionType
    reaction_type: ReactionType
    priority: int
    threshold: float
    target_character_id: Optional[str] = None


@dataclass
class GlobalTrigger:
    """Global trigger rule loaded from trigger_rules.json."""

    id: str
    condition_type: ConditionType
    description: str
    priority: int
    threshold: float
    default_reaction_type: ReactionType
    params: dict = field(default_factory=dict)
    detection: dict = field(default_factory=dict)


def load_global_triggers(config_path: Optional[Path] = None) -> list[GlobalTrigger]:
    """Load global trigger rules from trigger_rules.json."""
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "trigger_rules.json"

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    triggers = []
    for t in data.get("global_triggers", []):
        triggers.append(
            GlobalTrigger(
                id=t["id"],
                condition_type=ConditionType(t["condition_type"]),
                description=t["description"],
                priority=t["priority"],
                threshold=t["threshold"],
                default_reaction_type=ReactionType(t["default_reaction_type"]),
                params=t.get("params", {}),
                detection=t.get("detection", {}),
            )
        )
    return triggers


class TriggerChecker:
    """Checks triggers after each turn in the game."""

    def __init__(
        self,
        characters: list[Character],
        global_triggers: Optional[list[GlobalTrigger]] = None,
    ):
        self.characters = {c.id: c for c in characters}
        self.global_triggers = global_triggers or load_global_triggers()
        self._silence_counters: dict[str, int] = {c.id: 0 for c in characters}
        self._accusation_counts: dict[str, dict[str, int]] = {}

        self._accusation_patterns = self._compile_accusation_patterns()

    def _compile_accusation_patterns(self) -> list[re.Pattern]:
        """Compile regex patterns for accusation detection."""
        patterns = []
        for gt in self.global_triggers:
            if gt.condition_type == ConditionType.DIRECT_ACCUSATION:
                detection = gt.detection
                if detection.get("method") == "markers":
                    for pattern in detection.get("accusation_patterns", []):
                        patterns.append(re.compile(pattern, re.IGNORECASE))
        return patterns

    def check_direct_accusation(
        self,
        turn: Turn,
        accused_character_id: str,
    ) -> bool:
        """
        Check if a turn contains a direct accusation of a character.

        Detection logic:
        1. The accused character's name must be mentioned in the content
        2. At least one accusation marker must be present
        """
        accused = self.characters.get(accused_character_id)
        if not accused:
            return False

        content_lower = turn.content.lower()
        name_lower = accused.display_name.lower()
        if name_lower not in content_lower:
            return False

        for pattern in self._accusation_patterns:
            if pattern.search(content_lower):
                return True

        return False

    def check_silent_for_n_turns(
        self,
        character_id: str,
        n_turns: int = 3,
    ) -> bool:
        """
        Check if a character has been silent for N turns.

        Uses internal counter that tracks turns since each character spoke.
        """
        return self._silence_counters.get(character_id, 0) >= n_turns

    def update_silence_counters(self, turn: Turn) -> None:
        """
        Update silence counters after a turn.

        - Reset counter for speaker
        - Increment counters for everyone else
        """
        for char_id in self._silence_counters:
            if char_id == turn.speaker_id:
                self._silence_counters[char_id] = 0
            else:
                self._silence_counters[char_id] += 1

    def get_silence_count(self, character_id: str) -> int:
        """Get the current silence counter for a character."""
        return self._silence_counters.get(character_id, 0)

    def reset_silence_counter(self, character_id: str) -> None:
        """Reset the silence counter for a character."""
        if character_id in self._silence_counters:
            self._silence_counters[character_id] = 0

    def check_triggers_for_character(
        self,
        character_id: str,
        turn: Turn,
        game: Game,
    ) -> list[TriggerResult]:
        """
        Check all triggers (global + personal) for a character after a turn.

        Returns list of triggered results, sorted by priority (highest first).
        """
        results = []
        character = self.characters.get(character_id)
        if not character:
            return results

        for gt in self.global_triggers:
            result = self._check_global_trigger(gt, character_id, turn, game)
            if result and result.triggered:
                results.append(result)

        for pt in character.personal_triggers:
            result = self._check_personal_trigger(pt, character_id, turn, game)
            if result and result.triggered:
                results.append(result)

        results.sort(key=lambda r: r.priority, reverse=True)
        return results

    def _check_global_trigger(
        self,
        trigger: GlobalTrigger,
        character_id: str,
        turn: Turn,
        game: Game,
    ) -> Optional[TriggerResult]:
        """Check a single global trigger for a character."""
        triggered = False

        if trigger.condition_type == ConditionType.DIRECT_ACCUSATION:
            if turn.speaker_id != character_id:
                triggered = self.check_direct_accusation(turn, character_id)

        elif trigger.condition_type == ConditionType.SILENT_FOR_N_TURNS:
            n_turns = trigger.params.get("silent_turns", 3)
            triggered = self.check_silent_for_n_turns(character_id, n_turns)

        if triggered:
            character = self.characters.get(character_id)
            reaction = trigger.default_reaction_type
            if character:
                for pt in character.personal_triggers:
                    if pt.condition_type == trigger.condition_type:
                        reaction = pt.reaction_type
                        break

            return TriggerResult(
                triggered=True,
                character_id=character_id,
                condition_type=trigger.condition_type,
                reaction_type=reaction,
                priority=trigger.priority,
                threshold=trigger.threshold,
                target_character_id=turn.speaker_id if triggered else None,
            )

        return None

    def _check_personal_trigger(
        self,
        trigger: Trigger,
        character_id: str,
        turn: Turn,
        game: Game,
    ) -> Optional[TriggerResult]:
        """Check a personal trigger for a character."""
        triggered = False

        if trigger.condition_type == ConditionType.DIRECT_ACCUSATION:
            if turn.speaker_id != character_id:
                triggered = self.check_direct_accusation(turn, character_id)

        elif trigger.condition_type == ConditionType.SILENT_FOR_N_TURNS:
            n_turns = trigger.params.get("silent_turns", 3) if trigger.params else 3
            triggered = self.check_silent_for_n_turns(character_id, n_turns)

        if triggered:
            return TriggerResult(
                triggered=True,
                character_id=character_id,
                condition_type=trigger.condition_type,
                reaction_type=trigger.reaction_type,
                priority=trigger.priority,
                threshold=trigger.threshold,
                target_character_id=turn.speaker_id,
            )

        return None

    def check_all_characters(
        self,
        turn: Turn,
        game: Game,
    ) -> list[TriggerResult]:
        """
        Check triggers for all characters after a turn.

        Returns all triggered results, sorted by priority (highest first).
        Use this after each answer to determine if anyone wants to intervene.
        """
        all_results = []

        for character_id in self.characters:
            if character_id == turn.speaker_id:
                continue
            results = self.check_triggers_for_character(character_id, turn, game)
            all_results.extend(results)

        all_results.sort(key=lambda r: r.priority, reverse=True)
        return all_results

    def select_winner(self, results: list[TriggerResult]) -> Optional[TriggerResult]:
        """
        Select the winning trigger when multiple triggers fire.

        Rules:
        1. Highest priority wins
        2. If tie, random selection (for now, just take first)
        """
        if not results:
            return None

        results.sort(key=lambda r: r.priority, reverse=True)
        highest_priority = results[0].priority
        top_results = [r for r in results if r.priority == highest_priority]

        return top_results[0]

    def create_trigger_event(
        self,
        result: TriggerResult,
        turn_number: int,
        intervened: bool,
    ) -> TriggerEvent:
        """Create a TriggerEvent from a TriggerResult for logging."""
        return TriggerEvent(
            turn_number=turn_number,
            timestamp=datetime.now(),
            character_id=result.character_id,
            condition_type=result.condition_type.value,
            reaction_type=result.reaction_type.value,
            intervened=intervened,
        )
