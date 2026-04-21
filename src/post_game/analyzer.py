"""Post-game character analysis module (CR-003).

This module provides automated analysis of character behavior after game completion.
It checks detectable_markers and must_directives compliance for each character.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from src.llm.adapter import (
    LLMConfig,
    LLMTimeoutError,
    OpenAIProvider,
)
from src.models.character import Character
from src.models.game import Game, Turn
from src.models.post_game_analysis import (
    AnalysisStatus,
    CharacterAnalysis,
    MarkerAnalysis,
    MarkerAnalysisEntry,
    MarkerTurnAnalysis,
    MustComplianceAnalysis,
    MustDirectiveAnalysis,
    PostGameAnalysis,
)
from src.post_game.config import (
    POST_GAME_ANALYSIS_MODEL_ROLE,
    POST_GAME_ANALYSIS_TIMEOUT_SECONDS,
)
from src.post_game.prompts import build_analysis_prompt

logger = logging.getLogger(__name__)


class PostGameAnalyzer:
    """Analyzer for post-game character behavior.

    Analyzes each character's performance in terms of:
    - detectable_markers: Did the character show their characteristic markers?
    - must_directives: Did the character comply with their MUST rules?
    """

    def __init__(self) -> None:
        """Initialize the analyzer."""
        pass

    async def analyze(self, game_path: Path) -> PostGameAnalysis:
        """Analyze a completed game and return analysis results.

        Args:
            game_path: Path to the game JSON log file.

        Returns:
            PostGameAnalysis with per-character analysis results.
        """
        raise NotImplementedError("Will be implemented in TASK-086")

    def _collect_character_turns(
        self, game: Game, character_id: str
    ) -> list[Turn]:
        """Collect all turns for a specific character with context.

        Collects all turns where the speaker is the specified character.
        Each Turn includes contextual information:
        - turn_number: position in game, use to find previous turn
        - addressee_id: who the character was addressing
        - type: the type of turn (QUESTION, ANSWER, INTERVENTION, etc.)

        To find the previous turn (what prompted this reply), use:
            prev_turn = game.turns[turn.turn_number - 2] if turn.turn_number > 1 else None
        (turn_number is 1-indexed, list is 0-indexed, so -2 gives previous)

        Args:
            game: The game to analyze.
            character_id: ID of the character to collect turns for.

        Returns:
            List of Turn objects for this character in chronological order.
            Returns empty list if no turns found for this character.
        """
        return [
            turn for turn in game.turns
            if turn.speaker_id == character_id
        ]

    async def _analyze_character(
        self,
        character: Character,
        turns: list[Turn],
    ) -> CharacterAnalysis:
        """Analyze a single character's performance.

        Calls the LLM with the analysis prompt and parses the JSON response.
        Uses timeout from POST_GAME_ANALYSIS_TIMEOUT_SECONDS env variable.

        Edge cases handled:
        - No turns: returns skipped analysis with reason='no_replies'
        - No detectable_markers: markers.status='skipped', reason='no_markers_in_profile'
        - No must_directives: must_compliance.status='skipped', reason='no_must_in_profile'

        Args:
            character: The character profile.
            turns: Character's turns with context.

        Returns:
            CharacterAnalysis with markers and must_compliance results.
            On error, returns CharacterAnalysis with status='failed' and error description.
        """
        if not turns:
            logger.info(f"Character {character.id} has no turns, skipping analysis")
            return self._skipped_analysis(character.id, "no_replies")

        has_markers = bool(character.detectable_markers)
        has_must = bool(character.must_directives)

        if not has_markers and not has_must:
            logger.info(f"Character {character.id} has no markers and no must_directives")
            return self._skipped_analysis(
                character.id, "no_markers_in_profile_and_no_must_in_profile"
            )

        prompt = build_analysis_prompt(character, turns)

        config = LLMConfig()
        _, model = config.get_model_for_role(POST_GAME_ANALYSIS_MODEL_ROLE)

        provider = OpenAIProvider(
            default_model=model,
            timeout=float(POST_GAME_ANALYSIS_TIMEOUT_SECONDS)
        )

        system_msg = "You are an expert character analyst for the Spyfall game."
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt}
        ]

        try:
            response = await provider.complete(
                messages=messages,
                model=model,
                temperature=0.3,
                max_tokens=2000,
                json_mode=True,
            )
            raw_content = response.content.strip()

        except LLMTimeoutError:
            logger.warning(f"Timeout analyzing character {character.id}")
            return self._failed_analysis(character.id, "timeout")
        except Exception as e:
            logger.warning(f"LLM error analyzing character {character.id}: {e}")
            return self._failed_analysis(character.id, f"llm_error: {e}")

        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON from LLM for character {character.id}: {e}")
            return self._failed_analysis(character.id, "invalid_json")

        return self._parse_llm_response(
            character, data, has_markers=has_markers, has_must=has_must
        )

    def _failed_analysis(self, character_id: str, error: str) -> CharacterAnalysis:
        """Create a failed CharacterAnalysis with the given error."""
        return CharacterAnalysis(
            character_id=character_id,
            markers=MarkerAnalysis(
                status=AnalysisStatus.FAILED,
                per_marker=[],
                error=error
            ),
            must_compliance=MustComplianceAnalysis(
                status=AnalysisStatus.FAILED,
                per_directive=[],
                error=error
            ),
            status=AnalysisStatus.FAILED,
            error=error
        )

    def _skipped_analysis(self, character_id: str, reason: str) -> CharacterAnalysis:
        """Create a skipped CharacterAnalysis with the given reason."""
        return CharacterAnalysis(
            character_id=character_id,
            markers=MarkerAnalysis(
                status=AnalysisStatus.SKIPPED,
                per_marker=[],
                reason=reason
            ),
            must_compliance=MustComplianceAnalysis(
                status=AnalysisStatus.SKIPPED,
                per_directive=[],
                reason=reason
            ),
            status=AnalysisStatus.SKIPPED,
            reason=reason
        )

    def _skipped_markers_analysis(self, reason: str) -> MarkerAnalysis:
        """Create a skipped MarkerAnalysis for edge case handling."""
        return MarkerAnalysis(
            status=AnalysisStatus.SKIPPED,
            per_marker=[],
            reason=reason
        )

    def _skipped_must_analysis(self, reason: str) -> MustComplianceAnalysis:
        """Create a skipped MustComplianceAnalysis for edge case handling."""
        return MustComplianceAnalysis(
            status=AnalysisStatus.SKIPPED,
            per_directive=[],
            reason=reason
        )

    def _parse_llm_response(
        self,
        character: Character,
        data: dict,
        has_markers: bool = True,
        has_must: bool = True,
    ) -> CharacterAnalysis:
        """Parse and validate LLM JSON response into CharacterAnalysis.

        Args:
            character: Character profile for validation.
            data: Parsed JSON from LLM.
            has_markers: Whether character has detectable_markers in profile.
            has_must: Whether character has must_directives in profile.

        Returns:
            CharacterAnalysis. On validation error, returns failed analysis.
        """
        required_fields = {"character_id"}
        if has_markers:
            required_fields.add("markers")
        if has_must:
            required_fields.add("must_compliance")

        if not required_fields.issubset(data.keys()):
            missing = required_fields - set(data.keys())
            logger.warning(f"Missing required fields for {character.id}: {missing}")
            return self._failed_analysis(character.id, "missing_required_fields")

        try:
            if has_markers:
                markers_data = data.get("markers", {})
                markers = self._parse_markers(character, markers_data)
            else:
                logger.info(f"Character {character.id} has no markers in profile")
                markers = self._skipped_markers_analysis("no_markers_in_profile")

            if has_must:
                must_data = data.get("must_compliance", {})
                must_compliance = self._parse_must_compliance(character, must_data)
            else:
                logger.info(f"Character {character.id} has no must_directives in profile")
                must_compliance = self._skipped_must_analysis("no_must_in_profile")

            analysis = CharacterAnalysis(
                character_id=character.id,
                markers=markers,
                must_compliance=must_compliance,
                status=None
            )

            if has_markers:
                self._check_for_missing_markers(character, markers, analysis)
                self._check_for_hallucinated_markers(character, markers, analysis)

            return analysis

        except Exception as e:
            logger.warning(f"Error parsing LLM response for {character.id}: {e}")
            return self._failed_analysis(character.id, f"parse_error: {e}")

    def _parse_markers(self, character: Character, markers_data: dict) -> MarkerAnalysis:
        """Parse markers section from LLM response."""
        per_marker_raw = markers_data.get("per_marker", [])
        per_marker = []

        for marker_entry in per_marker_raw:
            per_turn_raw = marker_entry.get("per_turn", [])
            per_turn = [
                MarkerTurnAnalysis(
                    turn_number=t.get("turn_number", 0),
                    triggered=bool(t.get("triggered", False)),
                    reasoning=str(t.get("reasoning", ""))
                )
                for t in per_turn_raw
            ]

            entry = MarkerAnalysisEntry(
                marker_id=str(marker_entry.get("marker_id", "")),
                triggered_count=int(marker_entry.get("triggered_count", 0)),
                total_relevant_replies=int(marker_entry.get("total_relevant_replies", 0)),
                rate=float(marker_entry.get("rate", 0.0)),
                per_turn=per_turn
            )
            per_marker.append(entry)

        return MarkerAnalysis(
            status=AnalysisStatus.COMPLETED,
            per_marker=per_marker
        )

    def _parse_must_compliance(
        self, character: Character, must_data: dict
    ) -> MustComplianceAnalysis:
        """Parse must_compliance section from LLM response."""
        per_directive_raw = must_data.get("per_directive", [])
        per_directive = []

        for directive_entry in per_directive_raw:
            evidence = directive_entry.get("evidence_turns", [])
            if not isinstance(evidence, list):
                evidence = []

            directive = MustDirectiveAnalysis(
                directive=str(directive_entry.get("directive", "")),
                satisfied=bool(directive_entry.get("satisfied", False)),
                evidence_turns=[int(t) for t in evidence if isinstance(t, (int, float))],
                reasoning=str(directive_entry.get("reasoning", ""))
            )
            per_directive.append(directive)

        return MustComplianceAnalysis(
            status=AnalysisStatus.COMPLETED,
            per_directive=per_directive
        )

    def _check_for_missing_markers(
        self,
        character: Character,
        markers: MarkerAnalysis,
        analysis: CharacterAnalysis
    ) -> None:
        """Check if LLM missed any markers from the character profile."""
        profile_marker_ids = {m.id for m in character.detectable_markers}
        analyzed_marker_ids = {m.marker_id for m in markers.per_marker}

        missing = profile_marker_ids - analyzed_marker_ids
        for marker_id in missing:
            markers.per_marker.append(
                MarkerAnalysisEntry(
                    marker_id=marker_id,
                    triggered_count=0,
                    total_relevant_replies=0,
                    rate=0.0,
                    per_turn=[],
                    status=AnalysisStatus.NOT_ANALYZED
                )
            )
            analysis.add_warning(f"Marker '{marker_id}' from profile was not analyzed by LLM")

    def _check_for_hallucinated_markers(
        self,
        character: Character,
        markers: MarkerAnalysis,
        analysis: CharacterAnalysis
    ) -> None:
        """Check if LLM returned markers not in character profile."""
        profile_marker_ids = {m.id for m in character.detectable_markers}
        hallucinated = []

        valid_markers = []
        for marker_entry in markers.per_marker:
            if marker_entry.marker_id in profile_marker_ids:
                valid_markers.append(marker_entry)
            else:
                hallucinated.append(marker_entry.marker_id)
                analysis.add_warning(
                    f"LLM hallucinated marker '{marker_entry.marker_id}' not in profile - ignored"
                )

        markers.per_marker = valid_markers

    def save_analysis(
        self, game_path: Path, analysis: PostGameAnalysis
    ) -> None:
        """Save analysis results back to the game log file.

        Adds or overwrites the post_game_analysis field in the game JSON.

        Args:
            game_path: Path to the game JSON log file.
            analysis: Analysis results to save.
        """
        raise NotImplementedError("Will be implemented in TASK-087")

    def _load_character_profile(self, character_id: str) -> Optional[Character]:
        """Load a character profile from the characters/ directory.

        Args:
            character_id: ID of the character to load.

        Returns:
            Character model or None if not found.
        """
        raise NotImplementedError("Will be implemented in TASK-086")
