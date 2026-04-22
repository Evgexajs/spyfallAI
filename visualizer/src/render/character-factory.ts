import type { CharacterRenderer } from './character-renderer'
import { PlaceholderCharacterRenderer } from './placeholder-character'

// Future: replace PlaceholderCharacterRenderer with SpriteCharacterRenderer
// when character images are available. Only this factory needs to change —
// Scene and other layers use CharacterRenderer interface.

export function createCharacterRenderer(
  characterId: string,
  displayName: string
): CharacterRenderer {
  return new PlaceholderCharacterRenderer(characterId, displayName)
}
