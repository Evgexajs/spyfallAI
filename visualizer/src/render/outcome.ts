import { Container, Graphics, Text, Ticker } from 'pixi.js'
import { Winner } from '@parser/types'

const SCENE_WIDTH = 1920
const SCENE_HEIGHT = 1080
const OVERLAY_COLOR = 0x000000
const OVERLAY_ALPHA = 0.85

const WINNER_FONT_SIZE = 72
const SPY_LABEL_FONT_SIZE = 32
const REASON_FONT_SIZE = 36

const SPY_WIN_COLOR = 0xe74c3c
const CIVILIANS_WIN_COLOR = 0x3498db
const GOLD_ACCENT = 0xf1c40f

type AnimationPhase = 'fade_in' | 'hold'

interface SpyPosition {
  x: number
  y: number
}

export class OutcomeOverlay {
  private container: Container
  private overlay: Graphics
  private spyHighlight: Graphics
  private winnerBanner: Graphics
  private winnerText: Text
  private spyLabel: Text
  private spyNameText: Text
  private reasonText: Text

  private animationTicker: Ticker | null = null
  private animationTime = 0
  private animationPhase: AnimationPhase = 'fade_in'

  private spyPosition: SpyPosition | null = null
  private winnerValue: Winner = Winner.Civilians

  private readonly fadeInDuration = 1500

  constructor() {
    this.container = new Container()
    this.container.visible = false

    this.overlay = new Graphics()
    this.container.addChild(this.overlay)

    this.spyHighlight = new Graphics()
    this.container.addChild(this.spyHighlight)

    this.winnerBanner = new Graphics()
    this.container.addChild(this.winnerBanner)

    this.winnerText = new Text({
      text: '',
      style: {
        fontFamily: 'Arial, sans-serif',
        fontSize: WINNER_FONT_SIZE,
        fontWeight: 'bold',
        fill: 0xffffff,
        align: 'center',
        dropShadow: {
          color: 0x000000,
          blur: 15,
          distance: 4,
          alpha: 0.9,
        },
      },
    })
    this.winnerText.anchor.set(0.5, 0.5)
    this.winnerText.x = SCENE_WIDTH / 2
    this.winnerText.y = SCENE_HEIGHT / 2 - 100
    this.container.addChild(this.winnerText)

    this.spyLabel = new Text({
      text: '',
      style: {
        fontFamily: 'Arial, sans-serif',
        fontSize: SPY_LABEL_FONT_SIZE,
        fontWeight: 'normal',
        fill: 0xaaaaaa,
        align: 'center',
      },
    })
    this.spyLabel.anchor.set(0.5, 0.5)
    this.spyLabel.x = SCENE_WIDTH / 2
    this.spyLabel.y = SCENE_HEIGHT / 2 + 20
    this.container.addChild(this.spyLabel)

    this.spyNameText = new Text({
      text: '',
      style: {
        fontFamily: 'Arial, sans-serif',
        fontSize: 48,
        fontWeight: 'bold',
        fill: GOLD_ACCENT,
        align: 'center',
        dropShadow: {
          color: 0x000000,
          blur: 8,
          distance: 2,
          alpha: 0.8,
        },
      },
    })
    this.spyNameText.anchor.set(0.5, 0.5)
    this.spyNameText.x = SCENE_WIDTH / 2
    this.spyNameText.y = SCENE_HEIGHT / 2 + 70
    this.container.addChild(this.spyNameText)

    this.reasonText = new Text({
      text: '',
      style: {
        fontFamily: 'Arial, sans-serif',
        fontSize: REASON_FONT_SIZE,
        fontWeight: 'normal',
        fill: 0xdddddd,
        align: 'center',
        wordWrap: true,
        wordWrapWidth: SCENE_WIDTH * 0.7,
      },
    })
    this.reasonText.anchor.set(0.5, 0.5)
    this.reasonText.x = SCENE_WIDTH / 2
    this.reasonText.y = SCENE_HEIGHT / 2 + 160
    this.container.addChild(this.reasonText)
  }

