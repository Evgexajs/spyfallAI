# Asset Generator

CLI-утилита для генерации картинок персонажей SpyfallAI через OpenAI Image API. Использует reference image для поддержания единого стиля между персонажами.

## Установка

1. Установить зависимости:
```bash
pip install -r requirements.txt
```

2. Создать файл `.env` с API-ключом:
```bash
echo "OPENAI_API_KEY=sk-your-key-here" > .env
```

## Тестирование

### 1. Подготовка reference image

Положить эталон стиля в `reference/style_reference.png`. Это первый сгенерированный персонаж, от которого наследуется стиль всех остальных.

### 2. Проверка промпта (dry-run)

```bash
python generate_assets.py --character boris_molot --dry-run
```

Выводит финальный промпт и параметры без вызова API.

### 3. Генерация персонажа

```bash
python generate_assets.py --character boris_molot
```

Результат: `output/characters/boris_molot.png`
Лог: `output/logs/{timestamp}_boris_molot.json`

### 4. Сравнение стиля

Сравнить `output/characters/boris_molot.png` с `reference/style_reference.png` — стиль должен совпадать.

### 5. Генерация второго персонажа

```bash
python generate_assets.py --character aurora
```

### 6. Проверка ансамбля

Сравнить Бориса и Аврору — должны выглядеть как персонажи одного шоу.

### 7. Режимы генерации

Гарантированный reference (без fallback):
```bash
python generate_assets.py --character boris_molot --approach reference
```

Без reference (для сравнения):
```bash
python generate_assets.py --character boris_molot --approach text-only
```

Генерация всех персонажей:
```bash
python generate_assets.py --all-characters
```

## Если стиль не держится

Проверить логи в `output/logs/`:
- `approach` — фактически использованный режим (`reference` или `text_only`)
- `requested_approach` — запрошенный режим из CLI
- `fallback_trigger` — причина fallback, если он был

Если в логе `approach: "text_only"` при `requested_approach: "auto"` — значит сработал fallback. Причина в поле `fallback_trigger`.

## CLI параметры

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `--character ID` | Генерация одного персонажа | — |
| `--all-characters` | Генерация всех персонажей | — |
| `--model NAME` | Модель OpenAI | `gpt-image-2` |
| `--approach MODE` | `auto`, `reference`, `text-only` | `auto` |
| `--regenerate` | Перезаписать существующие | `false` |
| `--dry-run` | Только показать промпт | `false` |
