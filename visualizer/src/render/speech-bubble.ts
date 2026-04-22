import { Container, Graphics, Text, Ticker } from 'pixi.js'
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

const DOT_RADIUS = 5
const DOT_SPACING = 12
const DOT_COLOR = 0x666666
const DOT_ANIMATION_DURATION = 400  // ms per dot cycle
const DOT_COUNT = 3

export class SpeechBubble {
  private container: Container
  private background: Graphics
  private textDisplay: Text
  private visible = false
  private typingIndicator: Container
  private typingDots: Graphics[] = []
  private typingTicker: Ticker | null = null
  private typingAnimationTime = 0

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

    this.typingIndicator = new Container()
    this.typingIndicator.visible = false
    this.createTypingDots()
    this.container.addChild(this.typingIndicator)
  }

  private createTypingDots(): void {
    const totalWidth = DOT_COUNT * DOT_RADIUS * 2 + (DOT_COUNT - 1) * DOT_SPACING
    const startX = -totalWidth / 2 + DOT_RADIUS

    for (let i = 0; i < DOT_COUNT; i++) {
      const dot = new Graphics()
      dot.circle(0, 0, DOT_RADIUS)
      dot.fill(DOT_COLOR)
      dot.x = startX + i * (DOT_RADIUS * 2 + DOT_SPACING)
      dot.y = 0
      dot.alpha = 0.3
      this.typingDots.push(dot)
      this.typingIndicator.addChild(dot)
    }
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
    this.hideTypingIndicator()
  }

  showTypingIndicator(): void {
    this.textDisplay.visible = false
    this.typingIndicator.visible = true
    this.typingAnimationTime = 0

    this.positionTypingIndicator()
    this.drawBackgroundForTypingIndicator()

    if (!this.typingTicker) {
      this.typingTicker = new Ticker()
      this.typingTicker.add(this.animateTypingDots, this)
      this.typingTicker.start()
    }
  }

  hideTypingIndicator(): void {
    this.typingIndicator.visible = false
    this.textDisplay.visible = true

    if (this.typingTicker) {
      this.typingTicker.stop()
      this.typingTicker.destroy()
      this.typingTicker = null
    }

    for (const dot of this.typingDots) {
      dot.alpha = 0.3
    }
  }

  private positionTypingIndicator(): void {
    const indicatorWidth = DOT_COUNT * DOT_RADIUS * 2 + (DOT_COUNT - 1) * DOT_SPACING
    this.typingIndicator.x = BUBBLE_PADDING + indicatorWidth / 2
    this.typingIndicator.y = BUBBLE_PADDING + DOT_RADIUS
  }

  private drawBackgroundForTypingIndicator(): void {
    this.background.clear()

    const indicatorWidth = DOT_COUNT * DOT_RADIUS * 2 + (DOT_COUNT - 1) * DOT_SPACING
    const width = indicatorWidth + BUBBLE_PADDING * 2
    const height = DOT_RADIUS * 2 + BUBBLE_PADDING * 2

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

  private animateTypingDots(ticker: Ticker): void {
    this.typingAnimationTime += ticker.deltaMS

    const cycleDuration = DOT_ANIMATION_DURATION * DOT_COUNT
    const phase = (this.typingAnimationTime % cycleDuration) / DOT_ANIMATION_DURATION

    for (let i = 0; i < DOT_COUNT; i++) {
      const dot = this.typingDots[i]
      if (!dot) continue

      const dotPhase = (phase - i + DOT_COUNT) % DOT_COUNT
      if (dotPhase < 1) {
        dot.alpha = 0.3 + 0.7 * Math.sin(dotPhase * Math.PI)
      } else {
        dot.alpha = 0.3
      }
    }
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
    this.hideTypingIndicator()
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
