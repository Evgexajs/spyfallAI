import { createApp, Scene, loadBackground, preloadAssets } from '@render/index'
import { parseGameData } from '@parser/index'
import type { GameData } from '@parser/index'
import { PlayerState } from '@player/index'
import type { PlaybackSpeed } from '@player/index'
import {
  createFileSelector,
  createErrorDisplay,
  createLoadingIndicator,
  createPlaybackControls,
  createSpeedControls,
  createProgressIndicator,
} from '@ui/index'

let currentGameData: GameData | null = null
let scene: Scene | null = null
let playerState: PlayerState | null = null

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

      scene!.placeCharacters(currentGameData.characters)

      playerState = new PlayerState(currentGameData.timeline)

      progressIndicator.update(0, currentGameData.timeline.length)

      loadingIndicator.hide()
      playbackControls.enable()

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

  playbackControls.onPlay(() => {
    if (!playerState) return

    playerState.play()
    playbackControls.setPlaying(true)

    console.log(`Play: status=${playerState.status}, event=${playerState.currentEventIndex}/${playerState.totalEvents}`)
  })

  playbackControls.onPause(() => {
    if (!playerState) return

    playerState.pause()
    playbackControls.setPlaying(false)

    console.log(`Pause: status=${playerState.status}, event=${playerState.currentEventIndex}/${playerState.totalEvents}`)
  })

  playbackControls.onRestart(() => {
    if (!playerState || !scene || !currentGameData) return

    playerState.restart()
    playbackControls.setPlaying(false)
    playbackControls.reset()
    progressIndicator.update(0, playerState.totalEvents)

    scene.hideSpeechBubble()
    scene.resetPhase()

    console.log(`Restart: status=${playerState.status}, index reset to 0`)
  })

  speedControls.onSpeedChange((speed: PlaybackSpeed) => {
    if (!playerState) return

    playerState.setSpeed(speed)

    console.log(`Speed changed to: ${speed}x`)
  })

  console.log('Spyfall Visualizer initialized')
}

init().catch(console.error)

export { currentGameData, scene, playerState }
