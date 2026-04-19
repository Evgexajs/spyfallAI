"""Game repository for saving and loading game logs."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models.game import Game


def _get_games_dir() -> Path:
    """Get the games directory path."""
    root = Path(__file__).parent.parent.parent
    return root / "games"


def save_game(game: Game, games_dir: Optional[Path] = None) -> Path:
    """
    Save a game to a JSON file.

    Filename format: {YYYY-MM-DD}_{HH-MM-SS}_{game_id}.json
    Never overwrites existing files.

    Args:
        game: The Game object to save.
        games_dir: Optional custom directory for saving. Defaults to project's games/.

    Returns:
        Path to the saved file.

    Raises:
        FileExistsError: If file already exists (should never happen with unique IDs).
    """
    if games_dir is None:
        games_dir = _get_games_dir()

    games_dir = Path(games_dir)
    games_dir.mkdir(parents=True, exist_ok=True)

    timestamp = game.started_at.strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{timestamp}_{game.id}.json"
    filepath = games_dir / filename

    if filepath.exists():
        raise FileExistsError(f"Game log already exists: {filepath}")

    game_data = game.model_dump(mode="json")

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(game_data, f, ensure_ascii=False, indent=2, default=str)

    return filepath


def load_game(filepath: Path) -> Game:
    """
    Load a game from a JSON file.

    Args:
        filepath: Path to the game JSON file.

    Returns:
        Loaded Game object.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    return Game.model_validate(data)


def list_games(games_dir: Optional[Path] = None) -> list[Path]:
    """
    List all game log files.

    Args:
        games_dir: Optional custom directory. Defaults to project's games/.

    Returns:
        List of paths to game files, sorted by modification time (newest first).
    """
    if games_dir is None:
        games_dir = _get_games_dir()

    games_dir = Path(games_dir)
    if not games_dir.exists():
        return []

    files = list(games_dir.glob("*.json"))
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files
