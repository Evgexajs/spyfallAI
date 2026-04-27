"""JSON log saver for Asset Generator."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


REQUIRED_FIELDS = {
    "character_id",
    "timestamp",
    "model",
    "approach",
    "requested_approach",
    "status",
    "prompt",
    "elapsed_seconds",
}

OPTIONAL_FIELDS = {
    "revised_prompt",
    "usage",
    "output_format",
    "size",
    "quality",
    "warning",
    "error",
    "fallback_trigger",
}


class LogValidationError(Exception):
    """Raised when log data is missing required fields."""
    pass


def _get_logs_dir() -> Path:
    """Return path to logs output directory."""
    return Path(__file__).parent / "output" / "logs"


def save_log(log_data: Dict[str, Any]) -> Path:
    """
    Save generation log to JSON file.

    Args:
        log_data: Dictionary with log fields.
            Required: character_id, timestamp, model, approach,
                      requested_approach, status, prompt, elapsed_seconds
            Optional: revised_prompt, usage, output_format, size,
                      quality, warning, error, fallback_trigger

    Returns:
        Path to saved log file

    Raises:
        LogValidationError: If required fields are missing
    """
    missing = REQUIRED_FIELDS - set(log_data.keys())
    if missing:
        raise LogValidationError(
            f"Missing required log fields: {', '.join(sorted(missing))}"
        )

    logs_dir = _get_logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = log_data["timestamp"]
    if isinstance(timestamp, datetime):
        timestamp_str = timestamp.isoformat()
        log_data = {**log_data, "timestamp": timestamp_str}
    else:
        timestamp_str = timestamp

    filename_ts = timestamp_str.replace(":", "-").replace(".", "-")
    character_id = log_data["character_id"]
    filename = f"{filename_ts}_{character_id}.json"

    log_path = logs_dir / filename
    log_path.write_text(json.dumps(log_data, indent=2, ensure_ascii=False))

    return log_path


def get_logs_dir() -> Path:
    """
    Get the logs output directory path.

    Returns:
        Path to logs directory (may not exist yet)
    """
    return _get_logs_dir()
