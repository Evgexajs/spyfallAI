/**
 * PlayerState - state machine for timeline playback
 * Based on PRD section 6.9 (Play/Pause/Restart behavior)
 */

import type { TimelineEvent } from '@parser/types';

export enum PlayerStatus {
  Idle = 'idle',
  Playing = 'playing',
  Paused = 'paused',
  Finished = 'finished',
}

export type PlaybackSpeed = 0.5 | 1 | 2;

export class PlayerState {
  private _status: PlayerStatus = PlayerStatus.Idle;
  private _currentEventIndex: number = 0;
  private _speed: PlaybackSpeed = 1;
  private _timeline: TimelineEvent[] = [];

  constructor(timeline: TimelineEvent[] = []) {
    this._timeline = timeline;
  }

  get status(): PlayerStatus {
    return this._status;
  }

  get currentEventIndex(): number {
    return this._currentEventIndex;
  }

  get speed(): PlaybackSpeed {
    return this._speed;
  }

  get timeline(): TimelineEvent[] {
    return this._timeline;
  }

  get currentEvent(): TimelineEvent | null {
    return this._timeline[this._currentEventIndex] ?? null;
  }

  get isFinished(): boolean {
    return this._status === PlayerStatus.Finished;
  }

  get totalEvents(): number {
    return this._timeline.length;
  }

  setTimeline(timeline: TimelineEvent[]): void {
    this._timeline = timeline;
    this.restart();
  }

  play(): void {
    if (this._timeline.length === 0) {
      return;
    }

    if (this._status === PlayerStatus.Finished) {
      return;
    }

    this._status = PlayerStatus.Playing;
  }

  pause(): void {
    if (this._status === PlayerStatus.Playing) {
      this._status = PlayerStatus.Paused;
    }
  }

  restart(): void {
    this._currentEventIndex = 0;
    this._status = PlayerStatus.Idle;
  }

  setSpeed(speed: PlaybackSpeed): void {
    this._speed = speed;
  }

  nextEvent(): TimelineEvent | null {
    if (this._status !== PlayerStatus.Playing) {
      return null;
    }

    if (this._currentEventIndex >= this._timeline.length) {
      this._status = PlayerStatus.Finished;
      return null;
    }

    const event = this._timeline[this._currentEventIndex];
    this._currentEventIndex++;

    if (this._currentEventIndex >= this._timeline.length) {
      this._status = PlayerStatus.Finished;
    }

    return event ?? null;
  }
}
