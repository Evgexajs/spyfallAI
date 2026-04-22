import { Application } from 'pixi.js'

const SCENE_WIDTH = 1920
const SCENE_HEIGHT = 1080
const BACKGROUND_COLOR = 0x000000

export async function createApp(): Promise<Application> {
  const app = new Application()

  await app.init({
    width: SCENE_WIDTH,
    height: SCENE_HEIGHT,
    backgroundColor: BACKGROUND_COLOR,
    resolution: window.devicePixelRatio || 1,
    autoDensity: true,
  })

  const container = document.getElementById('app')
  if (!container) {
    throw new Error('Container #app not found')
  }

  container.appendChild(app.canvas)

  return app
}
