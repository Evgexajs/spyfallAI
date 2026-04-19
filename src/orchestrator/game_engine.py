"""Game orchestrator for SpyfallAI - setup and game flow management."""

import json
import os
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional
from uuid import uuid4

from src.agents import (
    SecretInfo,
    build_system_prompt,
    build_intervention_micro_prompt,
    build_intervention_content_prompt,
    build_spy_confidence_check_prompt,
    build_spy_guess_prompt,
)
from src.llm import CostExceededError, LLMConfig, LLMProvider, LLMResponse, create_provider
from src.models import (
    Character,
    ConfidenceEntry,
    ConfidenceLevel,
    Game,
    GameConfig,
    GameOutcome,
    GamePhase,
    Location,
    PhaseEntry,
    Player,
    Turn,
    TurnType,
)
from src.triggers import TriggerChecker, TriggerResult, VoteTriggerChecker


import logging

SPEECH_DELAY_MULTIPLIER = float(os.environ.get("SPEECH_DELAY_MULTIPLIER", "0.03"))
CONTEXT_COMPRESSION_AFTER_N_TURNS = int(os.environ.get("CONTEXT_COMPRESSION_AFTER_N_TURNS", "10"))
CONTEXT_KEEP_LAST_K_TURNS = int(os.environ.get("CONTEXT_KEEP_LAST_K_TURNS", "6"))
MAX_PARTY_COST_USD = float(os.environ.get("MAX_PARTY_COST_USD", "3.0"))
MAX_QUESTION_REROLL_ATTEMPTS = int(os.environ.get("MAX_QUESTION_REROLL_ATTEMPTS", "3"))

logger = logging.getLogger(__name__)


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


