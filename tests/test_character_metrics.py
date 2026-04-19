"""Tests for character distinctiveness metrics (TASK-042)."""

from datetime import datetime
from uuid import uuid4

import pytest

from src.analysis import (
    CharacterMetrics,
    GameAnalysis,
    MarkerResult,
    ReplyAnalysis,
    analyze_game,
    count_sentences,
    detect_marker,
    detect_markers,
    generate_report,
)
from src.models import (
    Character,
    Game,
    GameConfig,
    Marker,
    MarkerMethod,
    Player,
    Turn,
    TurnType,
)


class TestCountSentences:
    """Tests for sentence counting."""

    def test_empty_string(self):
        assert count_sentences("") == 0
        assert count_sentences("   ") == 0

    def test_single_sentence(self):
        assert count_sentences("Привет.") == 1
        assert count_sentences("Привет!") == 1
        assert count_sentences("Кто ты?") == 1

    def test_multiple_sentences(self):
        assert count_sentences("Привет. Как дела?") == 2
        assert count_sentences("Один. Два. Три.") == 3

    def test_mixed_punctuation(self):
        assert count_sentences("Что?! Ты шутишь!") == 2
        assert count_sentences("Хм. Интересно... Очень.") == 3

    def test_ellipsis_handling(self):
        assert count_sentences("Ну... это странно.") == 2
        assert count_sentences("Думаю... да.") == 2

    def test_sentence_without_final_punctuation(self):
        assert count_sentences("Это предложение") == 1


class TestEvaluateCounterRule:
    """Tests for counter rule evaluation."""

    def test_sentences_less_equal(self):
        from src.analysis.character_metrics import evaluate_counter_rule

        assert evaluate_counter_rule("Привет.", "sentences <= 2") is True
        assert evaluate_counter_rule("Один. Два.", "sentences <= 2") is True
        assert evaluate_counter_rule("Один. Два. Три.", "sentences <= 2") is False

    def test_sentences_greater_equal(self):
        from src.analysis.character_metrics import evaluate_counter_rule

        assert evaluate_counter_rule("Один. Два. Три.", "sentences >= 3") is True
        assert evaluate_counter_rule("Один. Два.", "sentences >= 3") is False

    def test_words_less_equal(self):
        from src.analysis.character_metrics import evaluate_counter_rule

        assert evaluate_counter_rule("раз два три", "words <= 5") is True
        assert evaluate_counter_rule("раз два три четыре пять шесть", "words <= 5") is False


class TestDetectMarker:
    """Tests for single marker detection."""

    def test_regex_marker_match(self):
        marker = Marker(
            id="question_mark",
            method=MarkerMethod.REGEX,
            pattern=r"\?",
            description="Contains question mark",
        )
        assert detect_marker("Кто ты?", marker) is True
        assert detect_marker("Я здесь.", marker) is False

    def test_regex_marker_case_insensitive(self):
        marker = Marker(
            id="name",
            method=MarkerMethod.REGEX,
            pattern=r"(борис|марго|зоя)",
            description="Contains name",
        )
        assert detect_marker("Борис, что скажешь?", marker) is True
        assert detect_marker("Привет, Ким.", marker) is False

    def test_regex_marker_complex_pattern(self):
        marker = Marker(
            id="no_hedging",
            method=MarkerMethod.REGEX,
            pattern=r"^(?!.*(возможно|наверное|может быть)).*$",
            description="No hedging words",
        )
        assert detect_marker("Это точно он.", marker) is True
        assert detect_marker("Возможно, это он.", marker) is False

    def test_counter_marker_sentences(self):
        marker = Marker(
            id="short_reply",
            method=MarkerMethod.COUNTER,
            rule="sentences <= 2",
            description="Short reply",
        )
        assert detect_marker("Да.", marker) is True
        assert detect_marker("Раз. Два.", marker) is True
        assert detect_marker("Раз. Два. Три.", marker) is False

    def test_counter_marker_words(self):
        marker = Marker(
            id="brief",
            method=MarkerMethod.COUNTER,
            rule="words <= 5",
            description="Brief reply",
        )
        assert detect_marker("да нет конечно", marker) is True
        assert detect_marker("много слов тут раз два три четыре", marker) is False

    def test_binary_llm_without_provider(self):
        marker = Marker(
            id="ironic",
            method=MarkerMethod.BINARY_LLM,
            prompt="Is this ironic?",
            description="Ironic tone",
        )
        assert detect_marker("Test text", marker, llm_provider=None) is False


