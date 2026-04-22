import { Assets } from 'pixi.js'

export interface PreloadResult {
  locationLoaded: boolean
  fontsLoaded: boolean
}

const FONT_FAMILY = 'Inter'
const FALLBACK_FONT = 'system-ui, -apple-system, sans-serif'

export async function preloadAssets(locationId: string): Promise<PreloadResult> {
  const result: PreloadResult = {
    locationLoaded: false,
    fontsLoaded: false,
  }

  const [locationResult, fontsResult] = await Promise.allSettled([
    preloadLocationTexture(locationId),
    preloadFonts(),
  ])

  result.locationLoaded = locationResult.status === 'fulfilled' && locationResult.value
  result.fontsLoaded = fontsResult.status === 'fulfilled' && fontsResult.value

  return result
}

async function preloadLocationTexture(locationId: string): Promise<boolean> {
  const imagePath = `assets/locations/${locationId}.png`

  try {
    await Assets.load(imagePath)
    return true
  } catch {
    console.warn(`Failed to preload location texture: ${imagePath}, will use fallback gradient`)
    return false
  }
}

async function preloadFonts(): Promise<boolean> {
  if (!document.fonts) {
    console.warn('Font loading API not supported, using system fonts')
    return false
  }

  try {
    const fontUrl = `assets/fonts/${FONT_FAMILY}.woff2`
    const fontFace = new FontFace(FONT_FAMILY, `url(${fontUrl})`)

    const loadedFont = await fontFace.load()
    document.fonts.add(loadedFont)
    return true
  } catch {
    console.warn(`Failed to load font "${FONT_FAMILY}", using fallback: ${FALLBACK_FONT}`)
    return false
  }
}

export function getFontFamily(): string {
  if (document.fonts && document.fonts.check(`12px ${FONT_FAMILY}`)) {
    return FONT_FAMILY
  }
  return FALLBACK_FONT
}
