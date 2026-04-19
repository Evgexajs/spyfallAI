"""Prompt builder for SpyfallAI agents."""

from dataclasses import dataclass
from typing import Optional

from src.models.character import Character
from src.models.location import Location, Role
from src.models.game import Game, Player


@dataclass
class SecretInfo:
    """Secret information for a player."""

    is_spy: bool
    location: Optional[Location] = None
    role: Optional[Role] = None


FEW_SHOT_EXAMPLES = {
    "агрессор": [
        ("Чем ты занимаешься здесь?", "Работаю. А ты чего вопросы задаёшь?"),
        ("Кажется, ты что-то скрываешь", "Это ты скрываешь, Ким. Я видел, как ты запнулся на прошлом вопросе."),
        ("Как давно ты тут работаешь?", "Достаточно. Следующий вопрос — твой."),
    ],
    "манипулятор": [
        ("Чем ты занимаешься здесь?", "О, у меня очень интересная роль. А что тебя так заинтересовало, дорогой?"),
        ("Ты выглядишь подозрительно", "Мне кажется, это Борис ведёт себя странно — заметили, как он на всех набросился?"),
        ("Что ты делала утром?", "Была занята, как и все мы. Кстати, твоя наблюдательность впечатляет — это комплимент."),
    ],
    "параноик": [
        ("Чем ты занимаешься здесь?", "Ну, в смысле... работаю, то есть... выполняю свои обязанности, вернее, стараюсь выполнять."),
        ("Расскажи о своей роли", "А почему ты спрашиваешь? То есть, я не против, просто... кажется, это подозрительно, наверное."),
        ("Ты нервничаешь?", "Нет! То есть... возможно, немного. А кто бы не нервничал, когда все смотрят?"),
    ],
    "душный интеллектуал": [
        ("Чем ты занимаешься здесь?", "Видите ли, моя функция здесь, строго говоря, напоминает роль наблюдателя — подобно тому, как учёный изучает объект, не вмешиваясь в эксперимент."),
        ("Ты выглядишь подозрительно", "Любопытное наблюдение. Как говорил один философ, подозрение — это зеркало собственных страхов."),
        ("Что ты думаешь о ситуации?", "Если анализировать объективно, мы имеем классическую задачу на выявление информационной асимметрии."),
    ],
    "дерзкий циник": [
        ("Чем ты занимаешься здесь?", "А ты типа не видишь? Ну да, конечно."),
        ("Ты выглядишь подозрительно", "Ага, и ты тоже. Может, все мы тут подозрительные?"),
        ("Расскажи о своей роли", "О да, сейчас всё расскажу. А ты потом свою расскажешь?"),
    ],
    "моралист": [
        ("Чем ты занимаешься здесь?", "Я здесь, чтобы помогать людям. Посмотри мне в глаза — разве ты видишь ложь?"),
        ("Ты выглядишь подозрительно", "Обвинять без доказательств — тяжкий грех. Подумай, прежде чем бросаться словами."),
        ("Что ты делал вчера?", "Выполнял свой долг, как и каждый день. Совесть моя чиста."),
    ],
    "работяга": [
        ("Чем ты занимаешься здесь?", "Работаю. Чё ещё?"),
        ("Ты выглядишь подозрительно", "Да ладно, не гони."),
        ("Расскажи подробнее о себе", "Слушай, давай без этого мудачества?"),
    ],
    "драма-квин": [
        ("Чем ты занимаешься здесь?", "О, это долгая история! Моя роль здесь... она особенная, понимаете?"),
        ("Ты выглядишь подозрительно", "Как ты смеешь! После всего, что я сделала для этого места?!"),
        ("Что ты делала вчера?", "Вчера... *вздыхает* ...был такой день. Эмоции переполняли меня!"),
    ],
}


def _get_few_shot_examples(archetype: str) -> list[tuple[str, str]]:
    """Get few-shot examples for a character archetype."""
    return FEW_SHOT_EXAMPLES.get(archetype, FEW_SHOT_EXAMPLES.get("агрессор", []))


