import { createApp, Scene, loadBackground, preloadAssets } from '@render/index'
import { parseGameData } from '@parser/index'
import type { GameData, TimelineEvent } from '@parser/index'
import { PlayerState, EventPlayer, EVENT_GAP_MS } from '@player/index'
import type { PlaybackSpeed } from '@player/index'
import {
  createFileSelector,
  createErrorDisplay,
  createLoadingIndicator,
  createPlaybackControls,
  createSpeedControls,
  createProgressIndicator,
} from '@ui/index'

// =============================================================================
// SOUND HOOKS - Stub functions for future audio integration (PRD 7.3)
// These functions are called at key moments where sound effects will be added.
// Current implementation: no-op stubs that don't affect playback.
// =============================================================================

// SOUND_HOOK: персонаж начал говорить
function onCharacterStartedSpeaking(characterId: string, _text: string): void {
  void characterId
}

// SOUND_HOOK: смена фазы
function onPhaseChange(phase: string, _label: string): void {
  void phase
}

// SOUND_HOOK: spy_guess момент
function onSpyGuess(spyId: string, guessedLocation: string, _correct: boolean): void {
  void spyId
  void guessedLocation
}

// SOUND_HOOK: фоновая атмосфера локации
function onLocationLoaded(locationId: string): void {
  void locationId
}

let currentGameData: GameData | null = null
let scene: Scene | null = null
let playerState: PlayerState | null = null
let eventPlayer: EventPlayer | null = null
let isPlaybackRunning = false

async function init() {
  const app = await createApp()

  const fileSelector = createFileSelector()
  const errorDisplay = createErrorDisplay()
  const loadingIndicator = createLoadingIndicator()
  const playbackControls = createPlaybackControls()
  const speedControls = createSpeedControls()
  const progressIndicator = createProgressIndicator()

  scene = new Scene(app)

  fileSelector.onFileSelected(async (content: string, fileName: string) => {
    errorDisplay.clearError()
    playbackControls.disable()
    progressIndicator.reset()

    const result = parseGameData(content)

    if (!result.data) {
      const errorMessage = result.errors.length > 0
        ? `Ошибка в файле "${fileName}":\n${result.errors.join('\n')}`
        : `Ошибка при загрузке файла "${fileName}"`
      errorDisplay.showError(errorMessage)
      return
    }

    currentGameData = result.data
    loadingIndicator.show()

    try {
      const preloadResult = await preloadAssets(currentGameData.scene.location_id)

      await loadBackground(app, currentGameData.scene.location_id)

      // SOUND_HOOK: фоновая атмосфера локации
      onLocationLoaded(currentGameData.scene.location_id)

      scene!.placeCharacters(currentGameData.characters)

      playerState = new PlayerState(currentGameData.timeline)
      eventPlayer = new EventPlayer()

      progressIndicator.update(0, currentGameData.timeline.length)

      loadingIndicator.hide()
      playbackControls.enable()
      isPlaybackRunning = false

      console.log(
        `Loaded: ${fileName}, ${currentGameData.characters.length} characters, ${currentGameData.timeline.length} events`,
        `(location: ${preloadResult.locationLoaded ? 'loaded' : 'fallback'}, fonts: ${preloadResult.fontsLoaded ? 'loaded' : 'fallback'})`
      )
    } catch (error) {
      loadingIndicator.hide()
      const message = error instanceof Error ? error.message : 'Unknown error'
      errorDisplay.showError(`Ошибка загрузки ассетов: ${message}`)
    }
  })

  async function runPlaybackLoop() {
    if (!playerState || !eventPlayer || !scene || isPlaybackRunning) return

    isPlaybackRunning = true

    while (playerState.status === 'playing' && !playerState.isFinished) {
      const event = playerState.nextEvent()
      if (!event) break

      progressIndicator.update(playerState.currentEventIndex, playerState.totalEvents)

      await renderEvent(event)

      if (eventPlayer.isStopped) break

      // Wait for gap between events
      const adjustedGap = EVENT_GAP_MS / eventPlayer.speed
      await pausableDelay(adjustedGap)
    }

    if (playerState.isFinished) {
      playbackControls.setFinished()
      progressIndicator.update(playerState.totalEvents, playerState.totalEvents)
      console.log('Playback finished')
    }

    isPlaybackRunning = false
  }

  async function renderEvent(event: TimelineEvent) {
    if (!scene || !eventPlayer) return

    switch (event.type) {
      case 'speech':
        // SOUND_HOOK: персонаж начал говорить
        onCharacterStartedSpeaking(event.speaker_id, event.content)
        await scene.renderSpeech(event, eventPlayer)
        break

      case 'phase_change':
        // SOUND_HOOK: смена фазы
        onPhaseChange(event.phase, event.label)
        await scene.renderPhaseChange(event)
        break

      case 'system_message':
        await scene.renderSystemMessage(event)
        break

      case 'vote':
        await scene.showVote(event.voter_id, event.target_id, event.phase, event.comment)
        break

      case 'spy_guess':
        // SOUND_HOOK: spy_guess момент
        onSpyGuess(event.spy_id, event.guessed_location_name, event.correct)
        await scene.renderSpyGuess(event)
        break

      case 'outcome':
        scene.renderOutcome(event)
        break
    }
  }

  async function pausableDelay(ms: number): Promise<void> {
    if (!eventPlayer) return

    const startTime = Date.now()
    let elapsed = 0

    while (elapsed < ms) {
      if (eventPlayer.isStopped) return

      if (eventPlayer.isPaused) {
        await new Promise(resolve => setTimeout(resolve, 50))
        continue
      }

      const remaining = ms - elapsed
      const chunk = Math.min(remaining, 50)
      await new Promise(resolve => setTimeout(resolve, chunk))
      elapsed = Date.now() - startTime
    }
  }

  playbackControls.onPlay(() => {
    if (!playerState || !eventPlayer) return

    if (playerState.status === 'paused') {
      playerState.play()
      eventPlayer.resume()
    } else {
      playerState.play()
      eventPlayer.reset()
    }

    playbackControls.setPlaying(true)

    if (!isPlaybackRunning) {
      runPlaybackLoop()
    }

    console.log(`Play: status=${playerState.status}, event=${playerState.currentEventIndex}/${playerState.totalEvents}`)
  })

  playbackControls.onPause(() => {
    if (!playerState || !eventPlayer) return

    playerState.pause()
    eventPlayer.pause()
    playbackControls.setPlaying(false)

    console.log(`Pause: status=${playerState.status}, event=${playerState.currentEventIndex}/${playerState.totalEvents}`)
  })

  playbackControls.onRestart(() => {
    if (!playerState || !scene || !currentGameData || !eventPlayer) return

    eventPlayer.stop()
    playerState.restart()
    eventPlayer.reset()

    playbackControls.setPlaying(false)
    playbackControls.reset()
    progressIndicator.update(0, playerState.totalEvents)
    isPlaybackRunning = false

    scene.hideAllOverlays()
    scene.resetPhase()

    console.log(`Restart: status=${playerState.status}, index reset to 0`)
  })

  speedControls.onSpeedChange((speed: PlaybackSpeed) => {
    if (!playerState || !eventPlayer) return

    playerState.setSpeed(speed)
    eventPlayer.setSpeed(speed)

    console.log(`Speed changed to: ${speed}x`)
  })

  console.log('Spyfall Visualizer initialized')
}

init().catch(console.error)

export { currentGameData, scene, playerState, eventPlayer }