def _transition_phase(game: Game, to_phase: GamePhase, reason: str) -> None:
    """Record a phase transition in the game."""
    current_phase = game.phase_transitions[-1].to_phase if game.phase_transitions else None
    game.phase_transitions.append(
        PhaseEntry(
            timestamp=datetime.now(),
            from_phase=current_phase,
            to_phase=to_phase,
            reason=reason,
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


def _select_target(players: list[Player], questioner_id: str) -> str:
    """Select a random target for the question (not the questioner)."""
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

    prompt = build_intervention_micro_prompt(
        character=character,
        answer_turn=answer_turn,
        reaction_type=trigger_result.reaction_type,
    )

    response = await provider.complete(
        messages=[{"role": "user", "content": prompt}],
        model=model,
        temperature=0.7,
        max_tokens=10,
    )

    _track_usage_and_check_cost(game, response)
    response_lower = response.content.strip().lower()
    return "да" in response_lower or "yes" in response_lower


async def _generate_intervention_content(
    trigger_result: TriggerResult,
    answer_turn: Turn,
    game: Game,
    characters: list[Character],
    provider: LLMProvider,
) -> str:
    """Generate the intervention content for a character."""
    character = _get_character_by_id(characters, trigger_result.character_id)
    player = next(p for p in game.players if p.character_id == character.id)
    secret_info = _get_secret_info(game, player)

    prompt = build_intervention_content_prompt(
        character=character,
        game=game,
        secret_info=secret_info,
        answer_turn=answer_turn,
        reaction_type=trigger_result.reaction_type,
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
    return response.content.strip()


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

    recent_turns = game.turns[-6:] if game.turns else []

    prompt = build_spy_confidence_check_prompt(
        character=spy_character,
        recent_turns=recent_turns,
    )

    response = await provider.complete(
        messages=[{"role": "user", "content": prompt}],
        model=game.config.utility_model,
        temperature=0.5,
        max_tokens=20,
    )

    _track_usage_and_check_cost(game, response)
    response_lower = response.content.strip().lower()

    if "confident" in response_lower:
        level = ConfidenceLevel.CONFIDENT
    elif "few_guesses" in response_lower or "few" in response_lower:
        level = ConfidenceLevel.FEW_GUESSES
    else:
        level = ConfidenceLevel.NO_IDEA

    entry = ConfidenceEntry(
        turn_number=max(1, len(game.turns)),
        timestamp=datetime.now(),
        level=level,
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
    recent_turns = game.turns[-10:] if game.turns else []
    available_locations = load_locations()

    prompt = build_spy_guess_prompt(
        character=spy_character,
        recent_turns=recent_turns,
        available_locations=available_locations,
    )

    response = await provider.complete(
        messages=[{"role": "user", "content": prompt}],
        model=game.config.utility_model,
        temperature=0.3,
        max_tokens=30,
    )

    _track_usage_and_check_cost(game, response)
    response_text = response.content.strip().lower()

    for loc in available_locations:
        if loc.id.lower() == response_text or loc.id.lower() in response_text:
            return loc.id

    return None


async def run_main_round(
    game: Game,
    characters: list[Character],
    provider: Optional[LLMProvider] = None,
    on_turn: Optional[callable] = None,
) -> Game:
    """Run the main question-answer round of the game.

    Args:
        game: Initialized Game object from setup_game().
        characters: List of Character objects participating.
        provider: Optional LLM provider. If None, creates one from config.
        on_turn: Optional callback called after each turn (question, answer, intervention).

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

    start_time = game.started_at
    duration = timedelta(minutes=game.config.duration_minutes)
    question_count = 0
    answer_count = 0
    last_check_answer_count = 0

    while True:
        if datetime.now() - start_time >= duration:
            break
        if question_count >= game.config.max_questions:
            break

        target_id = _select_target(game.players, current_questioner)

        questioner_char = _get_character_by_id(characters, current_questioner)
        questioner_player = next(p for p in game.players if p.character_id == current_questioner)
        questioner_secret = _get_secret_info(game, questioner_player)
        questioner_prompt = build_system_prompt(questioner_char, game, questioner_secret)

        history = await _build_compressed_conversation_history(game, provider)
        question_instruction = (
            f"Ты — {questioner_char.display_name}. Сейчас твоя очередь задать вопрос игроку {target_id}. "
            f"Задай один вопрос в своём стиле. Только вопрос, без пояснений."
        )
        messages = [
            {"role": "system", "content": questioner_prompt},
            *history,
            {"role": "user", "content": question_instruction},
        ]

        reroll_count = 0
        question_text = ""

        for attempt in range(MAX_QUESTION_REROLL_ATTEMPTS + 1):
            question_response = await provider.complete(
                messages=messages,
                model=game.config.main_model,
                temperature=0.9,
                max_tokens=150,
            )
            _track_usage_and_check_cost(game, question_response)
            question_text = question_response.content.strip()

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
                on_turn(leak_turn, game)

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
        )
        game.turns.append(turn)
        if on_turn:
            on_turn(turn, game)

        vote_trigger_checker.update_after_turn(turn)

        answerer_char = _get_character_by_id(characters, target_id)
        answerer_player = next(p for p in game.players if p.character_id == target_id)
        answerer_secret = _get_secret_info(game, answerer_player)
        answerer_prompt = build_system_prompt(answerer_char, game, answerer_secret)

        history = await _build_compressed_conversation_history(game, provider)
        answer_instruction = (
            f"Ты — {answerer_char.display_name}. Тебе только что задали вопрос. "
            f"Ответь на него в своём стиле. Только ответ, без пояснений."
        )
        messages = [
            {"role": "system", "content": answerer_prompt},
            *history,
            {"role": "user", "content": answer_instruction},
        ]

        answer_response = await provider.complete(
            messages=messages,
            model=game.config.main_model,
            temperature=0.9,
            max_tokens=200,
        )
        _track_usage_and_check_cost(game, answer_response)
        answer_text = answer_response.content.strip()

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
                on_turn(leak_turn, game)

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
        )
        game.turns.append(answer_turn)
        if on_turn:
            on_turn(answer_turn, game)

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

            if confidence_entry.level == ConfidenceLevel.CONFIDENT:
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
                        on_turn(guess_turn, game)

                    if guessed_correct:
                        game.outcome = GameOutcome(
                            winner="spy",
                            reason=f"Шпион ({game.spy_id}) угадал локацию: {actual_location.display_name}",
                            spy_guess=guessed_location_id,
                            spy_guess_correct=True,
                        )
                    else:
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
                intervention_content = await _generate_intervention_content(
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
                        on_turn(leak_turn, game)

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
                )
                game.turns.append(intervention_turn)
                if on_turn:
                    on_turn(intervention_turn, game)

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
            )
            break

        question_count += 1
        current_questioner = target_id

    return game


async def run_final_vote(
    game: Game,
    characters: list[Character],
    provider: Optional[LLMProvider] = None,
    on_turn: Optional[callable] = None,
) -> Game:
    """Run the final voting phase of the game.

    Each player votes for who they think is the spy.
    Winner is determined by majority vote.

    Args:
        game: Game object after main_round.
        characters: List of Character objects participating.
        provider: Optional LLM provider. If None, creates one from config.

    Returns:
        Updated Game object with outcome and votes recorded.
    """
    if provider is None:
        llm_config = LLMConfig()
        provider, _ = create_provider(llm_config, role="main")

    _transition_phase(game, GamePhase.FINAL_VOTE, "Final voting started")

    player_ids = [p.character_id for p in game.players]
    votes: dict[str, str] = {}

    for voter_player in game.players:
        voter_id = voter_player.character_id
        voter_char = _get_character_by_id(characters, voter_id)
        voter_secret = _get_secret_info(game, voter_player)
        voter_prompt = build_system_prompt(voter_char, game, voter_secret)

        candidates = [pid for pid in player_ids if pid != voter_id]
        candidates_str = ", ".join(candidates)

        history = await _build_compressed_conversation_history(game, provider)
        vote_instruction = (
            f"Ты — {voter_char.display_name}. Время голосования. "
            f"Кто из игроков, по-твоему, шпион? Выбери ОДНОГО из: {candidates_str}. "
            f"Напиши ТОЛЬКО имя (id) игрока, за которого голосуешь, без пояснений."
        )

        messages = [
            {"role": "system", "content": voter_prompt},
            *history,
            {"role": "user", "content": vote_instruction},
        ]

        vote_llm_response = await provider.complete(
            messages=messages,
            model=game.config.main_model,
            temperature=0.7,
            max_tokens=50,
        )
        _track_usage_and_check_cost(game, vote_llm_response)
        vote_response = vote_llm_response.content.strip().lower()

        voted_for = None
        for candidate in candidates:
            if candidate.lower() in vote_response or vote_response in candidate.lower():
                voted_for = candidate
                break

        if voted_for is None:
            voted_for = random.choice(candidates)

        votes[voter_id] = voted_for

        vote_content = f"Голосую за {voted_for}"
        turn = Turn(
            turn_number=len(game.turns) + 1,
            timestamp=datetime.now(),
            speaker_id=voter_id,
            addressee_id="all",
            type=TurnType.VOTE,
            content=vote_content,
            display_delay_ms=calculate_display_delay_ms(vote_content),
        )
        game.turns.append(turn)
        if on_turn:
            on_turn(turn, game)

    vote_counts: dict[str, int] = {}
    for voted_for in votes.values():
        vote_counts[voted_for] = vote_counts.get(voted_for, 0) + 1

    max_votes = max(vote_counts.values())
    top_voted = [pid for pid, count in vote_counts.items() if count == max_votes]
    accused = random.choice(top_voted) if len(top_voted) > 1 else top_voted[0]

    spy_caught = accused == game.spy_id

    if spy_caught:
        winner = "civilians"
        reason = f"Шпион ({game.spy_id}) был разоблачён голосованием"
    else:
        winner = "spy"
        reason = f"Мирные обвинили {accused}, но шпионом был {game.spy_id}"

    game.outcome = GameOutcome(
        winner=winner,
        reason=reason,
        votes=votes,
        accused_id=accused,
    )

    game.ended_at = datetime.now()
    _transition_phase(game, GamePhase.RESOLUTION, f"Game ended: {winner} won")

    return game