class TestDetectMarkers:
    """Tests for multiple marker detection."""

    def test_detect_multiple_markers(self):
        markers = [
            Marker(
                id="question", method=MarkerMethod.REGEX,
                pattern=r"\?", description="Question"
            ),
            Marker(
                id="short", method=MarkerMethod.COUNTER,
                rule="sentences <= 2", description="Short"
            ),
            Marker(
                id="name", method=MarkerMethod.REGEX,
                pattern=r"(ты|Ты)", description="Addresses"
            ),
        ]

        results = detect_markers("Ты кто?", markers)

        assert len(results) == 3
        assert results["question"].detected is True
        assert results["short"].detected is True
        assert results["name"].detected is True

    def test_partial_detection(self):
        markers = [
            Marker(
                id="question", method=MarkerMethod.REGEX,
                pattern=r"\?", description="Question"
            ),
            Marker(
                id="long", method=MarkerMethod.COUNTER,
                rule="sentences >= 3", description="Long"
            ),
        ]

        results = detect_markers("Кто это?", markers)

        assert results["question"].detected is True
        assert results["long"].detected is False


class TestReplyAnalysis:
    """Tests for ReplyAnalysis class."""

    def test_is_marked_true(self):
        analysis = ReplyAnalysis(
            turn_number=1,
            speaker_id="boris",
            content="Test",
            turn_type=TurnType.ANSWER,
            marker_results={
                "m1": MarkerResult(marker_id="m1", detected=True, method=MarkerMethod.REGEX),
                "m2": MarkerResult(marker_id="m2", detected=False, method=MarkerMethod.COUNTER),
            },
        )
        assert analysis.is_marked is True
        assert analysis.marker_count == 1
        assert analysis.detected_markers == ["m1"]

    def test_is_marked_false(self):
        analysis = ReplyAnalysis(
            turn_number=1,
            speaker_id="boris",
            content="Test",
            turn_type=TurnType.ANSWER,
            marker_results={
                "m1": MarkerResult(marker_id="m1", detected=False, method=MarkerMethod.REGEX),
            },
        )
        assert analysis.is_marked is False
        assert analysis.marker_count == 0


class TestCharacterMetrics:
    """Tests for CharacterMetrics class."""

    def test_add_marked_reply(self):
        metrics = CharacterMetrics(character_id="boris", display_name="Борис")

        analysis = ReplyAnalysis(
            turn_number=1,
            speaker_id="boris",
            content="Test",
            turn_type=TurnType.ANSWER,
            marker_results={
                "m1": MarkerResult(marker_id="m1", detected=True, method=MarkerMethod.REGEX),
            },
        )

        metrics.add_reply(analysis)

        assert metrics.total_replies == 1
        assert metrics.marked_replies == 1
        assert metrics.unmarked_replies == 0
        assert metrics.marked_percentage == 100.0

    def test_consecutive_unmarked_detection(self):
        metrics = CharacterMetrics(character_id="boris", display_name="Борис")

        for i in range(3):
            analysis = ReplyAnalysis(
                turn_number=i,
                speaker_id="boris",
                content="Test",
                turn_type=TurnType.ANSWER,
                marker_results={
                    "m1": MarkerResult(marker_id="m1", detected=False, method=MarkerMethod.REGEX),
                },
            )
            metrics.add_reply(analysis)

        assert metrics.max_consecutive_unmarked == 3
        assert metrics.has_consecutive_unmarked_violation is True

    def test_no_violation_with_marked_between(self):
        metrics = CharacterMetrics(character_id="boris", display_name="Борис")

        unmarked = ReplyAnalysis(
            turn_number=1,
            speaker_id="boris",
            content="Test",
            turn_type=TurnType.ANSWER,
            marker_results={"m1": MarkerResult("m1", False, MarkerMethod.REGEX)},
        )
        marked = ReplyAnalysis(
            turn_number=2,
            speaker_id="boris",
            content="Test?",
            turn_type=TurnType.ANSWER,
            marker_results={"m1": MarkerResult("m1", True, MarkerMethod.REGEX)},
        )

        metrics.add_reply(unmarked)
        metrics.add_reply(marked)
        metrics.add_reply(unmarked)

        assert metrics.max_consecutive_unmarked == 1
        assert metrics.has_consecutive_unmarked_violation is False


