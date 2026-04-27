"""CLI argument parser for Asset Generator."""

import argparse
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class CLIArgs:
    """Parsed CLI arguments."""
    character: Optional[str]
    all_characters: bool
    model: str
    approach: str
    regenerate: bool
    dry_run: bool


def create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(
        prog="generate_assets.py",
        description="Generate character images using OpenAI Image API.",
        epilog="Example: python generate_assets.py --character boris_molot --dry-run"
    )

    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument(
        "--character",
        metavar="ID",
        help="Generate a single character by ID (e.g., boris_molot, aurora)"
    )
    target_group.add_argument(
        "--all-characters",
        action="store_true",
        help="Generate all characters from config/characters.json"
    )

    parser.add_argument(
        "--model",
        default="gpt-image-2",
        metavar="NAME",
        help="OpenAI image model to use (default: gpt-image-2)"
    )

    parser.add_argument(
        "--approach",
        choices=["auto", "reference", "text-only"],
        default="auto",
        help="Generation approach: auto (reference with fallback), "
             "reference (no fallback), text-only (no reference). Default: auto"
    )

    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Overwrite existing output files (default: skip existing)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show prompt and parameters without calling API or creating files"
    )

    return parser


def parse_args(args: Optional[list[str]] = None) -> CLIArgs:
    """
    Parse command-line arguments.

    Args:
        args: List of arguments to parse. If None, uses sys.argv[1:].

    Returns:
        CLIArgs dataclass with parsed values.

    Raises:
        SystemExit: On invalid arguments (argparse behavior).
    """
    parser = create_parser()

    try:
        parsed = parser.parse_args(args)
    except SystemExit as e:
        raise

    return CLIArgs(
        character=parsed.character,
        all_characters=parsed.all_characters,
        model=parsed.model,
        approach=parsed.approach,
        regenerate=parsed.regenerate,
        dry_run=parsed.dry_run,
    )
