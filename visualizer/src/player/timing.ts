import {
  TYPING_INDICATOR_MIN_MS,
  TYPING_INDICATOR_MAX_MS,
  TYPING_INDICATOR_MS_PER_CHAR,
  TYPING_SPEED_MS_PER_CHAR,
  HOLD_MS_PER_20_CHARS,
  HOLD_MIN_MS,
  EVENT_GAP_MS,
  VOTING_EXTRA_PAUSE_MS,
  PHASE_CHANGE_DURATION_MS,
  SPY_GUESS_DURATION_MS,
} from '@config/timings';

import type { TimelineEvent, VoteEvent } from '@parser/types';

/**
 * Calculate typing indicator duration (three dots animation before text)
 * Formula: max(500ms, min(3000ms, 100ms × textLength))
 */
export function calculateTypingIndicatorDuration(textLength: number): number {
  const calculated = TYPING_INDICATOR_MS_PER_CHAR * textLength;
  return Math.max(TYPING_INDICATOR_MIN_MS, Math.min(TYPING_INDICATOR_MAX_MS, calculated));
}

/**
 * Calculate typing duration (text appearing character by character)
 * Formula: 30ms per character
 */
export function calculateTypingDuration(textLength: number): number {
  return TYPING_SPEED_MS_PER_CHAR * textLength;
}

/**
 * Calculate hold duration (text stays visible after typing completes)
 * Formula: 1500ms per 20 chars, minimum 1000ms
 */
export function calculateHoldDuration(textLength: number): number {
  const calculated = Math.ceil(textLength / 20) * HOLD_MS_PER_20_CHARS;
  return Math.max(HOLD_MIN_MS, calculated);
}

/**
 * Calculate total speech duration including indicator, typing, and hold
 */
function calculateSpeechDuration(textLength: number): number {
  return (
    calculateTypingIndicatorDuration(textLength) +
    calculateTypingDuration(textLength) +
    calculateHoldDuration(textLength)
  );
}

/**
 * Calculate vote event duration
 * If comment exists: speech-like duration + vote visualization
 * Otherwise: just vote visualization time
 */
function calculateVoteDuration(event: VoteEvent): number {
  const voteVisualizationMs = 1000;

  if (event.comment) {
    return calculateSpeechDuration(event.comment.length) + voteVisualizationMs;
  }

  return voteVisualizationMs;
}

/**
 * Calculate total duration for any timeline event
 * Does not include EVENT_GAP_MS between events - that's added by the player
 */
export function calculateEventDuration(event: TimelineEvent): number {
  switch (event.type) {
    case 'speech':
      return calculateSpeechDuration(event.content.length);

    case 'phase_change':
      return PHASE_CHANGE_DURATION_MS;

    case 'system_message':
      return calculateHoldDuration(event.content.length) + 500;

    case 'vote':
      return calculateVoteDuration(event) + VOTING_EXTRA_PAUSE_MS;

    case 'spy_guess':
      return SPY_GUESS_DURATION_MS;

    case 'outcome':
      return 0;

    default: {
      const _exhaustive: never = event;
      return _exhaustive;
    }
  }
}

export { EVENT_GAP_MS, VOTING_EXTRA_PAUSE_MS };
