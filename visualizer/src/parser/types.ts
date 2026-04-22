/**
 * TypeScript types for the Visualizer API contract
 * Based on PRD section 5
 */

// ============================================
// Enums
// ============================================

export enum SpeechSubtype {
  Normal = 'normal',
  Defense = 'defense',
  PostGuess = 'post_guess',
}

export enum Phase {
  MainRound = 'main_round',
  Voting = 'voting',
  Defense = 'defense',
  Final = 'final',
  Resolution = 'resolution',
}

export enum VotePhase {
  Preliminary = 'preliminary',
  Final = 'final',
}

export enum Winner {
  Spy = 'spy',
  Civilians = 'civilians',
}

// ============================================
// Core Types
// ============================================

export interface Metadata {
  game_id: string;
  title?: string;
}

export interface Scene {
  location_id: string;
  location_name: string;
}

export interface Character {
  id: string;
  display_name: string;
  position_hint?: number;
}

// ============================================
// Timeline Event Types
// ============================================

export interface SpeechEvent {
  type: 'speech';
  speaker_id: string;
  addressee_id: string | null;
  content: string;
  subtype: SpeechSubtype;
}

export interface PhaseChangeEvent {
  type: 'phase_change';
  phase: Phase;
  label: string;
}

export interface SystemMessageEvent {
  type: 'system_message';
  content: string;
}

export interface VoteEvent {
  type: 'vote';
  phase: VotePhase;
  voter_id: string;
  target_id: string;
  comment: string | null;
}

export interface SpyGuessEvent {
  type: 'spy_guess';
  spy_id: string;
  guessed_location_id: string;
  guessed_location_name: string;
  correct: boolean;
}

export interface OutcomeEvent {
  type: 'outcome';
  winner: Winner;
  spy_id: string;
  reason: string;
}

export type TimelineEvent =
  | SpeechEvent
  | PhaseChangeEvent
  | SystemMessageEvent
  | VoteEvent
  | SpyGuessEvent
  | OutcomeEvent;

// ============================================
// Top-level GameData
// ============================================

export interface GameData {
  version: string;
  metadata: Metadata;
  scene: Scene;
  characters: Character[];
  timeline: TimelineEvent[];
}
