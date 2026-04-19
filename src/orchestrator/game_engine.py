"""Game orchestrator for SpyfallAI - setup and game flow management."""

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from src.models import (
    Character,
    Game,
    GameConfig,
    GamePhase,
    Location,
    PhaseEntry,
    Player,
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
