import { Application, Container, Graphics, ColorMatrixFilter } from 'pixi.js'
import type { Character, SpeechEvent, PhaseChangeEvent, SystemMessageEvent, SpyGuessEvent, OutcomeEvent } from '@parser/types'
import { Phase, VotePhase, SpeechSubtype } from '@parser/types'
import type { CharacterRenderer } from './character-renderer'
import { createCharacterRenderer } from './character-factory'
import { getSlotMap, type SlotPosition } from '@config/slots'
import { getPhaseStyle } from '@config/phase-styles'
import { SpeechBubble } from './speech-bubble'
import { VoteIndicator } from './vote-indicator'
import { PhaseOverlay } from './phase-overlay'
import { SystemMessage } from './system-message'
import { SpyGuessOverlay } from './spy-guess'
import { OutcomeOverlay } from './outcome'
import {
  TYPING_SPEED_MS_PER_CHAR,
} from '@config/timings'
import {
  calculateTypingIndicatorDuration,
  calculateHoldDuration,
} from '@player/timing'
import type { EventPlayer } from '@player/event-player'

const CHARACTER_RADIUS = 60
const BUBBLE_OFFSET_Y = 15
const SCENE_WIDTH = 1920
const SCENE_HEIGHT = 1080

export class Scene {
  private app: Application
  private characterContainer: Container
  private bubbleContainer: Container
  private voteIndicatorContainer: Container
  private overlayContainer: Container
  private renderers: Map<string, CharacterRenderer> = new Map()
  private characterPositions: Map<string, SlotPosition> = new Map()
  private characterNames: Map<string, string> = new Map()
  private currentBubble: SpeechBubble | null = null
  private voteIndicator: VoteIndicator
  private phaseOverlay: PhaseOverlay
  private systemMessage: SystemMessage
  private spyGuessOverlay: SpyGuessOverlay
  private outcomeOverlay: OutcomeOverlay
  private phaseFilter: ColorMatrixFilter
  private phaseTintOverlay: Graphics
  private currentPhase: Phase = Phase.MainRound

  constructor(app: Application) {
    this.app = app

    this.phaseFilter = new ColorMatrixFilter()
    this.app.stage.filters = [this.phaseFilter]

    this.phaseTintOverlay = new Graphics()
    this.phaseTintOverlay.label = 'phase-tint'
    this.app.stage.addChild(this.phaseTintOverlay)

    this.characterContainer = new Container()
    this.characterContainer.label = 'characters'
    this.app.stage.addChild(this.characterContainer)

    this.bubbleContainer = new Container()
    this.bubbleContainer.label = 'speech-bubbles'
    this.app.stage.addChild(this.bubbleContainer)

    this.voteIndicatorContainer = new Container()
    this.voteIndicatorContainer.label = 'vote-indicators'
    this.app.stage.addChild(this.voteIndicatorContainer)

    this.voteIndicator = new VoteIndicator()
    this.voteIndicatorContainer.addChild(this.voteIndicator.getContainer())

    this.overlayContainer = new Container()
    this.overlayContainer.label = 'overlays'
    this.app.stage.addChild(this.overlayContainer)

    this.phaseOverlay = new PhaseOverlay()
    this.overlayContainer.addChild(this.phaseOverlay.getContainer())

    this.systemMessage = new SystemMessage()
    this.overlayContainer.addChild(this.systemMessage.getContainer())

    this.spyGuessOverlay = new SpyGuessOverlay()
    this.overlayContainer.addChild(this.spyGuessOverlay.getContainer())

    this.outcomeOverlay = new OutcomeOverlay()
    this.overlayContainer.addChild(this.outcomeOverlay.getContainer())

    this.applyPhaseStyle(Phase.MainRound)
  }

  placeCharacters(characters: Character[]): void {
    this.clearCharacters()

    const positions = this.resolvePositions(characters)

    for (let i = 0; i < characters.length; i++) {
      const character = characters[i]!
      const position = positions[i]!

      const renderer = createCharacterRenderer(character.id, character.display_name)
      renderer.render(position)
      this.characterContainer.addChild(renderer.getContainer())
      this.renderers.set(character.id, renderer)
      this.characterPositions.set(character.id, position)
      this.characterNames.set(character.id, character.display_name)
    }
  }

