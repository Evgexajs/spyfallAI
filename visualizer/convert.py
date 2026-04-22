#!/usr/bin/env python3
"""
Конвертер из формата SpyfallAI в формат визуализатора.
Использование: python convert.py <input.json> [output.json]
"""
import json
import sys
from pathlib import Path

# Пути к данным SpyfallAI
SPYFALL_ROOT = Path(__file__).parent.parent
CHARACTERS_DIR = SPYFALL_ROOT / "characters"
LOCATIONS_FILE = SPYFALL_ROOT / "locations.json"


def load_characters() -> dict[str, dict]:
    """Загрузить все профили персонажей."""
    chars = {}
    for f in CHARACTERS_DIR.glob("*.json"):
        with open(f) as fp:
            data = json.load(fp)
            chars[data["id"]] = data
    return chars


def load_locations() -> dict[str, dict]:
    """Загрузить все локации."""
    with open(LOCATIONS_FILE) as fp:
        data = json.load(fp)
    return {loc["id"]: loc for loc in data}


def convert(game: dict, characters: dict, locations: dict) -> dict:
    """Конвертировать игру SpyfallAI в формат визуализатора."""
    location = locations.get(game["location_id"], {})

    # Персонажи
    chars = []
    for i, player in enumerate(game["players"]):
        char_id = player["character_id"]
        char_data = characters.get(char_id, {})
        chars.append({
            "id": char_id,
            "display_name": char_data.get("display_name", char_id),
            "position_hint": i
        })

    timeline = []

    # phase_change: main_round
    timeline.append({
        "type": "phase_change",
        "phase": "main_round",
        "label": "Основной раунд"
    })

    # Реплики из turns
    for turn in game.get("turns", []):
        speaker_id = turn["speaker_id"]
        addressee_id = turn.get("addressee_id")

        # "all" -> null (обращение ко всем)
        if addressee_id == "all":
            addressee_id = None

        # Системные сообщения
        if speaker_id == "system":
            timeline.append({
                "type": "system_message",
                "content": turn["content"]
            })
        else:
            timeline.append({
                "type": "speech",
                "speaker_id": speaker_id,
                "addressee_id": addressee_id,
                "content": turn["content"],
                "subtype": "normal"
            })

    # Preliminary votes
    prelim_votes = game.get("preliminary_vote_result", {})
    if prelim_votes:
        timeline.append({
            "type": "phase_change",
            "phase": "voting",
            "label": "Голосование"
        })
        for voter_id, target_id in prelim_votes.items():
            timeline.append({
                "type": "vote",
                "phase": "preliminary",
                "voter_id": voter_id,
                "target_id": target_id,
                "comment": None
            })

    # Defense speeches
    defense_speeches = game.get("defense_speeches", [])
    if defense_speeches:
        timeline.append({
            "type": "phase_change",
            "phase": "defense",
            "label": "Защитные речи"
        })
        for speech in defense_speeches:
            timeline.append({
                "type": "speech",
                "speaker_id": speech["defender_id"],
                "addressee_id": None,
                "content": speech["content"],
                "subtype": "defense"
            })

    # Final votes
    final_votes = game.get("final_vote_result")
    if final_votes:
        timeline.append({
            "type": "phase_change",
            "phase": "final",
            "label": "Финальное голосование"
        })
        for voter_id, target_id in final_votes.items():
            timeline.append({
                "type": "vote",
                "phase": "final",
                "voter_id": voter_id,
                "target_id": target_id,
                "comment": None
            })

    # Spy guess
    outcome = game.get("outcome", {})
    if outcome.get("spy_guess"):
        guessed_loc = locations.get(outcome["spy_guess"], {})
        timeline.append({
            "type": "spy_guess",
            "spy_id": game["spy_id"],
            "guessed_location_id": outcome["spy_guess"],
            "guessed_location_name": guessed_loc.get("display_name", outcome["spy_guess"]),
            "correct": outcome.get("spy_guess_correct", False)
        })

    # Outcome
    timeline.append({
        "type": "phase_change",
        "phase": "resolution",
        "label": "Итоги"
    })
    timeline.append({
        "type": "outcome",
        "winner": outcome.get("winner", "civilians"),
        "spy_id": game["spy_id"],
        "reason": outcome.get("reason", "Игра завершена")
    })

    return {
        "version": "1.0",
        "metadata": {
            "game_id": game["id"],
            "title": f"Партия в {location.get('display_name', game['location_id'])}"
        },
        "scene": {
            "location_id": game["location_id"],
            "location_name": location.get("display_name", game["location_id"])
        },
        "characters": chars,
        "timeline": timeline
    }


def main():
    if len(sys.argv) < 2:
        print("Использование: python convert.py <input.json> [output.json]")
        sys.exit(1)

    input_path = Path(sys.argv[1])

    if len(sys.argv) > 2:
        output_path = Path(sys.argv[2])
    else:
        # По умолчанию сохраняем в visualizer/games/
        output_dir = Path(__file__).parent / "games"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / f"{input_path.stem}.json"

    with open(input_path) as fp:
        game = json.load(fp)

    characters = load_characters()
    locations = load_locations()

    result = convert(game, characters, locations)

    with open(output_path, "w") as fp:
        json.dump(result, fp, ensure_ascii=False, indent=2)

    print(f"Конвертировано: {output_path}")


if __name__ == "__main__":
    main()
