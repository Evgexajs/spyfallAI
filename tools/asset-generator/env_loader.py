"""Environment loader for Asset Generator."""

import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


class ApiKeyMissingError(Exception):
    """Raised when OPENAI_API_KEY is not set."""
    pass


def _get_env_path() -> Path:
    """Return path to .env file."""
    return Path(__file__).parent / ".env"


def load_env() -> bool:
    """
    Load environment variables from .env file.

    Returns:
        True if .env file was found and loaded, False otherwise
    """
    env_path = _get_env_path()
    if env_path.exists():
        load_dotenv(env_path)
        return True
    return False


def get_api_key(dry_run: bool = False) -> Optional[str]:
    """
    Get OpenAI API key from environment.

    Args:
        dry_run: If True, missing key produces a warning instead of error

    Returns:
        API key string, or None in dry_run mode if key is missing

    Raises:
        ApiKeyMissingError: If key is not set and dry_run is False
    """
    load_env()

    api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        if dry_run:
            print(
                "Warning: OPENAI_API_KEY is not set. "
                "Create a .env file with OPENAI_API_KEY=your-key",
                file=sys.stderr
            )
            return None
        else:
            raise ApiKeyMissingError(
                "OPENAI_API_KEY is not set. "
                "Create a .env file in tools/asset-generator/ with:\n"
                "OPENAI_API_KEY=sk-your-api-key"
            )

    return api_key
