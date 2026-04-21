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

from src.llm import CostExceededError, LLMConfig, create_provider
from src.models import Character, Game, Turn, TurnType
from src.models import GameOutcome
from src.orchestrator import (
    load_locations,
    run_defense_speeches,
    run_final_vote,
    run_main_round,
    run_preliminary_vote,
    run_preliminary_with_revotes,
    setup_game,
)
from src.post_game.analyzer import PostGameAnalyzer
from src.post_game.config import POST_GAME_ANALYSIS_ENABLED
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
        elif turn.type == TurnType.PRELIMINARY_VOTE:
            type_marker = colorize("[PV]", "bold")
            print(f"{type_marker} {speaker}: {turn.content}")
        elif turn.type == TurnType.DEFENSE_SPEECH:
            type_marker = colorize("[DEF]", "magenta")
            print(f"{type_marker} {speaker}: {turn.content}")
        elif turn.type == TurnType.FINAL_VOTE:
            type_marker = colorize("[FV]", "bold")
            print(f"{type_marker} {speaker}: {turn.content}")
        elif turn.type == TurnType.INTERVENTION:
            type_marker = colorize("[!]", "bold")
            print(f"{type_marker} {speaker}: {turn.content}")
        elif turn.type == TurnType.SPY_LEAK:
            type_marker = colorize("[LEAK!]", "red")
            print(f"{type_marker} {speaker}: {turn.content}")
        elif turn.type == TurnType.SYSTEM:
            print(colorize(turn.content, "yellow"))
        else:
            print(f"[{turn.type}] {speaker}: {turn.content}")

        print()

    return print_turn


