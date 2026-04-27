#!/usr/bin/env python3
"""Asset Generator - CLI tool for generating character images via OpenAI API."""

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from cli_parser import parse_args, CLIArgs
from character_loader import load_character, list_characters, CharacterNotFoundError
from prompt_builder import build_prompt
from env_loader import load_env, get_api_key, ApiKeyMissingError
from reference_loader import get_reference_path, ReferenceImageMissingError
from image_saver import save_image, image_exists, get_image_path
from log_saver import save_log
from generation_orchestrator import generate_image, GenerationResult
from image_client import ImageGenerationError, MIN_REQUEST_INTERVAL


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


def generate_character(
    character_id: str,
    args: CLIArgs,
    api_key: str,
    reference_path: Optional[Path],
) -> bool:
    """
    Generate image for a single character.

    Returns:
        True on success, False on error
    """
    try:
        character_config = load_character(character_id)
    except CharacterNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return False

    if image_exists(character_id) and not args.regenerate:
        print(f"[{character_id}] Image already exists, skipping (use --regenerate to overwrite)")
        return True

    prompt = build_prompt(character_config)
    display_name = character_config.get("display_name", character_id)

    print(f"[{character_id}] Generating {display_name}...")

    start_time = time.time()
    timestamp = datetime.now()
    status = "success"
    error_msg = None
    warning_msg = None
    result: Optional[GenerationResult] = None

    try:
        result = generate_image(
            prompt=prompt,
            approach=args.approach,
            reference_path=reference_path,
            model=args.model,
            size=DEFAULT_SIZE,
            quality=DEFAULT_QUALITY,
            api_key=api_key,
        )
    except ImageGenerationError as e:
        status = "error"
        error_msg = str(e)
        print(f"[{character_id}] ERROR: {e}", file=sys.stderr)

    elapsed = time.time() - start_time

    log_data = {
        "character_id": character_id,
        "timestamp": timestamp,
        "model": args.model,
        "approach": result.actual_approach if result else "unknown",
        "requested_approach": args.approach,
        "status": status,
        "prompt": prompt,
        "elapsed_seconds": round(elapsed, 2),
        "size": DEFAULT_SIZE,
        "quality": DEFAULT_QUALITY,
    }

    if result and result.fallback_triggered:
        warning_msg = f"Fallback to text-only triggered: {result.fallback_reason}"
        log_data["warning"] = warning_msg
        log_data["fallback_trigger"] = result.fallback_reason
        print(f"[{character_id}] WARNING: {warning_msg}")

    if error_msg:
        log_data["error"] = error_msg

    log_path = save_log(log_data)
    print(f"[{character_id}] Log saved: {log_path}")

    if status == "error":
        return False

    output_path, was_written = save_image(
        character_id=character_id,
        image_bytes=result.image_bytes,
        regenerate=args.regenerate,
    )

    if was_written:
        print(f"[{character_id}] Image saved: {output_path}")
    else:
        print(f"[{character_id}] Image already exists: {output_path}")

    print(f"[{character_id}] Done ({elapsed:.1f}s)")
    return True


def run_generation(args: CLIArgs) -> int:
    """
    Execute generation mode for --character.

    Returns:
        0 on success, 1 on error
    """
    load_env()

    try:
        api_key = get_api_key(dry_run=False)
    except ApiKeyMissingError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    reference_path = None
    if args.approach != "text-only":
        try:
            reference_path = get_reference_path(text_only=False)
        except ReferenceImageMissingError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

    if args.character:
        success = generate_character(args.character, args, api_key, reference_path)
        return 0 if success else 1
    else:
        return run_all_characters(args, api_key, reference_path)


def run_all_characters(args: CLIArgs, api_key: str, reference_path: Optional[Path]) -> int:
    """
    Execute generation mode for --all-characters.

    Generates all characters from config with a pause between each request.
    Continues with remaining characters if one fails.

    Returns:
        0 if all succeeded, 1 if any failed
    """
    character_ids = list_characters()
    total = len(character_ids)
    succeeded = 0
    failed = 0

    print(f"Generating {total} character(s)...")
    print()

    for i, character_id in enumerate(character_ids):
        if i > 0:
            print(f"Waiting {MIN_REQUEST_INTERVAL:.0f}s before next request...")
            time.sleep(MIN_REQUEST_INTERVAL)
            print()

        success = generate_character(character_id, args, api_key, reference_path)
        if success:
            succeeded += 1
        else:
            failed += 1

    print()
    print("=" * 40)
    print(f"SUMMARY: {succeeded}/{total} succeeded, {failed}/{total} failed")
    print("=" * 40)

    return 0 if failed == 0 else 1


def main() -> int:
    """Main entry point."""
    try:
        args = parse_args()
    except SystemExit as e:
        return e.code if e.code is not None else 1

    if args.dry_run:
        return run_dry_run(args)

    return run_generation(args)


if __name__ == "__main__":
    sys.exit(main())
