import { Container, Graphics, Text, Ticker } from 'pixi.js'
import type { Position } from './character-renderer'
import { SpeechSubtype } from '@parser/types'

const BUBBLE_MAX_WIDTH = 400
const BUBBLE_PADDING = 16
const BUBBLE_RADIUS = 12
const TAIL_WIDTH = 20
const TAIL_HEIGHT = 15
const FONT_SIZE = 18

interface BubbleStyle {
  backgroundColor: number
  borderColor: number
  borderWidth: number
  textColor: number
}

const STYLES: Record<SpeechSubtype, BubbleStyle> = {
  [SpeechSubtype.Normal]: {
    backgroundColor: 0xffffff,
    borderColor: 0xcccccc,
    borderWidth: 2,
    textColor: 0x333333,
  },
  [SpeechSubtype.Defense]: {
    backgroundColor: 0xfffef0,
    borderColor: 0xf5a623,
    borderWidth: 4,
    textColor: 0x333333,
  },
  [SpeechSubtype.PostGuess]: {
    backgroundColor: 0xf0f0f0,
    borderColor: 0x999999,
    borderWidth: 2,
    textColor: 0x555555,
  },
}

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

  private _isPaused = false
  private typeTextResolve: (() => void) | null = null
  private typeTextFullText = ''
  private typeTextCurrentIndex = 0
  private typeTextSpeed = 30
  private typeTextTicker: Ticker | null = null
  private typeTextAccumulator = 0

  private currentStyle: BubbleStyle = STYLES[SpeechSubtype.Normal]
  private targetPosition: Position = { x: 0, y: 0 }

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
        fill: this.currentStyle.textColor,
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
    const bubbleWidth = indicatorWidth + BUBBLE_PADDING * 2
    this.container.x = this.targetPosition.x - bubbleWidth / 2
    this.container.y = this.targetPosition.y
    const width = indicatorWidth + BUBBLE_PADDING * 2
    const height = DOT_RADIUS * 2 + BUBBLE_PADDING * 2
    const { backgroundColor, borderColor, borderWidth } = this.currentStyle

    this.background.roundRect(0, 0, width, height, BUBBLE_RADIUS)
    this.background.fill(backgroundColor)
    this.background.stroke({ width: borderWidth, color: borderColor })

    const tailX = width / 2
    const tailY = height

    this.background.moveTo(tailX - TAIL_WIDTH / 2, tailY)
    this.background.lineTo(tailX, tailY + TAIL_HEIGHT)
    this.background.lineTo(tailX + TAIL_WIDTH / 2, tailY)
    this.background.closePath()
    this.background.fill(backgroundColor)

    this.background.moveTo(tailX - TAIL_WIDTH / 2, tailY)
    this.background.lineTo(tailX, tailY + TAIL_HEIGHT)
    this.background.stroke({ width: borderWidth, color: borderColor })

    this.background.moveTo(tailX, tailY + TAIL_HEIGHT)
    this.background.lineTo(tailX + TAIL_WIDTH / 2, tailY)
    this.background.stroke({ width: borderWidth, color: borderColor })

    this.background.rect(tailX - TAIL_WIDTH / 2 + 1, tailY - 2, TAIL_WIDTH - 2, 4)
    this.background.fill(backgroundColor)
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

  setStyle(subtype: SpeechSubtype): void {
    this.currentStyle = STYLES[subtype]
    this.textDisplay.style.fill = this.currentStyle.textColor
    if (this.visible) {
      this.drawBackground()
    }
  }

  setText(text: string): void {
    this.textDisplay.text = text
    this.drawBackground()
  }

  getText(): string {
    return this.textDisplay.text
  }

  get isPaused(): boolean {
    return this._isPaused
  }

  set isPaused(value: boolean) {
    this._isPaused = value
  }

  typeText(text: string, speed: number): Promise<void> {
    return new Promise((resolve) => {
      this.hideTypingIndicator()
      this.textDisplay.visible = true

      this.typeTextFullText = text
      this.typeTextCurrentIndex = 0
      this.typeTextSpeed = speed
      this.typeTextResolve = resolve

      this.textDisplay.text = ''
      this.drawBackground()

      if (this.typeTextTicker) {
        this.typeTextTicker.stop()
        this.typeTextTicker.destroy()
      }

      this.typeTextTicker = new Ticker()
      this.typeTextTicker.add(this.tickTypeText, this)
      this.typeTextTicker.start()
    })
  }

  private tickTypeText(ticker: Ticker): void {
    if (this._isPaused) return

    this.typeTextAccumulator += ticker.deltaMS

    while (this.typeTextAccumulator >= this.typeTextSpeed && this.typeTextCurrentIndex < this.typeTextFullText.length) {
      this.typeTextAccumulator -= this.typeTextSpeed
      this.typeTextCurrentIndex++
      this.textDisplay.text = this.typeTextFullText.slice(0, this.typeTextCurrentIndex)
      this.drawBackground()
    }

    if (this.typeTextCurrentIndex >= this.typeTextFullText.length) {
      this.stopTypeText()
      if (this.typeTextResolve) {
        this.typeTextResolve()
        this.typeTextResolve = null
      }
    }
  }

  private stopTypeText(): void {
    if (this.typeTextTicker) {
      this.typeTextTicker.stop()
      this.typeTextTicker.destroy()
      this.typeTextTicker = null
    }
    this.typeTextAccumulator = 0
  }

  getContainer(): Container {
    return this.container
  }

  isVisible(): boolean {
    return this.visible
  }

  destroy(): void {
    this.hideTypingIndicator()
    this.stopTypeText()
    this.container.destroy({ children: true })
  }

  private updatePosition(position?: Position): void {
    if (position) {
      this.targetPosition = position
    }
    const bubbleWidth = this.calculateBubbleWidth()
    this.container.x = this.targetPosition.x - bubbleWidth / 2
    this.container.y = this.targetPosition.y
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
    this.updatePosition()

    const width = this.calculateBubbleWidth()
    const height = this.calculateBubbleHeight()
    const { backgroundColor, borderColor, borderWidth } = this.currentStyle

    this.background.roundRect(0, 0, width, height, BUBBLE_RADIUS)
    this.background.fill(backgroundColor)
    this.background.stroke({ width: borderWidth, color: borderColor })

    const tailX = width / 2
    const tailY = height

    this.background.moveTo(tailX - TAIL_WIDTH / 2, tailY)
    this.background.lineTo(tailX, tailY + TAIL_HEIGHT)
    this.background.lineTo(tailX + TAIL_WIDTH / 2, tailY)
    this.background.closePath()
    this.background.fill(backgroundColor)

    this.background.moveTo(tailX - TAIL_WIDTH / 2, tailY)
    this.background.lineTo(tailX, tailY + TAIL_HEIGHT)
    this.background.stroke({ width: borderWidth, color: borderColor })

    this.background.moveTo(tailX, tailY + TAIL_HEIGHT)
    this.background.lineTo(tailX + TAIL_WIDTH / 2, tailY)
    this.background.stroke({ width: borderWidth, color: borderColor })

    this.background.rect(tailX - TAIL_WIDTH / 2 + 1, tailY - 2, TAIL_WIDTH - 2, 4)
    this.background.fill(backgroundColor)
  }
}
