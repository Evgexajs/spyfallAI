/**
 * Phase visual styles configuration
 * Based on PRD section 6.6 - visual temperature changes by phase
 */

import { Phase } from '@parser/types'

/**
 * Color adjustment values for ColorMatrixFilter
 * These control the visual temperature/mood of the scene
 */
export interface PhaseStyle {
  brightness: number      // -1 to 1, 0 = normal
  contrast: number        // -1 to 1, 0 = normal
  saturation: number      // -1 to 1, 0 = normal
  hue: number             // rotation in degrees, 0 = normal
  tint: number            // overlay tint color (hex)
  tintAlpha: number       // overlay tint alpha (0-1)
}

/**
 * Phase styles configuration
 *
 * main_round: neutral, warm feel
 * voting: cold blue tint (tension)
 * defense: slightly warm, orange hint (urgency)
 * final: high contrast, dramatic (climax)
 * resolution: desaturated, calm (conclusion)
 */
export const PHASE_STYLES: Record<Phase, PhaseStyle> = {
  [Phase.MainRound]: {
    brightness: 0,
    contrast: 0,
    saturation: 0,
    hue: 0,
    tint: 0x000000,
    tintAlpha: 0,
  },

  [Phase.Voting]: {
    brightness: -0.05,
    contrast: 0.1,
    saturation: -0.1,
    hue: -10,
    tint: 0x3366cc,
    tintAlpha: 0.12,
  },

  [Phase.Defense]: {
    brightness: 0,
    contrast: 0.05,
    saturation: 0.1,
    hue: 10,
    tint: 0xff9933,
    tintAlpha: 0.08,
  },

  [Phase.Final]: {
    brightness: 0.05,
    contrast: 0.2,
    saturation: 0.15,
    hue: 0,
    tint: 0xff3333,
    tintAlpha: 0.1,
  },

  [Phase.Resolution]: {
    brightness: -0.02,
    contrast: 0,
    saturation: -0.2,
    hue: 0,
    tint: 0x000000,
    tintAlpha: 0.05,
  },
}

export function getPhaseStyle(phase: Phase): PhaseStyle {
  return PHASE_STYLES[phase]
}
