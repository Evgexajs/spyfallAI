/**
 * JSON schema validation for GameData
 * TASK-008: Basic validation of required fields and structure
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
    }
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
}
