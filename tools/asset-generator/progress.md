# Progress Log - Asset Generator

## Summary

This file tracks the progress of Asset Generator development tasks.
Each agent session should add an entry when completing a task.

---

## Log Entries

<!-- 
Format for entries:
### TASK-AG-XXX: [Task Description]
**Date:** YYYY-MM-DD
**Status:** done
**Summary:** Brief description of what was implemented
**Files changed:**
- path/to/file1.py
- path/to/file2.py
**Notes:** Any additional notes or blockers encountered
-->

### TASK-AG-001: Инициализация структуры проекта asset-generator
**Date:** 2026-04-27
**Status:** done
**Summary:** Created project folder structure with config/, prompts/, reference/, output/characters/, output/logs/. Added .gitkeep files and configured .gitignore to exclude binary assets while keeping directory structure.
**Files changed:**
- config/ (created)
- prompts/ (created)
- reference/.gitkeep (created)
- output/characters/.gitkeep (created)
- output/logs/.gitkeep (created)
- .gitignore (created)
**Notes:** None

### TASK-AG-002: Создание requirements.txt с зависимостями
**Date:** 2026-04-27
**Status:** done
**Summary:** Created requirements.txt with openai>=1.0.0 and python-dotenv>=1.0.0 dependencies. Installation tested successfully.
**Files changed:**
- requirements.txt (created)
**Notes:** Used python3 -m pip for installation as pip command was not in PATH.

### TASK-AG-003: Создание config/characters.json с 2 персонажами
**Date:** 2026-04-27
**Status:** done
**Summary:** Created config/characters.json with boris_molot and aurora character configurations. Content matches spec section 6.1 exactly. All required fields present: display_name, archetype, color_accent, visual_description, pose_notes.
**Files changed:**
- config/characters.json (created)
**Notes:** JSON validated with python -m json.tool.

### TASK-AG-004: Создание prompts/character_template.txt
**Date:** 2026-04-27
**Status:** done
**Summary:** Created prompts/character_template.txt with exact content from spec section 6.2. Template contains placeholders {visual_description} and {pose_notes} for character-specific substitution.
**Files changed:**
- prompts/character_template.txt (created)
**Notes:** All test steps passed - template content verified and placeholders confirmed.

### TASK-AG-005: Модуль загрузки конфигурации персонажей
**Date:** 2026-04-27
**Status:** done
**Summary:** Created character_loader.py module with load_character() and list_characters() functions. Includes CharacterNotFoundError with clear error messages listing available characters.
**Files changed:**
- character_loader.py (created)
**Notes:** All test steps passed - module imports cleanly, load_character returns dict with all 5 fields, CharacterNotFoundError shows available characters.

### TASK-AG-006: Модуль сборки промпта из шаблона
**Date:** 2026-04-27
**Status:** done
**Summary:** Created prompt_builder.py module with build_prompt(character_config) function. Loads template from prompts/character_template.txt, substitutes {visual_description} and {pose_notes} placeholders with character config values, returns complete prompt string.
**Files changed:**
- prompt_builder.py (created)
**Notes:** All test steps passed - prompt for boris_molot contains correct description, no unsubstituted placeholders remain.

### TASK-AG-007: Модуль загрузки .env и проверки API ключа
**Date:** 2026-04-27
**Status:** done
**Summary:** Created env_loader.py module with load_env() and get_api_key(dry_run) functions. load_env() loads .env via python-dotenv. get_api_key() returns OPENAI_API_KEY with clear error message (ApiKeyMissingError) if missing. In dry_run mode, missing key produces a warning to stderr and returns None instead of raising.
**Files changed:**
- env_loader.py (created)
**Notes:** All test steps passed - key loads correctly from .env, clear error on missing key, dry_run mode warns but doesn't crash.

### TASK-AG-008: Модуль загрузки и проверки reference image
**Date:** 2026-04-27
**Status:** done
**Summary:** Created reference_loader.py module with get_reference_path(text_only) function. Returns Path to reference/style_reference.png if exists. Raises ReferenceImageMissingError with clear message if file missing (when not text_only). In text_only mode, missing file returns None without error.
**Files changed:**
- reference_loader.py (created)
**Notes:** All test steps passed - path returned correctly, clear error on missing file, text_only mode doesn't crash.

### TASK-AG-009: Базовый клиент OpenAI Image API (text-only)
**Date:** 2026-04-27
**Status:** done
**Summary:** Created image_client.py module with generate_image_text_only(prompt, model, size, quality, api_key) function. Uses OpenAI client.images.generate() with b64_json response format, returns PNG bytes. Handles AuthenticationFailedError (401) and ServerError (5xx) with clear messages.
**Files changed:**
- image_client.py (created)
**Notes:** Tested with invalid API key - correctly raises AuthenticationFailedError with helpful message. Module compiles and imports cleanly.

### TASK-AG-010: Клиент OpenAI с reference-flow
**Date:** 2026-04-27
**Status:** done
**Summary:** Extended image_client.py with generate_image_with_reference() function and ReferenceFlowError exception. Uses OpenAI Images Edit API with reference image as style guide. ReferenceFlowError is raised for reference-specific failures (BadRequestError with image-related keywords), enabling fallback logic in 'auto' mode.
**Files changed:**
- image_client.py (extended)
**Notes:** All test steps passed. Function signature: generate_image_with_reference(prompt, reference_path, model, size, quality, api_key) -> bytes. ReferenceFlowError properly inherits from ImageGenerationError.

### TASK-AG-011: Retry логика с exponential backoff
**Date:** 2026-04-27
**Status:** done
**Summary:** Added retry logic with exponential backoff for rate limits (429) and network timeouts. New exceptions: RateLimitExceededError, NetworkError. Helper function _retry_on_transient_errors() retries up to 3 times with exponential backoff + jitter. Both generate_image_text_only() and generate_image_with_reference() now use this retry logic. Added MIN_REQUEST_INTERVAL constant (2s) for batch mode.
**Files changed:**
- image_client.py (extended with retry logic)
**Notes:** All test steps passed with mocked responses. Retry does NOT trigger fallback — only ReferenceFlowError does. Auth errors, server errors pass through without retry.

### TASK-AG-012: Логика fallback в режиме auto
**Date:** 2026-04-27
**Status:** done
**Summary:** Created generation_orchestrator.py module with generate_image() function that handles all three approaches (auto, reference, text-only). In auto mode: tries reference-flow first, falls back to text-only ONLY on ReferenceFlowError. In reference mode: any error propagates without fallback. In text-only mode: uses text-only directly. Returns GenerationResult dataclass with actual_approach, fallback_triggered, and fallback_reason.
**Files changed:**
- generation_orchestrator.py (created)
**Notes:** All test steps passed with mocked responses. Critical distinction: 429/network/auth/5xx errors do NOT trigger fallback — they propagate as errors. Only ReferenceFlowError triggers fallback in auto mode.

### TASK-AG-013: Сохранение PNG результата
**Date:** 2026-04-27
**Status:** done
**Summary:** Created image_saver.py module with save_image(character_id, image_bytes, regenerate) function. Saves PNG to output/characters/{character_id}.png. Creates directory if not exists. Returns Tuple[Path, bool] where bool indicates if file was written. Without regenerate=True, existing files are skipped (returns was_written=False). Helper functions: image_exists(), get_image_path().
**Files changed:**
- image_saver.py (created)
**Notes:** All test steps passed. Enhanced return type (Tuple[Path, bool]) provides useful was_written flag for logging purposes.