  showSpeechBubble(characterId: string): SpeechBubble | null {
    const position = this.characterPositions.get(characterId)
    if (!position) {
      return null
    }

    this.hideSpeechBubble()

    const bubble = new SpeechBubble()
    this.bubbleContainer.addChild(bubble.getContainer())

    const bubblePosition = {
      x: position.x,
      y: position.y - CHARACTER_RADIUS - BUBBLE_OFFSET_Y
    }
    bubble.show(bubblePosition)

    this.currentBubble = bubble
    return bubble
  }

  hideSpeechBubble(): void {
    if (this.currentBubble) {
      this.currentBubble.hide()
      this.bubbleContainer.removeChild(this.currentBubble.getContainer())
      this.currentBubble.destroy()
      this.currentBubble = null
    }
  }

  async showVote(
    voterId: string,
    targetId: string,
    phase: VotePhase,
    comment?: string | null
  ): Promise<void> {
    const voterPosition = this.characterPositions.get(voterId)
    const targetPosition = this.characterPositions.get(targetId)

    if (!voterPosition || !targetPosition) {
      return
    }

    if (comment) {
      const bubble = this.showSpeechBubble(voterId)
      if (bubble) {
        bubble.setStyle(SpeechSubtype.Normal)
        bubble.showTypingIndicator()

        const indicatorDuration = calculateTypingIndicatorDuration(comment.length)
        await this.delay(indicatorDuration)

        await bubble.typeText(comment, TYPING_SPEED_MS_PER_CHAR)

        const holdDuration = calculateHoldDuration(comment.length)
        await this.delay(holdDuration)

        this.hideSpeechBubble()
      }
    }

    await this.voteIndicator.showVote(voterPosition, targetPosition, phase)
  }

