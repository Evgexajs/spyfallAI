"""Tests for TASK-046: MUST NOT toxicity directives.

Verifies that:
1. All character profiles have the toxicity MUST NOT directive
2. Base prompt contains the toxicity rule
3. Game logs don't contain forbidden patterns
"""

import json
import re
from pathlib import Path

import pytest

from src.models import Character, Location, Role
from src.agents import build_system_prompt, SecretInfo


CHARACTERS_DIR = Path(__file__).parent.parent / "characters"
GAMES_DIR = Path(__file__).parent.parent / "games"

TOXICITY_DIRECTIVE = "Использовать мат, реальные оскорбления или унижения — только игровое давление в рамках роли"

FORBIDDEN_PATTERNS = [
    r"\bсука\b",
    r"\bблядь\b",
    r"\bхуй\b",
    r"\bпизд",
    r"\bеба[тнл]",
    r"\bдолбо[её]б",
    r"\bмудак",
    r"\bдебил\b",
    r"\bидиот\b",
    r"\bтупица\b",
    r"\bурод\b",
    r"\bчмо\b",
    r"\bлох\b",
    r"\bтварь\b",
    r"\bмразь\b",
    r"\bпадла\b",
    r"\bскотина\b",
    r"\bнигер",
    r"\bжид\b",
    r"\bхач\b",
    r"\bчурк",
    r"\bпидор",
    r"\bгомик\b",
]


def get_all_character_files() -> list[Path]:
    """Return list of all character JSON files."""
    return list(CHARACTERS_DIR.glob("*.json"))


def get_all_game_logs() -> list[Path]:
    """Return list of all game log files."""
    if not GAMES_DIR.exists():
        return []
    return list(GAMES_DIR.glob("*.json"))


