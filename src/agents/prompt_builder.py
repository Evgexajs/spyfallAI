"""Prompt builder for SpyfallAI agents."""

from dataclasses import dataclass
from typing import Optional

from src.models.character import Character, ReactionType
from src.models.location import Location, Role
from src.models.game import Game, Player, Turn


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
                "",
                "=== ПРИМЕРЫ ВОПРОСОВ ===",
                "",
                "ПЛОХИЕ вопросы (ЗАПРЕЩЕНО — выдают локацию шпиону):",
                "✗ «Это больница?» — прямое название локации",
                "✗ «Ты работаешь хирургом?» — прямое название роли",
                "✗ «Мы в ресторане или в кафе?» — перечисление локаций",
                "✗ «Здесь подают еду?» — слишком очевидный намёк",
                "",
                "ХОРОШИЕ вопросы (помогают найти шпиона):",
                "✓ «Как часто ты здесь бываешь?» — общий, но осмысленный",
                "✓ «Что тебе нравится в твоей работе?» — про деятельность, не локацию",
                "✓ «Какой у тебя был самый сложный день?» — косвенная проверка роли",
                "✓ «Как ты относишься к шуму?» — намёк на атмосферу без названия",
                "✓ «Что бы ты изменил в этом месте?» — шпион не знает, что менять",
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
• Нейтральный тон запрещён. Каждая реплика должна быть в твоём стиле.
• ЗАПРЕЩЕНО: мат, реальные оскорбления, унижения по полу/расе/религии. Только игровое давление в рамках ролей."""


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


REACTION_TYPE_DESCRIPTIONS = {
    ReactionType.PRESSURE_WITH_SHARPER_QUESTION: "задать резкий уточняющий вопрос, надавить",
    ReactionType.MOCK_WITH_DRY_SARCASM: "высмеять с сухим сарказмом",
    ReactionType.MORALIZE_AND_ACCUSE: "морализировать и обвинить",
    ReactionType.PANIC_AND_DERAIL: "нервно отреагировать, увести тему",
    ReactionType.POINT_OUT_INCONSISTENCY: "указать на противоречие",
    ReactionType.DEFLECT_SUSPICION_TO_ANOTHER: "перевести подозрение на другого",
    ReactionType.SHORT_DISMISSIVE_JAB: "коротко обрубить, отмахнуться",
}


def build_intervention_micro_prompt(
    character: Character,
    answer_turn: Turn,
    reaction_type: ReactionType,
) -> str:
    """Build micro-prompt asking if character wants to intervene."""
    reaction_desc = REACTION_TYPE_DESCRIPTIONS.get(
        reaction_type, "отреагировать в своём стиле"
    )

    return f"""Ты — {character.display_name} ({character.archetype}).

Только что {answer_turn.speaker_id} ответил: «{answer_turn.content}»

Это показалось тебе подозрительным. Твой стиль реакции: {reaction_desc}.

Хочешь вмешаться? Ответь ТОЛЬКО "да" или "нет"."""


def build_intervention_content_prompt(
    character: Character,
    game: Game,
    secret_info: SecretInfo,
    answer_turn: Turn,
    reaction_type: ReactionType,
) -> str:
    """Build prompt for generating intervention content."""
    reaction_desc = REACTION_TYPE_DESCRIPTIONS.get(
        reaction_type, "отреагировать в своём стиле"
    )

    base_prompt = build_system_prompt(character, game, secret_info)

    return f"""{base_prompt}

=== ВМЕШАТЕЛЬСТВО ===

Только что {answer_turn.speaker_id} ответил: «{answer_turn.content}»

Ты решил вмешаться. Твоя реакция: {reaction_desc}.

Напиши ОДНУ фразу вмешательства в своём стиле. Не более 1-2 предложений."""


def build_spy_confidence_check_prompt(
    character: Character,
    conversation_summary: str,
) -> str:
    """Build micro-prompt for spy confidence check.

    Args:
        character: The spy's character profile.
        conversation_summary: Full conversation context (compressed + recent).

    Returns:
        Prompt asking spy to assess their confidence level.
    """
    return f"""Ты — {character.display_name} ({character.archetype}). Ты — ШПИОН в этой игре.

Ты слушал разговор и пытаешься понять, где вы находитесь.
Ищи подсказки: упоминания еды, напитков, музыки, одежды, оборудования, действий — всё, что может указать на место.

Разговор:
{conversation_summary}

Оцени свою уверенность в понимании локации:
- "no_idea" — понятия не имею, где мы
- "few_guesses" — есть несколько догадок, но не уверен
- "confident" — уверен, знаю локацию (есть явные подсказки)

Ответь ОДНИМ словом: no_idea, few_guesses или confident."""


def build_spy_guess_prompt(
    character: Character,
    conversation_summary: str,
    available_locations: list[Location],
) -> str:
    """Build prompt for spy to guess the location.

    Args:
        character: The spy's character profile.
        conversation_summary: Full conversation context (compressed + recent).
        available_locations: All available locations to choose from.

    Returns:
        Prompt asking spy to name the location.
    """
    locations_list = "\n".join(
        f"• {loc.id} — {loc.display_name}" for loc in available_locations
    )

    return f"""Ты — {character.display_name} ({character.archetype}). Ты — ШПИОН в этой игре.

Ты уверен, что понял, где находятся игроки. Это твой шанс угадать локацию и выиграть!

Разговор:
{conversation_summary}

Доступные локации:
{locations_list}

Какая локация? Напиши ТОЛЬКО id локации (например: hospital, airplane, restaurant).
Одно слово, без пояснений."""


def build_defense_speech_prompt(
    character: Character,
    game: Game,
    secret_info: SecretInfo,
    votes_received: int,
    max_sentences: int = 2,
) -> str:
    """Build prompt for a defense speech during pre-final-vote defense phase.

    Args:
        character: The defending character profile.
        game: The current game state.
        secret_info: Secret information (is_spy, location, role).
        votes_received: How many votes this character received.
        max_sentences: Maximum allowed sentences in defense.

    Returns:
        Prompt for generating a defense speech.
    """
    base_prompt = build_system_prompt(character, game, secret_info)

    voters_against = []
    if game.preliminary_vote_result:
        for voter_id, target_id in game.preliminary_vote_result.items():
            if target_id == character.id:
                voters_against.append(voter_id)

    voters_str = ", ".join(voters_against) if voters_against else "несколько игроков"

    return f"""{base_prompt}

=== ЗАЩИТНАЯ РЕЧЬ ===

{votes_received} игрок(ов) проголосовали против тебя: {voters_str}.

Теперь у тебя есть шанс защититься перед финальным голосованием.
Убеди всех, что ты НЕ шпион. Оставайся в образе своего персонажа!

ВАЖНО:
- Говори в своём стиле ({character.archetype})
- Не более {max_sentences} предложений
- Обращайся ко всем игрокам
- Не признавай, что ты шпион (даже если это так)

Напиши свою защитную речь:"""