class TestAnalyzeGame:
    """Tests for game analysis."""

    @pytest.fixture
    def sample_characters(self) -> dict[str, Character]:
        boris = Character(
            id="boris_molot",
            display_name="Борис",
            archetype="агрессор",
            backstory="Test backstory for Boris character",
            voice_style="Short aggressive phrases",
            must_directives=["Must be aggressive"],
            must_not_directives=["Must not be polite"],
            detectable_markers=[
                Marker(
                    id="question", method=MarkerMethod.REGEX,
                    pattern=r"\?", description="Question"
                ),
                Marker(
                    id="short", method=MarkerMethod.COUNTER,
                    rule="sentences <= 2", description="Short"
                ),
            ],
            intervention_priority=9,
            intervention_threshold=0.3,
        )

        zoya = Character(
            id="zoya",
            display_name="Зоя",
            archetype="циник",
            backstory="Test backstory for Zoya character",
            voice_style="Sarcastic short replies",
            must_directives=["Must be sarcastic"],
            must_not_directives=["Must not be sincere"],
            detectable_markers=[
                Marker(
                    id="sarcasm", method=MarkerMethod.REGEX,
                    pattern=r"(ага|конечно)", description="Sarcasm"
                ),
            ],
            intervention_priority=7,
            intervention_threshold=0.4,
        )

        kim = Character(
            id="kim",
            display_name="Ким",
            archetype="параноик",
            backstory="Test backstory for Kim character",
            voice_style="Nervous hedging speech",
            must_directives=["Must be nervous"],
            must_not_directives=["Must not be confident"],
            detectable_markers=[
                Marker(
                    id="hedging", method=MarkerMethod.REGEX,
                    pattern=r"(возможно|наверное)", description="Hedging"
                ),
            ],
            intervention_priority=4,
            intervention_threshold=0.4,
        )

        return {"boris_molot": boris, "zoya": zoya, "kim": kim}

    @pytest.fixture
    def sample_game(self) -> Game:
        return Game(
            id=str(uuid4()),
            started_at=datetime.now(),
            config=GameConfig(
                duration_minutes=5,
                max_questions=10,
                players_count=3,
                main_model="gpt-4o",
                utility_model="gpt-4o-mini",
            ),
            location_id="hospital",
            players=[
                Player(character_id="boris_molot", role_id="surgeon", is_spy=False),
                Player(character_id="zoya", role_id="nurse", is_spy=True),
                Player(character_id="kim", role_id="patient", is_spy=False),
            ],
            spy_id="zoya",
            turns=[
                Turn(
                    turn_number=1,
                    timestamp=datetime.now(),
                    speaker_id="boris_molot",
                    addressee_id="zoya",
                    type=TurnType.QUESTION,
                    content="Зоя, что ты делаешь здесь?",
                    display_delay_ms=0,
                ),
                Turn(
                    turn_number=2,
                    timestamp=datetime.now(),
                    speaker_id="zoya",
                    addressee_id="boris_molot",
                    type=TurnType.ANSWER,
                    content="Ага, конечно, как будто тебе есть дело.",
                    display_delay_ms=0,
                ),
                Turn(
                    turn_number=3,
                    timestamp=datetime.now(),
                    speaker_id="zoya",
                    addressee_id="boris_molot",
                    type=TurnType.QUESTION,
                    content="Борис, а ты сам-то что тут забыл.",
                    display_delay_ms=0,
                ),
                Turn(
                    turn_number=4,
                    timestamp=datetime.now(),
                    speaker_id="boris_molot",
                    addressee_id="zoya",
                    type=TurnType.ANSWER,
                    content="Работаю.",
                    display_delay_ms=0,
                ),
            ],
        )

    def test_analyze_game_basic(self, sample_game, sample_characters):
        analysis = analyze_game(sample_game, sample_characters)

        assert analysis.game_id == sample_game.id
        assert analysis.location_id == "hospital"
        assert len(analysis.character_metrics) == 3
        assert "boris_molot" in analysis.character_metrics
        assert "zoya" in analysis.character_metrics
        assert "kim" in analysis.character_metrics

    def test_analyze_game_boris_metrics(self, sample_game, sample_characters):
        analysis = analyze_game(sample_game, sample_characters)
        boris_metrics = analysis.character_metrics["boris_molot"]

        assert boris_metrics.total_replies == 2
        assert boris_metrics.marked_replies == 2
        assert boris_metrics.marked_percentage == 100.0

    def test_analyze_game_zoya_metrics(self, sample_game, sample_characters):
        analysis = analyze_game(sample_game, sample_characters)
        zoya_metrics = analysis.character_metrics["zoya"]

        assert zoya_metrics.total_replies == 2
        assert zoya_metrics.marked_replies >= 1

    def test_analyze_game_no_violations(self, sample_game, sample_characters):
        analysis = analyze_game(sample_game, sample_characters)

        assert len(analysis.characters_with_violations) == 0


