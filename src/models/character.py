"""Character, Trigger, and Marker models for SpyfallAI."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ConditionType(str, Enum):
    """Trigger condition types (MVP — only formally detectable conditions)."""

    DIRECT_ACCUSATION = "direct_accusation"
    SILENT_FOR_N_TURNS = "silent_for_n_turns"
    DODGED_DIRECT_QUESTION = "dodged_direct_question"
    REPEATED_ACCUSATION_ON_SAME_TARGET = "repeated_accusation_on_same_target"
    CONTRADICTION_WITH_PREVIOUS_ANSWER = "contradiction_with_previous_answer"


class ReactionType(str, Enum):
    """Trigger reaction types."""

    PRESSURE_WITH_SHARPER_QUESTION = "pressure_with_sharper_question"
    MOCK_WITH_DRY_SARCASM = "mock_with_dry_sarcasm"
    MORALIZE_AND_ACCUSE = "moralize_and_accuse"
    PANIC_AND_DERAIL = "panic_and_derail"
    POINT_OUT_INCONSISTENCY = "point_out_inconsistency"
    DEFLECT_SUSPICION_TO_ANOTHER = "deflect_suspicion_to_another"
    SHORT_DISMISSIVE_JAB = "short_dismissive_jab"


class MarkerMethod(str, Enum):
    """Methods for detecting character markers."""

    REGEX = "regex"
    COUNTER = "counter"
    BINARY_LLM = "binary_llm"


class Trigger(BaseModel):
    """Trigger definition for character interventions."""

    condition_type: ConditionType
    priority: int = Field(ge=1, le=10, description="Priority for competition (1-10)")
    threshold: float = Field(ge=0.0, le=1.0, description="Sensitivity threshold (0-1)")
    reaction_type: ReactionType
    params: Optional[dict] = Field(default=None, description="Additional parameters (e.g., silent_turns: 2)")


class Marker(BaseModel):
    """Formal marker for detecting characteristic replies."""

    id: str = Field(min_length=1, description="Unique slug for the marker")
    method: MarkerMethod
    pattern: Optional[str] = Field(default=None, description="Regex or keywords (for regex method)")
    rule: Optional[str] = Field(default=None, description="Counter rule description (e.g., sentences <= 2)")
    prompt: Optional[str] = Field(default=None, description="Yes/no prompt for binary_llm method")
    description: str = Field(min_length=1, description="Human-readable explanation")

    @field_validator("pattern")
    @classmethod
    def validate_pattern_for_regex(cls, v: Optional[str], info) -> Optional[str]:
        if info.data.get("method") == MarkerMethod.REGEX and not v:
            raise ValueError("pattern is required for regex method")
        return v

    @field_validator("rule")
    @classmethod
    def validate_rule_for_counter(cls, v: Optional[str], info) -> Optional[str]:
        if info.data.get("method") == MarkerMethod.COUNTER and not v:
            raise ValueError("rule is required for counter method")
        return v

    @field_validator("prompt")
    @classmethod
    def validate_prompt_for_binary_llm(cls, v: Optional[str], info) -> Optional[str]:
        if info.data.get("method") == MarkerMethod.BINARY_LLM and not v:
            raise ValueError("prompt is required for binary_llm method")
        return v


class LLMOverride(BaseModel):
    """Optional LLM provider/model override for a character."""

    provider: Optional[str] = None
    model: Optional[str] = None


class Character(BaseModel):
    """Character profile for SpyfallAI."""

    id: str = Field(min_length=1, description="Unique slug: boris_molot, margo_honeytongue, etc.")
    display_name: str = Field(min_length=1, description="Display name in chat: Борис, Марго")
    archetype: str = Field(min_length=1, description="Short label: агрессор, манипулятор")
    backstory: str = Field(min_length=10, description="Biography in 3-5 sentences")
    voice_style: str = Field(min_length=10, description="Speech style description")
    must_directives: list[str] = Field(min_length=1, description="List of MUST rules")
    must_not_directives: list[str] = Field(min_length=1, description="List of MUST NOT rules")
    detectable_markers: list[Marker] = Field(min_length=1, description="3-5 formal markers")
    personal_triggers: list[Trigger] = Field(default_factory=list, description="Personal triggers")
    intervention_priority: int = Field(ge=1, le=10, description="Priority for intervention window (1-10)")
    intervention_threshold: float = Field(ge=0.0, le=1.0, description="Trigger threshold (0-1)")
    llm_override: Optional[LLMOverride] = Field(default=None, description="Optional model/provider override")

    @field_validator("detectable_markers")
    @classmethod
    def validate_markers_count(cls, v: list[Marker]) -> list[Marker]:
        if len(v) < 1:
            raise ValueError("At least 1 detectable marker is required")
        return v