  show(winner: Winner, spyPosition: SpyPosition | null, spyName: string, reason: string): void {
    this.winnerValue = winner
    this.spyPosition = spyPosition

    const accentColor = winner === Winner.Spy ? SPY_WIN_COLOR : CIVILIANS_WIN_COLOR

    this.drawOverlay(0)
    this.drawWinnerBanner(0, accentColor)
    this.drawSpyHighlight(0)

    this.winnerText.text = winner === Winner.Spy ? 'ПОБЕДА ШПИОНА!' : 'ПОБЕДА МИРНЫХ!'
    this.winnerText.style.fill = accentColor
    this.winnerText.alpha = 0
    this.winnerText.scale.set(0.5)

    this.spyLabel.text = 'Шпионом был:'
    this.spyLabel.alpha = 0

    this.spyNameText.text = spyName
    this.spyNameText.alpha = 0

    this.reasonText.text = reason
    this.reasonText.alpha = 0

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
  }

  private animate(ticker: Ticker): void {
    this.animationTime += ticker.deltaMS

    if (this.animationPhase === 'fade_in') {
      this.animateFadeIn()
    }
  }

  private animateFadeIn(): void {
    const progress = Math.min(this.animationTime / this.fadeInDuration, 1)
    const eased = this.easeOutCubic(progress)

    const accentColor = this.winnerValue === Winner.Spy ? SPY_WIN_COLOR : CIVILIANS_WIN_COLOR

    this.drawOverlay(OVERLAY_ALPHA * eased)
    this.drawWinnerBanner(eased, accentColor)
    this.drawSpyHighlight(eased)

    this.winnerText.alpha = eased
    this.winnerText.scale.set(0.5 + 0.5 * eased)

    const delayedProgress = Math.max(0, (progress - 0.3) / 0.7)
    const delayedEased = this.easeOutCubic(delayedProgress)

    this.spyLabel.alpha = delayedEased
    this.spyNameText.alpha = delayedEased

    const reasonProgress = Math.max(0, (progress - 0.5) / 0.5)
    const reasonEased = this.easeOutCubic(reasonProgress)
    this.reasonText.alpha = reasonEased

    if (progress >= 1) {
      this.animationPhase = 'hold'
      if (this.animationTicker) {
        this.animationTicker.stop()
        this.animationTicker.destroy()
        this.animationTicker = null
      }
    }
  }

  private drawOverlay(alpha: number): void {
    this.overlay.clear()
    this.overlay.rect(0, 0, SCENE_WIDTH, SCENE_HEIGHT)
    this.overlay.fill({ color: OVERLAY_COLOR, alpha })
  }

  private drawWinnerBanner(alpha: number, color: number): void {
    this.winnerBanner.clear()

    if (alpha <= 0) return

    const bannerHeight = 200
    const bannerY = SCENE_HEIGHT / 2 - bannerHeight / 2 - 50

    this.winnerBanner.rect(0, bannerY, SCENE_WIDTH, bannerHeight)
    this.winnerBanner.fill({ color, alpha: alpha * 0.15 })

    this.winnerBanner.rect(0, bannerY, SCENE_WIDTH, 3)
    this.winnerBanner.fill({ color, alpha: alpha * 0.6 })

    this.winnerBanner.rect(0, bannerY + bannerHeight - 3, SCENE_WIDTH, 3)
    this.winnerBanner.fill({ color, alpha: alpha * 0.6 })
  }

  private drawSpyHighlight(alpha: number): void {
    this.spyHighlight.clear()

    if (!this.spyPosition || alpha <= 0) return

    const { x, y } = this.spyPosition
    const baseRadius = 70

    for (let i = 4; i >= 0; i--) {
      const ringRadius = baseRadius + i * 20
      const ringAlpha = alpha * (0.2 - i * 0.04)
      this.spyHighlight.circle(x, y, ringRadius)
      this.spyHighlight.fill({ color: GOLD_ACCENT, alpha: ringAlpha })
    }

    this.spyHighlight.circle(x, y, baseRadius)
    this.spyHighlight.stroke({ color: GOLD_ACCENT, width: 5, alpha })
    this.spyHighlight.circle(x, y, baseRadius - 8)
    this.spyHighlight.stroke({ color: GOLD_ACCENT, width: 2, alpha: alpha * 0.6 })
  }

  private easeOutCubic(t: number): number {
    return 1 - Math.pow(1 - t, 3)
  }

  getContainer(): Container {
    return this.container
  }

  hide(): void {
    if (this.animationTicker) {
      this.animationTicker.stop()
      this.animationTicker.destroy()
      this.animationTicker = null
    }
    this.container.visible = false
    this.spyPosition = null
  }

  isVisible(): boolean {
    return this.container.visible
  }

  destroy(): void {
    this.hide()
    this.container.destroy({ children: true })
  }
}
