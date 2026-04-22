/**
 * JSON parser for GameData
 * TASK-012: Parses JSON string into typed GameData objects
 */

import { GameData } from './types';
import { validateGameData } from './validator';

export interface ParseResult {
  data: GameData | null;
  errors: string[];
}

export function parseGameData(json: string): ParseResult {
  let parsed: unknown;

  try {
    parsed = JSON.parse(json);
  } catch (e) {
    const errorMessage = e instanceof Error ? e.message : 'Unknown parsing error';
    return {
      data: null,
      errors: [`JSON parsing error: ${errorMessage}`],
    };
  }

  const validationResult = validateGameData(parsed);

  if (!validationResult.isValid) {
    return {
      data: null,
      errors: validationResult.errors,
    };
  }

  return {
    data: parsed as GameData,
    errors: [],
  };
}