  getVoteIndicator(): VoteIndicator {
    return this.voteIndicator
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms))
  }

  getCharacterRenderer(characterId: string): CharacterRenderer | undefined {
    return this.renderers.get(characterId)
  }

  getCharacterPosition(characterId: string): SlotPosition | null {
    return this.characterPositions.get(characterId) ?? null
  }

  getCharacterName(characterId: string): string | null {
    return this.characterNames.get(characterId) ?? null
  }

  async renderSpeech(event: SpeechEvent, eventPlayer: EventPlayer): Promise<void> {
    const renderer = this.renderers.get(event.speaker_id)
    if (renderer) {
      renderer.setState('speaking')
    }

    const bubble = this.showSpeechBubble(event.speaker_id)
    if (!bubble) {
      return
    }

    bubble.setStyle(event.subtype)
    bubble.showTypingIndicator()

    const indicatorDuration = calculateTypingIndicatorDuration(event.content.length)
    await this.pausableDelay(indicatorDuration, eventPlayer)

    bubble.hideTypingIndicator()
    bubble.isPaused = eventPlayer.isPaused

    const linkPauseState = () => {
      bubble.isPaused = eventPlayer.isPaused
    }

    const intervalId = setInterval(linkPauseState, 16)

    await bubble.typeText(event.content, TYPING_SPEED_MS_PER_CHAR / eventPlayer.speed)

    clearInterval(intervalId)

    const holdDuration = calculateHoldDuration(event.content.length)
    await this.pausableDelay(holdDuration, eventPlayer)

    this.hideSpeechBubble()

    if (renderer) {
      renderer.setState('idle')
    }
  }

  async renderPhaseChange(event: PhaseChangeEvent): Promise<void> {
    await this.phaseOverlay.showPhaseChange(event.phase, event.label)
    this.setPhase(event.phase)
  }

  async renderSystemMessage(event: SystemMessageEvent): Promise<void> {
    await this.systemMessage.show(event.content)
  }

  async renderSpyGuess(event: SpyGuessEvent): Promise<void> {
    const position = this.characterPositions.get(event.spy_id)
    if (!position) {
      return
    }

    await this.spyGuessOverlay.show(position, event.guessed_location_name, event.correct)
  }

  renderOutcome(event: OutcomeEvent): void {
    const position = this.characterPositions.get(event.spy_id) ?? null
    const spyName = this.characterNames.get(event.spy_id) ?? 'Неизвестный'

    this.outcomeOverlay.show(event.winner, position, spyName, event.reason)
  }

  hideAllOverlays(): void {
    this.hideSpeechBubble()
    this.phaseOverlay.hide()
    this.systemMessage.hide()
    this.spyGuessOverlay.hide()
    this.outcomeOverlay.hide()
    this.voteIndicator.hide()

    for (const renderer of this.renderers.values()) {
      renderer.setState('idle')
    }
  }

  private async pausableDelay(ms: number, eventPlayer: EventPlayer): Promise<void> {
    const startTime = Date.now()
    let elapsed = 0

    while (elapsed < ms) {
      if (eventPlayer.isStopped) {
        return
      }

      if (eventPlayer.isPaused) {
        await new Promise(resolve => setTimeout(resolve, 50))
        continue
      }

      const remaining = ms - elapsed
      const chunk = Math.min(remaining, 50)
      await new Promise(resolve => setTimeout(resolve, chunk))
      elapsed = Date.now() - startTime
    }
  }

  setPhase(phase: Phase): void {
    if (this.currentPhase === phase) return
    this.currentPhase = phase
    this.applyPhaseStyle(phase)
  }

  resetPhase(): void {
    this.setPhase(Phase.MainRound)
  }

  getCurrentPhase(): Phase {
    return this.currentPhase
  }

  private applyPhaseStyle(phase: Phase): void {
    const style = getPhaseStyle(phase)

    this.phaseFilter.reset()

    if (style.brightness !== 0) {
      this.phaseFilter.brightness(1 + style.brightness, false)
    }
    if (style.contrast !== 0) {
      this.phaseFilter.contrast(1 + style.contrast, false)
    }
    if (style.saturation !== 0) {
      this.phaseFilter.saturate(style.saturation, false)
    }
    if (style.hue !== 0) {
      this.phaseFilter.hue(style.hue, false)
    }

    this.phaseTintOverlay.clear()
    if (style.tintAlpha > 0) {
      this.phaseTintOverlay.rect(0, 0, SCENE_WIDTH, SCENE_HEIGHT)
      this.phaseTintOverlay.fill({ color: style.tint, alpha: style.tintAlpha })
    }
  }

  private resolvePositions(characters: Character[]): SlotPosition[] {
    const count = characters.length
    const slotMap = getSlotMap(count)

    if (!slotMap) {
      return this.fallbackPositions(count)
    }

    const positions: SlotPosition[] = new Array(count)
    const usedSlots = new Set<number>()
    const unassigned: number[] = []

    for (let i = 0; i < characters.length; i++) {
      const hint = characters[i]?.position_hint

      if (
        hint === undefined ||
        hint === null ||
        hint < 0 ||
        hint >= count ||
        usedSlots.has(hint)
      ) {
        unassigned.push(i)
      } else {
        usedSlots.add(hint)
        positions[i] = slotMap[hint]!
      }
    }

    const availableSlots = []
    for (let slot = 0; slot < count; slot++) {
      if (!usedSlots.has(slot)) {
        availableSlots.push(slot)
      }
    }

    for (let j = 0; j < unassigned.length; j++) {
      const charIndex = unassigned[j]!
      const slot = availableSlots[j]!
      positions[charIndex] = slotMap[slot]!
    }

    return positions
  }

  private fallbackPositions(count: number): SlotPosition[] {
    const positions: SlotPosition[] = []
    const spacing = 1920 / (count + 1)

    for (let i = 0; i < count; i++) {
      positions.push({
        x: spacing * (i + 1),
        y: 700,
      })
    }

    return positions
  }

  private clearCharacters(): void {
    this.hideSpeechBubble()
    for (const renderer of this.renderers.values()) {
      renderer.destroy()
    }
    this.renderers.clear()
    this.characterPositions.clear()
    this.characterNames.clear()
    this.characterContainer.removeChildren()
  }

  destroy(): void {
    this.clearCharacters()
    this.voteIndicator.destroy()
    this.phaseOverlay.destroy()
    this.systemMessage.destroy()
    this.spyGuessOverlay.destroy()
    this.outcomeOverlay.destroy()
    this.app.stage.filters = []
    this.phaseFilter.destroy()
    this.app.stage.removeChild(this.phaseTintOverlay)
    this.phaseTintOverlay.destroy()
    this.app.stage.removeChild(this.characterContainer)
    this.app.stage.removeChild(this.bubbleContainer)
    this.app.stage.removeChild(this.voteIndicatorContainer)
    this.app.stage.removeChild(this.overlayContainer)
  }
}
