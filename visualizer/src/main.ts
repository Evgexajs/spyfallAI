import { createApp, Scene, loadBackground } from '@render/index'
import { parseGameData } from '@parser/index'
import type { GameData } from '@parser/index'
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
      await loadBackground(app, currentGameData.scene.location_id)

      scene!.placeCharacters(currentGameData.characters)

      progressIndicator.update(0, currentGameData.timeline.length)

      loadingIndicator.hide()
      playbackControls.enable()

      console.log(`Loaded: ${fileName}, ${currentGameData.characters.length} characters, ${currentGameData.timeline.length} events`)
    } catch (error) {
      loadingIndicator.hide()
      const message = error instanceof Error ? error.message : 'Unknown error'
      errorDisplay.showError(`Ошибка загрузки ассетов: ${message}`)
    }
  })

  speedControls.onSpeedChange((speed) => {
    console.log(`Speed changed to: ${speed}x`)
  })

  console.log('Spyfall Visualizer initialized')
}

init().catch(console.error)

export { currentGameData, scene }
