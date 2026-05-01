# Codex Project Guidance

## Project Context
- SpyfallAI is an AI-powered Spyfall game generator with a Python backend and a Vite/Pixi visualizer.
- Core backend code lives in `src/`; character and game data live in `characters/`, `locations.json`, `trigger_rules.json`, `llm_config.json`, and `games/`.
- Codex agent definitions live in `.codex/agents/*.toml`.
- Claude Code agent definitions live in `.claude/agents/*.md` and are legacy/source material only; do not edit them during Codex agent work unless explicitly requested.
- The web UI is intended for local use. Keep default localhost binding unless authentication, TLS, and rate limiting are explicitly added.

## Project Rules
- Prefer existing project patterns and folder boundaries over new abstractions.
- Keep changes scoped to the requested behavior; do not change application code when the task is documentation or configuration only.
- Never commit secrets. API keys belong in `.env`, and keys must not be logged.
- Use boring, proven technology for critical paths. Introduce new dependencies only with clear justification.
- Document meaningful technical decisions, assumptions, and rejected alternatives when they affect future maintenance.

## Architecture Rules
- Start simple, but leave clear paths for scale, observability, and recovery.
- Keep service boundaries and contracts explicit. Separate orchestration, agents, triggers, LLM provider adapters, storage, web, and CLI concerns.
- For APIs, use consistent response shapes, proper HTTP status codes, input validation, and comprehensive error handling.
- For data and storage changes, consider schema relationships, migrations, indexing, concurrency, backups, and auditability.
- Design security into backend work: validate and sanitize inputs, protect credentials, use least privilege, and consider rate limiting for exposed endpoints.
- For architecture planning, identify MVP scope, integration points, risks, operational complexity, and success criteria before implementation.

## Backend Guidance
- Favor maintainable Python with type-aware, structured code. Use Pydantic models where structured validation is needed.
- Keep LLM provider logic behind the adapter layer instead of spreading provider-specific behavior across the codebase.
- Make failure modes explicit: timeouts, retries, fallback behavior, and user-facing errors should be intentional.
- Add logging that helps diagnose game flow and provider issues without exposing prompts, secrets, or private data unnecessarily.
- When adding web behavior, preserve local-only safety unless the task explicitly includes production hardening.

## Frontend Guidance
- The visualizer lives under `visualizer/` and uses TypeScript, Vite, and Pixi.js.
- Build responsive, accessible UI with stable layout dimensions for boards, controls, panels, and interactive elements.
- Prefer reusable, composable components and clear state ownership.
- Optimize rendering for interactive scenes: avoid unnecessary rerenders, lazy-load heavy assets where useful, and verify canvas output when visual behavior changes.
- Keep UI text and controls concise; avoid explanatory copy inside the app unless it directly supports the workflow.

## Product And Requirements Guidance
- For PRDs or planning docs, capture problem statement, target users, value proposition, assumptions, success metrics, functional requirements, non-functional requirements, risks, and acceptance criteria.
- Use clear user stories: `As a [user], I want [capability] so that [value]`, with Given/When/Then acceptance criteria when helpful.
- Prioritize work by business value, technical risk, user impact, and implementation effort.
- Treat requirements documents as living artifacts; update them when project understanding changes.

## Task Tracking Workflow
- Before starting feature work, look for nearby planning files such as `tasks.json`, `progress.md`, and relevant docs under `docs/`.
- Treat `tasks.json` as the structured task list: use task IDs, titles, dependencies, and statuses to choose the next logical unit of work.
- Treat `progress.md` as the human-readable work log: update it when a task starts, finishes, is blocked, or needs follow-up context.
- Keep task IDs visible in commits, progress updates, and summaries when the area already uses them, for example `TASK-AG-017`.
- Follow task dependencies instead of jumping ahead. If dependencies are unclear or stale, note the assumption before changing code.
- When completing a task, update both implementation and supporting documentation/progress files as appropriate.
- Do not mark a task `done` until the relevant validation has run, or until the skipped validation and residual risk are explicitly documented.
- If a task list and docs disagree, prefer the latest explicit user instruction, then the newest project documentation, then the task file; mention the mismatch in the final summary.

## Testing And Validation
- Backend validation should usually include targeted `pytest` runs and `ruff` checks when Python code changes.
- Visualizer validation should usually include `npm run build` from `visualizer/` when TypeScript or frontend code changes.
- For web changes, use relevant localhost checks such as `/health` when the server is available.
- Add or update tests when behavior, contracts, edge cases, or regressions are affected.
- If a validation command cannot be run, note the reason and the residual risk.

## Documentation And Progress
- Keep documentation practical and close to the code it explains.
- Summarize progress, decisions, and remaining risks clearly when finishing work.
- For larger changes, describe the implementation approach before editing and report exact files changed afterward.
- Prefer concise decision records for important architecture or technology choices.
- When migrating or syncing agent guidance, write Codex-compatible output to `.codex/agents/*.toml` and preserve the original Claude files unchanged.

## Safe Editing Rules
- Do not delete or rewrite unrelated user changes.
- Do not modify `.claude/` files unless explicitly asked; in particular, do not change Claude agent `model` fields while creating Codex agents.
- Do not modify `llm_config.json` unless the task is explicitly about runtime LLM configuration.
- Do not run destructive git commands or cleanup commands without explicit approval.
- Read existing code before editing; preserve formatting, naming conventions, and local idioms.
- Keep generated or machine-specific files out of commits unless the project already tracks them intentionally.

## Useful Commands
- Backend install: `pip install -e .` or `pip install -e '.[web]'`
- CLI game: `python -m src.cli -c boris_molot,zoya,kim -l hospital`
- Web UI: `python -m src.web`
- Python tests: `pytest`
- Python lint: `ruff check .`
- Visualizer dev server: `npm run dev` from `visualizer/`
- Visualizer build: `npm run build` from `visualizer/`