class TestGenerateReport:
    """Tests for report generation."""

    def test_empty_report(self):
        report = generate_report([])
        assert "Нет данных для анализа" in report

    def test_report_structure(self):
        metrics = CharacterMetrics(
            character_id="boris",
            display_name="Борис",
            total_replies=10,
            marked_replies=8,
            unmarked_replies=2,
        )

        analysis = GameAnalysis(
            game_id="test-game-id",
            location_id="hospital",
            character_metrics={"boris": metrics},
            total_turns=15,
            analyzed_turns=10,
        )

        report = generate_report([analysis])

        assert "ОТЧЁТ: МЕТРИКИ ХАРАКТЕРНОСТИ ПЕРСОНАЖЕЙ" in report
        assert "Борис" in report
        assert "hospital" in report
        assert "Проанализировано партий: 1" in report

    def test_report_shows_violations(self):
        metrics = CharacterMetrics(
            character_id="boris",
            display_name="Борис",
            total_replies=5,
            marked_replies=2,
            unmarked_replies=3,
            max_consecutive_unmarked=2,
            has_consecutive_unmarked_violation=True,
        )

        analysis = GameAnalysis(
            game_id="test-id",
            location_id="hospital",
            character_metrics={"boris": metrics},
        )

        report = generate_report([analysis])

        assert "ФЛАГ" in report or "немаркированных подряд" in report
        assert "ВНИМАНИЕ" in report


class TestGameAnalysis:
    """Tests for GameAnalysis class."""

    def test_overall_marked_percentage(self):
        metrics1 = CharacterMetrics(
            character_id="a", display_name="A",
            total_replies=10, marked_replies=8,
        )
        metrics2 = CharacterMetrics(
            character_id="b", display_name="B",
            total_replies=10, marked_replies=6,
        )

        analysis = GameAnalysis(
            game_id="test",
            location_id="test",
            character_metrics={"a": metrics1, "b": metrics2},
        )

        assert analysis.overall_marked_percentage == 70.0

    def test_all_characters_above_threshold(self):
        metrics1 = CharacterMetrics(
            character_id="a", display_name="A",
            total_replies=10, marked_replies=6,
        )
        metrics2 = CharacterMetrics(
            character_id="b", display_name="B",
            total_replies=10, marked_replies=6,
        )

        analysis = GameAnalysis(
            game_id="test",
            location_id="test",
            character_metrics={"a": metrics1, "b": metrics2},
        )

        assert analysis.all_characters_above_threshold is True

    def test_below_threshold(self):
        metrics = CharacterMetrics(
            character_id="a", display_name="A",
            total_replies=10, marked_replies=4,
        )

        analysis = GameAnalysis(
            game_id="test",
            location_id="test",
            character_metrics={"a": metrics},
        )

        assert analysis.all_characters_above_threshold is False
