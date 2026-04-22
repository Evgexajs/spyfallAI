import { Container, Graphics, Ticker } from 'pixi.js'
import { VotePhase } from '@parser/types'
import type { SlotPosition } from '@config/slots'

const ARROW_WIDTH_PRELIMINARY = 4
const ARROW_WIDTH_FINAL = 8
const ARROW_HEAD_LENGTH = 20
const ARROW_HEAD_WIDTH = 16

const COLOR_PRELIMINARY = 0x5c7cfa
const COLOR_FINAL = 0xe74c3c

const HIGHLIGHT_RADIUS = 80
const HIGHLIGHT_ALPHA_PRELIMINARY = 0.3
const HIGHLIGHT_ALPHA_FINAL = 0.5

const VOTE_DURATION_MS = 2000
const FADE_IN_RATIO = 0.2
const HOLD_RATIO = 0.6
const FADE_OUT_RATIO = 0.2

type AnimationPhase = 'fade_in' | 'hold' | 'fade_out'

export class VoteIndicator {
  private container: Container
  private arrowGraphics: Graphics
  private highlightGraphics: Graphics

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

    this.highlightGraphics = new Graphics()
    this.container.addChild(this.highlightGraphics)

    this.arrowGraphics = new Graphics()
    this.container.addChild(this.arrowGraphics)

    this.fadeInDuration = VOTE_DURATION_MS * FADE_IN_RATIO
    this.holdDuration = VOTE_DURATION_MS * HOLD_RATIO
    this.fadeOutDuration = VOTE_DURATION_MS * FADE_OUT_RATIO
  }

  showVote(
    voterPosition: SlotPosition,
    targetPosition: SlotPosition,
    phase: VotePhase
  ): Promise<void> {
    return new Promise((resolve) => {
      this.animationResolve = resolve

      const isFinal = phase === VotePhase.Final
      const color = isFinal ? COLOR_FINAL : COLOR_PRELIMINARY
      const arrowWidth = isFinal ? ARROW_WIDTH_FINAL : ARROW_WIDTH_PRELIMINARY
      const highlightAlpha = isFinal ? HIGHLIGHT_ALPHA_FINAL : HIGHLIGHT_ALPHA_PRELIMINARY

      this.drawArrow(voterPosition, targetPosition, color, arrowWidth, 0)
      this.drawHighlight(targetPosition, color, highlightAlpha, 0)

      this.container.visible = true
      this.animationTime = 0
      this.animationPhase = 'fade_in'

      const animateFrame = (ticker: Ticker) => this.animate(
        ticker,
        voterPosition,
        targetPosition,
        color,
        arrowWidth,
        highlightAlpha
      )

      if (this.animationTicker) {
        this.animationTicker.stop()
        this.animationTicker.destroy()
      }

      this.animationTicker = new Ticker()
      this.animationTicker.add(animateFrame)
      this.animationTicker.start()
    })
  }

  private animate(
    ticker: Ticker,
    voterPos: SlotPosition,
    targetPos: SlotPosition,
    color: number,
    arrowWidth: number,
    highlightAlpha: number
  ): void {
    this.animationTime += ticker.deltaMS

    switch (this.animationPhase) {
      case 'fade_in':
        this.animateFadeIn(voterPos, targetPos, color, arrowWidth, highlightAlpha)
        break
      case 'hold':
        this.animateHold()
        break
      case 'fade_out':
        this.animateFadeOut(voterPos, targetPos, color, arrowWidth, highlightAlpha)
        break
    }
  }

  private animateFadeIn(
    voterPos: SlotPosition,
    targetPos: SlotPosition,
    color: number,
    arrowWidth: number,
    highlightAlpha: number
  ): void {
    const progress = Math.min(this.animationTime / this.fadeInDuration, 1)
    const eased = this.easeOutCubic(progress)

    this.drawArrow(voterPos, targetPos, color, arrowWidth, eased)
    this.drawHighlight(targetPos, color, highlightAlpha, eased)

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

  private animateFadeOut(
    voterPos: SlotPosition,
    targetPos: SlotPosition,
    color: number,
    arrowWidth: number,
    highlightAlpha: number
  ): void {
    const progress = Math.min(this.animationTime / this.fadeOutDuration, 1)
    const eased = this.easeInCubic(progress)
    const alpha = 1 - eased

    this.drawArrow(voterPos, targetPos, color, arrowWidth, alpha)
    this.drawHighlight(targetPos, color, highlightAlpha, alpha)

    if (progress >= 1) {
      this.finishAnimation()
    }
  }

  private drawArrow(
    from: SlotPosition,
    to: SlotPosition,
    color: number,
    width: number,
    alpha: number
  ): void {
    this.arrowGraphics.clear()

    if (alpha <= 0) return

    const dx = to.x - from.x
    const dy = to.y - from.y
    const length = Math.sqrt(dx * dx + dy * dy)

    if (length < 1) return

    const unitX = dx / length
    const unitY = dy / length

    const perpX = -unitY
    const perpY = unitX

    const endX = to.x - unitX * HIGHLIGHT_RADIUS
    const endY = to.y - unitY * HIGHLIGHT_RADIUS

    const startX = from.x + unitX * 60
    const startY = from.y + unitY * 60

    this.arrowGraphics.moveTo(startX, startY)
    this.arrowGraphics.lineTo(endX, endY)
    this.arrowGraphics.stroke({ color, width, alpha })

    const arrowTipX = endX
    const arrowTipY = endY
    const arrowBackX = endX - unitX * ARROW_HEAD_LENGTH
    const arrowBackY = endY - unitY * ARROW_HEAD_LENGTH

    const arrowLeft = {
      x: arrowBackX + perpX * ARROW_HEAD_WIDTH / 2,
      y: arrowBackY + perpY * ARROW_HEAD_WIDTH / 2,
    }
    const arrowRight = {
      x: arrowBackX - perpX * ARROW_HEAD_WIDTH / 2,
      y: arrowBackY - perpY * ARROW_HEAD_WIDTH / 2,
    }

    this.arrowGraphics.moveTo(arrowTipX, arrowTipY)
    this.arrowGraphics.lineTo(arrowLeft.x, arrowLeft.y)
    this.arrowGraphics.lineTo(arrowRight.x, arrowRight.y)
    this.arrowGraphics.closePath()
    this.arrowGraphics.fill({ color, alpha })
  }

  private drawHighlight(
    position: SlotPosition,
    color: number,
    baseAlpha: number,
    animAlpha: number
  ): void {
    this.highlightGraphics.clear()

    const alpha = baseAlpha * animAlpha
    if (alpha <= 0) return

    this.highlightGraphics.circle(position.x, position.y, HIGHLIGHT_RADIUS)
    this.highlightGraphics.fill({ color, alpha })

    this.highlightGraphics.circle(position.x, position.y, HIGHLIGHT_RADIUS + 10)
    this.highlightGraphics.stroke({ color, width: 3, alpha: alpha * 0.5 })
  }

  private finishAnimation(): void {
    if (this.animationTicker) {
      this.animationTicker.stop()
      this.animationTicker.destroy()
      this.animationTicker = null
    }

    this.container.visible = false
    this.arrowGraphics.clear()
    this.highlightGraphics.clear()

    if (this.animationResolve) {
      this.animationResolve()
      this.animationResolve = null
    }
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
