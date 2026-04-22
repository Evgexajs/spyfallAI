/**
 * EventPlayer - handles sequential playback of timeline events with pause/resume support
 * Based on PRD section 6.9 (Play/Pause/Restart behavior) and 5.4 (sequential processing)
 */

import type { TimelineEvent } from '@parser/types';
import type { PlaybackSpeed } from './state';
import { calculateEventDuration, EVENT_GAP_MS } from './timing';

export class EventPlayer {
  private _isPaused = false;
  private _isStopped = false;
  private _speed: PlaybackSpeed = 1;

  private timeoutId: ReturnType<typeof setTimeout> | null = null;
  private delayStartTime = 0;
  private remainingTime = 0;
  private delayResolve: (() => void) | null = null;

  get isPaused(): boolean {
    return this._isPaused;
  }

  get isStopped(): boolean {
    return this._isStopped;
  }

  get speed(): PlaybackSpeed {
    return this._speed;
  }

  setSpeed(speed: PlaybackSpeed): void {
    this._speed = speed;
  }

  /**
   * Play a single timeline event
   * Returns a Promise that resolves when the event duration has elapsed
   * The actual rendering is handled by the render layer using the isPaused flag
   */
  async playEvent(event: TimelineEvent): Promise<void> {
    if (this._isStopped) {
      return;
    }

    const duration = calculateEventDuration(event);
    const adjustedDuration = duration / this._speed;

    await this.delay(adjustedDuration);
  }

  /**
   * Wait for the gap between events
   */
  async waitEventGap(): Promise<void> {
    if (this._isStopped) {
      return;
    }

    const adjustedGap = EVENT_GAP_MS / this._speed;
    await this.delay(adjustedGap);
  }

  /**
   * Pausable delay - can be paused/resumed mid-wait
   */
  delay(ms: number): Promise<void> {
    return new Promise((resolve) => {
      if (this._isStopped) {
        resolve();
        return;
      }

      if (ms <= 0) {
        resolve();
        return;
      }

      this.delayResolve = resolve;
      this.remainingTime = ms;
      this.delayStartTime = Date.now();

      if (this._isPaused) {
        return;
      }

      this.startTimeout();
    });
  }

  private startTimeout(): void {
    if (this.remainingTime <= 0) {
      this.resolveDelay();
      return;
    }

    this.delayStartTime = Date.now();
    this.timeoutId = setTimeout(() => {
      this.resolveDelay();
    }, this.remainingTime);
  }

  private resolveDelay(): void {
    this.timeoutId = null;
    this.remainingTime = 0;
    if (this.delayResolve) {
      const resolve = this.delayResolve;
      this.delayResolve = null;
      resolve();
    }
  }

  /**
   * Pause playback - freezes current state exactly as-is
   * Per PRD 6.9: "Pause замораживает текущее состояние ровно как есть"
   */
  pause(): void {
    if (this._isPaused || this._isStopped) {
      return;
    }

    this._isPaused = true;

    if (this.timeoutId !== null) {
      clearTimeout(this.timeoutId);
      this.timeoutId = null;
      const elapsed = Date.now() - this.delayStartTime;
      this.remainingTime = Math.max(0, this.remainingTime - elapsed);
    }
  }

  /**
   * Resume playback from paused state
   * Continues from exactly where it was paused
   */
  resume(): void {
    if (!this._isPaused || this._isStopped) {
      return;
    }

    this._isPaused = false;

    if (this.delayResolve !== null) {
      if (this.remainingTime > 0) {
        this.startTimeout();
      } else {
        this.resolveDelay();
      }
    }
  }

  /**
   * Stop playback completely
   * Resolves any pending delay immediately
   */
  stop(): void {
    this._isStopped = true;
    this._isPaused = false;

    if (this.timeoutId !== null) {
      clearTimeout(this.timeoutId);
      this.timeoutId = null;
    }

    this.resolveDelay();
  }

  /**
   * Reset the player to initial state
   * Call this before starting a new playback session
   */
  reset(): void {
    this.stop();
    this._isStopped = false;
    this._isPaused = false;
    this.remainingTime = 0;
    this.delayStartTime = 0;
  }
}
