"""Trigger detection and checking system for SpyfallAI."""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from src.models.character import Character, ConditionType, ReactionType, Trigger
from src.models.game import Game, TriggerEvent, Turn

if TYPE_CHECKING:
    from src.llm.adapter import LLMProvider

logger = logging.getLogger(__name__)


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
    deprecated: bool = False


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
                deprecated=t.get("deprecated", False),
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
        self._accusation_tracker: dict[str, list[int]] = {}

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

    def track_accusation(self, target_id: str, turn_number: int) -> None:
        """Track an accusation against a target for repeated_accusation detection."""
        if target_id not in self._accusation_tracker:
            self._accusation_tracker[target_id] = []
        self._accusation_tracker[target_id].append(turn_number)

    def check_repeated_accusation(
        self,
        target_id: str,
        current_turn: int,
        window: int = 5,
    ) -> bool:
        """
        Check if a target was accused 2+ times in the last `window` turns.

        Args:
            target_id: The character who was accused
            current_turn: Current turn number
            window: Number of recent turns to consider (default 5)

        Returns:
            True if 2+ accusations in the window, False otherwise
        """
        if target_id not in self._accusation_tracker:
            return False

        accusations = self._accusation_tracker[target_id]
        recent = [t for t in accusations if t > current_turn - window]
        return len(recent) >= 2

    async def check_dodged_question(
        self,
        question_turn: Turn,
        answer_turn: Turn,
        provider: "LLMProvider",
        model: str,
    ) -> bool:
        """
        Check if a player dodged answering a direct question substantively.

        Uses LLM to analyze whether the answer addresses the question.

        Args:
            question_turn: The question Turn object
            answer_turn: The answer Turn object
            provider: LLMProvider instance for LLM calls
            model: Model name to use (typically utility model)

        Returns:
            True if the answer dodged the question, False otherwise.
            Returns False on LLM errors and logs warning.
        """
        prompt = f"""Вопрос: "{question_turn.content}"

Ответ: "{answer_turn.content}"

Ответил ли игрок по существу на заданный вопрос? Отвечай только "да" или "нет"."""

        try:
            response = await provider.complete(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                temperature=0.3,
                max_tokens=10,
            )

            answer = response.content.strip().lower()

            if answer not in ("да", "нет", "yes", "no"):
                logger.warning(
                    f"Invalid LLM response for dodged_question check: '{answer}'"
                )
                return False

            # "да"/"yes" means answered substantively -> not dodged -> return False
            # "нет"/"no" means did NOT answer substantively -> dodged -> return True
            return answer in ("нет", "no")

        except Exception as e:
            logger.warning(f"Error checking dodged question: {e}")
            return False

    def detect_accusation_target(self, turn: Turn) -> Optional[str]:
        """
        Detect which character (if any) is being accused in this turn.

        Returns the character_id of the accused, or None if no accusation detected.
        """
        has_accusation_marker = False
        for pattern in self._accusation_patterns:
            if pattern.search(turn.content.lower()):
                has_accusation_marker = True
                break

        if not has_accusation_marker:
            return None

        content_lower = turn.content.lower()
        for char_id, char in self.characters.items():
            if char_id == turn.speaker_id:
                continue
            if char.display_name.lower() in content_lower:
                return char_id

        return None

    def check_triggers_for_character(
        self,
        character_id: str,
        turn: Turn,
        game: Game,
    ) -> list[TriggerResult]:
        """
        Check all triggers (global + personal) for a character after a turn.

        Returns list of triggered results, sorted by priority (highest first).

        TASK-070: Global triggers use detection patterns but require personal triggers
        to fire. To avoid duplicates, we track which condition_types were handled
        by global triggers and skip personal trigger checks for those.
        """
        results = []
        character = self.characters.get(character_id)
        if not character:
            return results

        # Track condition_types handled by global triggers to avoid duplicates
        handled_conditions: set[ConditionType] = set()

        for gt in self.global_triggers:
            if gt.deprecated:
                continue
            result = self._check_global_trigger(gt, character_id, turn, game)
            if result and result.triggered:
                results.append(result)
                handled_conditions.add(gt.condition_type)

        # Check personal triggers, skip if already handled by global trigger
        for pt in character.personal_triggers:
            if pt.condition_type in handled_conditions:
                continue
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
        """Check a single global trigger for a character.

        TASK-070: Global triggers only fire if the character has a matching
        personal trigger for this condition_type. The reaction_type, priority,
        and threshold are taken from the personal trigger, not from global defaults.
        """
        character = self.characters.get(character_id)
        if not character:
            return None

        # Find matching personal trigger for this condition_type
        matching_personal = None
        for pt in character.personal_triggers:
            if pt.condition_type == trigger.condition_type:
                matching_personal = pt
                break

        # If no personal trigger exists, global trigger does NOT fire for this character
        if matching_personal is None:
            return None

        triggered = False

        target_for_result = turn.speaker_id

        if trigger.condition_type == ConditionType.DIRECT_ACCUSATION:
            if turn.speaker_id != character_id:
                triggered = self.check_direct_accusation(turn, character_id)

        elif trigger.condition_type == ConditionType.SILENT_FOR_N_TURNS:
            # Use personal trigger's params for silent_turns
            n_turns = (
                matching_personal.params.get("silent_turns", 3)
                if matching_personal.params
                else 3
            )
            triggered = self.check_silent_for_n_turns(character_id, n_turns)

        elif trigger.condition_type == ConditionType.REPEATED_ACCUSATION_ON_SAME_TARGET:
            # Get window from personal trigger params or default to 5
            window = (
                matching_personal.params.get("window", 5)
                if matching_personal.params
                else 5
            )
            # Detect who was accused in this turn
            accused_id = self.detect_accusation_target(turn)
            if accused_id:
                # Check if this is a repeated accusation
                triggered = self.check_repeated_accusation(
                    accused_id, turn.turn_number, window
                )
                if triggered:
                    target_for_result = accused_id

        if triggered:
            # Use personal trigger's reaction_type, priority, and threshold
            return TriggerResult(
                triggered=True,
                character_id=character_id,
                condition_type=trigger.condition_type,
                reaction_type=matching_personal.reaction_type,
                priority=matching_personal.priority,
                threshold=matching_personal.threshold,
                target_character_id=target_for_result,
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
        params = None
        if (
            result.condition_type == ConditionType.REPEATED_ACCUSATION_ON_SAME_TARGET
            and result.target_character_id
        ):
            params = {"target_id": result.target_character_id}

        return TriggerEvent(
            turn_number=turn_number,
            timestamp=datetime.now(),
            character_id=result.character_id,
            condition_type=result.condition_type.value,
            reaction_type=result.reaction_type.value,
            intervened=intervened,
            params=params,
        )
