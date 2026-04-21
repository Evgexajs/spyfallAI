"""LLM prompts for post-game character analysis."""

import json
from typing import Optional

from src.models.character import Character, Marker
from src.models.game import Turn


def _format_marker(marker: Marker) -> dict:
    """Format a marker for inclusion in the prompt."""
    result = {
        "marker_id": marker.id,
        "description": marker.description,
        "method": marker.method.value
    }
    if marker.prompt:
        result["check_question"] = marker.prompt
    if marker.rule:
        result["rule"] = marker.rule
    return result


def _format_turn(turn: Turn, previous_turn: Optional[Turn] = None) -> dict:
    """Format a turn with context for inclusion in the prompt."""
    result = {
        "turn_number": turn.turn_number,
        "type": turn.type.value,
        "addressee": turn.addressee_id,
        "content": turn.content
    }
    if previous_turn:
        result["previous_speaker"] = previous_turn.speaker_id
        result["previous_content"] = previous_turn.content
    return result


def build_analysis_prompt(character: Character, turns: list[Turn]) -> str:
    """Build the LLM prompt for character analysis.

    Args:
        character: The character profile with detectable_markers and must_directives.
        turns: List of turns (with context) for this character in the game.

    Returns:
        Complete prompt string for the analysis LLM call.
    """
    markers_data = [_format_marker(m) for m in character.detectable_markers]

    turns_data = []
    for i, turn in enumerate(turns):
        previous = turns[i - 1] if i > 0 else None
        turns_data.append(_format_turn(turn, previous))

    expected_format = {
        "character_id": character.id,
        "markers": {
            "status": "completed",
            "per_marker": [
                {
                    "marker_id": "<marker_id из профиля>",
                    "triggered_count": "<число реплик, где маркер сработал>",
                    "total_relevant_replies": "<общее число реплик персонажа>",
                    "rate": "<triggered_count / total_relevant_replies, от 0.0 до 1.0>",
                    "per_turn": [
                        {
                            "turn_number": "<номер хода>",
                            "triggered": "<true/false>",
                            "reasoning": "<краткое обоснование на русском>"
                        }
                    ]
                }
            ]
        },
        "must_compliance": {
            "status": "completed",
            "per_directive": [
                {
                    "directive": "<текст директивы>",
                    "satisfied": "<true/false>",
                    "evidence_turns": ["<номера ходов, подтверждающих выполнение>"],
                    "reasoning": "<обоснование на русском>"
                }
            ]
        }
    }

    prompt = f"""Ты анализатор характерности персонажа в игре Spyfall. Твоя задача — оценить, насколько персонаж проявил свой характер в партии.

## Профиль персонажа

Имя: {character.display_name}
ID: {character.id}
Архетип: {character.archetype}
Стиль речи: {character.voice_style}

## Маркеры характерности (detectable_markers)

Для каждой реплики персонажа определи, сработал ли маркер. Маркер срабатывает, если реплика соответствует его описанию.

{json.dumps(markers_data, ensure_ascii=False, indent=2)}

## MUST-директивы

Определи, выполнил ли персонаж каждую из этих обязательных директив за партию.

{json.dumps(character.must_directives, ensure_ascii=False, indent=2)}

## Реплики персонажа в партии

Ниже все реплики персонажа {character.display_name} с контекстом (предыдущая реплика, адресат).

{json.dumps(turns_data, ensure_ascii=False, indent=2)}

## Инструкции

1. Проанализируй КАЖДУЮ реплику персонажа на предмет КАЖДОГО маркера.
2. Для каждого маркера посчитай: в скольких репликах он сработал, какова доля (rate).
3. Проверь выполнение КАЖДОЙ MUST-директивы за всю партию.
4. Верни результат СТРОГО в формате JSON без markdown-обёртки, без комментариев, без пояснений.

## ОБЯЗАТЕЛЬНЫЙ формат ответа

Верни ТОЛЬКО валидный JSON объект следующей структуры (без ```json, без текста до/после):

{json.dumps(expected_format, ensure_ascii=False, indent=2)}

ВАЖНО:
- Не оборачивай JSON в markdown-блоки (```json ... ```)
- Не добавляй комментарии или пояснения до/после JSON
- per_marker должен содержать запись для КАЖДОГО маркера из профиля
- per_directive должен содержать запись для КАЖДОЙ MUST-директивы
- per_turn должен содержать запись для КАЖДОЙ реплики персонажа
- Все обоснования (reasoning) должны быть на русском языке
- rate — это число с плавающей точкой от 0.0 до 1.0
"""

    return prompt
