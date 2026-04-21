"""CLI command for retrospective game analysis (CR-003).

Usage:
    python -m src.analyze --game-id <uuid>
    python -m src.analyze --game-id <uuid> --no-overwrite
    python -m src.analyze --all
    python -m src.analyze --all --no-overwrite
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

from src.post_game.analyzer import PostGameAnalyzer
from src.storage.game_repository import list_games


def find_game_path_by_id(game_id: str, games_dir: Optional[Path] = None) -> Optional[Path]:
    """Find game log file path by game ID.

    Args:
        game_id: The UUID string of the game to find.
        games_dir: Optional custom directory. Defaults to project's games/.

    Returns:
        Path to the game file if found, None otherwise.
    """
    if games_dir is None:
        games_dir = Path(__file__).parent.parent / "games"

    games_dir = Path(games_dir)
    if not games_dir.exists():
        return None

    matching_files = list(games_dir.glob(f"*_{game_id}.json"))
    if not matching_files:
        return None

    return matching_files[0]


def has_post_game_analysis(game_path: Path) -> bool:
    """Check if a game log already has post_game_analysis field."""
    try:
        with open(game_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return "post_game_analysis" in data
    except (json.JSONDecodeError, OSError):
        return False


def get_game_id_from_path(game_path: Path) -> str:
    """Extract game ID from filename.

    Filename format: {YYYY-MM-DD}_{HH-MM-SS}_{game_id}.json
    """
    stem = game_path.stem
    parts = stem.split("_")
    if len(parts) >= 3:
        return "_".join(parts[2:])
    return stem


async def analyze_single_game(
    game_path: Path,
    no_overwrite: bool = False
) -> tuple[bool, str]:
    """Analyze a single game.

    Args:
        game_path: Path to the game JSON file.
        no_overwrite: If True, skip if analysis already exists.

    Returns:
        Tuple of (success: bool, message: str).
    """
    game_id = get_game_id_from_path(game_path)

    if no_overwrite and has_post_game_analysis(game_path):
        return True, f"Skipped (analysis exists): {game_id}"

    analyzer = PostGameAnalyzer()

    try:
        analysis = await analyzer.analyze(game_path)

        if analysis.status.value == "failed":
            error_msg = analysis.error or "unknown error"
            return False, f"Analysis failed for {game_id}: {error_msg}"

        analyzer.save_analysis(game_path, analysis)

        status_msg = f"Analyzed: {game_id} (status={analysis.status.value})"
        if analysis.error:
            status_msg += f", note: {analysis.error}"

        return True, status_msg

    except FileNotFoundError:
        return False, f"Game file not found: {game_path}"
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON in {game_id}: {e}"
    except Exception as e:
        return False, f"Error analyzing {game_id}: {e}"


async def analyze_all_games(no_overwrite: bool = False) -> tuple[int, int, int]:
    """Analyze all games without post_game_analysis.

    Args:
        no_overwrite: If True, skip games that already have analysis.

    Returns:
        Tuple of (analyzed_count, skipped_count, error_count).
    """
    game_paths = list_games()

    if not game_paths:
        print("No games found in games/ directory")
        return 0, 0, 0

    analyzed = 0
    skipped = 0
    errors = 0

    for game_path in game_paths:
        success, message = await analyze_single_game(game_path, no_overwrite)
        print(message)

        if "Skipped" in message:
            skipped += 1
        elif success:
            analyzed += 1
        else:
            errors += 1

    return analyzed, skipped, errors


def main() -> int:
    """Main entry point for the analyze CLI.

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    parser = argparse.ArgumentParser(
        description="Analyze completed SpyfallAI games for character behavior."
    )
    parser.add_argument(
        "--game-id",
        type=str,
        help="UUID of the game to analyze"
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Skip if post_game_analysis already exists"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="analyze_all",
        help="Analyze all games without post_game_analysis"
    )

    args = parser.parse_args()

    if not args.game_id and not args.analyze_all:
        parser.error("Either --game-id or --all is required")

    if args.game_id and args.analyze_all:
        parser.error("Cannot use both --game-id and --all")

    if args.analyze_all:
        analyzed, skipped, errors = asyncio.run(
            analyze_all_games(no_overwrite=args.no_overwrite)
        )
        print(f"\nSummary: {analyzed} analyzed, {skipped} skipped, {errors} errors")
        return 1 if errors > 0 else 0

    game_path = find_game_path_by_id(args.game_id)
    if game_path is None:
        print(f"Error: Game not found with ID: {args.game_id}")
        return 1

    success, message = asyncio.run(
        analyze_single_game(game_path, no_overwrite=args.no_overwrite)
    )
    print(message)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
