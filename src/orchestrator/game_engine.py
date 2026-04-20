"""Game orchestrator for SpyfallAI - setup and game flow management."""

import inspect
import json
import logging
import os
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from uuid import uuid4

from src.agents import (
    SecretInfo,
    build_defense_characteristic_check_prompt,
    build_defense_speech_prompt,
    build_final_vote_with_defense_prompt,
    build_intervention_content_prompt,
    build_intervention_micro_prompt,
    build_spy_confidence_check_prompt,
    build_spy_guess_prompt,
    build_system_prompt,
)
from src.llm import (
    CostExceededError,
    LLMConfig,
    LLMProvider,
    LLMResponse,
    create_provider,
)
from src.models import (
    Character,
    ConfidenceEntry,
    ConfidenceLevel,
    DefenseSpeech,
    Game,
    GameConfig,
    GameOutcome,
    GamePhase,
    Location,
    PhaseEntry,
    Player,
    SpyRiskTolerance,
    Turn,
    TurnType,
    VoteChange,
)
from src.triggers import TriggerChecker, TriggerResult, VoteTriggerChecker

SPEECH_DELAY_MULTIPLIER = float(os.environ.get("SPEECH_DELAY_MULTIPLIER", "0.03"))
CONTEXT_COMPRESSION_AFTER_N_TURNS = int(os.environ.get("CONTEXT_COMPRESSION_AFTER_N_TURNS", "10"))
CONTEXT_KEEP_LAST_K_TURNS = int(os.environ.get("CONTEXT_KEEP_LAST_K_TURNS", "6"))
MAX_PARTY_COST_USD = float(os.environ.get("MAX_PARTY_COST_USD", "3.0"))
MAX_QUESTION_REROLL_ATTEMPTS = int(os.environ.get("MAX_QUESTION_REROLL_ATTEMPTS", "3"))

# Defense phase settings (CR-001)
DEFENSE_MIN_VOTES_TO_QUALIFY = int(os.environ.get("DEFENSE_MIN_VOTES_TO_QUALIFY", "2"))
DEFENSE_SPEECH_MAX_SENTENCES = int(os.environ.get("DEFENSE_SPEECH_MAX_SENTENCES", "2"))
DEFENSE_ALLOW_ABSTAIN = os.environ.get("DEFENSE_ALLOW_ABSTAIN", "true").lower() in ("true", "1", "yes")
MAX_RE_VOTES = 2  # Maximum number of re-votes when leader changes

logger = logging.getLogger(__name__)


async def _call_callback(callback, *args):
    """Call a callback, awaiting if it's async."""
    if callback is None:
        return
    result = callback(*args)
    if inspect.iscoroutine(result):
        await result


def calculate_display_delay_ms(content: str) -> int:
    """Calculate display delay in milliseconds based on content length.

    Formula: length * SPEECH_DELAY_MULTIPLIER + random(0.2s, 0.6s)
    """
    base_delay = len(content) * SPEECH_DELAY_MULTIPLIER
    random_delay = random.uniform(0.2, 0.6)
    total_seconds = base_delay + random_delay
    return int(total_seconds * 1000)


def _track_usage_and_check_cost(game: Game, response: LLMResponse) -> None:
    """Track token usage from LLM response and check cost limit.

    Args:
        game: Game to update token usage.
        response: LLM response with usage info.

    Raises:
        CostExceededError: If total cost exceeds MAX_PARTY_COST_USD.
    """
    cost = response.calculate_cost()
    game.token_usage.add_usage(
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost=cost,
    )

    if game.token_usage.total_cost_usd >= MAX_PARTY_COST_USD:
        raise CostExceededError(
            current_cost=game.token_usage.total_cost_usd,
            max_cost=MAX_PARTY_COST_USD,
        )


def _parse_json_response(raw_response: str) -> dict:
    """Parse JSON response from LLM.

    With json_mode=True, response should be clean JSON.
    Falls back to extracting JSON if wrapped in markdown.
    """
    raw_response = raw_response.strip()

    # Try direct parse first (expected with json_mode=True)
    try:
        return json.loads(raw_response)
    except json.JSONDecodeError:
        pass

    # Fallback: extract JSON from markdown wrapper
    json_start = raw_response.find("{")
    json_end = raw_response.rfind("}") + 1
    if json_start != -1 and json_end > json_start:
        try:
            return json.loads(raw_response[json_start:json_end])
        except json.JSONDecodeError:
            pass

    # Last resort fallback
    logger.warning(f"Failed to parse JSON response: {raw_response[:100]}")
    return {}


def _clean_content(content: str) -> str:
    """Remove system artifacts from content like [player_id → target_id]."""
    import re
    # Remove patterns like [boris_molot → zoya] or [boris_molot]
    content = re.sub(r'\[[\w_]+(?:\s*→\s*[\w_]+)?\]\s*', '', content)
    return content.strip()


