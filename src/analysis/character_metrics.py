"""Character distinctiveness metrics for SpyfallAI.

Analyzes game logs to measure how well characters maintain their distinctive voice
by checking detectable_markers and MUST-patterns in each reply.
"""

import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..models import Character, Game, Marker, MarkerMethod, TurnType


def count_sentences(text: str) -> int:
    """
    Count sentences in Russian/English text.

    Uses simple heuristics: splits by sentence-ending punctuation,
    handles common abbreviations and ellipsis.
    """
    if not text or not text.strip():
        return 0

    text = text.strip()
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r'\s+', ' ', text)

    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    return len(sentences)


def evaluate_counter_rule(text: str, rule: str) -> bool:
    """
    Evaluate a counter rule against text.

    Supported rules:
    - "sentences <= N" / "sentences < N" / "sentences >= N"
    - "words <= N" / "words < N" / "words >= N"
    """
    rule = rule.lower().strip()

    sentences_match = re.match(r'sentences\s*([<>=]+)\s*(\d+)', rule)
    if sentences_match:
        op = sentences_match.group(1)
        threshold = int(sentences_match.group(2))
        count = count_sentences(text)
        return _compare(count, op, threshold)

    words_match = re.match(r'words\s*([<>=]+)\s*(\d+)', rule)
    if words_match:
        op = words_match.group(1)
        threshold = int(words_match.group(2))
        count = len(text.split())
        return _compare(count, op, threshold)

    return False


def _compare(value: int, op: str, threshold: int) -> bool:
    """Compare value with threshold using operator."""
    if op == "<=":
        return value <= threshold
    elif op == "<":
        return value < threshold
    elif op == ">=":
        return value >= threshold
    elif op == ">":
        return value > threshold
    elif op == "==" or op == "=":
        return value == threshold
    return False


def detect_marker(
    text: str,
    marker: Marker,
    llm_provider=None,
) -> bool:
    """
    Detect if a single marker is present in the text.

    Args:
        text: The reply text to check
        marker: The Marker definition
        llm_provider: Optional LLM provider for binary_llm markers

    Returns:
        True if marker detected, False otherwise
    """
    if marker.method == MarkerMethod.REGEX:
        if marker.pattern:
            try:
                return bool(re.search(marker.pattern, text, re.IGNORECASE))
            except re.error:
                return False
        return False

    elif marker.method == MarkerMethod.COUNTER:
        if marker.rule:
            return evaluate_counter_rule(text, marker.rule)
        return False

    elif marker.method == MarkerMethod.BINARY_LLM:
        if llm_provider is None:
            return False
        if marker.prompt:
            return _check_binary_llm_sync(text, marker.prompt, llm_provider)
        return False

    return False


