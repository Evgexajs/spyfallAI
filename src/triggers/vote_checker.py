"""Early voting trigger checker for SpyfallAI."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.models.character import Character
from src.models.game import Game, Turn, TurnType


@dataclass
class VoteTriggerRule:
    """Rule for triggering early voting."""

    id: str
    condition_type: str
    description: str
    priority: int
    params: dict = field(default_factory=dict)


@dataclass
class VoteTriggerResult:
    """Result of a vote trigger check."""

    triggered: bool
    rule_id: str
    condition_type: str
    priority: int
    reason: str
    target_player_id: Optional[str] = None


def load_vote_trigger_rules(config_path: Optional[Path] = None) -> tuple[list[VoteTriggerRule], list[re.Pattern]]:
    """Load vote trigger rules from vote_trigger_rules.json.

    Returns:
        Tuple of (list of rules, list of compiled accusation patterns).
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "vote_trigger_rules.json"

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    rules = []
    for r in data.get("vote_triggers", []):
        rules.append(
            VoteTriggerRule(
                id=r["id"],
                condition_type=r["condition_type"],
                description=r["description"],
                priority=r["priority"],
                params=r.get("params", {}),
            )
        )

    patterns = []
    for pattern in data.get("accusation_patterns", []):
        patterns.append(re.compile(pattern, re.IGNORECASE))

    return rules, patterns


