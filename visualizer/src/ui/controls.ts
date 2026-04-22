export type PlaybackCallback = () => void;

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
