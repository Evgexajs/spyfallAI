"""Game, Player, Turn and related models for SpyfallAI."""

from datetime import datetime
from enum import Enum
from typing import Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TurnType(str, Enum):
    """Types of game turns."""

    QUESTION = "question"
    ANSWER = "answer"
    INTERVENTION = "intervention"
    VOTE = "vote"
    SPY_GUESS = "spy_guess"


class GamePhase(str, Enum):
    """Game phase states."""

    SETUP = "setup"
    MAIN_ROUND = "main_round"
    OPTIONAL_VOTE = "optional_vote"
    FINAL_VOTE = "final_vote"
    RESOLUTION = "resolution"


class ConfidenceLevel(str, Enum):
    """Spy confidence levels."""

    NO_IDEA = "no_idea"
    FEW_GUESSES = "few_guesses"
    CONFIDENT = "confident"


class Player(BaseModel):
    """Player in a game session."""

    character_id: str = Field(min_length=1, description="Character profile ID")
    role_id: Optional[str] = Field(default=None, description="Role in location (null for spy)")
    is_spy: bool = Field(default=False, description="Whether this player is the spy")


class Turn(BaseModel):
    """A single turn in the game."""

    turn_number: int = Field(ge=1, description="Sequential turn number")
    timestamp: datetime = Field(description="When the turn occurred")
    speaker_id: str = Field(min_length=1, description="Who spoke")
    addressee_id: str = Field(min_length=1, description="Who was addressed (or 'all')")
    type: TurnType = Field(description="Type of turn")
    content: str = Field(min_length=1, description="Text content of the turn")
    display_delay_ms: int = Field(ge=0, description="Display delay in milliseconds")


class ConfidenceEntry(BaseModel):
    """Entry in the spy confidence log."""

    turn_number: int = Field(ge=1, description="Turn number when checked")
    timestamp: datetime = Field(description="When the check occurred")
    level: ConfidenceLevel = Field(description="Confidence level chosen by spy")


class TriggerEvent(BaseModel):
    """Record of a trigger firing."""

    turn_number: int = Field(ge=1, description="Turn number when triggered")
    timestamp: datetime = Field(description="When the trigger fired")
    character_id: str = Field(min_length=1, description="Character whose trigger fired")
    condition_type: str = Field(min_length=1, description="Type of condition that triggered")
    reaction_type: str = Field(min_length=1, description="Type of reaction")
    intervened: bool = Field(description="Whether the character actually intervened")


class PhaseEntry(BaseModel):
    """Record of a phase transition."""

    timestamp: datetime = Field(description="When the transition occurred")
    from_phase: Optional[GamePhase] = Field(default=None, description="Previous phase (null at start)")
    to_phase: GamePhase = Field(description="New phase")
    reason: Optional[str] = Field(default=None, description="Reason for transition")


class GameOutcome(BaseModel):
    """Final outcome of a game."""

    winner: str = Field(description="Winner: 'spy' or 'civilians'")
    reason: str = Field(min_length=1, description="Why this outcome occurred")
    votes: Optional[dict[str, str]] = Field(default=None, description="Who voted for whom")
    spy_guess: Optional[str] = Field(default=None, description="Location guessed by spy (if applicable)")
    spy_guess_correct: Optional[bool] = Field(default=None, description="Whether spy guess was correct")


class GameConfig(BaseModel):
    """Snapshot of game configuration."""

    duration_minutes: int = Field(ge=1, description="Game duration in minutes")
    players_count: int = Field(ge=3, description="Number of players")
    max_questions: int = Field(ge=1, description="Max questions before forced vote")
    main_model: str = Field(min_length=1, description="Main LLM model used")
    utility_model: str = Field(min_length=1, description="Utility LLM model used")


class Game(BaseModel):
    """Complete game session record."""

    id: UUID = Field(description="Unique game ID")
    started_at: datetime = Field(description="Game start time")
    ended_at: Optional[datetime] = Field(default=None, description="Game end time")
    config: GameConfig = Field(description="Configuration snapshot")
    location_id: str = Field(min_length=1, description="Selected location")
    players: list[Player] = Field(min_length=3, description="List of participants")
    spy_id: str = Field(min_length=1, description="ID of the spy character")
    turns: list[Turn] = Field(default_factory=list, description="Full turn log")
    spy_confidence_log: list[ConfidenceEntry] = Field(default_factory=list, description="Spy confidence history")
    triggered_events: list[TriggerEvent] = Field(default_factory=list, description="Triggered events log")
    phase_transitions: list[PhaseEntry] = Field(default_factory=list, description="Phase history")
    outcome: Optional[GameOutcome] = Field(default=None, description="Final outcome")

    @field_validator("players")
    @classmethod
    def validate_exactly_one_spy(cls, v: list[Player]) -> list[Player]:
        spy_count = sum(1 for p in v if p.is_spy)
        if spy_count != 1:
            raise ValueError(f"Exactly 1 spy required, found {spy_count}")
        return v

    @field_validator("spy_id")
    @classmethod
    def validate_spy_id_matches_player(cls, v: str, info) -> str:
        players = info.data.get("players", [])
        if players:
            spy_players = [p for p in players if p.is_spy]
            if spy_players and spy_players[0].character_id != v:
                raise ValueError("spy_id must match the character_id of the spy player")
        return v
