import { Container, Graphics, Text, Ticker } from 'pixi.js'
import { Phase } from '@parser/types'
import { PHASE_CHANGE_DURATION_MS } from '@config/timings'

const SCENE_WIDTH = 1920
const SCENE_HEIGHT = 1080
const OVERLAY_COLOR = 0x000000
const OVERLAY_ALPHA = 0.7
const LABEL_FONT_SIZE = 72
const LABEL_COLOR = 0xffffff

interface PhaseStyle {
  accentColor: number
  glowIntensity: number
}

const PHASE_STYLES: Record<Phase, PhaseStyle> = {
  [Phase.MainRound]: {
    accentColor: 0x4a90d9,
    glowIntensity: 0.3,
  },
  [Phase.Voting]: {
    accentColor: 0x5c7cfa,
    glowIntensity: 0.5,
  },
  [Phase.Defense]: {
    accentColor: 0xf5a623,
    glowIntensity: 0.6,
  },
  [Phase.Final]: {
    accentColor: 0xe74c3c,
    glowIntensity: 0.8,
  },
  [Phase.Resolution]: {
    accentColor: 0x27ae60,
    glowIntensity: 0.4,
  },
}

type AnimationPhase = 'fade_in' | 'hold' | 'fade_out'

export class PhaseOverlay {
  private container: Container
  private overlay: Graphics
  private labelText: Text
  private accentBar: Graphics

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

    this.overlay = new Graphics()
    this.container.addChild(this.overlay)

    this.accentBar = new Graphics()
    this.container.addChild(this.accentBar)

    this.labelText = new Text({
      text: '',
      style: {
        fontFamily: 'Arial, sans-serif',
        fontSize: LABEL_FONT_SIZE,
        fontWeight: 'bold',
        fill: LABEL_COLOR,
        align: 'center',
        dropShadow: {
          color: 0x000000,
          blur: 8,
          distance: 2,
          alpha: 0.8,
        },
      },
    })
    this.labelText.anchor.set(0.5, 0.5)
    this.labelText.x = SCENE_WIDTH / 2
    this.labelText.y = SCENE_HEIGHT / 2
    this.container.addChild(this.labelText)

    const totalDuration = PHASE_CHANGE_DURATION_MS
    this.fadeInDuration = totalDuration * 0.25
    this.holdDuration = totalDuration * 0.5
    this.fadeOutDuration = totalDuration * 0.25
  }

  showPhaseChange(phase: Phase, label: string): Promise<void> {
    return new Promise((resolve) => {
      this.animationResolve = resolve

      const style = PHASE_STYLES[phase]
      this.drawOverlay(0)
      this.drawAccentBar(style.accentColor, 0)
      this.labelText.text = label
      this.labelText.alpha = 0

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

    this.drawOverlay(OVERLAY_ALPHA * eased)
    this.labelText.alpha = eased
    this.labelText.scale.set(0.8 + 0.2 * eased)
    this.accentBar.alpha = eased

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

    this.drawOverlay(OVERLAY_ALPHA * (1 - eased))
    this.labelText.alpha = 1 - eased
    this.accentBar.alpha = 1 - eased

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

  private drawOverlay(alpha: number): void {
    this.overlay.clear()
    this.overlay.rect(0, 0, SCENE_WIDTH, SCENE_HEIGHT)
    this.overlay.fill({ color: OVERLAY_COLOR, alpha })
  }

  private drawAccentBar(color: number, alpha: number = 1): void {
    this.accentBar.clear()

    const barHeight = 6
    const barY = SCENE_HEIGHT / 2 + 60

    this.accentBar.rect(0, barY, SCENE_WIDTH, barHeight)
    this.accentBar.fill({ color, alpha })

    this.accentBar.rect(0, barY - barHeight - 4, SCENE_WIDTH, barHeight)
    this.accentBar.fill({ color, alpha: alpha * 0.3 })
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

  destroy(): void {
    this.finishAnimation()
    this.container.destroy({ children: true })
  }
}
