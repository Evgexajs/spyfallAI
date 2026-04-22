import { Container, Graphics, Text } from 'pixi.js'
import type { Position } from './character-renderer'

const BUBBLE_MAX_WIDTH = 400
const BUBBLE_PADDING = 16
const BUBBLE_RADIUS = 12
const TAIL_WIDTH = 20
const TAIL_HEIGHT = 15
const BACKGROUND_COLOR = 0xffffff
const BORDER_COLOR = 0xcccccc
const BORDER_WIDTH = 2
const TEXT_COLOR = 0x333333
const FONT_SIZE = 18

export class SpeechBubble {
  private container: Container
  private background: Graphics
  private textDisplay: Text
  private visible = false

  constructor() {
    this.container = new Container()
    this.container.visible = false

    this.background = new Graphics()
    this.container.addChild(this.background)

    this.textDisplay = new Text({
      text: '',
      style: {
        fontFamily: 'Arial, sans-serif',
        fontSize: FONT_SIZE,
        fill: TEXT_COLOR,
        align: 'left',
        wordWrap: true,
        wordWrapWidth: BUBBLE_MAX_WIDTH - BUBBLE_PADDING * 2
      }
    })
    this.textDisplay.x = BUBBLE_PADDING
    this.textDisplay.y = BUBBLE_PADDING
    this.container.addChild(this.textDisplay)
  }

  show(position: Position): void {
    this.visible = true
    this.container.visible = true
    this.updatePosition(position)
    this.drawBackground()
  }

  hide(): void {
    this.visible = false
    this.container.visible = false
  }

  setText(text: string): void {
    this.textDisplay.text = text
    this.drawBackground()
  }

  getText(): string {
    return this.textDisplay.text
  }

  getContainer(): Container {
    return this.container
  }

  isVisible(): boolean {
    return this.visible
  }

  destroy(): void {
    this.container.destroy({ children: true })
  }

  private updatePosition(position: Position): void {
    const bubbleWidth = this.calculateBubbleWidth()
    this.container.x = position.x - bubbleWidth / 2
    this.container.y = position.y
  }

  private calculateBubbleWidth(): number {
    const textWidth = this.textDisplay.width
    return Math.min(BUBBLE_MAX_WIDTH, textWidth + BUBBLE_PADDING * 2)
  }

  private calculateBubbleHeight(): number {
    return this.textDisplay.height + BUBBLE_PADDING * 2
  }

  private drawBackground(): void {
    this.background.clear()

    const width = this.calculateBubbleWidth()
    const height = this.calculateBubbleHeight()

    this.background.roundRect(0, 0, width, height, BUBBLE_RADIUS)
    this.background.fill(BACKGROUND_COLOR)
    this.background.stroke({ width: BORDER_WIDTH, color: BORDER_COLOR })

    const tailX = width / 2
    const tailY = height

    this.background.moveTo(tailX - TAIL_WIDTH / 2, tailY)
    this.background.lineTo(tailX, tailY + TAIL_HEIGHT)
    this.background.lineTo(tailX + TAIL_WIDTH / 2, tailY)
    this.background.closePath()
    this.background.fill(BACKGROUND_COLOR)

    this.background.moveTo(tailX - TAIL_WIDTH / 2, tailY)
    this.background.lineTo(tailX, tailY + TAIL_HEIGHT)
    this.background.stroke({ width: BORDER_WIDTH, color: BORDER_COLOR })

    this.background.moveTo(tailX, tailY + TAIL_HEIGHT)
    this.background.lineTo(tailX + TAIL_WIDTH / 2, tailY)
    this.background.stroke({ width: BORDER_WIDTH, color: BORDER_COLOR })

    this.background.rect(tailX - TAIL_WIDTH / 2 + 1, tailY - 2, TAIL_WIDTH - 2, 4)
    this.background.fill(BACKGROUND_COLOR)
  }
}
