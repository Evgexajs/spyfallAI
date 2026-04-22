export type PlaybackCallback = () => void;
export type PlaybackSpeed = 0.5 | 1 | 2;
export type SpeedChangeCallback = (speed: PlaybackSpeed) => void;

export interface PlaybackControls {
  onPlay(callback: PlaybackCallback): void;
  onPause(callback: PlaybackCallback): void;
  onRestart(callback: PlaybackCallback): void;
  enable(): void;
  disable(): void;
  setPlaying(isPlaying: boolean): void;
  setFinished(): void;
  reset(): void;
}

export function createPlaybackControls(): PlaybackControls {
  const playBtn = document.getElementById('play-button') as HTMLButtonElement | null;
  const pauseBtn = document.getElementById('pause-button') as HTMLButtonElement | null;
  const restartBtn = document.getElementById('restart-button') as HTMLButtonElement | null;

  if (!playBtn || !pauseBtn || !restartBtn) {
    throw new Error('Playback control buttons not found in DOM');
  }

  const playButton: HTMLButtonElement = playBtn;
  const pauseButton: HTMLButtonElement = pauseBtn;
  const restartButton: HTMLButtonElement = restartBtn;

  let playCallback: PlaybackCallback | null = null;
  let pauseCallback: PlaybackCallback | null = null;
  let restartCallback: PlaybackCallback | null = null;
  let isEnabled = false;
  let isPlaying = false;
  let isFinished = false;

  playButton.addEventListener('click', () => {
    if (!playButton.disabled && playCallback) {
      playCallback();
    }
  });

  pauseButton.addEventListener('click', () => {
    if (!pauseButton.disabled && pauseCallback) {
      pauseCallback();
    }
  });

  restartButton.addEventListener('click', () => {
    if (!restartButton.disabled && restartCallback) {
      restartCallback();
    }
  });

  function updateButtonStates(): void {
    if (!isEnabled) {
      playButton.disabled = true;
      pauseButton.disabled = true;
      restartButton.disabled = true;
      return;
    }

    if (isFinished) {
      playButton.disabled = true;
      pauseButton.disabled = true;
      restartButton.disabled = false;
      return;
    }

    playButton.disabled = isPlaying;
    pauseButton.disabled = !isPlaying;
    restartButton.disabled = false;
  }

  return {
    onPlay(callback: PlaybackCallback): void {
      playCallback = callback;
    },

    onPause(callback: PlaybackCallback): void {
      pauseCallback = callback;
    },

    onRestart(callback: PlaybackCallback): void {
      restartCallback = callback;
    },

    enable(): void {
      isEnabled = true;
      isFinished = false;
      isPlaying = false;
      updateButtonStates();
    },

    disable(): void {
      isEnabled = false;
      updateButtonStates();
    },

    setPlaying(playing: boolean): void {
      isPlaying = playing;
      isFinished = false;
      updateButtonStates();
    },

    setFinished(): void {
      isFinished = true;
      isPlaying = false;
      updateButtonStates();
    },

    reset(): void {
      isPlaying = false;
      isFinished = false;
      updateButtonStates();
    }
  };
}

export interface SpeedControls {
  onSpeedChange(callback: SpeedChangeCallback): void;
  getSpeed(): PlaybackSpeed;
  setSpeed(speed: PlaybackSpeed): void;
}

export function createSpeedControls(): SpeedControls {
  const speedButtons = document.querySelectorAll<HTMLButtonElement>('#speed-controls .speed-btn');

  if (speedButtons.length === 0) {
    throw new Error('Speed control buttons not found in DOM');
  }

  let currentSpeed: PlaybackSpeed = 1;
  let speedChangeCallback: SpeedChangeCallback | null = null;

  function parseSpeed(value: string | null): PlaybackSpeed | null {
    if (value === '0.5') return 0.5;
    if (value === '1') return 1;
    if (value === '2') return 2;
    return null;
  }

  function updateActiveButton(): void {
    speedButtons.forEach((btn) => {
      const btnSpeed = parseSpeed(btn.dataset['speed'] ?? null);
      if (btnSpeed === currentSpeed) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });
  }

  speedButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const newSpeed = parseSpeed(btn.dataset['speed'] ?? null);
      if (newSpeed !== null && newSpeed !== currentSpeed) {
        currentSpeed = newSpeed;
        updateActiveButton();
        if (speedChangeCallback) {
          speedChangeCallback(currentSpeed);
        }
      }
    });
  });

  return {
    onSpeedChange(callback: SpeedChangeCallback): void {
      speedChangeCallback = callback;
    },

    getSpeed(): PlaybackSpeed {
      return currentSpeed;
    },

    setSpeed(speed: PlaybackSpeed): void {
      if (speed !== currentSpeed) {
        currentSpeed = speed;
        updateActiveButton();
      }
    }
  };
}
