"""Pydantic models for post-game analysis (CR-003)."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class AnalysisStatus(str, Enum):
    """Status of analysis operation."""

    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"
    NOT_ANALYZED = "not_analyzed"


class MarkerTurnAnalysis(BaseModel):
    """Analysis of a single marker for a specific turn."""

    turn_number: int = Field(ge=1, description="Turn number being analyzed")
    triggered: bool = Field(description="Whether the marker was triggered in this turn")
    reasoning: str = Field(min_length=1, description="LLM reasoning for the decision")


class MarkerAnalysisEntry(BaseModel):
    """Analysis result for a single marker across all turns."""

    marker_id: str = Field(min_length=1, description="ID of the marker from character profile")
    triggered_count: int = Field(ge=0, description="Number of times marker was triggered")
    total_relevant_replies: int = Field(ge=0, description="Total number of relevant replies analyzed")
    rate: float = Field(ge=0.0, le=1.0, description="Trigger rate (triggered_count / total_relevant_replies)")
    per_turn: list[MarkerTurnAnalysis] = Field(default_factory=list, description="Per-turn analysis details")
    status: Optional[AnalysisStatus] = Field(default=None, description="Status if marker was not analyzed")

    @field_validator("rate")
    @classmethod
    def validate_rate_consistency(cls, v: float, info) -> float:
        total = info.data.get("total_relevant_replies", 0)
        triggered = info.data.get("triggered_count", 0)
        if total > 0:
            expected_rate = triggered / total
            if abs(v - expected_rate) > 0.01:
                pass
        return v


class MarkerAnalysis(BaseModel):
    """Container for all marker analysis results for a character."""

    status: AnalysisStatus = Field(description="Overall status of marker analysis")
    per_marker: list[MarkerAnalysisEntry] = Field(
        default_factory=list, description="Analysis for each marker"
    )
    reason: Optional[str] = Field(default=None, description="Reason for skipped/failed status")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class MustDirectiveAnalysis(BaseModel):
    """Analysis result for a single MUST directive."""

    directive: str = Field(min_length=1, description="The MUST directive text from character profile")
    satisfied: bool = Field(description="Whether the directive was satisfied during the game")
    evidence_turns: list[int] = Field(
        default_factory=list, description="Turn numbers where directive was demonstrated"
    )
    reasoning: str = Field(min_length=1, description="LLM reasoning for the decision")


class MustComplianceAnalysis(BaseModel):
    """Container for all MUST directive compliance results for a character."""

    status: AnalysisStatus = Field(description="Overall status of must compliance analysis")
    per_directive: list[MustDirectiveAnalysis] = Field(
        default_factory=list, description="Analysis for each MUST directive"
    )
    reason: Optional[str] = Field(default=None, description="Reason for skipped/failed status")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class CharacterAnalysis(BaseModel):
    """Complete analysis result for a single character in the game."""

    character_id: str = Field(min_length=1, description="Character ID being analyzed")
    markers: MarkerAnalysis = Field(description="Marker analysis results")
    must_compliance: MustComplianceAnalysis = Field(description="MUST directive compliance results")
    status: Optional[AnalysisStatus] = Field(
        default=None, description="Overall status if character analysis was skipped/failed"
    )
    reason: Optional[str] = Field(default=None, description="Reason for skipped status")
    error: Optional[str] = Field(default=None, description="Error description if failed")
    _analyzer_warnings: list[str] = []

    def add_warning(self, warning: str) -> None:
        """Add an analyzer warning (e.g., for hallucinated markers)."""
        if not hasattr(self, "_analyzer_warnings") or self._analyzer_warnings is None:
            self._analyzer_warnings = []
        self._analyzer_warnings.append(warning)


class PostGameAnalysis(BaseModel):
    """Top-level container for post-game analysis results."""

    analyzed_at: datetime = Field(description="When the analysis was performed")
    analyzer_model: str = Field(min_length=1, description="Model used for analysis (e.g. 'gpt-4o-mini')")
    status: AnalysisStatus = Field(description="Overall analysis status")
    per_character: dict[str, CharacterAnalysis] = Field(
        default_factory=dict, description="Analysis results keyed by character_id"
    )
    error: Optional[str] = Field(default=None, description="Error message if top-level analysis failed")

    @field_validator("status")
    @classmethod
    def validate_status_consistency(cls, v: AnalysisStatus, info) -> AnalysisStatus:
        per_char = info.data.get("per_character", {})
        if v == AnalysisStatus.COMPLETED and not per_char:
            pass
        return v

    def get_character_analysis(self, character_id: str) -> Optional[CharacterAnalysis]:
        """Get analysis for a specific character."""
        return self.per_character.get(character_id)

    def all_completed(self) -> bool:
        """Check if all character analyses completed successfully."""
        if not self.per_character:
            return False
        return all(
            ca.status in (None, AnalysisStatus.COMPLETED)
            for ca in self.per_character.values()
        )

    def failed_characters(self) -> list[str]:
        """Get list of character IDs that failed analysis."""
        return [
            char_id for char_id, analysis in self.per_character.items()
            if analysis.status == AnalysisStatus.FAILED
        ]

    def skipped_characters(self) -> list[str]:
        """Get list of character IDs that were skipped."""
        return [
            char_id for char_id, analysis in self.per_character.items()
            if analysis.status == AnalysisStatus.SKIPPED
        ]