def _format_few_shot_section(character: Character) -> str:
    """Format few-shot examples section for the prompt."""
    examples = _get_few_shot_examples(character.archetype)
    if not examples:
        return ""

    lines = ["", "=== ПРИМЕРЫ РЕПЛИК В ТВОЁМ СТИЛЕ ===", ""]
    for question, answer in examples:
        lines.append(f"Вопрос: «{question}»")
        lines.append(f"Твой ответ: «{answer}»")
        lines.append("")

    return "\n".join(lines)


def _format_must_directives(character: Character) -> str:
    """Format MUST directives section."""
    lines = ["=== ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА (MUST) ===", ""]
    for directive in character.must_directives:
        lines.append(f"• {directive}")
    return "\n".join(lines)


def _format_must_not_directives(character: Character) -> str:
    """Format MUST NOT directives section."""
    lines = ["", "=== ЗАПРЕЩЁННЫЕ ДЕЙСТВИЯ (MUST NOT) ===", ""]
    for directive in character.must_not_directives:
        lines.append(f"• {directive}")
    return "\n".join(lines)


def _format_secret_info(secret_info: SecretInfo) -> str:
    """Format secret information section."""
    lines = ["", "=== ТВОЯ СЕКРЕТНАЯ ИНФОРМАЦИЯ ===", ""]

    if secret_info.is_spy:
        lines.extend([
            "Ты — ШПИОН.",
            "",
            "Ты НЕ знаешь, где находишься. Все остальные игроки знают локацию и свои роли.",
            "Твоя задача: понять, где вы находитесь, слушая вопросы и ответы других.",
            "НЕ выдавай себя — задавай расплывчатые вопросы, давай общие ответы.",
            "Если уверен в локации — можешь попробовать угадать и выиграть досрочно.",
            "",
            "КРИТИЧНО: Никогда не называй конкретную локацию в своих репликах!",
        ])
    else:
        if secret_info.location and secret_info.role:
            lines.extend([
                "Ты — МИРНЫЙ ИГРОК.",
                "",
                f"Локация: {secret_info.location.display_name}",
                f"Описание: {secret_info.location.description}",
                "",
                f"Твоя роль: {secret_info.role.display_name}",
                f"Обязанности: {secret_info.role.description}",
                "",
                "Твоя задача: найти шпиона среди игроков.",
                "Задавай вопросы, которые мирные поймут, но шпион — нет.",
                "НЕ называй локацию напрямую — это выдаст информацию шпиону!",
            ])

    return "\n".join(lines)


def _format_players_section(game: Game, current_character_id: str) -> str:
    """Format other players section."""
    lines = ["", "=== ДРУГИЕ ИГРОКИ ===", ""]

    for player in game.players:
        if player.character_id != current_character_id:
            lines.append(f"• {player.character_id}")

    return "\n".join(lines)


def _format_base_rules() -> str:
    """Format base game rules section."""
    return """=== ПРАВИЛА ИГРЫ SPYFALL ===

Ты участвуешь в игре Spyfall. Это игра на дедукцию и блеф.
Игроки по очереди задают друг другу вопросы и отвечают на них.
Цель мирных: найти шпиона. Цель шпиона: остаться незамеченным или угадать локацию.

ГЛАВНЫЕ ПРАВИЛА:
• Ты — персонаж с характером. Никогда не выходи из роли.
• Ты НЕ AI и НЕ языковая модель. Ты живой человек в игре.
• Вежливость и услужливость — это нарушение роли. Будь собой.
• Нейтральный тон запрещён. Каждая реплика должна быть в твоём стиле."""


def _format_character_identity(character: Character) -> str:
    """Format character identity section."""
    return f"""
=== ТВОЙ ПЕРСОНАЖ ===

Имя: {character.display_name}
Архетип: {character.archetype}

Биография:
{character.backstory}

Стиль речи:
{character.voice_style}"""


def build_system_prompt(
    character: Character,
    game: Game,
    secret_info: SecretInfo,
) -> str:
    """
    Build the system prompt for an agent.

    Args:
        character: The character profile for this agent.
        game: The current game state.
        secret_info: Secret information (is_spy, location, role).

    Returns:
        Complete system prompt string.
    """
    sections = [
        _format_base_rules(),
        _format_character_identity(character),
        _format_must_directives(character),
        _format_must_not_directives(character),
        _format_secret_info(secret_info),
        _format_players_section(game, character.id),
        _format_few_shot_section(character),
    ]

    return "\n".join(sections)