def _check_binary_llm_sync(text: str, prompt: str, llm_provider) -> bool:
    """Run binary LLM check synchronously."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                coro = _check_binary_llm_async(text, prompt, llm_provider)
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=30)
        else:
            return asyncio.run(_check_binary_llm_async(text, prompt, llm_provider))
    except Exception:
        return False


async def _check_binary_llm_async(text: str, prompt: str, llm_provider) -> bool:
    """Check binary LLM marker asynchronously."""
    full_prompt = f"Реплика: \"{text}\"\n\nВопрос: {prompt}"

    try:
        response = await llm_provider.complete(
            messages=[{"role": "user", "content": full_prompt}],
            system="Отвечай только 'да' или 'нет'.",
            max_tokens=5,
        )
        answer = response.content.strip().lower()
        return answer in ("да", "yes", "да.")
    except Exception:
        return False


@dataclass
class MarkerResult:
    """Result of checking a single marker."""
    marker_id: str
    detected: bool
    method: MarkerMethod


def detect_markers(
    text: str,
    markers: list[Marker],
    llm_provider=None,
) -> dict[str, MarkerResult]:
    """
    Detect all markers in the text.

    Args:
        text: The reply text to check
        markers: List of Marker definitions
        llm_provider: Optional LLM provider for binary_llm markers

    Returns:
        Dict mapping marker_id to MarkerResult
    """
    results = {}
    for marker in markers:
        detected = detect_marker(text, marker, llm_provider)
        results[marker.id] = MarkerResult(
            marker_id=marker.id,
            detected=detected,
            method=marker.method,
        )
    return results


@dataclass
class ReplyAnalysis:
    """Analysis of a single reply."""
    turn_number: int
    speaker_id: str
    content: str
    turn_type: TurnType
    marker_results: dict[str, MarkerResult]

    @property
    def is_marked(self) -> bool:
        """Return True if at least one marker detected."""
        return any(r.detected for r in self.marker_results.values())

    @property
    def detected_markers(self) -> list[str]:
        """Return list of detected marker IDs."""
        return [r.marker_id for r in self.marker_results.values() if r.detected]

    @property
    def marker_count(self) -> int:
        """Return count of detected markers."""
        return sum(1 for r in self.marker_results.values() if r.detected)


@dataclass
class CharacterMetrics:
    """Metrics for a single character in a game."""
    character_id: str
    display_name: str
    total_replies: int = 0
    marked_replies: int = 0
    unmarked_replies: int = 0
    max_consecutive_unmarked: int = 0
    has_consecutive_unmarked_violation: bool = False
    marker_detection_counts: dict[str, int] = field(default_factory=dict)
    reply_analyses: list[ReplyAnalysis] = field(default_factory=list)

    @property
    def marked_percentage(self) -> float:
        """Return percentage of marked replies."""
        if self.total_replies == 0:
            return 0.0
        return (self.marked_replies / self.total_replies) * 100

    def add_reply(self, analysis: ReplyAnalysis) -> None:
        """Add a reply analysis and update metrics."""
        self.reply_analyses.append(analysis)
        self.total_replies += 1

        if analysis.is_marked:
            self.marked_replies += 1
        else:
            self.unmarked_replies += 1

        for marker_id in analysis.detected_markers:
            self.marker_detection_counts[marker_id] = (
                self.marker_detection_counts.get(marker_id, 0) + 1
            )

        self._update_consecutive_unmarked()

    def _update_consecutive_unmarked(self) -> None:
        """Update consecutive unmarked counter."""
        current_streak = 0
        max_streak = 0

        for analysis in self.reply_analyses:
            if not analysis.is_marked:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0

        self.max_consecutive_unmarked = max_streak
        self.has_consecutive_unmarked_violation = max_streak >= 2


@dataclass
class GameAnalysis:
    """Full analysis result for a game."""
    game_id: str
    location_id: str
    character_metrics: dict[str, CharacterMetrics]
    total_turns: int = 0
    analyzed_turns: int = 0

    @property
    def overall_marked_percentage(self) -> float:
        """Return overall percentage of marked replies."""
        total = sum(m.total_replies for m in self.character_metrics.values())
        marked = sum(m.marked_replies for m in self.character_metrics.values())
        if total == 0:
            return 0.0
        return (marked / total) * 100

    @property
    def characters_with_violations(self) -> list[str]:
        """Return character IDs that have 2+ consecutive unmarked replies."""
        return [
            char_id for char_id, metrics in self.character_metrics.items()
            if metrics.has_consecutive_unmarked_violation
        ]

    @property
    def all_characters_above_threshold(self) -> bool:
        """Check if all characters have > 50% marked replies."""
        return all(
            m.marked_percentage > 50
            for m in self.character_metrics.values()
            if m.total_replies > 0
        )


def analyze_game(
    game: Game,
    characters: dict[str, Character],
    llm_provider=None,
    include_turn_types: Optional[set[TurnType]] = None,
) -> GameAnalysis:
    """
    Analyze a single game for character distinctiveness.

    Args:
        game: The Game object to analyze
        characters: Dict mapping character_id to Character
        llm_provider: Optional LLM provider for binary_llm markers
        include_turn_types: Set of turn types to analyze (default: QUESTION, ANSWER, INTERVENTION)

    Returns:
        GameAnalysis with per-character metrics
    """
    if include_turn_types is None:
        include_turn_types = {TurnType.QUESTION, TurnType.ANSWER, TurnType.INTERVENTION}

    character_metrics: dict[str, CharacterMetrics] = {}

    for player in game.players:
        char_id = player.character_id
        if char_id in characters:
            char = characters[char_id]
            character_metrics[char_id] = CharacterMetrics(
                character_id=char_id,
                display_name=char.display_name,
            )

    analyzed_turns = 0
    for turn in game.turns:
        if turn.type not in include_turn_types:
            continue

        speaker_id = turn.speaker_id
        if speaker_id not in character_metrics:
            continue

        char = characters.get(speaker_id)
        if not char:
            continue

        marker_results = detect_markers(
            turn.content,
            char.detectable_markers,
            llm_provider,
        )

        reply_analysis = ReplyAnalysis(
            turn_number=turn.turn_number,
            speaker_id=speaker_id,
            content=turn.content,
            turn_type=turn.type,
            marker_results=marker_results,
        )

        character_metrics[speaker_id].add_reply(reply_analysis)
        analyzed_turns += 1

    return GameAnalysis(
        game_id=game.id,
        location_id=game.location_id,
        character_metrics=character_metrics,
        total_turns=len(game.turns),
        analyzed_turns=analyzed_turns,
    )


def analyze_games(
    game_paths: list[Path],
    characters_dir: Path,
    llm_provider=None,
) -> list[GameAnalysis]:
    """
    Analyze multiple games from file paths.

    Args:
        game_paths: List of paths to game JSON files
        characters_dir: Path to characters directory
        llm_provider: Optional LLM provider for binary_llm markers

    Returns:
        List of GameAnalysis results
    """
    import json

    characters: dict[str, Character] = {}
    for char_file in characters_dir.glob("*.json"):
        with open(char_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        char = Character.model_validate(data)
        characters[char.id] = char

    from ..storage import load_game

    results = []
    for game_path in game_paths:
        try:
            game = load_game(game_path)
            analysis = analyze_game(game, characters, llm_provider)
            results.append(analysis)
        except Exception as e:
            print(f"Error analyzing {game_path}: {e}")

    return results


def generate_report(analyses: list[GameAnalysis]) -> str:
    """
    Generate a human-readable report from analysis results.

    Args:
        analyses: List of GameAnalysis objects

    Returns:
        Formatted report string
    """
    lines = []
    lines.append("=" * 70)
    lines.append("ОТЧЁТ: МЕТРИКИ ХАРАКТЕРНОСТИ ПЕРСОНАЖЕЙ")
    lines.append("=" * 70)
    lines.append("")

    if not analyses:
        lines.append("Нет данных для анализа.")
        return "\n".join(lines)

    lines.append(f"Проанализировано партий: {len(analyses)}")
    lines.append("")

    all_character_metrics: dict[str, list[CharacterMetrics]] = {}
    total_violations = 0
    games_with_all_above_50 = 0

    for analysis in analyses:
        if analysis.all_characters_above_threshold:
            games_with_all_above_50 += 1

        for char_id, metrics in analysis.character_metrics.items():
            if char_id not in all_character_metrics:
                all_character_metrics[char_id] = []
            all_character_metrics[char_id].append(metrics)

            if metrics.has_consecutive_unmarked_violation:
                total_violations += 1

    lines.append("-" * 70)
    lines.append("СВОДКА ПО ПЕРСОНАЖАМ")
    lines.append("-" * 70)
    lines.append("")

    for char_id, metrics_list in sorted(all_character_metrics.items()):
        if not metrics_list:
            continue

        display_name = metrics_list[0].display_name
        total_replies = sum(m.total_replies for m in metrics_list)
        total_marked = sum(m.marked_replies for m in metrics_list)
        avg_marked_pct = (total_marked / total_replies * 100) if total_replies > 0 else 0

        violations = sum(1 for m in metrics_list if m.has_consecutive_unmarked_violation)

        marker_totals: dict[str, int] = {}
        for m in metrics_list:
            for marker_id, count in m.marker_detection_counts.items():
                marker_totals[marker_id] = marker_totals.get(marker_id, 0) + count

        status = "OK" if avg_marked_pct > 50 and violations == 0 else "ВНИМАНИЕ"

        lines.append(f"[{status}] {display_name} ({char_id})")
        marked_info = f"маркированных: {total_marked} ({avg_marked_pct:.1f}%)"
        lines.append(f"    Реплик: {total_replies}, {marked_info}")

        if violations > 0:
            lines.append(f"    ФЛАГ: 2+ немаркированных подряд в {violations} партиях")

        if marker_totals:
            sorted_markers = sorted(marker_totals.items(), key=lambda x: -x[1])
            markers_str = ", ".join(f"{m}:{c}" for m, c in sorted_markers[:5])
            lines.append(f"    Маркеры: {markers_str}")

        lines.append("")

    lines.append("-" * 70)
    lines.append("ИТОГО")
    lines.append("-" * 70)
    lines.append("")

    total_games = len(analyses)
    lines.append(f"Партий с >50% маркированных у всех: {games_with_all_above_50}/{total_games}")
    lines.append(f"Всего нарушений (2+ подряд): {total_violations}")

    lines.append("")
    lines.append("-" * 70)
    lines.append("ДЕТАЛИ ПО ПАРТИЯМ")
    lines.append("-" * 70)

    for i, analysis in enumerate(analyses, 1):
        lines.append("")
        loc = analysis.location_id
        lines.append(f"Партия {i}: {analysis.game_id[:8]}... (локация: {loc})")
        turns_info = f"проанализировано: {analysis.analyzed_turns}"
        lines.append(f"    Ходов: {analysis.total_turns}, {turns_info}")
        lines.append(f"    Общий % маркированных: {analysis.overall_marked_percentage:.1f}%")

        if analysis.characters_with_violations:
            lines.append(f"    Нарушения: {', '.join(analysis.characters_with_violations)}")

        for char_id, metrics in analysis.character_metrics.items():
            if metrics.total_replies == 0:
                continue
            status = "!" if metrics.has_consecutive_unmarked_violation else " "
            pct = metrics.marked_percentage
            ratio = f"{metrics.marked_replies}/{metrics.total_replies}"
            lines.append(f"      {status} {metrics.display_name}: {ratio} ({pct:.0f}%)")

    lines.append("")
    lines.append("=" * 70)
    lines.append("КОНЕЦ ОТЧЁТА")
    lines.append("=" * 70)

    return "\n".join(lines)