class VoteTriggerChecker:
    """Checks conditions for triggering early voting."""

    def __init__(
        self,
        characters: list[Character],
        rules: Optional[list[VoteTriggerRule]] = None,
        accusation_patterns: Optional[list[re.Pattern]] = None,
    ):
        self.characters = {c.id: c for c in characters}

        if rules is None or accusation_patterns is None:
            loaded_rules, loaded_patterns = load_vote_trigger_rules()
            self.rules = rules or loaded_rules
            self.accusation_patterns = accusation_patterns or loaded_patterns
        else:
            self.rules = rules
            self.accusation_patterns = accusation_patterns

        self._accusation_counts: dict[str, int] = {c.id: 0 for c in characters}
        self._last_accused: Optional[str] = None
        self._consecutive_accusations_on_target: int = 0
        self._turns_since_any_accusation: int = 0

    def _detect_accusation(self, turn: Turn) -> Optional[str]:
        """
        Detect if a turn contains an accusation and return the accused character ID.

        Returns:
            Character ID of the accused, or None if no accusation detected.
        """
        content_lower = turn.content.lower()

        for char_id, char in self.characters.items():
            if char_id == turn.speaker_id:
                continue

            name_lower = char.display_name.lower()
            if name_lower not in content_lower:
                continue

            for pattern in self.accusation_patterns:
                if pattern.search(content_lower):
                    return char_id

        return None

    def update_after_turn(self, turn: Turn) -> None:
        """Update internal state after a turn."""
        if turn.type not in (TurnType.QUESTION, TurnType.ANSWER, TurnType.INTERVENTION):
            return

        accused = self._detect_accusation(turn)

        if accused:
            self._accusation_counts[accused] = self._accusation_counts.get(accused, 0) + 1
            self._turns_since_any_accusation = 0

            if accused == self._last_accused:
                self._consecutive_accusations_on_target += 1
            else:
                self._consecutive_accusations_on_target = 1
                self._last_accused = accused
        else:
            self._turns_since_any_accusation += 1
            self._consecutive_accusations_on_target = 0
            self._last_accused = None

    def check_vote_triggers(self, game: Game) -> Optional[VoteTriggerResult]:
        """
        Check if any vote trigger condition is met.

        Returns:
            VoteTriggerResult if voting should be triggered, None otherwise.
        """
        # Calculate game progress (0.0 to 1.0) based on questions asked
        turn_count = len([t for t in game.turns if t.type.value in ("question", "answer")])
        max_questions = game.config.max_questions * 2  # questions + answers
        progress = min(1.0, turn_count / max_questions) if max_questions > 0 else 0.0

        results: list[VoteTriggerResult] = []

        for rule in self.rules:
            result = self._check_rule(rule, progress)
            if result and result.triggered:
                results.append(result)

        if not results:
            return None

        results.sort(key=lambda r: r.priority, reverse=True)
        return results[0]

    def _check_rule(
        self, rule: VoteTriggerRule, progress: float = 0.0
    ) -> Optional[VoteTriggerResult]:
        """Check a single vote trigger rule."""
        if rule.condition_type == "accusations_on_same_player":
            return self._check_accusations_threshold(rule)
        elif rule.condition_type == "consecutive_accusations_on_same_player":
            return self._check_consecutive_accusations(rule)
        elif rule.condition_type == "no_progress_for_n_turns":
            return self._check_no_progress(rule, progress)
        return None

    def _check_accusations_threshold(self, rule: VoteTriggerRule) -> Optional[VoteTriggerResult]:
        """Check if any player has received min_accusations or more."""
        min_accusations = rule.params.get("min_accusations", 2)

        for char_id, count in self._accusation_counts.items():
            if count >= min_accusations:
                char = self.characters.get(char_id)
                name = char.display_name if char else char_id
                return VoteTriggerResult(
                    triggered=True,
                    rule_id=rule.id,
                    condition_type=rule.condition_type,
                    priority=rule.priority,
                    reason=f"{name} получил {count} обвинений",
                    target_player_id=char_id,
                )

        return None

    def _check_consecutive_accusations(self, rule: VoteTriggerRule) -> Optional[VoteTriggerResult]:
        """Check if the same player was accused consecutively."""
        consecutive_count = rule.params.get("consecutive_count", 2)

        if self._consecutive_accusations_on_target >= consecutive_count and self._last_accused:
            char = self.characters.get(self._last_accused)
            name = char.display_name if char else self._last_accused
            return VoteTriggerResult(
                triggered=True,
                rule_id=rule.id,
                condition_type=rule.condition_type,
                priority=rule.priority,
                reason=f"{name} обвинён {self._consecutive_accusations_on_target} раз подряд",
                target_player_id=self._last_accused,
            )

        return None

    def _check_no_progress(
        self, rule: VoteTriggerRule, progress: float = 0.0
    ) -> Optional[VoteTriggerResult]:
        """Check if there have been no accusations for N turns.

        Threshold scales with game progress:
        - Start of game (0%): higher threshold (more patience)
        - End of game (100%): lower threshold (trigger sooner)
        """
        min_threshold = rule.params.get("turns_without_accusations", 8)
        max_threshold = rule.params.get("turns_without_accusations_start", 20)

        # Linear interpolation: start high, end low
        turns_threshold = int(max_threshold - (max_threshold - min_threshold) * progress)

        if self._turns_since_any_accusation >= turns_threshold:
            return VoteTriggerResult(
                triggered=True,
                rule_id=rule.id,
                condition_type=rule.condition_type,
                priority=rule.priority,
                reason=f"Нет обвинений уже {self._turns_since_any_accusation} ходов",
                target_player_id=None,
            )

        return None

    def get_accusation_counts(self) -> dict[str, int]:
        """Get current accusation counts per character."""
        return dict(self._accusation_counts)

    def get_most_accused(self) -> Optional[str]:
        """Get the character with the most accusations."""
        if not self._accusation_counts:
            return None

        max_count = max(self._accusation_counts.values())
        if max_count == 0:
            return None

        for char_id, count in self._accusation_counts.items():
            if count == max_count:
                return char_id
        return None

    def reset(self) -> None:
        """Reset all counters."""
        for char_id in self._accusation_counts:
            self._accusation_counts[char_id] = 0
        self._last_accused = None
        self._consecutive_accusations_on_target = 0
        self._turns_since_any_accusation = 0
