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
    VOTE = "vote"  # Kept for backwards compatibility
    PRELIMINARY_VOTE = "preliminary_vote"  # Vote in preliminary voting phase
    DEFENSE_SPEECH = "defense_speech"  # Defense speech by accused player
    FINAL_VOTE = "final_vote"  # Vote in final voting phase
    SPY_GUESS = "spy_guess"
    SPY_LEAK = "spy_leak"


class GamePhase(str, Enum):
    """Game phase states."""

    SETUP = "setup"
    MAIN_ROUND = "main_round"
    OPTIONAL_VOTE = "optional_vote"
    PRELIMINARY_VOTE = "preliminary_vote"  # CR-001: Before defense phase
    PRE_FINAL_VOTE_DEFENSE = "pre_final_vote_defense"  # CR-001: Defense speeches
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
    status: Optional[str] = Field(default=None, description="Phase status (e.g. 'skipped_copied_from_preliminary')")


class DefenseSpeech(BaseModel):
    """A defense speech by an accused player."""

    defender_id: str = Field(min_length=1, description="ID of defending character")
    votes_received: int = Field(ge=0, description="Votes received in preliminary voting")
    content: str = Field(min_length=1, description="Text of defense speech")
    timestamp: datetime = Field(description="When the speech was given")


class VoteChange(BaseModel):
    """Record of a vote change between preliminary and final voting."""

    voter_id: str = Field(min_length=1, description="Who changed their vote")
    from_target: Optional[str] = Field(default=None, description="Previous vote target (null if abstained)")
    to_target: Optional[str] = Field(default=None, description="New vote target (null if abstained)")


class TokenUsage(BaseModel):
    """Accumulated token usage and cost tracking."""

    total_input_tokens: int = Field(default=0, ge=0, description="Total input tokens used")
    total_output_tokens: int = Field(default=0, ge=0, description="Total output tokens used")
    total_cost_usd: float = Field(default=0.0, ge=0.0, description="Total cost in USD")
    llm_calls_count: int = Field(default=0, ge=0, description="Number of LLM calls made")

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    def add_usage(self, input_tokens: int, output_tokens: int, cost: float) -> None:
        """Add usage from a single LLM call."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd += cost
        self.llm_calls_count += 1


class GameOutcome(BaseModel):
    """Final outcome of a game."""

    winner: str = Field(description="Winner: 'spy', 'civilians', or 'cancelled'")
    reason: str = Field(min_length=1, description="Why this outcome occurred")
    votes: Optional[dict[str, str]] = Field(default=None, description="Who voted for whom")
    spy_guess: Optional[str] = Field(default=None, description="Location guessed by spy (if applicable)")
    spy_guess_correct: Optional[bool] = Field(default=None, description="Whether spy guess was correct")
    accused_id: Optional[str] = Field(default=None, description="Who was accused (if applicable)")


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
    compressed_history: Optional[str] = Field(default=None, description="Compressed summary of old turns")
    compression_checkpoint: Optional[int] = Field(default=None, description="Turn number when last compressed")
    token_usage: TokenUsage = Field(default_factory=TokenUsage, description="Token usage and cost tracking")
    preliminary_vote_result: Optional[dict[str, Optional[str]]] = Field(
        default=None, description="Preliminary voting results: {voter_id: target_id | null}"
    )
    defense_speeches: list[DefenseSpeech] = Field(
        default_factory=list, description="List of defense speeches (ordered)"
    )
    final_vote_result: Optional[dict[str, Optional[str]]] = Field(
        default=None, description="Final voting results: {voter_id: target_id | null}"
    )
    vote_changes: list[VoteChange] = Field(
        default_factory=list, description="List of vote changes between preliminary and final"
    )

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
