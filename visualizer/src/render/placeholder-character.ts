import { Container, Graphics, Text, Ticker } from 'pixi.js'
import type { CharacterRenderer, CharacterState, Position } from './character-renderer'
import { getColorFromId } from '../utils'

const CIRCLE_DIAMETER = 120
const CIRCLE_RADIUS = CIRCLE_DIAMETER / 2

export class PlaceholderCharacterRenderer implements CharacterRenderer {
  private container: Container
  private circle: Graphics
  private nameText: Text
  private state: CharacterState = 'idle'
  private ticker: Ticker | null = null
  private animationTime = 0

  constructor(characterId: string, displayName: string) {
    this.container = new Container()

    const color = getColorFromId(characterId)

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