class TestCharacterProfiles:
    """Test that all character profiles have toxicity MUST NOT directive."""

    def test_all_characters_have_toxicity_directive(self):
        """Every character must have the toxicity MUST NOT directive."""
        character_files = get_all_character_files()
        assert len(character_files) == 8, f"Expected 8 characters, found {len(character_files)}"

        missing_directive = []
        for char_file in character_files:
            with open(char_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            directives = data.get("must_not_directives", [])
            has_toxicity = any("мат" in d and "оскорбления" in d for d in directives)

            if not has_toxicity:
                missing_directive.append(char_file.stem)

        assert not missing_directive, f"Characters missing toxicity directive: {missing_directive}"

    @pytest.mark.parametrize("char_file", get_all_character_files(), ids=lambda p: p.stem)
    def test_character_loads_with_toxicity_directive(self, char_file: Path):
        """Each character loads successfully and has toxicity directive."""
        with open(char_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        character = Character.model_validate(data)

        has_toxicity = any(
            "мат" in d and "оскорбления" in d
            for d in character.must_not_directives
        )
        assert has_toxicity, f"{character.id} missing toxicity MUST NOT directive"


class TestBasePrompt:
    """Test that base prompt contains toxicity rule."""

    def test_base_prompt_has_toxicity_rule(self):
        """Base prompt must contain toxicity prohibition rule."""
        from src.agents.prompt_builder import _format_base_rules

        base_rules = _format_base_rules()

        assert "ЗАПРЕЩЕНО" in base_rules
        assert "мат" in base_rules
        assert "оскорбления" in base_rules or "унижения" in base_rules

    def test_toxicity_rule_keywords(self):
        """Toxicity rule must include key terms."""
        from src.agents.prompt_builder import _format_base_rules

        base_rules = _format_base_rules()

        assert "игровое давление" in base_rules.lower()
        assert "унижения" in base_rules or "унижени" in base_rules.lower()


class TestGameLogs:
    """Test that game logs don't contain forbidden patterns."""

    def test_no_forbidden_patterns_in_existing_logs(self):
        """Existing game logs should not contain forbidden patterns."""
        game_files = get_all_game_logs()

        if not game_files:
            pytest.skip("No game logs to check")

        violations = []

        for game_file in game_files:
            try:
                with open(game_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                turns = data.get("turns", [])
                for turn in turns:
                    content = turn.get("content", "")
                    for pattern in FORBIDDEN_PATTERNS:
                        if re.search(pattern, content, re.IGNORECASE):
                            violations.append({
                                "file": game_file.name,
                                "turn": turn.get("turn_number"),
                                "speaker": turn.get("speaker_id"),
                                "pattern": pattern,
                                "content_preview": content[:100]
                            })
            except (json.JSONDecodeError, KeyError):
                continue

        if violations:
            violation_report = "\n".join(
                f"  - {v['file']} turn {v['turn']}: {v['speaker']} matched '{v['pattern']}'"
                for v in violations
            )
            pytest.fail(f"Found {len(violations)} toxicity violations:\n{violation_report}")


def check_text_for_violations(text: str) -> list[str]:
    """Check text for forbidden patterns, return list of matched patterns."""
    matches = []
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            matches.append(pattern)
    return matches


class TestViolationDetection:
    """Test that violation detection works correctly."""

    def test_clean_text_passes(self):
        """Normal game text should not trigger violations."""
        clean_texts = [
            "Ты явно что-то скрываешь, Борис.",
            "Это очень странный ответ, не находишь?",
            "По-моему, ты врёшь!",
            "Зоя, ты подозрительно много молчишь.",
            "Давай без этих манипуляций, отвечай прямо.",
        ]

        for text in clean_texts:
            violations = check_text_for_violations(text)
            assert not violations, f"Clean text triggered false positive: {text}"

    def test_forbidden_patterns_detected(self):
        """Forbidden patterns should be detected."""
        bad_texts = [
            ("Ты сука, признавайся!", r"\bсука\b"),
            ("Это просто идиот какой-то", r"\bидиот\b"),
            ("Ты полный дебил", r"\bдебил\b"),
        ]

        for text, expected_pattern in bad_texts:
            violations = check_text_for_violations(text)
            assert violations, f"Expected violation not detected in: {text}"
            assert any(expected_pattern in v for v in violations)


def grep_games_for_violations(games_dir: Path = GAMES_DIR) -> dict:
    """Scan all game logs for forbidden patterns. Returns summary."""
    results = {
        "total_games": 0,
        "games_with_violations": 0,
        "total_violations": 0,
        "violations": []
    }

    if not games_dir.exists():
        return results

    for game_file in games_dir.glob("*.json"):
        results["total_games"] += 1
        try:
            with open(game_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            game_violations = []
            for turn in data.get("turns", []):
                content = turn.get("content", "")
                matched = check_text_for_violations(content)
                if matched:
                    game_violations.append({
                        "turn": turn.get("turn_number"),
                        "speaker": turn.get("speaker_id"),
                        "patterns": matched
                    })

            if game_violations:
                results["games_with_violations"] += 1
                results["total_violations"] += len(game_violations)
                results["violations"].append({
                    "file": game_file.name,
                    "violations": game_violations
                })
        except (json.JSONDecodeError, KeyError):
            continue

    return results


if __name__ == "__main__":
    print("Checking all character profiles...")
    char_files = get_all_character_files()
    print(f"Found {len(char_files)} character files")

    all_ok = True
    for cf in char_files:
        with open(cf, "r", encoding="utf-8") as f:
            data = json.load(f)
        directives = data.get("must_not_directives", [])
        has_toxicity = any("мат" in d and "оскорбления" in d for d in directives)
        status = "OK" if has_toxicity else "MISSING"
        if not has_toxicity:
            all_ok = False
        print(f"  {cf.stem}: {status}")

    print("\nChecking game logs for violations...")
    results = grep_games_for_violations()
    print(f"  Total games: {results['total_games']}")
    print(f"  Games with violations: {results['games_with_violations']}")
    print(f"  Total violations: {results['total_violations']}")

    if results['violations']:
        print("\nViolation details:")
        for v in results['violations']:
            print(f"  {v['file']}:")
            for vv in v['violations']:
                print(f"    Turn {vv['turn']} ({vv['speaker']}): {vv['patterns']}")

    print("\n" + ("All checks passed!" if all_ok and results['games_with_violations'] == 0 else "Some checks failed!"))
