import { Container } from 'pixi.js'

export type CharacterState = 'idle' | 'speaking'

export interface Position {
  x: number
  y: number
}

export interface CharacterRenderer {
  render(position: Position): void
  setState(state: CharacterState): void
  getContainer(): Container
  destroy(): void
}
