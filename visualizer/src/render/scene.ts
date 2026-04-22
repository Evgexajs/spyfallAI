import { Application, Container, Graphics, ColorMatrixFilter } from 'pixi.js'
import type { Character } from '@parser/types'
import { Phase } from '@parser/types'
import type { CharacterRenderer } from './character-renderer'
import { createCharacterRenderer } from './character-factory'
import { getSlotMap, type SlotPosition } from '@config/slots'
import { getPhaseStyle } from '@config/phase-styles'
import { SpeechBubble } from './speech-bubble'

const CHARACTER_RADIUS = 60
const BUBBLE_OFFSET_Y = 15
const SCENE_WIDTH = 1920
const SCENE_HEIGHT = 1080

export class Scene {
  private app: Application
  private characterContainer: Container
  private bubbleContainer: Container
  private renderers: Map<string, CharacterRenderer> = new Map()
  private characterPositions: Map<string, SlotPosition> = new Map()
  private currentBubble: SpeechBubble | null = null
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

  getCharacterRenderer(characterId: string): CharacterRenderer | undefined {
    return this.renderers.get(characterId)
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
    this.characterContainer.removeChildren()
  }

  destroy(): void {
    this.clearCharacters()
    this.app.stage.filters = []
    this.phaseFilter.destroy()
    this.app.stage.removeChild(this.phaseTintOverlay)
    this.phaseTintOverlay.destroy()
    this.app.stage.removeChild(this.characterContainer)
    this.app.stage.removeChild(this.bubbleContainer)
  }
}
