# Asset Generator

CLI-утилита для генерации картинок персонажей SpyfallAI через OpenAI Image API. Использует reference image для поддержания единого стиля между персонажами.

Текущая версия работает только с персонажами. Asset-конфиг `tools/asset-generator/config/characters.json` содержит все 8 персонажей; он был составлен на основе корневых профилей `characters/*.json` и дополнен визуальными описаниями для генерации. Генерация локаций была вынесена из MVP asset-generator и должна добавляться отдельной задачей с отдельным конфигом и шаблоном промпта.

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

### 0. Ручная генерация через веб-интерфейс

Если API-модель недоступна или результат удобнее отбирать руками, экспортировать готовые промпты в Markdown:

```bash
python3 generate_assets.py --all-characters --export-prompts output/manual_prompts.md
```

Для одного персонажа:

```bash
python3 generate_assets.py --character boris_molot --export-prompts output/boris_prompt.md
```

Эти команды не читают API-ключ, не проверяют reference image, не вызывают API и не создают PNG. Они собирают финальные промпты из `config/characters.json` и `prompts/character_template.txt`.

Дальше последовательность ручной работы:
1. Открыть сгенерированный `.md`.
2. Скопировать промпт нужного персонажа в веб-интерфейс генерации.
3. Отбраковать результат по позе, чистому белому фону, отсутствию тяжелых теней и full-body кадрированию.
4. Сохранить удачный PNG в `output/characters/{character_id}.png`.
5. Повторить для следующего персонажа, сверяя стиль с уже принятыми ассетами.

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
| `--export-prompts PATH` | Записать готовые промпты в Markdown для ручной генерации | — |
