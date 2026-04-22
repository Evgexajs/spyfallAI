import { Container, Graphics, Text, Ticker } from 'pixi.js'

const SCENE_WIDTH = 1920
const SCENE_HEIGHT = 1080

const MESSAGE_FONT_SIZE = 36
const MESSAGE_COLOR = 0xffffff
const BACKGROUND_COLOR = 0x000000
const BACKGROUND_ALPHA = 0.6
const PADDING_X = 40
const PADDING_Y = 16
const BORDER_RADIUS = 8
const BOTTOM_MARGIN = 60

const TOTAL_DURATION_MS = 2000
const FADE_IN_RATIO = 0.15
const HOLD_RATIO = 0.7
const FADE_OUT_RATIO = 0.15

type AnimationPhase = 'fade_in' | 'hold' | 'fade_out'

export class SystemMessage {
  private container: Container
  private background: Graphics
  private messageText: Text

  private animationTicker: Ticker | null = null
  private animationTime = 0
  private animationPhase: AnimationPhase = 'fade_in'
  private animationResolve: (() => void) | null = null

  private fadeInDuration: number
  private holdDuration: number
  private fadeOutDuration: number

  constructor() {
    this.container = new Container()
    this.container.visible = false

    this.background = new Graphics()
    this.container.addChild(this.background)

    this.messageText = new Text({
      text: '',
      style: {
        fontFamily: 'Arial, sans-serif',
        fontSize: MESSAGE_FONT_SIZE,
        fontWeight: 'bold',
        fill: MESSAGE_COLOR,
        align: 'center',
        dropShadow: {
          color: 0x000000,
          blur: 4,
          distance: 1,
          alpha: 0.5,
        },
      },
    })
    this.messageText.anchor.set(0.5, 0.5)
    this.container.addChild(this.messageText)

    this.fadeInDuration = TOTAL_DURATION_MS * FADE_IN_RATIO
    this.holdDuration = TOTAL_DURATION_MS * HOLD_RATIO
    this.fadeOutDuration = TOTAL_DURATION_MS * FADE_OUT_RATIO
  }

  show(content: string): Promise<void> {
    return new Promise((resolve) => {
      this.animationResolve = resolve

      this.messageText.text = content

      const textWidth = this.messageText.width
      const textHeight = this.messageText.height
      const bgWidth = textWidth + PADDING_X * 2
      const bgHeight = textHeight + PADDING_Y * 2

      this.messageText.x = SCENE_WIDTH / 2
      this.messageText.y = SCENE_HEIGHT - BOTTOM_MARGIN - bgHeight / 2

      this.drawBackground(bgWidth, bgHeight, 0)
      this.messageText.alpha = 0

      this.container.visible = true
      this.animationTime = 0
      this.animationPhase = 'fade_in'

      if (this.animationTicker) {
        this.animationTicker.stop()
        this.animationTicker.destroy()
      }

      this.animationTicker = new Ticker()
      this.animationTicker.add((ticker) => this.animate(ticker))
      this.animationTicker.start()
    })
  }

  private animate(ticker: Ticker): void {
    this.animationTime += ticker.deltaMS

    switch (this.animationPhase) {
      case 'fade_in':
        this.animateFadeIn()
        break
      case 'hold':
        this.animateHold()
        break
      case 'fade_out':
        this.animateFadeOut()
        break
    }
  }

  private animateFadeIn(): void {
    const progress = Math.min(this.animationTime / this.fadeInDuration, 1)
    const eased = this.easeOutCubic(progress)

    const textWidth = this.messageText.width / this.messageText.scale.x
    const textHeight = this.messageText.height / this.messageText.scale.y
    const bgWidth = textWidth + PADDING_X * 2
    const bgHeight = textHeight + PADDING_Y * 2

    this.drawBackground(bgWidth, bgHeight, BACKGROUND_ALPHA * eased)
    this.messageText.alpha = eased

    if (progress >= 1) {
      this.animationPhase = 'hold'
      this.animationTime = 0
    }
  }

  private animateHold(): void {
    if (this.animationTime >= this.holdDuration) {
      this.animationPhase = 'fade_out'
      this.animationTime = 0
    }
  }

  private animateFadeOut(): void {
    const progress = Math.min(this.animationTime / this.fadeOutDuration, 1)
    const eased = this.easeInCubic(progress)

    const textWidth = this.messageText.width / this.messageText.scale.x
    const textHeight = this.messageText.height / this.messageText.scale.y
    const bgWidth = textWidth + PADDING_X * 2
    const bgHeight = textHeight + PADDING_Y * 2

    this.drawBackground(bgWidth, bgHeight, BACKGROUND_ALPHA * (1 - eased))
    this.messageText.alpha = 1 - eased

    if (progress >= 1) {
      this.finishAnimation()
    }
  }

  private finishAnimation(): void {
    if (this.animationTicker) {
      this.animationTicker.stop()
      this.animationTicker.destroy()
      this.animationTicker = null
    }

    this.container.visible = false

    if (this.animationResolve) {
      this.animationResolve()
      this.animationResolve = null
    }
  }

  private drawBackground(width: number, height: number, alpha: number): void {
    this.background.clear()

    const x = SCENE_WIDTH / 2 - width / 2
    const y = SCENE_HEIGHT - BOTTOM_MARGIN - height

    this.background.roundRect(x, y, width, height, BORDER_RADIUS)
    this.background.fill({ color: BACKGROUND_COLOR, alpha })
  }

  private easeOutCubic(t: number): number {
    return 1 - Math.pow(1 - t, 3)
  }

  private easeInCubic(t: number): number {
    return t * t * t
  }

  getContainer(): Container {
    return this.container
  }

  hide(): void {
    this.finishAnimation()
  }

  isVisible(): boolean {
    return this.container.visible
  }

  destroy(): void {
    this.finishAnimation()
    this.container.destroy({ children: true })
  }
}
