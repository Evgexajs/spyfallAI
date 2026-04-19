"""Game orchestrator for SpyfallAI - setup and game flow management."""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from uuid import uuid4

from src.agents import SecretInfo, build_system_prompt
from src.llm import LLMConfig, LLMProvider, create_provider
from src.models import (
    Character,
    Game,
    GameConfig,
    GamePhase,
    Location,
    PhaseEntry,
    Player,
    Turn,
    TurnType,
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


async def run_main_round(
    game: Game,
    characters: list[Character],
    provider: Optional[LLMProvider] = None,
) -> Game:
    """Run the main question-answer round of the game.

    Args:
        game: Initialized Game object from setup_game().
        characters: List of Character objects participating.
        provider: Optional LLM provider. If None, creates one from config.

    Returns:
        Updated Game object with turns recorded.
    """
    if provider is None:
        llm_config = LLMConfig()
        provider, _ = create_provider(llm_config, role="main")

    _transition_phase(game, GamePhase.MAIN_ROUND, "Main round started")

    player_ids = [p.character_id for p in game.players]
    current_questioner = random.choice(player_ids)

    start_time = game.started_at
    duration = timedelta(minutes=game.config.duration_minutes)
    question_count = 0

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

        history = _build_conversation_history(game)
        question_instruction = (
            f"Ты — {questioner_char.display_name}. Сейчас твоя очередь задать вопрос игроку {target_id}. "
            f"Задай один вопрос в своём стиле. Только вопрос, без пояснений."
        )
        messages = [
            {"role": "system", "content": questioner_prompt},
            *history,
            {"role": "user", "content": question_instruction},
        ]

        question_text = await provider.complete(
            messages=messages,
            model=game.config.main_model,
            temperature=0.9,
            max_tokens=150,
        )
        question_text = question_text.strip()

        game.turns.append(Turn(
            turn_number=len(game.turns) + 1,
            timestamp=datetime.now(),
            speaker_id=current_questioner,
            addressee_id=target_id,
            type=TurnType.QUESTION,
            content=question_text,
            display_delay_ms=0,
        ))

        answerer_char = _get_character_by_id(characters, target_id)
        answerer_player = next(p for p in game.players if p.character_id == target_id)
        answerer_secret = _get_secret_info(game, answerer_player)
        answerer_prompt = build_system_prompt(answerer_char, game, answerer_secret)

        history = _build_conversation_history(game)
        answer_instruction = (
            f"Ты — {answerer_char.display_name}. Тебе только что задали вопрос. "
            f"Ответь на него в своём стиле. Только ответ, без пояснений."
        )
        messages = [
            {"role": "system", "content": answerer_prompt},
            *history,
            {"role": "user", "content": answer_instruction},
        ]

        answer_text = await provider.complete(
            messages=messages,
            model=game.config.main_model,
            temperature=0.9,
            max_tokens=200,
        )
        answer_text = answer_text.strip()

        game.turns.append(Turn(
            turn_number=len(game.turns) + 1,
            timestamp=datetime.now(),
            speaker_id=target_id,
            addressee_id=current_questioner,
            type=TurnType.ANSWER,
            content=answer_text,
            display_delay_ms=0,
        ))

        question_count += 1
        current_questioner = target_id

    return game
