"""FastAPI backend for SpyfallAI web UI."""

import asyncio
import json
import os
import random
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.llm import CostExceededError, LLMConfig, create_provider
from src.models import Character, Game, GameOutcome, Turn, TurnType
from src.orchestrator import load_locations, run_final_vote, run_main_round, setup_game
from src.storage import save_game


app = FastAPI(title="SpyfallAI", version="0.1.0")


class GameStatus(str, Enum):
    """Current status of game execution."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"


class GameStartRequest(BaseModel):
    """Request body for starting a game."""

    character_ids: Optional[list[str]] = None
    location_id: Optional[str] = None
    duration_minutes: int = 3
    max_questions: int = 50


class GameStateResponse(BaseModel):
    """Response with current game state."""

    status: GameStatus
    game_id: Optional[str] = None
    message: str = ""


class GameManager:
    """Manages the currently running game."""

    def __init__(self):
        self.game: Optional[Game] = None
        self.characters: list[Character] = []
        self.status: GameStatus = GameStatus.IDLE
        self.task: Optional[asyncio.Task] = None
        self.inflight_tasks: set[asyncio.Task] = set()
        self.pause_event: asyncio.Event = asyncio.Event()
        self.pause_event.set()
        self.websocket_connections: list[WebSocket] = []
        self.error_message: str = ""

    def load_character(self, character_id: str) -> Character:
        """Load a single character from JSON."""
        characters_dir = Path(__file__).parent.parent.parent / "characters"
        filepath = characters_dir / f"{character_id}.json"
        if not filepath.exists():
            raise FileNotFoundError(f"Character file not found: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Character.model_validate(data)

    def list_available_characters(self) -> list[str]:
        """List all available character IDs."""
        characters_dir = Path(__file__).parent.parent.parent / "characters"
        return [f.stem for f in characters_dir.glob("*.json")]

    def register_inflight_task(self, task: asyncio.Task) -> None:
        """Register an inflight LLM task for tracking."""
        self.inflight_tasks.add(task)

    def unregister_inflight_task(self, task: asyncio.Task) -> None:
        """Unregister an inflight LLM task."""
        self.inflight_tasks.discard(task)

    def cancel_all_inflight_tasks(self) -> None:
        """Cancel all tracked inflight tasks."""
        for task in list(self.inflight_tasks):
            if not task.done():
                task.cancel()
        self.inflight_tasks.clear()

    async def broadcast(self, message: dict) -> None:
        """Send message to all connected WebSocket clients."""
        disconnected = []
        for ws in self.websocket_connections:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.websocket_connections.remove(ws)

    async def on_turn(self, turn: Turn, game: Game) -> None:
        """Callback fired after each turn - broadcasts to WebSockets."""
        await self.pause_event.wait()

        if self.status == GameStatus.STOPPED:
            raise asyncio.CancelledError("Game stopped by user")

        turn_data = {
            "type": "turn",
            "turn": {
                "turn_number": turn.turn_number,
                "timestamp": turn.timestamp.isoformat(),
                "speaker_id": turn.speaker_id,
                "addressee_id": turn.addressee_id,
                "turn_type": turn.type.value,
                "content": turn.content,
                "display_delay_ms": turn.display_delay_ms,
            },
            "game_phase": game.phase_transitions[-1].phase.value if game.phase_transitions else "unknown",
        }
        await self.broadcast(turn_data)

    async def run_game_loop(
        self,
        character_ids: list[str],
        location_id: Optional[str],
        duration_minutes: int,
        max_questions: int,
    ) -> None:
        """Main game loop - runs asynchronously."""
        try:
            self.characters = [self.load_character(cid) for cid in character_ids]

            locations = load_locations()
            if location_id is None:
                location = random.choice(locations)
                location_id = location.id
            else:
                location = next((loc for loc in locations if loc.id == location_id), None)
                if location is None:
                    raise ValueError(f"Location '{location_id}' not found")

            llm_config = LLMConfig()
            provider, model = create_provider(llm_config, role="main")

            self.game = setup_game(
                characters=self.characters,
                location_id=location_id,
                duration_minutes=duration_minutes,
                max_questions=max_questions,
                main_model=model,
            )

            await self.broadcast({
                "type": "game_started",
                "game_id": str(self.game.id),
                "location": location.display_name,
                "spy_id": self.game.spy_id,
                "players": [
                    {
                        "character_id": p.character_id,
                        "display_name": next((c.display_name for c in self.characters if c.id == p.character_id), p.character_id),
                        "color": next((c.color for c in self.characters if c.id == p.character_id), None),
                        "is_spy": p.is_spy,
                        "role_id": p.role_id,
                    }
                    for p in self.game.players
                ],
            })

            await self.broadcast({"type": "phase", "phase": "main_round"})
            self.game = await run_main_round(
                self.game, self.characters, provider, on_turn=self.on_turn
            )

            if self.game.outcome is None and self.status != GameStatus.STOPPED:
                await self.broadcast({"type": "phase", "phase": "final_vote"})
                self.game = await run_final_vote(
                    self.game, self.characters, provider, on_turn=self.on_turn
                )

            if self.status != GameStatus.STOPPED:
                self.status = GameStatus.COMPLETED

                outcome_data = None
                if self.game.outcome:
                    outcome_data = {
                        "winner": self.game.outcome.winner,
                        "reason": self.game.outcome.reason,
                        "accused_id": self.game.outcome.accused_id,
                    }

                await self.broadcast({
                    "type": "game_completed",
                    "outcome": outcome_data,
                    "token_usage": {
                        "total_input_tokens": self.game.token_usage.total_input_tokens,
                        "total_output_tokens": self.game.token_usage.total_output_tokens,
                        "total_cost_usd": self.game.token_usage.total_cost_usd,
                        "llm_calls_count": self.game.token_usage.llm_calls_count,
                    },
                })

                save_game(self.game)

        except asyncio.CancelledError:
            self.status = GameStatus.STOPPED
            if self.game:
                self.game.ended_at = datetime.now()
                if self.game.outcome is None:
                    self.game.outcome = GameOutcome(
                        winner="cancelled",
                        reason="Game stopped by user",
                    )
                save_game(self.game)
            await self.broadcast({
                "type": "game_stopped",
                "message": "Game stopped by user",
            })
        except CostExceededError as e:
            self.status = GameStatus.STOPPED
            self.error_message = str(e)
            if self.game:
                self.game.ended_at = datetime.now()
                if self.game.outcome is None:
                    self.game.outcome = GameOutcome(
                        winner="cancelled",
                        reason=f"Cost limit exceeded: {e}",
                    )
                save_game(self.game)
            await self.broadcast({
                "type": "error",
                "error": f"Cost limit exceeded: {e}",
            })
        except Exception as e:
            self.status = GameStatus.STOPPED
            self.error_message = str(e)
            if self.game:
                self.game.ended_at = datetime.now()
                if self.game.outcome is None:
                    self.game.outcome = GameOutcome(
                        winner="cancelled",
                        reason=f"Error: {e}",
                    )
                save_game(self.game)
            await self.broadcast({
                "type": "error",
                "error": str(e),
            })

    def start(
        self,
        character_ids: list[str],
        location_id: Optional[str],
        duration_minutes: int,
        max_questions: int,
    ) -> None:
        """Start a new game."""
        if self.status == GameStatus.RUNNING:
            raise HTTPException(status_code=400, detail="Game already running")

        self.status = GameStatus.RUNNING
        self.pause_event.set()
        self.error_message = ""

        self.task = asyncio.create_task(
            self.run_game_loop(character_ids, location_id, duration_minutes, max_questions)
        )

    def pause(self) -> None:
        """Pause the current game."""
        if self.status != GameStatus.RUNNING:
            raise HTTPException(status_code=400, detail="No game running")

        self.status = GameStatus.PAUSED
        self.pause_event.clear()

    def resume(self) -> None:
        """Resume a paused game."""
        if self.status != GameStatus.PAUSED:
            raise HTTPException(status_code=400, detail="Game not paused")

        self.status = GameStatus.RUNNING
        self.pause_event.set()

    def stop(self) -> None:
        """Stop the current game and cancel all inflight LLM requests."""
        if self.status not in (GameStatus.RUNNING, GameStatus.PAUSED):
            raise HTTPException(status_code=400, detail="No game to stop")

        self.status = GameStatus.STOPPED
        self.pause_event.set()

        self.cancel_all_inflight_tasks()

        if self.task and not self.task.done():
            self.task.cancel()

    def reset(self) -> None:
        """Reset game state for a new game."""
        self.game = None
        self.characters = []
        self.status = GameStatus.IDLE
        self.task = None
        self.inflight_tasks.clear()
        self.pause_event.set()
        self.error_message = ""


game_manager = GameManager()


@app.post("/game/start", response_model=GameStateResponse)
async def start_game(request: GameStartRequest) -> GameStateResponse:
    """Start a new game with specified parameters."""
    if game_manager.status in (GameStatus.RUNNING, GameStatus.PAUSED):
        raise HTTPException(status_code=400, detail="Game already in progress")

    game_manager.reset()

    character_ids = request.character_ids
    if character_ids is None:
        character_ids = game_manager.list_available_characters()

    if len(character_ids) < 3:
        raise HTTPException(status_code=400, detail="At least 3 characters required")

    game_manager.start(
        character_ids=character_ids,
        location_id=request.location_id,
        duration_minutes=request.duration_minutes,
        max_questions=request.max_questions,
    )

    await asyncio.sleep(0.1)

    game_id = str(game_manager.game.id) if game_manager.game else None

    return GameStateResponse(
        status=game_manager.status,
        game_id=game_id,
        message="Game started",
    )


@app.post("/game/pause", response_model=GameStateResponse)
async def pause_game() -> GameStateResponse:
    """Pause the currently running game."""
    game_manager.pause()

    await game_manager.broadcast({"type": "game_paused"})

    return GameStateResponse(
        status=game_manager.status,
        game_id=str(game_manager.game.id) if game_manager.game else None,
        message="Game paused",
    )


@app.post("/game/resume", response_model=GameStateResponse)
async def resume_game() -> GameStateResponse:
    """Resume a paused game."""
    game_manager.resume()

    await game_manager.broadcast({"type": "game_resumed"})

    return GameStateResponse(
        status=game_manager.status,
        game_id=str(game_manager.game.id) if game_manager.game else None,
        message="Game resumed",
    )


@app.post("/game/stop", response_model=GameStateResponse)
async def stop_game() -> GameStateResponse:
    """Stop the current game immediately."""
    game_manager.stop()

    await asyncio.sleep(0.2)

    return GameStateResponse(
        status=game_manager.status,
        game_id=str(game_manager.game.id) if game_manager.game else None,
        message="Game stopped",
    )


@app.get("/game/status", response_model=GameStateResponse)
async def get_game_status() -> GameStateResponse:
    """Get current game status."""
    return GameStateResponse(
        status=game_manager.status,
        game_id=str(game_manager.game.id) if game_manager.game else None,
        message=game_manager.error_message or "",
    )


@app.get("/characters")
async def list_characters() -> list[dict]:
    """List all available characters."""
    char_ids = game_manager.list_available_characters()
    result = []
    for cid in char_ids:
        char = game_manager.load_character(cid)
        result.append({
            "id": char.id,
            "display_name": char.display_name,
            "archetype": char.archetype,
        })
    return result


@app.get("/locations")
async def list_locations() -> list[dict]:
    """List all available locations."""
    locations = load_locations()
    return [
        {
            "id": loc.id,
            "display_name": loc.display_name,
            "description": loc.description,
            "roles": [{"id": r.id, "display_name": r.display_name} for r in loc.roles],
        }
        for loc in locations
    ]


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for live game updates."""
    await websocket.accept()
    game_manager.websocket_connections.append(websocket)

    await websocket.send_json({
        "type": "connected",
        "status": game_manager.status.value,
        "game_id": str(game_manager.game.id) if game_manager.game else None,
    })

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        if websocket in game_manager.websocket_connections:
            game_manager.websocket_connections.remove(websocket)


static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    async def serve_index():
        """Serve the main HTML page."""
        index_path = static_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        raise HTTPException(status_code=404, detail="index.html not found")
