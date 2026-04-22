/**
 * JSON schema validation for GameData
 * TASK-008: Basic validation of required fields and structure
 * TASK-009: Enum value validation for timeline events
 * TASK-010: Referential integrity validation for character IDs
 * TASK-011: Validation that outcome event is last in timeline
 */

export interface ValidationResult {
  isValid: boolean;
  errors: string[];
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isString(value: unknown): value is string {
  return typeof value === 'string';
}

function isArray(value: unknown): value is unknown[] {
  return Array.isArray(value);
}

const VALID_EVENT_TYPES = ['speech', 'phase_change', 'system_message', 'vote', 'spy_guess', 'outcome'] as const;
const VALID_SPEECH_SUBTYPES = ['normal', 'defense', 'post_guess'] as const;
const VALID_PHASES = ['main_round', 'voting', 'defense', 'final', 'resolution'] as const;
const VALID_VOTE_PHASES = ['preliminary', 'final'] as const;
const VALID_WINNERS = ['spy', 'civilians'] as const;

function validateTimelineEvents(timeline: unknown[], errors: string[]): void {
  timeline.forEach((event, index) => {
    if (!isObject(event)) {
      errors.push(`timeline[${index}] must be an object`);
      return;
    }

    if (!('type' in event) || !isString(event.type)) {
      errors.push(`timeline[${index}].type is missing or not a string`);
      return;
    }

    const eventType = event.type;

    if (!VALID_EVENT_TYPES.includes(eventType as typeof VALID_EVENT_TYPES[number])) {
      errors.push(`timeline[${index}].type has invalid value '${eventType}'. Expected one of: ${VALID_EVENT_TYPES.join(', ')}`);
      return;
    }

    switch (eventType) {
      case 'speech':
        if (!('subtype' in event) || !isString(event.subtype)) {
          errors.push(`timeline[${index}] (speech): subtype is missing or not a string`);
        } else if (!VALID_SPEECH_SUBTYPES.includes(event.subtype as typeof VALID_SPEECH_SUBTYPES[number])) {
          errors.push(`timeline[${index}] (speech): subtype has invalid value '${event.subtype}'. Expected one of: ${VALID_SPEECH_SUBTYPES.join(', ')}`);
        }
        break;

      case 'phase_change':
        if (!('phase' in event) || !isString(event.phase)) {
          errors.push(`timeline[${index}] (phase_change): phase is missing or not a string`);
        } else if (!VALID_PHASES.includes(event.phase as typeof VALID_PHASES[number])) {
          errors.push(`timeline[${index}] (phase_change): phase has invalid value '${event.phase}'. Expected one of: ${VALID_PHASES.join(', ')}`);
        }
        break;

      case 'vote':
        if (!('phase' in event) || !isString(event.phase)) {
          errors.push(`timeline[${index}] (vote): phase is missing or not a string`);
        } else if (!VALID_VOTE_PHASES.includes(event.phase as typeof VALID_VOTE_PHASES[number])) {
          errors.push(`timeline[${index}] (vote): phase has invalid value '${event.phase}'. Expected one of: ${VALID_VOTE_PHASES.join(', ')}`);
        }
        break;

      case 'outcome':
        if (!('winner' in event) || !isString(event.winner)) {
          errors.push(`timeline[${index}] (outcome): winner is missing or not a string`);
        } else if (!VALID_WINNERS.includes(event.winner as typeof VALID_WINNERS[number])) {
          errors.push(`timeline[${index}] (outcome): winner has invalid value '${event.winner}'. Expected one of: ${VALID_WINNERS.join(', ')}`);
        }
        break;
    }
  });
}

function validateReferentialIntegrity(
  characters: unknown[],
  timeline: unknown[],
  errors: string[]
): void {
  const characterIds = new Set<string>();
  characters.forEach((char) => {
    if (isObject(char) && 'id' in char && isString(char.id)) {
      characterIds.add(char.id);
    }
  });

  if (characterIds.size === 0) {
    return;
  }

  timeline.forEach((event, index) => {
    if (!isObject(event) || !('type' in event) || !isString(event.type)) {
      return;
    }

    const eventType = event.type;

    switch (eventType) {
      case 'speech': {
        if ('speaker_id' in event && isString(event.speaker_id)) {
          if (!characterIds.has(event.speaker_id)) {
            errors.push(
              `timeline[${index}] (speech): speaker_id '${event.speaker_id}' does not exist in characters`
            );
          }
        }
        if ('addressee_id' in event && event.addressee_id !== null) {
          if (isString(event.addressee_id) && !characterIds.has(event.addressee_id)) {
            errors.push(
              `timeline[${index}] (speech): addressee_id '${event.addressee_id}' does not exist in characters`
            );
          }
        }
        break;
      }

      case 'vote': {
        if ('voter_id' in event && isString(event.voter_id)) {
          if (!characterIds.has(event.voter_id)) {
            errors.push(
              `timeline[${index}] (vote): voter_id '${event.voter_id}' does not exist in characters`
            );
          }
        }
        if ('target_id' in event && isString(event.target_id)) {
          if (!characterIds.has(event.target_id)) {
            errors.push(
              `timeline[${index}] (vote): target_id '${event.target_id}' does not exist in characters`
            );
          }
        }
        break;
      }

      case 'spy_guess': {
        if ('spy_id' in event && isString(event.spy_id)) {
          if (!characterIds.has(event.spy_id)) {
            errors.push(
              `timeline[${index}] (spy_guess): spy_id '${event.spy_id}' does not exist in characters`
            );
          }
        }
        break;
      }

      case 'outcome': {
        if ('spy_id' in event && isString(event.spy_id)) {
          if (!characterIds.has(event.spy_id)) {
            errors.push(
              `timeline[${index}] (outcome): spy_id '${event.spy_id}' does not exist in characters`
            );
          }
        }
        break;
      }
    }
  });
}

function validateOutcomePosition(timeline: unknown[], errors: string[]): void {
  const outcomeIndices: number[] = [];

  timeline.forEach((event, index) => {
    if (isObject(event) && 'type' in event && event.type === 'outcome') {
      outcomeIndices.push(index);
    }
  });

  if (outcomeIndices.length === 0) {
    return;
  }

  const lastIndex = timeline.length - 1;
  outcomeIndices.forEach((outcomeIndex) => {
    if (outcomeIndex !== lastIndex) {
      errors.push(
        `timeline[${outcomeIndex}] (outcome): outcome event must be the last event in timeline, but found at index ${outcomeIndex} (last index is ${lastIndex})`
      );
    }
  });
}

export function validateGameData(json: unknown): ValidationResult {
  const errors: string[] = [];

  if (!isObject(json)) {
    errors.push('Input must be an object');
    return { isValid: false, errors };
  }

  if (!('version' in json) || !isString(json.version)) {
    errors.push('Missing or invalid required field: version (string expected)');
  }

  if (!('metadata' in json) || !isObject(json.metadata)) {
    errors.push('Missing or invalid required field: metadata (object expected)');
  } else {
    if (!('game_id' in json.metadata) || !isString(json.metadata.game_id)) {
      errors.push('Missing or invalid required field: metadata.game_id (string expected)');
    }
  }

  if (!('scene' in json) || !isObject(json.scene)) {
    errors.push('Missing or invalid required field: scene (object expected)');
  } else {
    if (!('location_id' in json.scene) || !isString(json.scene.location_id)) {
      errors.push('Missing or invalid required field: scene.location_id (string expected)');
    }
    if (!('location_name' in json.scene) || !isString(json.scene.location_name)) {
      errors.push('Missing or invalid required field: scene.location_name (string expected)');
    }
  }

  if (!('characters' in json) || !isArray(json.characters)) {
    errors.push('Missing or invalid required field: characters (array expected)');
  } else {
    const chars = json.characters;
    if (chars.length === 0) {
      errors.push('characters array must not be empty (minimum 2 characters required)');
    } else if (chars.length < 2) {
      errors.push(`characters array has ${chars.length} element(s), minimum 2 required`);
    } else if (chars.length > 8) {
      errors.push(`characters array has ${chars.length} elements, maximum 8 allowed`);
    } else {
      chars.forEach((char, index) => {
        if (!isObject(char)) {
          errors.push(`characters[${index}] must be an object`);
        } else {
          if (!('id' in char) || !isString(char.id)) {
            errors.push(`characters[${index}].id is missing or not a string`);
          }
          if (!('display_name' in char) || !isString(char.display_name)) {
            errors.push(`characters[${index}].display_name is missing or not a string`);
          }
        }
      });
    }
  }

  if (!('timeline' in json) || !isArray(json.timeline)) {
    errors.push('Missing or invalid required field: timeline (array expected)');
  } else {
    if (json.timeline.length === 0) {
      errors.push('timeline array must not be empty');
    } else {
      validateTimelineEvents(json.timeline, errors);
    }
  }

  if (isArray(json.characters) && isArray(json.timeline)) {
    validateReferentialIntegrity(json.characters, json.timeline, errors);
  }

  if (isArray(json.timeline) && json.timeline.length > 0) {
    validateOutcomePosition(json.timeline, errors);
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
}