async def run_game(
    character_ids: list[str],
    location_id: Optional[str],
    duration_minutes: int,
    max_questions: int,
    skip_analysis: bool = False,
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

    cost_exceeded = False
    try:
        while game.outcome is None:
            print(colorize("-" * 60, "bold"))
            print(colorize("MAIN ROUND", "bold"))
            print(colorize("-" * 60, "bold"))
            print()

            game = await run_main_round(game, characters, provider, on_turn=print_turn)

            if game.outcome is None:
                print(colorize("-" * 60, "bold"))
                print(colorize("PRELIMINARY VOTE + DEFENSE + REVOTES", "bold"))
                print(colorize("-" * 60, "bold"))
                print()

                # Run preliminary vote with re-vote cycle
                game, vote_counts, is_unanimous, accused_id = await run_preliminary_with_revotes(
                    game, characters, provider, on_turn=print_turn
                )

                if is_unanimous and accused_id:
                    # Unanimous - resolve
                    spy_caught = accused_id == game.spy_id
                    spy_char = next(c for c in characters if c.id == game.spy_id)

                    if spy_caught:
                        game.outcome = GameOutcome(
                            winner="civilians",
                            reason=f"Шпион ({spy_char.display_name}) был единогласно разоблачён",
                            votes=game.preliminary_vote_result,
                            accused_id=accused_id,
                        )
                    else:
                        accused_char = next(c for c in characters if c.id == accused_id)
                        game.outcome = GameOutcome(
                            winner="spy",
                            reason=f"Игроки единогласно обвинили {accused_char.display_name}, но шпионом был {spy_char.display_name}",
                            votes=game.preliminary_vote_result,
                            accused_id=accused_id,
                        )
                    game.ended_at = datetime.now()

                elif game.outcome is None:
                    # Not unanimous - proceed to final vote (for critical triggers only in web)
                    # In CLI we always go to final vote for simplicity
                    print()
                    print(colorize("Нет единогласия — финальное голосование", "yellow"))
                    print()

                    print(colorize("-" * 60, "bold"))
                    print(colorize("FINAL VOTE", "bold"))
                    print(colorize("-" * 60, "bold"))
                    print()

                    game = await run_final_vote(
                        game, characters, provider,
                        on_turn=print_turn,
                        defense_was_executed=True,
                    )
    except CostExceededError as e:
        cost_exceeded = True
        print()
        print(colorize(f"ОСТАНОВКА: {e}", "red"))
        game.ended_at = datetime.now()

    print(colorize("-" * 60, "bold"))
    print(colorize("RESOLUTION", "bold"))
    print(colorize("-" * 60, "bold"))
    print()

    if cost_exceeded:
        print(colorize("Игра прервана: превышен лимит стоимости", "red"))
    elif game.outcome:
        if game.outcome.winner == "civilians":
            print(colorize(f"Победа мирных! {game.outcome.reason}", "green"))
        else:
            print(colorize(f"Победа шпиона! {game.outcome.reason}", "red"))
    print()

    print(colorize("-" * 60, "bold"))
    print(colorize("СТАТИСТИКА", "bold"))
    print(colorize("-" * 60, "bold"))
    print()
    usage = game.token_usage
    print(f"Токены (вход): {usage.total_input_tokens:,}")
    print(f"Токены (выход): {usage.total_output_tokens:,}")
    print(f"Токенов всего: {usage.total_tokens:,}")
    print(f"LLM вызовов: {usage.llm_calls_count}")
    print(f"Стоимость: ${usage.total_cost_usd:.4f}")
    print()

    filepath = save_game(game)
    print(f"Лог сохранён: {filepath}")

    # Post-game analysis (runs AFTER game log is saved)
    should_analyze = POST_GAME_ANALYSIS_ENABLED and not skip_analysis
    if should_analyze:
        print()
        print(colorize("-" * 60, "bold"))
        print(colorize("POST-GAME ANALYSIS", "bold"))
        print(colorize("-" * 60, "bold"))
        print()
        try:
            analyzer = PostGameAnalyzer()
            analysis = await analyzer.analyze(filepath)
            if analysis.status.value != "failed":
                analyzer.save_analysis(filepath, analysis)
                print(colorize(f"Анализ сохранён в лог ({analysis.status.value})", "green"))
            else:
                print(colorize(f"Анализ не удался: {analysis.error}", "yellow"))
        except Exception as e:
            print(colorize(f"Ошибка анализа: {e}", "yellow"))
            print(colorize("Лог партии сохранён без анализа", "yellow"))

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
        help="Comma-separated character IDs (overrides -n)"
    )
    parser.add_argument(
        "-n", "--players",
        type=int,
        default=int(os.environ.get("PLAYERS_PER_GAME", "4")),
        help="Number of random players (default: 4, ignored if -c specified)"
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
        default=int(os.environ.get("GAME_DURATION_MINUTES", "5")),
        help="Game duration in minutes (default: 5, env: GAME_DURATION_MINUTES)"
    )
    parser.add_argument(
        "-q", "--max-questions",
        type=int,
        default=int(os.environ.get("MAX_QUESTIONS_BEFORE_VOTE", "30")),
        help="Max questions before forced vote (default: 30, env: MAX_QUESTIONS_BEFORE_VOTE)"
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
    parser.add_argument(
        "--skip-analysis",
        action="store_true",
        help="Skip post-game analysis after game completion"
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

    available = list_available_characters()

    if args.characters:
        character_ids = [c.strip() for c in args.characters.split(",")]
    else:
        if args.players > len(available):
            print(f"Error: Requested {args.players} players but only {len(available)} available", file=sys.stderr)
            sys.exit(1)
        character_ids = random.sample(available, args.players)
        print(f"Случайно выбрано {args.players} игроков: {', '.join(character_ids)}")

    if len(character_ids) < 3:
        print("Error: At least 3 characters required", file=sys.stderr)
        sys.exit(1)

    try:
        filepath = asyncio.run(run_game(
            character_ids=character_ids,
            location_id=args.location,
            duration_minutes=args.duration,
            max_questions=args.max_questions,
            skip_analysis=args.skip_analysis,
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
