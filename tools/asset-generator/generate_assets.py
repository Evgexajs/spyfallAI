#!/usr/bin/env python3
"""Asset Generator - CLI tool for generating character images via OpenAI API."""

import sys
from pathlib import Path

from cli_parser import parse_args, CLIArgs
from character_loader import load_character, list_characters, CharacterNotFoundError
from prompt_builder import build_prompt
from env_loader import get_api_key, ApiKeyMissingError
from reference_loader import get_reference_path, ReferenceImageMissingError
from image_saver import get_image_path


DEFAULT_SIZE = "1024x1536"
DEFAULT_QUALITY = "high"


def run_dry_run(args: CLIArgs) -> int:
    """
    Execute dry-run mode: validate config, show prompt and parameters.

    Returns:
        0 on success, 1 on error
    """
    print("=" * 60)
    print("DRY RUN MODE - No API calls will be made")
    print("=" * 60)
    print()

    character_ids = []
    if args.character:
        character_ids = [args.character]
    else:
        character_ids = list_characters()

    get_api_key(dry_run=True)

    reference_path = None
    if args.approach != "text-only":
        try:
            reference_path = get_reference_path(text_only=False)
        except ReferenceImageMissingError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

    for i, character_id in enumerate(character_ids):
        if i > 0:
            print()
            print("-" * 60)
            print()

        try:
            character_config = load_character(character_id)
        except CharacterNotFoundError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

        prompt = build_prompt(character_config)

        output_path = get_image_path(character_id)

        print(f"CHARACTER: {character_id}")
        print(f"  Display name: {character_config.get('display_name', 'N/A')}")
        print(f"  Archetype: {character_config.get('archetype', 'N/A')}")
        print()

        print("PARAMETERS:")
        print(f"  Model: {args.model}")
        print(f"  Approach: {args.approach}")
        print(f"  Size: {DEFAULT_SIZE}")
        print(f"  Quality: {DEFAULT_QUALITY}")
        print(f"  Regenerate: {args.regenerate}")
        print()

        print("PATHS:")
        print(f"  Output: {output_path}")
        if reference_path:
            print(f"  Reference: {reference_path}")
        else:
            print(f"  Reference: N/A (text-only mode)")
        print()

        print("PROMPT:")
        print("-" * 40)
        print(prompt)
        print("-" * 40)

    print()
    print("=" * 60)
    print(f"Dry run complete. {len(character_ids)} character(s) would be generated.")
    print("=" * 60)

    return 0


def main() -> int:
    """Main entry point."""
    try:
        args = parse_args()
    except SystemExit as e:
        return e.code if e.code is not None else 1

    if args.dry_run:
        return run_dry_run(args)

    print("Generation mode not implemented yet. Use --dry-run to preview.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