def load_locations(locations_path: Optional[Path] = None) -> list[Location]:
    """Load locations from JSON file."""
    if locations_path is None:
        locations_path = Path(__file__).parent.parent.parent / "locations.json"

    with open(locations_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return [Location(**loc) for loc in data]


def get_location_by_id(location_id: str, locations_path: Optional[Path] = None) -> Location:
    """Get a specific location by ID."""
    locations = load_locations(locations_path)
    for loc in locations:
        if loc.id == location_id:
            return loc
    raise ValueError(f"Location '{location_id}' not found")


def setup_game(
    characters: list[Character],
    location_id: str,
    duration_minutes: int = 20,
    max_questions: int = 50,
    main_model: str = "gpt-4o",
    utility_model: str = "gpt-4o-mini",
) -> Game:
    """Set up a new game with characters and location.

    Args:
        characters: List of Character objects to participate in the game (min 3).
        location_id: ID of the location to use.
        duration_minutes: Game duration in minutes.
        max_questions: Maximum questions before forced vote.
        main_model: Main LLM model for replies.
        utility_model: Utility LLM model for checks.

    Returns:
        Initialized Game object ready for main_round phase.

    Raises:
        ValueError: If less than 3 characters or location not found.
    """
    if len(characters) < 3:
        raise ValueError("At least 3 characters required for a game")

    location = get_location_by_id(location_id)

    if len(location.roles) < len(characters) - 1:
        raise ValueError(
            f"Location '{location_id}' has only {len(location.roles)} roles, "
            f"but need at least {len(characters) - 1} for {len(characters)} players"
        )

    spy_character = random.choice(characters)

    available_roles = list(location.roles)
    random.shuffle(available_roles)

    players: list[Player] = []
    role_index = 0

    for char in characters:
        if char.id == spy_character.id:
            players.append(Player(
                character_id=char.id,
                role_id=None,
                is_spy=True,
            ))
        else:
            players.append(Player(
                character_id=char.id,
                role_id=available_roles[role_index].id,
                is_spy=False,
            ))
            role_index += 1

    now = datetime.now()

    game = Game(
        id=uuid4(),
        started_at=now,
        config=GameConfig(
            duration_minutes=duration_minutes,
            players_count=len(characters),
            max_questions=max_questions,
            main_model=main_model,
            utility_model=utility_model,
        ),
        location_id=location_id,
        players=players,
        spy_id=spy_character.id,
        turns=[],
        spy_confidence_log=[],
        triggered_events=[],
        phase_transitions=[
            PhaseEntry(
                timestamp=now,
                from_phase=None,
                to_phase=GamePhase.SETUP,
                reason="Game initialized",
            )
        ],
        outcome=None,
    )

    return game


def _transition_phase(
    game: Game,
    to_phase: GamePhase,
    reason: str,
    status: Optional[str] = None,
    initiator_id: Optional[str] = None,
) -> None:
    """Record a phase transition in the game."""
    current_phase = game.phase_transitions[-1].to_phase if game.phase_transitions else None
    game.phase_transitions.append(
        PhaseEntry(
            timestamp=datetime.now(),
            from_phase=current_phase,
            to_phase=to_phase,
            reason=reason,
            status=status,
            initiator_id=initiator_id,
        )
    )


def _get_secret_info(game: Game, player: Player) -> SecretInfo:
    """Build SecretInfo for a player."""
    if player.is_spy:
        return SecretInfo(is_spy=True)

    location = get_location_by_id(game.location_id)
    role = None
    if player.role_id:
        for r in location.roles:
            if r.id == player.role_id:
                role = r
                break
    return SecretInfo(is_spy=False, location=location, role=role)


def _check_for_location_leak(content: str, speaker_id: str, game: Game) -> bool:
    """Check if spy accidentally mentioned location in their reply.

    Args:
        content: The text content to check.
        speaker_id: ID of the speaker.
        game: Current game state.

    Returns:
        True if spy leaked the location, False otherwise.
    """
    if speaker_id != game.spy_id:
        return False

    location = get_location_by_id(game.location_id)
    content_lower = content.lower()

    if location.display_name.lower() in content_lower:
        return True

    if location.id.lower() in content_lower:
        return True

    return False


def _check_for_direct_location_question(
    content: str,
    speaker_id: str,
    game: Game,
    all_locations: list[Location],
) -> bool:
    """Check if civilian asked a direct question about the location.

    Detects patterns like 'это больница?' or 'мы в ресторане?' that would
    give away location information to the spy.

    Args:
        content: The question text to check.
        speaker_id: ID of the questioner.
        game: Current game state.
        all_locations: List of all available locations.

    Returns:
        True if direct location question detected, False otherwise.
    """
    if speaker_id == game.spy_id:
        return False

    content_lower = content.lower()

    current_location = get_location_by_id(game.location_id)
    if current_location.display_name.lower() in content_lower:
        return True
    if current_location.id.lower() in content_lower:
        return True

    for loc in all_locations:
        if loc.display_name.lower() in content_lower:
            return True
        if loc.id.lower() in content_lower:
            return True

    for role in current_location.roles:
        if role.display_name.lower() in content_lower:
            return True

    return False


def _build_conversation_history(game: Game) -> list[dict]:
    """Build conversation history as chat messages from game turns."""
    messages = []
    for turn in game.turns:
        if turn.type in (TurnType.QUESTION, TurnType.ANSWER, TurnType.INTERVENTION):
            speaker_name = turn.speaker_id
            addressee = turn.addressee_id
            prefix = f"[{speaker_name} → {addressee}]"
            messages.append({
                "role": "user",
                "content": f"{prefix} {turn.content}",
            })
    return messages


def _get_conversational_turns(game: Game) -> list[Turn]:
    """Get only conversational turns (questions, answers, interventions)."""
    return [t for t in game.turns if t.type in (TurnType.QUESTION, TurnType.ANSWER, TurnType.INTERVENTION)]


def _turns_to_messages(turns: list[Turn]) -> list[dict]:
    """Convert turns to chat messages format."""
    messages = []
    for turn in turns:
        prefix = f"[{turn.speaker_id} → {turn.addressee_id}]"
        messages.append({
            "role": "user",
            "content": f"{prefix} {turn.content}",
        })
    return messages


async def _compress_history_with_llm(
    turns: list[Turn],
    provider: LLMProvider,
    model: str,
    game: Game,
) -> str:
    """Compress conversation history using utility LLM model.

    Args:
        turns: List of turns to compress.
        provider: LLM provider for the compression.
        model: Model to use (should be utility model).
        game: Game to track token usage.

    Returns:
        Compressed summary of the conversation.
    """
    if not turns:
        return ""

    conversation_text = "\n".join([
        f"[{t.speaker_id} → {t.addressee_id}] {t.content}"
        for t in turns
    ])

    prompt = f"""Сделай краткий конспект этого диалога из игры Spyfall (150-200 слов).
Сохрани ключевую информацию:
- Кто кого подозревает и почему
- Важные обвинения и контраргументы
- Подозрительные или уклончивые ответы
- Любые намёки на локацию (осторожно, могут быть ложными)

Диалог:
{conversation_text}

Конспект:"""

    response = await provider.complete(
        messages=[{"role": "user", "content": prompt}],
        model=model,
        temperature=0.3,
        max_tokens=300,
    )

    _track_usage_and_check_cost(game, response)
    return response.content.strip()


async def _build_compressed_conversation_history(
    game: Game,
    provider: LLMProvider,
) -> list[dict]:
    """Build conversation history with compression for long games.

    After N turns, compresses older turns into a summary and keeps
    the last K turns in full. This saves tokens on long games.

    Args:
        game: Current game state.
        provider: LLM provider for compression.

    Returns:
        List of chat messages (possibly with compressed prefix).
    """
    conv_turns = _get_conversational_turns(game)
    total_turns = len(conv_turns)

    if total_turns < CONTEXT_COMPRESSION_AFTER_N_TURNS:
        return _turns_to_messages(conv_turns)

    turns_to_compress = total_turns - CONTEXT_KEEP_LAST_K_TURNS

    if turns_to_compress <= 0:
        return _turns_to_messages(conv_turns)

    needs_compression = (
        game.compressed_history is None or
        game.compression_checkpoint is None or
        turns_to_compress > game.compression_checkpoint
    )

    if needs_compression:
        old_turns = conv_turns[:turns_to_compress]
        compressed = await _compress_history_with_llm(
            turns=old_turns,
            provider=provider,
            model=game.config.utility_model,
            game=game,
        )
        game.compressed_history = compressed
        game.compression_checkpoint = turns_to_compress

    recent_turns = conv_turns[turns_to_compress:]
    recent_messages = _turns_to_messages(recent_turns)

    if game.compressed_history:
        compressed_message = {
            "role": "user",
            "content": f"[КОНСПЕКТ ПРЕДЫДУЩИХ ХОДОВ]\n{game.compressed_history}\n[КОНЕЦ КОНСПЕКТА]",
        }
        return [compressed_message] + recent_messages

    return recent_messages


def _get_character_by_id(characters: list[Character], char_id: str) -> Character:
    """Find character by ID."""
    for char in characters:
        if char.id == char_id:
            return char
    raise ValueError(f"Character '{char_id}' not found")


def _select_target(players: list[Player], questioner_id: str, exclude_id: Optional[str] = None) -> str:
    """Select a random target for the question.

    Args:
        players: List of players.
        questioner_id: ID of the person asking (excluded).
        exclude_id: ID of person who just asked the questioner (excluded to prevent ping-pong).
    """
    excluded = {questioner_id}
    if exclude_id:
        excluded.add(exclude_id)
    candidates = [p.character_id for p in players if p.character_id not in excluded]
    if not candidates:
        # Fallback if everyone is excluded (shouldn't happen with 3+ players)
        candidates = [p.character_id for p in players if p.character_id != questioner_id]
    return random.choice(candidates)


async def _ask_to_intervene(
    trigger_result: TriggerResult,
    answer_turn: Turn,
    characters: list[Character],
    provider: LLMProvider,
    model: str,
    game: Game,
) -> bool:
    """Ask a character if they want to intervene. Returns True if yes."""
    character = _get_character_by_id(characters, trigger_result.character_id)
    id_to_name = {c.id: c.display_name for c in characters}

    prompt = build_intervention_micro_prompt(
        character=character,
        answer_turn=answer_turn,
        reaction_type=trigger_result.reaction_type,
        id_to_name=id_to_name,
    )

    response = await provider.complete(
        messages=[{"role": "user", "content": prompt}],
        model=model,
        temperature=0.7,
        max_tokens=20,
        json_mode=True,
    )

    _track_usage_and_check_cost(game, response)
    parsed = _parse_json_response(response.content.strip())
    return parsed.get("intervene", False) is True


async def _generate_intervention_content(
    trigger_result: TriggerResult,
    answer_turn: Turn,
    game: Game,
    characters: list[Character],
    provider: LLMProvider,
) -> tuple[str, str]:
    """Generate the intervention content for a character.

    Returns:
        Tuple of (cleaned_content, raw_response)
    """
    character = _get_character_by_id(characters, trigger_result.character_id)
    player = next(p for p in game.players if p.character_id == character.id)
    secret_info = _get_secret_info(game, player)
    id_to_name = {c.id: c.display_name for c in characters}

    prompt = build_intervention_content_prompt(
        character=character,
        game=game,
        secret_info=secret_info,
        answer_turn=answer_turn,
        reaction_type=trigger_result.reaction_type,
        id_to_name=id_to_name,
    )

    history = await _build_compressed_conversation_history(game, provider)
    messages = [
        {"role": "system", "content": prompt},
        *history,
    ]

    response = await provider.complete(
        messages=messages,
        model=game.config.main_model,
        temperature=0.9,
        max_tokens=100,
    )

    _track_usage_and_check_cost(game, response)
    raw_response = response.content
    cleaned_content = _clean_content(raw_response.strip())
    return cleaned_content, raw_response


async def _check_spy_confidence(
    game: Game,
    characters: list[Character],
    provider: LLMProvider,
    answer_count: int,
    last_check_answer_count: int,
) -> tuple[Optional[ConfidenceEntry], int]:
    """Check spy's confidence level every N answers.

    Args:
        game: Current game state.
        characters: List of characters.
        provider: LLM provider for the check.
        answer_count: Current number of answers in the game.
        last_check_answer_count: Answer count at last check.

    Returns:
        Tuple of (ConfidenceEntry or None, updated last_check_answer_count).
    """
    check_interval = int(os.getenv("SPY_CONFIDENCE_CHECK_EVERY_N", "3"))

    if answer_count - last_check_answer_count < check_interval:
        return None, last_check_answer_count

    spy_character = _get_character_by_id(characters, game.spy_id)

    # Build full conversation context for spy analysis
    history_messages = await _build_compressed_conversation_history(game, provider)
    conversation_summary = "\n".join(msg["content"] for msg in history_messages)

    prompt = build_spy_confidence_check_prompt(
        character=spy_character,
        conversation_summary=conversation_summary,
    )

    response = await provider.complete(
        messages=[{"role": "user", "content": prompt}],
        model=game.config.main_model,
        temperature=0.5,
        max_tokens=300,
        json_mode=True,
    )

    _track_usage_and_check_cost(game, response)
    raw_response = response.content.strip()

    # Parse JSON response
    parsed = _parse_json_response(raw_response)
    hints = parsed.get("hints")
    location_guess = parsed.get("location_guess")
    reasoning = parsed.get("reasoning")
    confidence_str = str(parsed.get("confidence", "")).lower()

    if "confident" in confidence_str:
        level = ConfidenceLevel.CONFIDENT
    elif "few_guesses" in confidence_str or "few" in confidence_str:
        level = ConfidenceLevel.FEW_GUESSES
    else:
        level = ConfidenceLevel.NO_IDEA

    entry = ConfidenceEntry(
        turn_number=max(1, len(game.turns)),
        timestamp=datetime.now(),
        level=level,
        hints=hints,
        location_guess=location_guess,
        reasoning=reasoning,
        raw_response=raw_response,
    )

    return entry, answer_count


async def _ask_spy_to_guess(
    game: Game,
    characters: list[Character],
    provider: LLMProvider,
) -> Optional[str]:
    """Ask spy to guess the location.

    Args:
        game: Current game state.
        characters: List of characters.
        provider: LLM provider for the guess.

    Returns:
        Location ID guessed by spy, or None if parsing failed.
    """
    spy_character = _get_character_by_id(characters, game.spy_id)
    available_locations = load_locations()

    # Build full conversation context for spy to analyze
    history_messages = await _build_compressed_conversation_history(game, provider)
    conversation_summary = "\n".join(msg["content"] for msg in history_messages)

    prompt = build_spy_guess_prompt(
        character=spy_character,
        conversation_summary=conversation_summary,
        available_locations=available_locations,
    )

    response = await provider.complete(
        messages=[{"role": "user", "content": prompt}],
        model=game.config.utility_model,
        temperature=0.3,
        max_tokens=100,
        json_mode=True,
    )

    _track_usage_and_check_cost(game, response)
    parsed = _parse_json_response(response.content.strip())
    location_id = parsed.get("location_id")

    # Validate location_id is valid
    valid_ids = {loc.id for loc in available_locations}
    if location_id and location_id in valid_ids:
        return location_id

    return None


async def _generate_spy_triumph_speech(
    game: Game,
    spy_character: Character,
    location_name: str,
    provider: LLMProvider,
) -> str:
    """Generate a triumphant speech for the spy after correctly guessing the location."""
    prompt = f"""Ты — {spy_character.display_name} ({spy_character.archetype}).
Ты был ШПИОНОМ и только что УГАДАЛ локацию: {location_name}!

Произнеси победную реплику (1-2 предложения) в своём стиле.
Можешь подколоть остальных игроков, похвастаться или сказать что-то характерное для твоего персонажа.

Стиль речи: {spy_character.voice_style}

Ответь ТОЛЬКО репликой, без кавычек и пояснений."""

    response = await provider.complete(
        messages=[{"role": "user", "content": prompt}],
        model=game.config.utility_model,
        temperature=0.9,
        max_tokens=100,
    )

    _track_usage_and_check_cost(game, response)
    return _clean_content(response.content.strip())


async def _generate_spy_defeat_speech(
    game: Game,
    spy_character: Character,
    guessed_location: str,
    actual_location: str,
    provider: LLMProvider,
) -> str:
    """Generate a defeat speech for the spy after incorrectly guessing the location."""
    prompt = f"""Ты — {spy_character.display_name} ({spy_character.archetype}).
Ты был ШПИОНОМ и только что ОШИБСЯ с локацией!
Ты сказал "{guessed_location}", а на самом деле это был: {actual_location}.

Произнеси реплику разочарования/удивления (1-2 предложения) в своём стиле.
Можешь посетовать, удивиться, или сказать что-то характерное для персонажа.

Стиль речи: {spy_character.voice_style}

Ответь ТОЛЬКО репликой, без кавычек и пояснений."""

    response = await provider.complete(
        messages=[{"role": "user", "content": prompt}],
        model=game.config.utility_model,
        temperature=0.9,
        max_tokens=100,
    )

    _track_usage_and_check_cost(game, response)
    return _clean_content(response.content.strip())


async def run_main_round(
    game: Game,
    characters: list[Character],
    provider: Optional[LLMProvider] = None,
    on_turn: Optional[callable] = None,
    on_typing: Optional[callable] = None,
) -> Game:
    """Run the main question-answer round of the game.

    Args:
        game: Initialized Game object from setup_game().
        characters: List of Character objects participating.
        provider: Optional LLM provider. If None, creates one from config.
        on_turn: Optional callback called after each turn (question, answer, intervention).
        on_typing: Optional callback called before LLM generation starts with speaker_id.

    Returns:
        Updated Game object with turns recorded.
    """
    if provider is None:
        llm_config = LLMConfig()
        provider, _ = create_provider(llm_config, role="main")

    _transition_phase(game, GamePhase.MAIN_ROUND, "Main round started")

    trigger_checker = TriggerChecker(characters)
    vote_trigger_checker = VoteTriggerChecker(characters)
    all_locations = load_locations()

    player_ids = [p.character_id for p in game.players]
    current_questioner = random.choice(player_ids)
    previous_questioner: Optional[str] = None  # Track who asked the current questioner

    # Build id -> display_name mapping for prompts
    id_to_name = {c.id: c.display_name for c in characters}

    start_time = game.started_at
    duration = timedelta(minutes=game.config.duration_minutes)
    question_count = 0
    answer_count = 0
    last_check_answer_count = 0
    consecutive_confident_count = 0  # Track consecutive "confident" checks for moderate risk tolerance

    while True:
        if datetime.now() - start_time >= duration:
            break
        if question_count >= game.config.max_questions:
            break

        # Exclude previous questioner to prevent ping-pong (A asks B, B asks A)
        target_id = _select_target(game.players, current_questioner, exclude_id=previous_questioner)
        target_char = _get_character_by_id(characters, target_id)

        questioner_char = _get_character_by_id(characters, current_questioner)
        questioner_player = next(p for p in game.players if p.character_id == current_questioner)
        questioner_secret = _get_secret_info(game, questioner_player)
        questioner_prompt = build_system_prompt(questioner_char, game, questioner_secret, id_to_name)

        history = await _build_compressed_conversation_history(game, provider)

        # Build list of other players for suspect_id
        other_players = [p.character_id for p in game.players if p.character_id != current_questioner]
        other_players_str = ", ".join([id_to_name.get(p, p) for p in other_players])

        other_players_json = ", ".join(f'"{p}"' for p in other_players)
        question_instruction = f"""Ты — {questioner_char.display_name}. Задай вопрос игроку {target_char.display_name}.

Ответь JSON:
{{
  "content": "твой вопрос",
  "wants_vote": true | false,
  "suspect_id": ID из [{other_players_json}] | null
}}

Правила:
- content: КОНКРЕТНЫЙ вопрос про локацию (оборудование, звуки, запахи, одежду, действия)
- wants_vote: true если хочешь СЕЙЧАС начать голосование (уверен кто шпион), иначе false
- suspect_id: если wants_vote=true укажи ID подозреваемого, иначе null"""
        messages = [
            {"role": "system", "content": questioner_prompt},
            *history,
            {"role": "user", "content": question_instruction},
        ]

        reroll_count = 0
        question_text = ""
        question_wants_vote = False
        question_suspect_id = None

        if on_typing:
            await on_typing(current_questioner)

        for attempt in range(MAX_QUESTION_REROLL_ATTEMPTS + 1):
            question_response = await provider.complete(
                messages=messages,
                model=game.config.main_model,
                temperature=0.9,
                max_tokens=200,
                json_mode=True,
            )
            _track_usage_and_check_cost(game, question_response)

            # Parse JSON response
            question_raw_response = question_response.content
            parsed = _parse_json_response(question_raw_response)
            question_text = _clean_content(parsed.get("content", question_raw_response))
            question_wants_vote = parsed.get("wants_vote", False)
            question_suspect_id = parsed.get("suspect_id")

            is_direct_question = _check_for_direct_location_question(
                question_text, current_questioner, game, all_locations
            )

            if is_direct_question and attempt < MAX_QUESTION_REROLL_ATTEMPTS:
                reroll_count += 1
                logger.debug(
                    "Direct location question detected from %s (attempt %d/%d): %s",
                    current_questioner,
                    attempt + 1,
                    MAX_QUESTION_REROLL_ATTEMPTS,
                    question_text[:50],
                )
                continue

            if is_direct_question:
                logger.warning(
                    "Direct location question from %s after %d rerolls, using anyway: %s",
                    current_questioner,
                    reroll_count,
                    question_text[:50],
                )
            break

        if reroll_count > 0:
            logger.info(
                "Question from %s required %d reroll(s) to avoid direct location mention",
                current_questioner,
                reroll_count,
            )

        # Check if questioner wants to trigger voting
        if question_wants_vote and question_suspect_id:
            logger.info(f"Player {current_questioner} wants to vote against {question_suspect_id}")

            # Record the question turn first
            turn = Turn(
                turn_number=len(game.turns) + 1,
                timestamp=datetime.now(),
                speaker_id=current_questioner,
                addressee_id=target_id,
                type=TurnType.QUESTION,
                content=question_text,
                display_delay_ms=calculate_display_delay_ms(question_text),
            )
            game.turns.append(turn)
            if on_turn:
                await _call_callback(on_turn, turn, game)

            # Add visual vote initiation message
            suspect_name = id_to_name.get(question_suspect_id, question_suspect_id)
            initiator_name = id_to_name.get(current_questioner, current_questioner)
            vote_init_content = f"[ГОЛОСОВАНИЕ] {initiator_name} инициирует голосование против {suspect_name}!"
            vote_init_turn = Turn(
                turn_number=len(game.turns) + 1,
                timestamp=datetime.now(),
                speaker_id=current_questioner,
                addressee_id="all",
                type=TurnType.INTERVENTION,
                content=vote_init_content,
                display_delay_ms=calculate_display_delay_ms(vote_init_content),
            )
            game.turns.append(vote_init_turn)
            if on_turn:
                await _call_callback(on_turn, vote_init_turn, game)

            _transition_phase(
                game,
                GamePhase.OPTIONAL_VOTE,
                f"Голосование инициировано игроком {initiator_name}",
                status="player_initiated",
                initiator_id=current_questioner,
            )
            break  # Exit main loop to go to voting

        if _check_for_location_leak(question_text, current_questioner, game):
            actual_location = get_location_by_id(game.location_id)
            leak_content = question_text
            leak_turn = Turn(
                turn_number=len(game.turns) + 1,
                timestamp=datetime.now(),
                speaker_id=current_questioner,
                addressee_id=target_id,
                type=TurnType.SPY_LEAK,
                content=leak_content,
                display_delay_ms=calculate_display_delay_ms(leak_content),
            )
            game.turns.append(leak_turn)
            if on_turn:
                await _call_callback(on_turn, leak_turn, game)

            game.outcome = GameOutcome(
                winner="civilians",
                reason=f"Шпион ({game.spy_id}) случайно назвал локацию в вопросе: {actual_location.display_name}",
            )
            game.ended_at = datetime.now()
            _transition_phase(game, GamePhase.RESOLUTION, "Spy leaked location in question")
            return game

        turn = Turn(
            turn_number=len(game.turns) + 1,
            timestamp=datetime.now(),
            speaker_id=current_questioner,
            addressee_id=target_id,
            type=TurnType.QUESTION,
            content=question_text,
            display_delay_ms=calculate_display_delay_ms(question_text),
            raw_response=question_raw_response,
        )
        game.turns.append(turn)
        if on_turn:
            await _call_callback(on_turn, turn, game)

        vote_trigger_checker.update_after_turn(turn)

        answerer_char = _get_character_by_id(characters, target_id)
        answerer_player = next(p for p in game.players if p.character_id == target_id)
        answerer_secret = _get_secret_info(game, answerer_player)
        answerer_prompt = build_system_prompt(answerer_char, game, answerer_secret, id_to_name)

        history = await _build_compressed_conversation_history(game, provider)

        # Build list of other players for suspect_id
        other_players_for_answer = [p.character_id for p in game.players if p.character_id != target_id]

        # Different instruction based on whether answerer is spy or civilian
        if answerer_player.is_spy:
            role_hint = "Ты ШПИОН — не знаешь локацию. Ответь достаточно конкретно чтобы не вызвать подозрений, но не слишком."
        else:
            role_hint = "Ты МИРНЫЙ — знаешь локацию. Ответь так, чтобы другие мирные поняли что ты свой, но НЕ выдай локацию шпиону. Избегай слов, которые однозначно указывают на место (двигатель, скальпель, меню и т.п.)."

        other_players_json = ", ".join(f'"{p}"' for p in other_players_for_answer)
        answer_instruction = f"""Ты — {answerer_char.display_name}. Тебе задали вопрос.
{role_hint}

Ответь JSON:
{{
  "content": "твой ответ",
  "wants_vote": true | false,
  "suspect_id": ID из [{other_players_json}] | null
}}

Правила:
- content: твой ответ на вопрос
- wants_vote: true если хочешь СЕЙЧАС начать голосование, иначе false
- suspect_id: если wants_vote=true укажи ID подозреваемого, иначе null"""

        messages = [
            {"role": "system", "content": answerer_prompt},
            *history,
            {"role": "user", "content": answer_instruction},
        ]

        if on_typing:
            await on_typing(target_id)

        answer_response = await provider.complete(
            messages=messages,
            model=game.config.main_model,
            temperature=0.9,
            max_tokens=250,
            json_mode=True,
        )
        _track_usage_and_check_cost(game, answer_response)

        # Parse JSON response
        answer_raw_response = answer_response.content
        answer_parsed = _parse_json_response(answer_raw_response)
        answer_text = _clean_content(answer_parsed.get("content", answer_raw_response))
        answer_wants_vote = answer_parsed.get("wants_vote", False)
        answer_suspect_id = answer_parsed.get("suspect_id")

        if _check_for_location_leak(answer_text, target_id, game):
            actual_location = get_location_by_id(game.location_id)
            leak_content = answer_text
            leak_turn = Turn(
                turn_number=len(game.turns) + 1,
                timestamp=datetime.now(),
                speaker_id=target_id,
                addressee_id=current_questioner,
                type=TurnType.SPY_LEAK,
                content=leak_content,
                display_delay_ms=calculate_display_delay_ms(leak_content),
            )
            game.turns.append(leak_turn)
            if on_turn:
                await _call_callback(on_turn, leak_turn, game)

            game.outcome = GameOutcome(
                winner="civilians",
                reason=f"Шпион ({game.spy_id}) случайно назвал локацию в ответе: {actual_location.display_name}",
            )
            game.ended_at = datetime.now()
            _transition_phase(game, GamePhase.RESOLUTION, "Spy leaked location in answer")
            return game

        answer_turn = Turn(
            turn_number=len(game.turns) + 1,
            timestamp=datetime.now(),
            speaker_id=target_id,
            addressee_id=current_questioner,
            type=TurnType.ANSWER,
            content=answer_text,
            display_delay_ms=calculate_display_delay_ms(answer_text),
            raw_response=answer_raw_response,
        )
        game.turns.append(answer_turn)
        if on_turn:
            await _call_callback(on_turn, answer_turn, game)

        # Check if answerer wants to trigger voting
        if answer_wants_vote and answer_suspect_id:
            logger.info(f"Player {target_id} wants to vote against {answer_suspect_id}")

            # Add visual vote initiation message
            suspect_name = id_to_name.get(answer_suspect_id, answer_suspect_id)
            initiator_name = id_to_name.get(target_id, target_id)
            vote_init_content = f"[ГОЛОСОВАНИЕ] {initiator_name} инициирует голосование против {suspect_name}!"
            vote_init_turn = Turn(
                turn_number=len(game.turns) + 1,
                timestamp=datetime.now(),
                speaker_id=target_id,
                addressee_id="all",
                type=TurnType.INTERVENTION,
                content=vote_init_content,
                display_delay_ms=calculate_display_delay_ms(vote_init_content),
            )
            game.turns.append(vote_init_turn)
            if on_turn:
                await _call_callback(on_turn, vote_init_turn, game)

            _transition_phase(
                game,
                GamePhase.OPTIONAL_VOTE,
                f"Голосование инициировано игроком {initiator_name}",
                status="player_initiated",
                initiator_id=target_id,
            )
            break  # Exit main loop to go to voting

        answer_count += 1

        vote_trigger_checker.update_after_turn(answer_turn)

        confidence_entry, last_check_answer_count = await _check_spy_confidence(
            game=game,
            characters=characters,
            provider=provider,
            answer_count=answer_count,
            last_check_answer_count=last_check_answer_count,
        )
        if confidence_entry:
            game.spy_confidence_log.append(confidence_entry)

            # Track consecutive confident checks
            if confidence_entry.level == ConfidenceLevel.CONFIDENT:
                consecutive_confident_count += 1
            else:
                consecutive_confident_count = 0

            # Check if spy should auto-guess based on risk tolerance
            spy_character = _get_character_by_id(characters, game.spy_id)
            should_auto_guess = False

            if confidence_entry.level == ConfidenceLevel.CONFIDENT:
                if spy_character.spy_risk_tolerance == SpyRiskTolerance.BOLD:
                    should_auto_guess = True
                    logger.info(f"Spy {game.spy_id} is bold - auto-guessing immediately")
                elif spy_character.spy_risk_tolerance == SpyRiskTolerance.MODERATE:
                    if consecutive_confident_count >= 2:
                        should_auto_guess = True
                        logger.info(f"Spy {game.spy_id} is moderate - auto-guessing after {consecutive_confident_count} confident checks")
                    else:
                        logger.info(f"Spy {game.spy_id} is moderate - waiting for more confident checks ({consecutive_confident_count}/2)")
                else:  # CAUTIOUS
                    logger.info(f"Spy {game.spy_id} is cautious - will not auto-guess")

            if should_auto_guess:
                guessed_location_id = await _ask_spy_to_guess(
                    game=game,
                    characters=characters,
                    provider=provider,
                )

                if guessed_location_id:
                    actual_location = get_location_by_id(game.location_id)
                    guessed_correct = guessed_location_id == game.location_id

                    if guessed_correct:
                        guessed_location = actual_location
                    else:
                        try:
                            guessed_location = get_location_by_id(guessed_location_id)
                        except ValueError:
                            guessed_location = None

                    guess_content = f"Я думаю, мы находимся в: {guessed_location.display_name if guessed_location else guessed_location_id}"
                    guess_turn = Turn(
                        turn_number=len(game.turns) + 1,
                        timestamp=datetime.now(),
                        speaker_id=game.spy_id,
                        addressee_id="all",
                        type=TurnType.SPY_GUESS,
                        content=guess_content,
                        display_delay_ms=calculate_display_delay_ms(guess_content),
                    )
                    game.turns.append(guess_turn)
                    if on_turn:
                        await _call_callback(on_turn, guess_turn, game)

                    if guessed_correct:
                        # Generate triumphant spy speech
                        spy_char = _get_character_by_id(characters, game.spy_id)
                        triumph_content = await _generate_spy_triumph_speech(
                            game, spy_char, actual_location.display_name, provider
                        )
                        triumph_turn = Turn(
                            turn_number=len(game.turns) + 1,
                            timestamp=datetime.now(),
                            speaker_id=game.spy_id,
                            addressee_id="all",
                            type=TurnType.INTERVENTION,
                            content=triumph_content,
                            display_delay_ms=calculate_display_delay_ms(triumph_content),
                        )
                        game.turns.append(triumph_turn)
                        if on_turn:
                            await _call_callback(on_turn, triumph_turn, game)

                        game.outcome = GameOutcome(
                            winner="spy",
                            reason=f"Шпион ({game.spy_id}) угадал локацию: {actual_location.display_name}",
                            spy_guess=guessed_location_id,
                            spy_guess_correct=True,
                        )
                    else:
                        # Generate defeat speech for spy
                        spy_char = _get_character_by_id(characters, game.spy_id)
                        defeat_content = await _generate_spy_defeat_speech(
                            game, spy_char,
                            guessed_location.display_name if guessed_location else guessed_location_id,
                            actual_location.display_name,
                            provider
                        )
                        defeat_turn = Turn(
                            turn_number=len(game.turns) + 1,
                            timestamp=datetime.now(),
                            speaker_id=game.spy_id,
                            addressee_id="all",
                            type=TurnType.INTERVENTION,
                            content=defeat_content,
                            display_delay_ms=calculate_display_delay_ms(defeat_content),
                        )
                        game.turns.append(defeat_turn)
                        if on_turn:
                            await _call_callback(on_turn, defeat_turn, game)

                        game.outcome = GameOutcome(
                            winner="civilians",
                            reason=f"Шпион ({game.spy_id}) неправильно угадал: {guessed_location.display_name if guessed_location else guessed_location_id} (на самом деле: {actual_location.display_name})",
                            spy_guess=guessed_location_id,
                            spy_guess_correct=False,
                        )

                    game.ended_at = datetime.now()
                    _transition_phase(game, GamePhase.RESOLUTION, f"Spy guessed location: {'correct' if guessed_correct else 'wrong'}")
                    return game

        trigger_checker.update_silence_counters(answer_turn)

        trigger_results = trigger_checker.check_all_characters(answer_turn, game)
        winner = trigger_checker.select_winner(trigger_results)

        if winner:
            wants_to_intervene = await _ask_to_intervene(
                trigger_result=winner,
                answer_turn=answer_turn,
                characters=characters,
                provider=provider,
                model=game.config.utility_model,
                game=game,
            )

            if wants_to_intervene:
                if on_typing:
                    await on_typing(winner.character_id)

                intervention_content, intervention_raw = await _generate_intervention_content(
                    trigger_result=winner,
                    answer_turn=answer_turn,
                    game=game,
                    characters=characters,
                    provider=provider,
                )

                if _check_for_location_leak(intervention_content, winner.character_id, game):
                    actual_location = get_location_by_id(game.location_id)
                    leak_turn = Turn(
                        turn_number=len(game.turns) + 1,
                        timestamp=datetime.now(),
                        speaker_id=winner.character_id,
                        addressee_id=answer_turn.speaker_id,
                        type=TurnType.SPY_LEAK,
                        content=intervention_content,
                        display_delay_ms=calculate_display_delay_ms(intervention_content),
                    )
                    game.turns.append(leak_turn)
                    if on_turn:
                        await _call_callback(on_turn, leak_turn, game)

                    game.outcome = GameOutcome(
                        winner="civilians",
                        reason=f"Шпион ({game.spy_id}) случайно назвал локацию во вмешательстве: {actual_location.display_name}",
                    )
                    game.ended_at = datetime.now()
                    _transition_phase(game, GamePhase.RESOLUTION, "Spy leaked location in intervention")
                    return game

                intervention_turn = Turn(
                    turn_number=len(game.turns) + 1,
                    timestamp=datetime.now(),
                    speaker_id=winner.character_id,
                    addressee_id=answer_turn.speaker_id,
                    type=TurnType.INTERVENTION,
                    content=intervention_content,
                    display_delay_ms=calculate_display_delay_ms(intervention_content),
                    raw_response=intervention_raw,
                )
                game.turns.append(intervention_turn)
                if on_turn:
                    await _call_callback(on_turn, intervention_turn, game)

                trigger_checker.update_silence_counters(intervention_turn)
                vote_trigger_checker.update_after_turn(intervention_turn)

            trigger_event = trigger_checker.create_trigger_event(
                result=winner,
                turn_number=answer_turn.turn_number,
                intervened=wants_to_intervene,
            )
            game.triggered_events.append(trigger_event)

        vote_trigger_result = vote_trigger_checker.check_vote_triggers(game)
        if vote_trigger_result and vote_trigger_result.triggered:
            _transition_phase(
                game,
                GamePhase.OPTIONAL_VOTE,
                f"Early voting triggered: {vote_trigger_result.reason}",
                status="critical" if vote_trigger_result.is_critical else "optional",
            )
            break

        question_count += 1
        previous_questioner = current_questioner  # Remember who asked
        current_questioner = target_id  # Answerer becomes next questioner

    return game


def _get_vote_leader_and_count(votes: dict[str, Optional[str]]) -> tuple[Optional[str], int, int]:
    """Get the leader (person with most votes) and vote counts.

    Args:
        votes: Dict mapping voter_id to target_id (or None for abstain).

    Returns:
        Tuple of (leader_id, votes_for_leader, total_voters_excluding_leader).
    """
    vote_counts: dict[str, int] = {}
    for voter_id, target in votes.items():
        if target is not None:
            vote_counts[target] = vote_counts.get(target, 0) + 1

    if not vote_counts:
        return None, 0, 0

    max_votes = max(vote_counts.values())
    leaders = [target for target, count in vote_counts.items() if count == max_votes]
    leader = leaders[0]

    # Count voters excluding the accused (leader) - they won't vote against themselves
    voters_excluding_leader = [vid for vid in votes.keys() if vid != leader]

    return leader, max_votes, len(voters_excluding_leader)


def _check_unanimity(votes: dict[str, Optional[str]], target_id: str) -> tuple[bool, int, int]:
    """Check if vote is unanimous against target (excluding target's own vote).

    Args:
        votes: Dict mapping voter_id to target_id.
        target_id: The accused person (their vote is excluded).

    Returns:
        Tuple of (is_unanimous, votes_for_target, total_eligible_voters).
    """
    eligible_voters = [vid for vid in votes.keys() if vid != target_id]
    votes_for_target = sum(1 for vid in eligible_voters if votes.get(vid) == target_id)

    is_unanimous = votes_for_target == len(eligible_voters) and len(eligible_voters) > 0

    return is_unanimous, votes_for_target, len(eligible_voters)


async def run_final_vote(
    game: Game,
    characters: list[Character],
    provider: Optional[LLMProvider] = None,
    on_turn: Optional[callable] = None,
    on_typing: Optional[callable] = None,
    on_vote_result: Optional[callable] = None,
    defense_was_executed: bool = False,
) -> Game:
    """Run the final voting phase of the game (only for critical triggers).

    This is the DECISIVE vote - if not unanimous, spy wins.
    Re-vote logic is handled in run_preliminary_with_revotes.

    Winner is determined by UNANIMOUS voting (excluding accused's vote):
    - If ALL players (except accused) vote for the same target → check if spy
    - If not unanimous → spy wins

    Args:
        game: Game object after preliminary vote cycle.
        characters: List of Character objects participating.
        provider: Optional LLM provider. If None, creates one from config.
        on_turn: Optional callback called after each vote turn.
        on_typing: Optional callback called before LLM generation starts with speaker_id.
        on_vote_result: Optional callback called with vote result.
        defense_was_executed: Whether defense speeches were delivered.

    Returns:
        Updated Game object with outcome set.
    """
    if provider is None:
        llm_config = LLMConfig()
        provider, _ = create_provider(llm_config, role="main")

    _transition_phase(game, GamePhase.FINAL_VOTE, "Final voting started")

    player_ids = [p.character_id for p in game.players]
    final_votes: dict[str, Optional[str]] = {}
    vote_changes: list[VoteChange] = []

    # Build id <-> display_name mappings for human-readable output and parsing
    id_to_name = {c.id: c.display_name for c in characters}
    name_to_id = {c.display_name: c.id for c in characters}

    if not defense_was_executed:
        # Defense was skipped - copy preliminary votes without LLM calls
        logger.info("Defense was skipped - copying preliminary votes to final votes")

        if game.preliminary_vote_result:
            final_votes = dict(game.preliminary_vote_result)
        else:
            # No preliminary votes - should not happen, but handle gracefully
            logger.warning("No preliminary votes found, using empty votes")
            final_votes = {}

        game.final_vote_result = final_votes
        game.vote_changes = []

        # Record turns for each vote (for consistency in logs)
        for voter_id, target_id in final_votes.items():
            if target_id:
                target_name = id_to_name.get(target_id, target_id)
                vote_content = f"Подтверждаю голос за {target_name}"
            else:
                vote_content = "Воздерживаюсь (подтверждено)"

            turn = Turn(
                turn_number=len(game.turns) + 1,
                timestamp=datetime.now(),
                speaker_id=voter_id,
                addressee_id="all",
                type=TurnType.FINAL_VOTE,
                content=vote_content,
                display_delay_ms=calculate_display_delay_ms(vote_content),
            )
            game.turns.append(turn)
            if on_turn:
                await _call_callback(on_turn, turn, game)

        # Mark phase transition with status
        game.phase_transitions[-1].status = "skipped_copied_from_preliminary"

    else:
        # Defense was executed - allow vote changes
        logger.info("Defense was executed - allowing vote changes in final voting")

        defense_speeches = game.defense_speeches or []
        preliminary_votes = game.preliminary_vote_result or {}

        for voter_player in game.players:
            voter_id = voter_player.character_id
            voter_char = _get_character_by_id(characters, voter_id)
            voter_secret = _get_secret_info(game, voter_player)

            candidates = [pid for pid in player_ids if pid != voter_id]
            candidates_json = ", ".join(f'"{c}"' for c in candidates)
            candidates_display = ", ".join(f"{id_to_name.get(c, c)} ({c})" for c in candidates)
            preliminary_vote = preliminary_votes.get(voter_id)

            # Build prompt with defense context
            vote_prompt = build_final_vote_with_defense_prompt(
                character=voter_char,
                game=game,
                secret_info=voter_secret,
                preliminary_vote=preliminary_vote,
                defense_speeches=defense_speeches,
                candidates=candidates,
                allow_abstain=DEFENSE_ALLOW_ABSTAIN,
                id_to_name=id_to_name,
            )

            history = await _build_compressed_conversation_history(game, provider)

            # Build context showing previous final votes
            previous_votes_text = ""
            if final_votes:
                votes_list = []
                for v, t in final_votes.items():
                    voter_name = id_to_name.get(v, v)
                    if t is None:
                        votes_list.append(f"{voter_name}: воздержался")
                    else:
                        target_name = id_to_name.get(t, t)
                        votes_list.append(f"{voter_name}: за {target_name}")
                previous_votes_text = f" Уже проголосовали: {', '.join(votes_list)}."

            allow_abstain_str = "null если воздерживаешься" if DEFENSE_ALLOW_ABSTAIN else "воздержание НЕДОСТУПНО"
            vote_instruction = (
                f"Финальное голосование!{previous_votes_text}\n"
                f"Кандидаты: {candidates_display}\n\n"
                f"Ответь JSON:\n"
                f'{{"vote_for": ID из [{candidates_json}] или {allow_abstain_str}, '
                f'"speech": "твоя речь"}}'
            )

            messages = [
                {"role": "system", "content": vote_prompt},
                *history,
                {"role": "user", "content": vote_instruction},
            ]

            if on_typing:
                await on_typing(voter_id)

            vote_llm_response = await provider.complete(
                messages=messages,
                model=game.config.main_model,
                temperature=0.7,
                max_tokens=200,
                json_mode=True,
            )
            _track_usage_and_check_cost(game, vote_llm_response)
            vote_raw = vote_llm_response.content.strip()
            vote_parsed = _parse_json_response(vote_raw)

            voted_for = vote_parsed.get("vote_for")
            vote_speech = vote_parsed.get("speech", "")

            # Validate vote_for is a valid candidate ID
            if voted_for is not None and voted_for not in candidates:
                logger.warning(f"Invalid vote_for '{voted_for}' from {voter_id}, treating as abstain")
                voted_for = None

            # If abstained in final vote, ping them again with a warning
            if voted_for is None:
                logger.info(f"Voter {voter_id} tried to abstain in final vote, pinging again")

                # Record the abstention attempt
                abstain_turn = Turn(
                    turn_number=len(game.turns) + 1,
                    timestamp=datetime.now(),
                    speaker_id=voter_id,
                    addressee_id="all",
                    type=TurnType.FINAL_VOTE,
                    content="Хочу воздержаться...",
                    display_delay_ms=calculate_display_delay_ms("Хочу воздержаться..."),
                )
                game.turns.append(abstain_turn)
                if on_turn:
                    await _call_callback(on_turn, abstain_turn, game)

                # Ping with dramatic warning
                retry_instruction = (
                    f"Это ФИНАЛЬНОЕ голосование! Воздержание = победа шпиона.\n"
                    f"Кандидаты: {candidates_display}\n\n"
                    f"Ответь JSON: {{\"vote_for\": ID из [{candidates_json}], \"speech\": \"...\"}}"
                )

                retry_messages = [
                    {"role": "system", "content": vote_prompt},
                    *history,
                    {"role": "user", "content": retry_instruction},
                ]

                if on_typing:
                    await on_typing(voter_id)

                retry_response = await provider.complete(
                    messages=retry_messages,
                    model=game.config.main_model,
                    temperature=0.8,
                    max_tokens=150,
                    json_mode=True,
                )
                _track_usage_and_check_cost(game, retry_response)

                retry_parsed = _parse_json_response(retry_response.content.strip())
                voted_for = retry_parsed.get("vote_for")
                vote_speech = retry_parsed.get("speech", vote_speech)

                if voted_for is not None and voted_for not in candidates:
                    voted_for = None

                if voted_for is None:
                    logger.info(f"Voter {voter_id} insisted on abstaining after warning")

            final_votes[voter_id] = voted_for

            # Record vote change if different from preliminary
            if voted_for != preliminary_vote:
                change = VoteChange(
                    voter_id=voter_id,
                    from_target=preliminary_vote,
                    to_target=voted_for,
                )
                vote_changes.append(change)
                logger.info(f"Vote change: {voter_id} changed from {preliminary_vote} to {voted_for}")

            # Build vote content: always show target, optionally add speech
            if voted_for is None:
                vote_content = "Воздерживаюсь"
            else:
                voted_for_name = id_to_name.get(voted_for, voted_for)
                if voted_for == preliminary_vote:
                    vote_content = f"[Голос: {voted_for_name}]"
                elif preliminary_vote:
                    vote_content = f"[Меняю голос: {voted_for_name}]"
                else:
                    vote_content = f"[Голос: {voted_for_name}]"
                if vote_speech:
                    vote_content += f" {_clean_content(vote_speech)}"

            turn = Turn(
                turn_number=len(game.turns) + 1,
                timestamp=datetime.now(),
                speaker_id=voter_id,
                addressee_id="all",
                type=TurnType.FINAL_VOTE,
                content=vote_content,
                display_delay_ms=calculate_display_delay_ms(vote_content),
            )
            game.turns.append(turn)
            if on_turn:
                await _call_callback(on_turn, turn, game)

        game.final_vote_result = final_votes
        game.vote_changes = vote_changes

    # Determine winner using UNANIMOUS voting
    # Exclude the ACCUSED's vote (they won't vote against themselves)
    winner_target, max_votes, _ = _get_vote_leader_and_count(final_votes)

    if winner_target is None:
        # No votes cast - spy wins
        spy_name = id_to_name.get(game.spy_id, game.spy_id)
        game.outcome = GameOutcome(
            winner="spy",
            reason=f"Никто не проголосовал — шпион ({spy_name}) побеждает",
            votes={},
        )
        game.ended_at = datetime.now()
        _transition_phase(game, GamePhase.RESOLUTION, "Game ended: spy won (no votes)")
        return game

    # Check unanimity excluding the accused's vote
    is_unanimous, votes_for, total_eligible = _check_unanimity(final_votes, winner_target)

    if on_vote_result:
        await _call_callback(on_vote_result, is_unanimous, dict(final_votes))

    spy_name = id_to_name.get(game.spy_id, game.spy_id)

    if is_unanimous:
        # All eligible voters voted for the same target
        spy_caught = winner_target == game.spy_id
        target_name = id_to_name.get(winner_target, winner_target)

        if spy_caught:
            winner = "civilians"
            reason = f"Шпион ({spy_name}) был единогласно разоблачён ({votes_for}/{total_eligible})"
        else:
            winner = "spy"
            reason = f"Игроки единогласно обвинили {target_name}, но шпионом был {spy_name}"

        game.outcome = GameOutcome(
            winner=winner,
            reason=reason,
            votes={k: v for k, v in final_votes.items() if v is not None},
            accused_id=winner_target,
        )
        game.ended_at = datetime.now()
        _transition_phase(game, GamePhase.RESOLUTION, f"Game ended: {game.outcome.winner} won")
        return game

    # Not unanimous - spy wins (final vote is decisive for critical triggers)
    target_name = id_to_name.get(winner_target, winner_target)
    game.outcome = GameOutcome(
        winner="spy",
        reason=f"Голоса разделились ({votes_for}/{total_eligible} за {target_name}) — шпион ({spy_name}) побеждает",
        votes={k: v for k, v in final_votes.items() if v is not None},
    )
    game.ended_at = datetime.now()
    _transition_phase(game, GamePhase.RESOLUTION, "Game ended: spy won (split vote)")

    return game


async def run_preliminary_vote(
    game: Game,
    characters: list[Character],
    provider: Optional[LLMProvider] = None,
    on_turn: Optional[callable] = None,
    on_typing: Optional[callable] = None,
) -> tuple[Game, dict[str, int]]:
    """Run the preliminary voting phase (CR-001 F11).

    Each player votes for who they think is the spy or abstains (if allowed).
    Results are stored in game.preliminary_vote_result.

    Args:
        game: Game object after main_round.
        characters: List of Character objects participating.
        provider: Optional LLM provider. If None, creates one from config.
        on_turn: Optional callback called after each vote turn.
        on_typing: Optional callback called before LLM generation starts.

    Returns:
        Tuple of:
        - Updated Game object with preliminary_vote_result populated
        - Aggregate dict {target_id: vote_count} (excluding abstentions)
    """
    if provider is None:
        llm_config = LLMConfig()
        provider, _ = create_provider(llm_config, role="utility")

    _transition_phase(game, GamePhase.PRELIMINARY_VOTE, "Preliminary voting started")

    player_ids = [p.character_id for p in game.players]
    votes: dict[str, Optional[str]] = {}

    # Build id <-> display_name mappings for human-readable output and parsing
    id_to_name = {c.id: c.display_name for c in characters}
    name_to_id = {c.display_name: c.id for c in characters}

    # Find vote initiator from phase transitions and put them first
    initiator_id = None
    for pt in reversed(game.phase_transitions):
        if pt.to_phase == GamePhase.OPTIONAL_VOTE and pt.initiator_id:
            initiator_id = pt.initiator_id
            break

    # Reorder players: initiator first, then others in original order
    voting_order = list(game.players)
    if initiator_id:
        voting_order = sorted(
            game.players,
            key=lambda p: (0 if p.character_id == initiator_id else 1)
        )

    for voter_player in voting_order:
        voter_id = voter_player.character_id
        voter_char = _get_character_by_id(characters, voter_id)
        voter_secret = _get_secret_info(game, voter_player)
        voter_prompt = build_system_prompt(voter_char, game, voter_secret, id_to_name)

        candidates = [pid for pid in player_ids if pid != voter_id]
        candidates_json = ", ".join(f'"{c}"' for c in candidates)
        candidates_display = ", ".join(f"{id_to_name.get(c, c)} ({c})" for c in candidates)

        history = await _build_compressed_conversation_history(game, provider)

        previous_votes_text = ""
        if votes:
            votes_list = []
            for v, t in votes.items():
                voter_name = id_to_name.get(v, v)
                if t is None:
                    votes_list.append(f"{voter_name}: воздержался")
                else:
                    target_name = id_to_name.get(t, t)
                    votes_list.append(f"{voter_name}: против {target_name}")
            previous_votes_text = f"Уже проголосовали: {', '.join(votes_list)}. "

        is_first_voter = len(votes) == 0
        allow_abstain_str = "null если воздерживаешься" if DEFENSE_ALLOW_ABSTAIN else "воздержание НЕДОСТУПНО"

        if is_first_voter:
            vote_instruction = (
                f"Ты — {voter_char.display_name}. Ты решаешь выдвинуть голосование!\n"
                f"Кандидаты: {candidates_display}\n\n"
                f"Ответь JSON:\n"
                f'{{"vote_for": ID из [{candidates_json}] или {allow_abstain_str}, '
                f'"speech": "твоя речь при голосовании"}}'
            )
        else:
            vote_instruction = (
                f"Ты — {voter_char.display_name}. Идёт голосование. {previous_votes_text}\n"
                f"Кандидаты: {candidates_display}\n\n"
                f"Ответь JSON:\n"
                f'{{"vote_for": ID из [{candidates_json}] или {allow_abstain_str}, '
                f'"speech": "твоя речь при голосовании"}}'
            )

        messages = [
            {"role": "system", "content": voter_prompt},
            *history,
            {"role": "user", "content": vote_instruction},
        ]

        if on_typing:
            await _call_callback(on_typing, voter_id)

        vote_llm_response = await provider.complete(
            messages=messages,
            model=game.config.main_model,
            temperature=0.7,
            max_tokens=200,
            json_mode=True,
        )
        _track_usage_and_check_cost(game, vote_llm_response)
        vote_raw = vote_llm_response.content.strip()
        vote_parsed = _parse_json_response(vote_raw)

        voted_for = vote_parsed.get("vote_for")
        vote_speech = vote_parsed.get("speech", "")

        # Validate vote_for is a valid candidate ID
        if voted_for is not None and voted_for not in candidates:
            logger.warning(f"Invalid vote_for '{voted_for}' from {voter_id}, treating as abstain")
            voted_for = None

        if voted_for is None and not DEFENSE_ALLOW_ABSTAIN:
            logger.warning(f"Player {voter_id} tried to abstain but DEFENSE_ALLOW_ABSTAIN=false, retrying")
            retry_instruction = (
                f"Ты — {voter_char.display_name}. "
                f"Воздержание НЕДОСТУПНО. Ты ОБЯЗАН выбрать.\n"
                f"Ответь JSON: {{\"vote_for\": ID из [{candidates_json}], \"speech\": \"...\"}}'"
            )
            retry_messages = [
                {"role": "system", "content": voter_prompt},
                *history,
                {"role": "user", "content": retry_instruction},
            ]

            retry_response = await provider.complete(
                messages=retry_messages,
                model=game.config.utility_model,
                temperature=0.7,
                max_tokens=100,
                json_mode=True,
            )
            _track_usage_and_check_cost(game, retry_response)
            retry_parsed = _parse_json_response(retry_response.content.strip())
            voted_for = retry_parsed.get("vote_for")
            vote_speech = retry_parsed.get("speech", vote_speech)

            if voted_for is not None and voted_for not in candidates:
                voted_for = None

            if voted_for is None:
                logger.info(f"Player {voter_id} insisted on abstaining in preliminary vote")

        votes[voter_id] = voted_for

        # Build vote content: always show target, optionally add speech
        if voted_for is None:
            vote_content = "Воздерживаюсь"
        else:
            target_name = id_to_name.get(voted_for, voted_for)
            vote_content = f"[Голос: {target_name}]"
            if vote_speech:
                vote_content += f" {_clean_content(vote_speech)}"

        turn = Turn(
            turn_number=len(game.turns) + 1,
            timestamp=datetime.now(),
            speaker_id=voter_id,
            addressee_id="all",
            type=TurnType.PRELIMINARY_VOTE,
            content=vote_content,
            display_delay_ms=calculate_display_delay_ms(vote_content),
        )
        game.turns.append(turn)
        if on_turn:
            await _call_callback(on_turn, turn, game)

    game.preliminary_vote_result = votes

    vote_counts: dict[str, int] = {}
    for target in votes.values():
        if target is not None:
            vote_counts[target] = vote_counts.get(target, 0) + 1

    logger.info(f"Preliminary vote results: {votes}")
    logger.info(f"Vote counts (excluding abstentions): {vote_counts}")

    return game, vote_counts


async def run_revote(
    game: Game,
    characters: list[Character],
    provider: LLMProvider,
    previous_votes: dict[str, Optional[str]],
    revote_number: int,
    on_turn: Optional[callable] = None,
    on_typing: Optional[callable] = None,
) -> tuple[Game, dict[str, int]]:
    """Run a re-vote after defense speeches.

    Similar to preliminary vote but with context about previous votes.
    """
    player_ids = [p.character_id for p in game.players]
    votes: dict[str, Optional[str]] = {}

    id_to_name = {c.id: c.display_name for c in characters}

    for voter_player in game.players:
        voter_id = voter_player.character_id
        voter_char = _get_character_by_id(characters, voter_id)
        voter_secret = _get_secret_info(game, voter_player)
        voter_prompt = build_system_prompt(voter_char, game, voter_secret, id_to_name)

        candidates = [pid for pid in player_ids if pid != voter_id]
        candidates_json = ", ".join(f'"{c}"' for c in candidates)
        candidates_display = ", ".join(f"{id_to_name.get(c, c)} ({c})" for c in candidates)

        history = await _build_compressed_conversation_history(game, provider)

        previous_votes_text = ""
        if votes:
            votes_list = []
            for v, t in votes.items():
                voter_name = id_to_name.get(v, v)
                if t is None:
                    votes_list.append(f"{voter_name}: воздержался")
                else:
                    target_name = id_to_name.get(t, t)
                    votes_list.append(f"{voter_name}: против {target_name}")
            previous_votes_text = f"Уже проголосовали в этом раунде: {', '.join(votes_list)}. "

        # Show what they voted for previously
        prev_vote = previous_votes.get(voter_id)
        prev_vote_text = ""
        if prev_vote:
            prev_vote_name = id_to_name.get(prev_vote, prev_vote)
            prev_vote_text = f"В прошлом раунде ты голосовал за {prev_vote_name}. "

        allow_abstain_str = "null если воздерживаешься" if DEFENSE_ALLOW_ABSTAIN else "воздержание НЕДОСТУПНО"
        vote_instruction = (
            f"Ты — {voter_char.display_name}. Идёт ПЕРЕВЫБОР (раунд {revote_number}). "
            f"{prev_vote_text}{previous_votes_text}\n"
            f"После защитной речи ты можешь изменить или подтвердить свой голос.\n"
            f"Кандидаты: {candidates_display}\n\n"
            f"Ответь JSON:\n"
            f'{{"vote_for": ID из [{candidates_json}] или {allow_abstain_str}, '
            f'"speech": "твоя речь"}}'
        )

        messages = [
            {"role": "system", "content": voter_prompt},
            *history,
            {"role": "user", "content": vote_instruction},
        ]

        if on_typing:
            await _call_callback(on_typing, voter_id)

        vote_llm_response = await provider.complete(
            messages=messages,
            model=game.config.main_model,
            temperature=0.7,
            max_tokens=200,
            json_mode=True,
        )
        _track_usage_and_check_cost(game, vote_llm_response)
        vote_parsed = _parse_json_response(vote_llm_response.content.strip())

        voted_for = vote_parsed.get("vote_for")
        vote_speech = vote_parsed.get("speech", "")

        if voted_for is not None and voted_for not in candidates:
            voted_for = None

        votes[voter_id] = voted_for

        # Build vote content
        if voted_for is None:
            vote_content = "Воздерживаюсь"
        else:
            voted_for_name = id_to_name.get(voted_for, voted_for)
            if voted_for == prev_vote:
                vote_content = f"[Подтверждаю: {voted_for_name}]"
            else:
                vote_content = f"[Меняю голос: {voted_for_name}]"
            if vote_speech:
                vote_content += f" {_clean_content(vote_speech)}"

        turn = Turn(
            turn_number=len(game.turns) + 1,
            timestamp=datetime.now(),
            speaker_id=voter_id,
            addressee_id="all",
            type=TurnType.PRELIMINARY_VOTE,
            content=vote_content,
            display_delay_ms=calculate_display_delay_ms(vote_content),
        )
        game.turns.append(turn)
        if on_turn:
            await _call_callback(on_turn, turn, game)

    vote_counts: dict[str, int] = {}
    for target in votes.values():
        if target is not None:
            vote_counts[target] = vote_counts.get(target, 0) + 1

    # Update preliminary_vote_result with re-vote results
    game.preliminary_vote_result = votes

    logger.info(f"Re-vote {revote_number} results: {votes}")
    return game, vote_counts


async def run_preliminary_with_revotes(
    game: Game,
    characters: list[Character],
    provider: LLMProvider,
    on_turn: Optional[callable] = None,
    on_typing: Optional[callable] = None,
) -> tuple[Game, dict[str, int], bool, Optional[str]]:
    """Run preliminary vote with re-vote cycle after defense.

    Flow:
    1. Preliminary vote
    2. Defense for top voted
    3. Check unanimity (excluding accused's vote)
    4. If leader changed → re-vote → defense → repeat (max MAX_RE_VOTES)
    5. Return final state

    Returns:
        Tuple of (game, vote_counts, is_unanimous, accused_id).
    """
    id_to_name = {c.id: c.display_name for c in characters}

    # Step 1: Run preliminary vote
    game, vote_counts = await run_preliminary_vote(
        game, characters, provider, on_turn, on_typing
    )

    if not vote_counts:
        return game, vote_counts, False, None

    # Get initial leader
    leader, leader_votes, eligible_voters = _get_vote_leader_and_count(game.preliminary_vote_result)

    if leader is None:
        return game, vote_counts, False, None

    # Check initial unanimity
    is_unanimous, votes_for, total_eligible = _check_unanimity(
        game.preliminary_vote_result, leader
    )

    if is_unanimous:
        logger.info(f"Unanimous vote for {leader} in preliminary ({votes_for}/{total_eligible})")
        return game, vote_counts, True, leader

    # Step 2: Defense for top voted
    game, defense_executed = await run_defense_speeches(
        game, characters, vote_counts, provider, on_turn, on_typing
    )

    if not defense_executed:
        # No defense was needed (below threshold)
        return game, vote_counts, False, None

    # Step 3-4: Re-vote cycle
    previous_leader = leader
    previous_votes = dict(game.preliminary_vote_result)
    revote_count = 0

    while revote_count < MAX_RE_VOTES:
        revote_count += 1

        # Announce re-vote
        revote_content = f"[ПЕРЕВЫБОР] Раунд {revote_count}/{MAX_RE_VOTES} после защитной речи"
        revote_turn = Turn(
            turn_number=len(game.turns) + 1,
            timestamp=datetime.now(),
            speaker_id="system",
            addressee_id="all",
            type=TurnType.INTERVENTION,
            content=revote_content,
            display_delay_ms=500,
        )
        game.turns.append(revote_turn)
        if on_turn:
            await _call_callback(on_turn, revote_turn, game)

        # Run re-vote
        game, vote_counts = await run_revote(
            game, characters, provider, previous_votes, revote_count, on_turn, on_typing
        )

        if not vote_counts:
            return game, vote_counts, False, None

        # Get new leader
        current_leader, leader_votes, eligible_voters = _get_vote_leader_and_count(
            game.preliminary_vote_result
        )

        if current_leader is None:
            return game, vote_counts, False, None

        # Check unanimity
        is_unanimous, votes_for, total_eligible = _check_unanimity(
            game.preliminary_vote_result, current_leader
        )

        if is_unanimous:
            logger.info(f"Unanimous vote for {current_leader} after re-vote {revote_count}")
            return game, vote_counts, True, current_leader

        # Check if leader changed
        leader_changed = current_leader != previous_leader

        if leader_changed:
            logger.info(f"Leader changed: {previous_leader} → {current_leader}")

            # Run defense for new leader
            new_leader_name = id_to_name.get(current_leader, current_leader)
            leader_change_content = (
                f"[СМЕНА ЛИДЕРА] Теперь больше голосов у {new_leader_name}. "
                f"Защитная речь!"
            )
            leader_turn = Turn(
                turn_number=len(game.turns) + 1,
                timestamp=datetime.now(),
                speaker_id="system",
                addressee_id="all",
                type=TurnType.INTERVENTION,
                content=leader_change_content,
                display_delay_ms=500,
            )
            game.turns.append(leader_turn)
            if on_turn:
                await _call_callback(on_turn, leader_turn, game)

            new_vote_counts = {current_leader: leader_votes}
            game, _ = await run_defense_speeches(
                game, characters, new_vote_counts, provider, on_turn, on_typing
            )

            previous_leader = current_leader
            previous_votes = dict(game.preliminary_vote_result)
        else:
            # Leader same, no more re-votes needed
            logger.info(f"Leader stable at {current_leader}, exiting re-vote cycle")
            break

    return game, vote_counts, False, None


def _count_sentences(text: str) -> int:
    """Count sentences in text using punctuation markers."""
    import re
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    return len(sentences)


def _truncate_to_sentences(text: str, max_sentences: int) -> tuple[str, bool]:
    """Truncate text to maximum number of sentences.

    Args:
        text: Input text.
        max_sentences: Maximum allowed sentences.

    Returns:
        Tuple of (truncated text, was_truncated flag).
    """
    import re
    sentence_pattern = r'([^.!?]*[.!?]+)'
    matches = re.findall(sentence_pattern, text)

    if len(matches) <= max_sentences:
        return text, False

    truncated = ''.join(matches[:max_sentences])
    return truncated.strip(), True


async def _check_defense_speech_characteristic(
    game: Game,
    character: Character,
    defense_content: str,
    provider: LLMProvider,
) -> bool:
    """Check if a defense speech is characteristic of the character.

    Uses the utility model to verify the speech matches the character's style
    and MUST-directives.

    Args:
        game: Current game state (for tracking usage).
        character: The defending character profile.
        defense_content: The generated defense speech content.
        provider: LLM provider for the check.

    Returns:
        True if characteristic, False if not.
    """
    prompt = build_defense_characteristic_check_prompt(character, defense_content)

    response = await provider.complete(
        messages=[{"role": "user", "content": prompt}],
        model=game.config.utility_model,
        temperature=0.3,
        max_tokens=20,
        json_mode=True,
    )

    _track_usage_and_check_cost(game, response)
    parsed = _parse_json_response(response.content.strip())
    return parsed.get("is_characteristic", False) is True


async def run_defense_speeches(
    game: Game,
    characters: list[Character],
    vote_counts: dict[str, int],
    provider: Optional[LLMProvider] = None,
    on_turn: Optional[callable] = None,
    on_typing: Optional[callable] = None,
) -> tuple[Game, bool]:
    """Run the defense speech phase (CR-001 F12).

    Players with the most votes get to defend themselves before final voting.

    Args:
        game: Game object after preliminary_vote.
        characters: List of Character objects participating.
        vote_counts: Dict {target_id: vote_count} from preliminary voting.
        provider: Optional LLM provider. If None, creates one from config.
        on_turn: Optional callback called after each defense turn.
        on_typing: Optional callback called before LLM generation starts.

    Returns:
        Tuple of:
        - Updated Game object with defense_speeches populated
        - Boolean indicating if defense phase was executed (True) or skipped (False)
    """
    if provider is None:
        llm_config = LLMConfig()
        provider, _ = create_provider(llm_config, role="main")

    # Build id -> display_name mapping for human-readable output
    id_to_name = {c.id: c.display_name for c in characters}

    if not vote_counts:
        logger.info("Defense phase skipped: no votes cast")
        _transition_phase(
            game,
            GamePhase.PRE_FINAL_VOTE_DEFENSE,
            "Defense phase skipped: no votes cast",
        )
        game.phase_transitions[-1].status = "skipped_no_votes"
        return game, False

    max_votes = max(vote_counts.values())

    if max_votes < DEFENSE_MIN_VOTES_TO_QUALIFY:
        logger.info(
            f"Defense phase skipped: max votes ({max_votes}) < threshold ({DEFENSE_MIN_VOTES_TO_QUALIFY})"
        )
        _transition_phase(
            game,
            GamePhase.PRE_FINAL_VOTE_DEFENSE,
            f"Defense phase skipped: max votes ({max_votes}) < threshold ({DEFENSE_MIN_VOTES_TO_QUALIFY})",
        )
        game.phase_transitions[-1].status = "skipped_below_threshold"
        return game, False

    defenders = [
        target_id for target_id, count in vote_counts.items()
        if count == max_votes
    ]

    random.shuffle(defenders)
    logger.info(f"Defense phase: {len(defenders)} defender(s) with {max_votes} votes: {defenders}")

    _transition_phase(
        game,
        GamePhase.PRE_FINAL_VOTE_DEFENSE,
        f"Defense speeches for {len(defenders)} player(s) with {max_votes} votes",
    )

    game.defense_speeches = []

    for defender_id in defenders:
        defender_player = next(
            (p for p in game.players if p.character_id == defender_id), None
        )
        if defender_player is None:
            logger.warning(f"Defender {defender_id} not found in players")
            continue

        defender_char = _get_character_by_id(characters, defender_id)
        defender_secret = _get_secret_info(game, defender_player)

        defense_prompt = build_defense_speech_prompt(
            character=defender_char,
            game=game,
            secret_info=defender_secret,
            votes_received=max_votes,
            max_sentences=DEFENSE_SPEECH_MAX_SENTENCES,
            id_to_name=id_to_name,
        )

        history = await _build_compressed_conversation_history(game, provider)

        messages = [
            {"role": "system", "content": defense_prompt},
            *history,
            {"role": "user", "content": "Произнеси свою защитную речь:"},
        ]

        if on_typing:
            await _call_callback(on_typing, defender_id)

        defense_response = await provider.complete(
            messages=messages,
            model=game.config.main_model,
            temperature=0.8,
            max_tokens=200,
        )
        _track_usage_and_check_cost(game, defense_response)

        defense_content = defense_response.content.strip()
        was_regenerated = False

        is_characteristic = await _check_defense_speech_characteristic(
            game, defender_char, defense_content, provider
        )

        if not is_characteristic:
            logger.info(
                f"Defense speech from {defender_id} not characteristic, regenerating once"
            )
            regenerated_response = await provider.complete(
                messages=messages,
                model=game.config.main_model,
                temperature=0.9,
                max_tokens=200,
            )
            _track_usage_and_check_cost(game, regenerated_response)
            defense_content = regenerated_response.content.strip()
            was_regenerated = True
            logger.info(f"Defense speech from {defender_id} regenerated")

        truncated_content, was_truncated = _truncate_to_sentences(
            defense_content, DEFENSE_SPEECH_MAX_SENTENCES
        )
        if was_truncated:
            logger.warning(
                f"Defense speech from {defender_id} truncated from "
                f"{_count_sentences(defense_content)} to {DEFENSE_SPEECH_MAX_SENTENCES} sentences"
            )
            defense_content = truncated_content

        defense_speech = DefenseSpeech(
            defender_id=defender_id,
            votes_received=max_votes,
            content=defense_content,
            timestamp=datetime.now(),
            regenerated=was_regenerated,
        )
        game.defense_speeches.append(defense_speech)

        turn = Turn(
            turn_number=len(game.turns) + 1,
            timestamp=datetime.now(),
            speaker_id=defender_id,
            addressee_id="all",
            type=TurnType.DEFENSE_SPEECH,
            content=defense_content,
            display_delay_ms=calculate_display_delay_ms(defense_content),
        )
        game.turns.append(turn)

        if on_turn:
            await _call_callback(on_turn, turn, game)

    logger.info(f"Defense phase completed: {len(game.defense_speeches)} speech(es)")
    return game, True
