import { Container, Graphics, Text, Ticker } from 'pixi.js'
import { SPY_GUESS_DURATION_MS } from '@config/timings'

const SCENE_WIDTH = 1920
const SCENE_HEIGHT = 1080
const OVERLAY_COLOR = 0x000000
const OVERLAY_ALPHA = 0.75

const LOCATION_FONT_SIZE = 64
const RESULT_FONT_SIZE = 48
const LABEL_FONT_SIZE = 28

const CORRECT_COLOR = 0x27ae60
const INCORRECT_COLOR = 0xe74c3c
const GUESS_ACCENT_COLOR = 0xf5a623

type AnimationPhase = 'fade_in' | 'hold_guess' | 'reveal' | 'hold_result' | 'fade_out'

interface SpyPosition {
  x: number
  y: number
}

export class SpyGuessOverlay {
  private container: Container
  private overlay: Graphics
  private spyHighlight: Graphics
  private guessLabel: Text
  private locationText: Text
  private resultText: Text

  private animationTicker: Ticker | null = null
  private animationTime = 0
  private animationPhase: AnimationPhase = 'fade_in'
  private animationResolve: (() => void) | null = null

  private spyPosition: SpyPosition | null = null
  private isCorrect = false

  private fadeInDuration: number
  private holdGuessDuration: number
  private revealDuration: number
  private holdResultDuration: number
  private fadeOutDuration: number

  constructor() {
    this.container = new Container()
    this.container.visible = false

    this.overlay = new Graphics()
    this.container.addChild(this.overlay)

    this.spyHighlight = new Graphics()
    this.container.addChild(this.spyHighlight)

    this.guessLabel = new Text({
      text: '',
      style: {
        fontFamily: 'Arial, sans-serif',
        fontSize: LABEL_FONT_SIZE,
        fontWeight: 'normal',
        fill: 0xcccccc,
        align: 'center',
      },
    })
    this.guessLabel.anchor.set(0.5, 0.5)
    this.guessLabel.x = SCENE_WIDTH / 2
    this.guessLabel.y = SCENE_HEIGHT / 2 - 80
    this.container.addChild(this.guessLabel)

    this.locationText = new Text({
      text: '',
      style: {
        fontFamily: 'Arial, sans-serif',
        fontSize: LOCATION_FONT_SIZE,
        fontWeight: 'bold',
        fill: GUESS_ACCENT_COLOR,
        align: 'center',
        dropShadow: {
          color: 0x000000,
          blur: 10,
          distance: 3,
          alpha: 0.9,
        },
      },
    })
    this.locationText.anchor.set(0.5, 0.5)
    this.locationText.x = SCENE_WIDTH / 2
    this.locationText.y = SCENE_HEIGHT / 2
    this.container.addChild(this.locationText)

    this.resultText = new Text({
      text: '',
      style: {
        fontFamily: 'Arial, sans-serif',
        fontSize: RESULT_FONT_SIZE,
        fontWeight: 'bold',
        fill: 0xffffff,
        align: 'center',
        dropShadow: {
          color: 0x000000,
          blur: 8,
          distance: 2,
          alpha: 0.8,
        },
      },
    })
    this.resultText.anchor.set(0.5, 0.5)
    this.resultText.x = SCENE_WIDTH / 2
    this.resultText.y = SCENE_HEIGHT / 2 + 80
    this.container.addChild(this.resultText)

    const totalDuration = SPY_GUESS_DURATION_MS
    this.fadeInDuration = totalDuration * 0.15
    this.holdGuessDuration = totalDuration * 0.30
    this.revealDuration = totalDuration * 0.15
    this.holdResultDuration = totalDuration * 0.25
    this.fadeOutDuration = totalDuration * 0.15
  }

  show(spyPosition: SpyPosition, guessedLocation: string, correct: boolean): Promise<void> {
    return new Promise((resolve) => {
      this.animationResolve = resolve
      this.spyPosition = spyPosition
      this.isCorrect = correct

      this.drawOverlay(0)
      this.drawSpyHighlight(0, 1)

      this.guessLabel.text = 'Шпион угадывает локацию:'
      this.guessLabel.alpha = 0

      this.locationText.text = guessedLocation
      this.locationText.alpha = 0
      this.locationText.scale.set(0.5)

      this.resultText.text = ''
      this.resultText.alpha = 0

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
      case 'hold_guess':
        this.animateHoldGuess()
        break
      case 'reveal':
        this.animateReveal()
        break
      case 'hold_result':
        this.animateHoldResult()
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
    this.drawSpyHighlight(eased, 1 + 0.3 * eased)

    this.guessLabel.alpha = eased
    this.locationText.alpha = eased
    this.locationText.scale.set(0.5 + 0.5 * eased)

    if (progress >= 1) {
      this.animationPhase = 'hold_guess'
      this.animationTime = 0
    }
  }

  private animateHoldGuess(): void {
    const progress = this.animationTime / this.holdGuessDuration
    const pulse = Math.sin(progress * Math.PI * 4) * 0.05
    this.locationText.scale.set(1 + pulse)

    if (this.animationTime >= this.holdGuessDuration) {
      this.locationText.scale.set(1)
      this.animationPhase = 'reveal'
      this.animationTime = 0
    }
  }

  private animateReveal(): void {
    const progress = Math.min(this.animationTime / this.revealDuration, 1)
    const eased = this.easeOutCubic(progress)

    if (progress < 0.1 && this.resultText.text === '') {
      this.resultText.text = this.isCorrect ? 'ВЕРНО!' : 'НЕВЕРНО!'
      const color = this.isCorrect ? CORRECT_COLOR : INCORRECT_COLOR
      this.resultText.style.fill = color
      this.locationText.style.fill = color
    }

    this.resultText.alpha = eased
    this.resultText.scale.set(0.8 + 0.2 * eased)

    const highlightColor = this.isCorrect ? CORRECT_COLOR : INCORRECT_COLOR
    this.drawSpyHighlightWithColor(1, 1.3, highlightColor)

    if (progress >= 1) {
      this.animationPhase = 'hold_result'
      this.animationTime = 0
    }
  }

  private animateHoldResult(): void {
    if (this.animationTime >= this.holdResultDuration) {
      this.animationPhase = 'fade_out'
      this.animationTime = 0
    }
  }

  private animateFadeOut(): void {
    const progress = Math.min(this.animationTime / this.fadeOutDuration, 1)
    const eased = this.easeInCubic(progress)

    this.drawOverlay(OVERLAY_ALPHA * (1 - eased))
    this.drawSpyHighlight(1 - eased, 1.3 - 0.3 * eased)

    this.guessLabel.alpha = 1 - eased
    this.locationText.alpha = 1 - eased
    this.resultText.alpha = 1 - eased

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
    this.spyPosition = null

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

  private drawSpyHighlight(alpha: number, scale: number): void {
    this.drawSpyHighlightWithColor(alpha, scale, GUESS_ACCENT_COLOR)
  }

  private drawSpyHighlightWithColor(alpha: number, scale: number, color: number): void {
    this.spyHighlight.clear()

    if (!this.spyPosition || alpha <= 0) return

    const { x, y } = this.spyPosition
    const baseRadius = 80
    const radius = baseRadius * scale

    for (let i = 3; i >= 0; i--) {
      const ringRadius = radius + i * 15
      const ringAlpha = alpha * (0.15 - i * 0.03)
      this.spyHighlight.circle(x, y, ringRadius)
      this.spyHighlight.fill({ color, alpha: ringAlpha })
    }

    this.spyHighlight.circle(x, y, radius)
    this.spyHighlight.stroke({ color, width: 4, alpha })
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
