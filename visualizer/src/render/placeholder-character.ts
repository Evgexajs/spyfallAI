import { Container, Graphics, Text, Ticker } from 'pixi.js'
import type { CharacterRenderer, CharacterState, Position } from './character-renderer'

const CIRCLE_DIAMETER = 120
const CIRCLE_RADIUS = CIRCLE_DIAMETER / 2

function hashStringToColor(str: string): number {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash)
    hash = hash & hash
  }

  const h = Math.abs(hash % 360)
  const s = 60 + (Math.abs(hash >> 8) % 20)
  const l = 45 + (Math.abs(hash >> 16) % 15)

  return hslToHex(h, s, l)
}

function hslToHex(h: number, s: number, l: number): number {
  s /= 100
  l /= 100

  const c = (1 - Math.abs(2 * l - 1)) * s
  const x = c * (1 - Math.abs((h / 60) % 2 - 1))
  const m = l - c / 2

  let r = 0, g = 0, b = 0

  if (h >= 0 && h < 60) { r = c; g = x; b = 0 }
  else if (h >= 60 && h < 120) { r = x; g = c; b = 0 }
  else if (h >= 120 && h < 180) { r = 0; g = c; b = x }
  else if (h >= 180 && h < 240) { r = 0; g = x; b = c }
  else if (h >= 240 && h < 300) { r = x; g = 0; b = c }
  else { r = c; g = 0; b = x }

  const toHex = (n: number) => Math.round((n + m) * 255)

  return (toHex(r) << 16) | (toHex(g) << 8) | toHex(b)
}

export class PlaceholderCharacterRenderer implements CharacterRenderer {
  private container: Container
  private circle: Graphics
  private nameText: Text
  private state: CharacterState = 'idle'
  private ticker: Ticker | null = null
  private animationTime = 0

  constructor(characterId: string, displayName: string) {
    this.container = new Container()

    const color = hashStringToColor(characterId)

    this.circle = new Graphics()
    this.circle.circle(0, 0, CIRCLE_RADIUS)
    this.circle.fill(color)
    this.circle.stroke({ width: 3, color: 0xffffff, alpha: 0.5 })

    this.nameText = new Text({
      text: displayName,
      style: {
        fontFamily: 'Arial, sans-serif',
        fontSize: 16,
        fill: 0xffffff,
        align: 'center',
        wordWrap: true,
        wordWrapWidth: CIRCLE_DIAMETER - 10
      }
    })
    this.nameText.anchor.set(0.5, 0.5)

    this.container.addChild(this.circle)
    this.container.addChild(this.nameText)
  }

  render(position: Position): void {
    this.container.x = position.x
    this.container.y = position.y
  }

  setState(state: CharacterState): void {
    if (this.state === state) return

    this.state = state

    if (state === 'speaking') {
      this.startPulsation()
    } else {
      this.stopPulsation()
    }
  }

  getContainer(): Container {
    return this.container
  }

  destroy(): void {
    this.stopPulsation()
    this.container.destroy({ children: true })
  }

  private startPulsation(): void {
    if (this.ticker) return

    this.animationTime = 0
    this.ticker = new Ticker()

    this.ticker.add((ticker) => {
      this.animationTime += ticker.deltaMS / 1000
      const scale = 1 + 0.08 * Math.sin(this.animationTime * 4)
      this.container.scale.set(scale, scale)
    })

    this.ticker.start()
  }

  private stopPulsation(): void {
    if (this.ticker) {
      this.ticker.stop()
      this.ticker.destroy()
      this.ticker = null
    }
    this.container.scale.set(1, 1)
    this.animationTime = 0
  }
}
