import { Application, Assets, Sprite, Graphics } from 'pixi.js'

const SCENE_WIDTH = 1920
const SCENE_HEIGHT = 1080

export async function loadBackground(
  app: Application,
  locationId: string
): Promise<void> {
  const existingBackground = app.stage.getChildByLabel('background')
  if (existingBackground) {
    app.stage.removeChild(existingBackground)
  }

  const imagePath = `assets/locations/${locationId}.png`

  try {
    const texture = await Assets.load(imagePath)
    const sprite = new Sprite(texture)
    sprite.label = 'background'
    sprite.width = SCENE_WIDTH
    sprite.height = SCENE_HEIGHT
    sprite.x = 0
    sprite.y = 0
    app.stage.addChildAt(sprite, 0)
  } catch {
    const fallback = createFallbackGradient()
    fallback.label = 'background'
    app.stage.addChildAt(fallback, 0)
  }
}

function createFallbackGradient(): Graphics {
  const graphics = new Graphics()

  const darkBlue = 0x0a1628

  for (let y = 0; y < SCENE_HEIGHT; y++) {
    const ratio = y / SCENE_HEIGHT
    const r = Math.round(((darkBlue >> 16) & 0xff) * (1 - ratio))
    const g = Math.round(((darkBlue >> 8) & 0xff) * (1 - ratio))
    const b = Math.round((darkBlue & 0xff) * (1 - ratio))
    const color = (r << 16) | (g << 8) | b

    graphics.rect(0, y, SCENE_WIDTH, 1)
    graphics.fill(color)
  }

  return graphics
}
