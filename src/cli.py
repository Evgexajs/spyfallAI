"""CLI entry point for SpyfallAI - Phase 0 MVP."""

import argparse
import asyncio
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.llm import LLMConfig, create_provider
from src.models import Character, Game, Turn, TurnType
from src.orchestrator import load_locations, run_final_vote, run_main_round, setup_game
from src.storage import save_game


COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "magenta": "\033[95m",
    "cyan": "\033[96m",
}

CHARACTER_COLORS = ["red", "green", "yellow", "blue", "magenta", "cyan"]


def load_character(character_id: str, characters_dir: Optional[Path] = None) -> Character:
    """Load a single character from JSON."""
    if characters_dir is None:
        characters_dir = Path(__file__).parent.parent / "characters"

    filepath = characters_dir / f"{character_id}.json"
    if not filepath.exists():
        raise FileNotFoundError(f"Character file not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Character.model_validate(data)


def list_available_characters(characters_dir: Optional[Path] = None) -> list[str]:
    """List all available character IDs."""
    if characters_dir is None:
        characters_dir = Path(__file__).parent.parent / "characters"

    return [f.stem for f in characters_dir.glob("*.json")]


def colorize(text: str, color: str) -> str:
    """Apply ANSI color to text."""
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def create_turn_printer(character_colors: dict[str, str], apply_delay: bool = True):
    """Create a callback to print turns to console with typing indicator and delay."""
    def print_turn(turn: Turn, game: Game) -> None:
        color = character_colors.get(turn.speaker_id, "reset")
        speaker = colorize(turn.speaker_id, color)

        if turn.display_delay_ms > 0 and apply_delay:
            typing_msg = f"{speaker} печатает..."
            print(typing_msg, end="\r", flush=True)
            time.sleep(turn.display_delay_ms / 1000)
            print(" " * len(typing_msg), end="\r")

        if turn.type == TurnType.QUESTION:
            type_marker = colorize("[Q]", "bold")
            addressee = colorize(turn.addressee_id, character_colors.get(turn.addressee_id, "reset"))
            print(f"{type_marker} {speaker} → {addressee}: {turn.content}")
        elif turn.type == TurnType.ANSWER:
            type_marker = colorize("[A]", "bold")
            addressee = colorize(turn.addressee_id, character_colors.get(turn.addressee_id, "reset"))
            print(f"{type_marker} {speaker} → {addressee}: {turn.content}")
        elif turn.type == TurnType.VOTE:
            type_marker = colorize("[V]", "bold")
            print(f"{type_marker} {speaker}: {turn.content}")
        elif turn.type == TurnType.INTERVENTION:
            type_marker = colorize("[!]", "bold")
            print(f"{type_marker} {speaker}: {turn.content}")
        else:
            print(f"[{turn.type}] {speaker}: {turn.content}")

        print()

    return print_turn


async def run_game(
    character_ids: list[str],
    location_id: Optional[str],
    duration_minutes: int,
    max_questions: int,
) -> Path:
    """Run a complete game and return the path to the saved log."""
    print(colorize("=" * 60, "bold"))
    print(colorize("        SpyfallAI - Phase 0 MVP", "bold"))
    print(colorize("=" * 60, "bold"))
    print()

    characters = [load_character(cid) for cid in character_ids]
    print(f"Игроки: {', '.join(c.display_name for c in characters)}")

    locations = load_locations()
    if location_id is None:
        location = random.choice(locations)
        location_id = location.id
    else:
        location = next((loc for loc in locations if loc.id == location_id), None)
        if location is None:
            raise ValueError(f"Location '{location_id}' not found")

    print(f"Локация: {location.display_name}")
    print(f"Длительность: {duration_minutes} мин, макс. вопросов: {max_questions}")
    print()

    llm_config = LLMConfig()
    provider, model = create_provider(llm_config, role="main")
    print(f"Модель: {model}")
    print()

    print(colorize("-" * 60, "bold"))
    print(colorize("SETUP", "bold"))
    print(colorize("-" * 60, "bold"))
    print()

    game = setup_game(
        characters=characters,
        location_id=location_id,
        duration_minutes=duration_minutes,
        max_questions=max_questions,
        main_model=model,
    )

    spy_char = next(c for c in characters if c.id == game.spy_id)
    print(colorize(f"Шпион: {spy_char.display_name} ({game.spy_id})", "red"))
    print()

    for player in game.players:
        char = next(c for c in characters if c.id == player.character_id)
        if player.is_spy:
            print(f"  {char.display_name}: ШПИОН (не знает локацию)")
        else:
            print(f"  {char.display_name}: роль '{player.role_id}'")
    print()

    character_colors = {
        cid: CHARACTER_COLORS[i % len(CHARACTER_COLORS)]
        for i, cid in enumerate(character_ids)
    }
    print_turn = create_turn_printer(character_colors)

    print(colorize("-" * 60, "bold"))
    print(colorize("MAIN ROUND", "bold"))
    print(colorize("-" * 60, "bold"))
    print()

    game = await run_main_round(game, characters, provider, on_turn=print_turn)

    print(colorize("-" * 60, "bold"))
    print(colorize("FINAL VOTE", "bold"))
    print(colorize("-" * 60, "bold"))
    print()

    game = await run_final_vote(game, characters, provider, on_turn=print_turn)

    print(colorize("-" * 60, "bold"))
    print(colorize("RESOLUTION", "bold"))
    print(colorize("-" * 60, "bold"))
    print()

    if game.outcome:
        if game.outcome.winner == "civilians":
            print(colorize(f"Победа мирных! {game.outcome.reason}", "green"))
        else:
            print(colorize(f"Победа шпиона! {game.outcome.reason}", "red"))
    print()

    filepath = save_game(game)
    print(f"Лог сохранён: {filepath}")

    return filepath


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SpyfallAI - AI-powered Spyfall game generator"
    )
    parser.add_argument(
        "-c", "--characters",
        type=str,
        default=None,
        help="Comma-separated character IDs (default: all available)"
    )
    parser.add_argument(
        "-l", "--location",
        type=str,
        default=None,
        help="Location ID (default: random)"
    )
    parser.add_argument(
        "-d", "--duration",
        type=int,
        default=int(os.environ.get("GAME_DURATION_MINUTES", "3")),
        help="Game duration in minutes (default: 3)"
    )
    parser.add_argument(
        "-q", "--max-questions",
        type=int,
        default=int(os.environ.get("MAX_QUESTIONS_BEFORE_VOTE", "50")),
        help="Max questions before forced vote (default: 50)"
    )
    parser.add_argument(
        "--list-characters",
        action="store_true",
        help="List available characters and exit"
    )
    parser.add_argument(
        "--list-locations",
        action="store_true",
        help="List available locations and exit"
    )

    args = parser.parse_args()

    if args.list_characters:
        chars = list_available_characters()
        print("Available characters:")
        for cid in chars:
            char = load_character(cid)
            print(f"  {cid}: {char.display_name} ({char.archetype})")
        return

    if args.list_locations:
        locations = load_locations()
        print("Available locations:")
        for loc in locations:
            roles = ", ".join(r.id for r in loc.roles)
            print(f"  {loc.id}: {loc.display_name}")
            print(f"    Roles: {roles}")
        return

    if args.characters:
        character_ids = [c.strip() for c in args.characters.split(",")]
    else:
        character_ids = list_available_characters()

    if len(character_ids) < 3:
        print("Error: At least 3 characters required", file=sys.stderr)
        sys.exit(1)

    try:
        filepath = asyncio.run(run_game(
            character_ids=character_ids,
            location_id=args.location,
            duration_minutes=args.duration,
            max_questions=args.max_questions,
        ))
        print()
        print(colorize("Game completed successfully!", "green"))
    except KeyboardInterrupt:
        print("\nGame interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
