# Asset Generator — техзадание

**Версия ТЗ:** 0.2  
**Статус:** готово к передаче разработчику

**Изменения v0.2 относительно v0.1:**
- Модель не привязана к одному endpoint: дефолт `gpt-image-2`, fallback настраиваемый
- Reference через API сформулирован как поддерживаемый сценарий (не гипотеза)
- `revised_prompt` помечен как опциональное поле лога; добавлены `usage`, фактические параметры ответа
- В CLI добавлены параметры `--model` и `--approach`
- Добавлен `--dry-run` режим
- Уточнена семантика "когда срабатывает fallback в auto": только на ошибки класса reference-flow, не на сеть/429/auth/5xx
- Зафиксирована возможность будущего per-character reference override (без реализации в MVP)

---

## 1. Контекст

В рамках разработки визуализатора партий нужны статические ассеты:
- 8 персонажей в полный рост на прозрачном (или белом) фоне
- 10 локаций в landscape-формате с пустой нижней третью (под персонажей)
- Стилистически связанный ансамбль (semi-realistic cartoon, 
  напоминающий стиль Arcane / Disenchantment)

Через chat.openai.com (браузерный диалог) генерация работает хорошо 
за счёт диалогового контекста. Через API нужен явный механизм 
поддержания стиля — **reference image** (первый сгенерированный 
персонаж используется как стилевой эталон для всех последующих 
генераций).

Согласно текущему OpenAI API guide, Images Edit endpoint поддерживает 
не только редактирование существующих картинок, но и "generation 
of new images using other images as reference". Также Responses API 
принимает image inputs. Таким образом, reference-flow через API — 
поддерживаемый сценарий, не гипотеза.

Текущий MVP — проверить, работает ли подход на 2 персонажах,
прежде чем расширять на полный набор (8 персонажей + 10 локаций).

---

## 2. Функциональные требования

### 2.1 CLI-интерфейс

Утилита запускается из командной строки и принимает:

**Целевые объекты (взаимоисключающие, обязательно один):**
- `--character {character_id}` — сгенерировать одного персонажа
- `--all-characters` — сгенерировать всех персонажей из конфига

**Управление моделью и подходом:**
- `--model {model_name}` — явное указание модели OpenAI Image API. 
  Дефолт — `gpt-image-2`. Допустимые значения зависят от того, что 
  доступно на момент имплементации (`gpt-image-2`, `gpt-image-1.5`, 
  `gpt-image-1`, `dall-e-3` — список разработчик уточняет под текущий 
  API). Указание неподдерживаемой модели — понятная ошибка.
- `--approach {auto|reference|text-only}` — режим генерации. 
  Дефолт `auto`. Семантика см. раздел 2.5.

**Прочие флаги:**
- `--regenerate` — перезаписать существующие файлы (без него — пропуск).
- `--dry-run` — собрать промпт, проверить `.env`, наличие reference, 
  пути output, **не вызывая API**. Полезно для отладки промптов и 
  конфигов перед реальной генерацией.

### 2.2 Конфигурация персонажей

Хранится в `config/characters.json` — словарь, ключ = `character_id`,
значение = объект с полями:
- `display_name` — имя для логов
- `archetype` — короткое описание роли (для логов)
- `color_accent` — hex-цвет персонажа (его сигнатурный цвет, 
  используется как акцент в одежде/украшениях)
- `visual_description` — подробное визуальное описание на английском
  (внешность, возраст, одежда, поза, выражение)
- `pose_notes` — описание позы и кадрирования

На MVP-этапе конфиг содержит 2 записи: `boris_molot`, `aurora`. 
Содержание этих записей предоставлено отдельно (см. раздел 6).

### 2.3 Шаблон промпта

Хранится в `prompts/character_template.txt` — текстовый файл с 
плейсхолдерами `{visual_description}` и `{pose_notes}`.

Точный текст шаблона предоставлен отдельно (раздел 6).

### 2.4 Reference image

В MVP используется **один глобальный reference**: 
`reference/style_reference.png`. Это первый сгенерированный персонаж 
(Борис из браузерного теста), используется как стилевой эталон для 
всех остальных генераций.

Если файла нет (и `--approach != text-only`) — утилита выдаёт 
понятную ошибку и не делает запрос к API.

**Future scope (НЕ реализуется в MVP):** возможен per-character 
reference override через опциональное поле в `config/characters.json` 
(например, `reference_override: "path/to/special.png"`). Реализация 
не входит в текущий scope, но структура кода не должна мешать 
будущему расширению — путь к reference не должен быть жёстко 
зашит в одном месте.

### 2.5 Семантика `--approach`

**`auto` (дефолт):**
- Сначала пытается генерацию с reference (reference-flow)
- Если reference-flow не поддерживается или падает по причинам, 
  относящимся именно к reference-flow — fallback на text-only 
  с warning в stdout и в JSON-логе
- На ошибки **не относящиеся к reference-flow** — fallback НЕ 
  срабатывает, ошибка пробрасывается наружу

Ошибки которые **триггерят fallback на text-only в `auto`**:
- Endpoint/model не поддерживает reference-flow (например, выбранная 
  модель не принимает image input)
- Reference image rejected / unsupported in this flow (API возвращает 
  ошибку валидации именно на reference image)
- API validation error именно на reference-path (структурная ошибка 
  запроса с reference)

Ошибки которые **НЕ триггерят fallback** (выбрасываются как ошибки):
- Rate limit (429) до исчерпания retry-попыток (см. 2.7)
- Network timeout, connection errors
- Authentication error (401)
- Server errors (5xx)
- Любые другие ошибки не связанные с reference-flow

Это критически важно. Иначе можно молча получить text-only генерацию 
из-за временной сетевой проблемы и думать, что "reference не работает".

**`reference`:**
- Только reference-flow
- Любая неудача (включая reference-flow ошибки) — это ошибка, 
  без fallback
- Используется когда нужна гарантия что генерация прошла через 
  reference (например, при финальном прогоне на всех 8 персонажах)

**`text-only`:**
- Сразу обычная генерация без reference
- Reference image не требуется (можно отсутствовать)
- Используется для отладки промпта или когда reference недоступен

### 2.6 Генерация через OpenAI API

Утилита делает запрос к OpenAI Image API. Конкретный endpoint 
(Images Edit / Responses API / другой) разработчик выбирает под 
текущее состояние API на момент имплементации.

**Предпочтительный путь:** Images Edit API с reference image как 
"generation using other image as reference". Если этот endpoint 
по факту не работает с выбранной моделью или ведёт себя иначе чем 
ожидается (например, пытается редактировать reference вместо 
использования как стиля) — допустимо использовать Responses API 
с image input + image generation tool, либо другой подход доступный 
в API.

**Размер картинки** — портретный, под персонажа в полный рост 
(рекомендуется `1024x1536` или ближайший поддерживаемый размер).

**Качество** — `high` (или эквивалент в текущем API).

### 2.7 Обработка rate limits и retry

Между запросами при `--all-characters` — пауза минимум 2 секунды.

Если API возвращает 429 (rate limit) — повтор с exponential backoff,
до 3 попыток. После 3 неудач — выбросить ошибку. **Не путать с 
fallback**: rate limit не активирует переход в text-only.

Network timeouts — retry с exponential backoff, тоже до 3 попыток.

### 2.8 Сохранение результата

Картинка сохраняется в `output/characters/{character_id}.png`.

Параллельно для каждого запроса записывается JSON-лог в 
`output/logs/{timestamp}_{character_id}.json` со следующими полями:

**Обязательные:**
- `character_id`
- `timestamp` (ISO format)
- `model` (какая модель использовалась)
- `approach` (`reference` или `text_only` — что фактически выполнилось)
- `requested_approach` (значение CLI-флага `--approach` на входе)
- `status` (`success` / `error`)
- `prompt` (полный текст промпта который ушёл в API)
- `elapsed_seconds`

**Опциональные (записывать если доступны от API/процесса):**
- `revised_prompt` — если API его вернул (DALL-E 3 это делает; для 
  GPT Image моделей может отсутствовать). Не завязывать на это поле 
  никакую аналитику.
- `usage` — usage info от API если возвращается
- `output_format`, `size`, `quality` — фактические параметры из 
  ответа API (не из запроса) — могут отличаться если API что-то 
  скорректировал
- `warning` — текст предупреждения, если был fallback или другая 
  пограничная ситуация
- `error` — описание ошибки, если status=error
- `fallback_trigger` — если в `auto` сработал fallback, описать 
  какая именно reference-flow ошибка его вызвала

### 2.9 Конфигурация через .env

API-ключ читается из `OPENAI_API_KEY` (через python-dotenv). 
Если не задан и режим не dry-run — понятная ошибка.

В dry-run режиме отсутствие ключа допустимо (просто отметить в выводе).

### 2.10 Поведение `--dry-run`

В этом режиме утилита:
- Загружает конфиг персонажа
- Собирает финальный промпт из шаблона + конфига
- Проверяет наличие `.env` (предупреждает но не падает)
- Проверяет наличие reference image (если approach != text-only)
- Проверяет доступность путей `output/`
- **Печатает финальный промпт в stdout** — чтобы можно было его 
  увидеть и оценить
- Печатает резюме: какая модель, какой approach, какой size, какие 
  пути будут использованы
- **НЕ делает запрос к API**
- **НЕ создаёт файлов в output/** (включая лог)

Полезно для итеративной отладки промптов и конфигов без расхода 
бюджета API.

---

## 3. Структура проекта

```
tools/asset-generator/
├── README.md                    # инструкция запуска и тестирования
├── requirements.txt             # зависимости
├── generate_assets.py           # основной скрипт (CLI entry point)
├── config/
│   └── characters.json          # конфигурация персонажей
├── prompts/
│   └── character_template.txt   # шаблон промпта
├── reference/                   # эталоны стиля (gitignored, кроме .gitkeep)
│   └── .gitkeep
└── output/                      # результаты (gitignored, кроме .gitkeep)
    ├── characters/.gitkeep
    └── logs/.gitkeep
```

Папки `reference/` и `output/` — в .gitignore (кроме .gitkeep), 
поскольку в них лежат бинарные ассеты.

---

## 4. Acceptance criteria

1. Скрипт устанавливается через `pip install -r requirements.txt`
2. `python generate_assets.py --character boris_molot` создаёт файл 
   `output/characters/boris_molot.png` (рекомендуемо 1024x1536, PNG)
3. `python generate_assets.py --all-characters` генерирует обоих 
   персонажей последовательно
4. Без `--regenerate` существующие файлы пропускаются с понятным 
   сообщением; с `--regenerate` — перезаписываются
5. Для каждой попытки создаётся JSON-лог в `output/logs/` со всеми 
   обязательными полями
6. CLI принимает `--model` и применяет указанное значение; дефолт — 
   `gpt-image-2` (или ближайшая актуальная модель на момент имплементации)
7. CLI принимает `--approach {auto|reference|text-only}` с семантикой 
   из раздела 2.5
8. В режиме `auto` fallback на text-only срабатывает только на 
   reference-flow ошибки и не срабатывает на network/429/auth/5xx
9. В режиме `reference` любая ошибка пробрасывается наружу без fallback
10. `--dry-run` печатает финальный промпт и резюме параметров без 
    вызова API и без создания файлов
11. Если `OPENAI_API_KEY` не задан (и не dry-run) — понятная ошибка, 
    без traceback
12. Если reference image отсутствует (и approach != text-only) — 
    понятная ошибка, без запроса к API
13. Rate limit (429) обрабатывается через retry с exponential backoff, 
    максимум 3 попытки; после исчерпания — ошибка (НЕ fallback)
14. Логи содержат фактически использованные параметры (`model`, 
    `approach`, плюс опциональные `usage`, `revised_prompt` если 
    доступны)

---

## 5. Что НЕ делать в этом MVP

- Локации (отдельная задача после успешной отладки персонажей)
- Удаление фона / постпроцессинг картинок (отдельная задача)
- Веб-интерфейс или GUI — только CLI
- Параллельная генерация — последовательно с паузами
- Кеширование промптов / умное определение похожих запросов
- Поддержка других провайдеров (Flux/Replicate/etc) — только OpenAI
- Тренировка LoRA или другая тонкая настройка стиля
- Автоматическая нарезка / обрезка результата
- Все остальные 6 персонажей — только Борис и Аврора
- **Per-character reference override** — задел в архитектуре есть, 
  но реализация не делается

Если в процессе работы покажется, что какая-то из этих фич нужна — 
**не реализовывать, а сообщить отдельно**.

---

## 6. Готовые артефакты

Эти артефакты используются как есть, разработчик их не сочиняет:

### 6.1 Содержимое `config/characters.json`

```json
{
  "boris_molot": {
    "display_name": "Борис",
    "archetype": "агрессор",
    "color_accent": "#e94560",
    "visual_description": "A stocky intimidating man in his late 40s, former police investigator with 20 years on the force. Heavy build but not bulky — solid, dense, the kind of man who's seen too much. Short cropped greying hair, tired narrow-set eyes that miss nothing, deep weathered face, faint stubble. Wears a worn dark leather jacket over a faded button-up shirt, dark trousers, scuffed boots. Posture is grounded, slightly leaning forward — a man used to dominating rooms by presence alone. Subtle red accent on the shirt collar or jacket lining (signature color #e94560). Confrontational but contained — not a brawler, an interrogator.",
    "pose_notes": "Full body, slight 3/4 turn to the right, weight on one leg, hands visible — one slightly clenched at side, intense gaze directed slightly off-camera as if assessing someone."
  },
  "aurora": {
    "display_name": "Аврора",
    "archetype": "драма-квин",
    "color_accent": "#ec4899",
    "visual_description": "A theatrical woman in her late 50s, former regional theater actress. Tall, slender, dramatic in every gesture. Elaborate dark red curly hair pinned up with a feather and a small ornamental clip. Expressive face with dramatic eye makeup, prominent cheekbones, lips painted dark wine. Wears a flowing burgundy theatrical coat with wide bell-sleeves trimmed in cream lace, over an old-fashioned high-collared dress with intricate ruffles. Long elbow-length dark gloves. Pink accent in the brooch or hair ornament (signature color #ec4899). Posture: one hand raised in a theatrical performance gesture, the other pressed dramatically to chest. Eyes wide with feigned shock, mouth slightly open mid-monologue.",
    "pose_notes": "Full body, 3/4 turn, mid-gesture, theatrical pose as if speaking on stage. She is performing even when no one is watching."
  }
}
```

### 6.2 Содержимое `prompts/character_template.txt`

```
Generate a character portrait for an animated AI-vs-AI social deduction show.

STYLE: Match the artistic style of the reference image exactly.
Semi-realistic cartoon, expressive character design, slightly stylized
proportions, rich color palette, soft cel-shading, dramatic lighting
from upper-left, clean linework. Think modern animated series like
Arcane crossed with Disenchantment — dramatic but readable.

COMPOSITION:
- Full body, head to feet, centered in frame
- Slight 3/4 turn pose (NOT direct front-facing, NOT pure side profile)
- Plain white or transparent background
- No environment, no other objects, no text
- Character occupies ~70% of frame height
- Even lighting from upper-left

CHARACTER:
{visual_description}

POSE: {pose_notes}

Render at high quality, consistent with the reference style.
The character must visually fit alongside other characters generated
in this same style — they all belong to one ensemble cast.
```

### 6.3 README инструкция тестирования (включить в репо)

README должен содержать:
- Что это и зачем (одна-две фразы)
- Установка (`pip install -r requirements.txt`, создание `.env`)
- Шаги тестирования:
  1. Положить reference-картинку в `reference/style_reference.png`
  2. Прогнать `--dry-run` для отладки промпта: 
     `python generate_assets.py --character boris_molot --dry-run`
  3. Реальная генерация: `python generate_assets.py --character boris_molot`
  4. Сравнить результат с reference — стиль должен совпадать
  5. `python generate_assets.py --character aurora`
  6. Сравнить Аврору с Борисом — должны выглядеть как один ансамбль
  7. Если хочется проверить чисто reference-режим без скрытого 
     fallback: `--approach reference`
  8. Если хочется быстро сравнить с генерацией без reference: 
     `--approach text-only`
- Что делать если стиль не держится — смотреть логи в `output/logs/`,
  в логе видно фактический approach (был ли fallback) и причину 
  fallback если он был

---

## 7. Известные риски и неопределённости

Разработчик должен быть готов к тому, что:

1. **Конкретный endpoint для reference может потребовать выбора** — 
   на момент имплементации нужно проверить, как выбранная модель 
   (`gpt-image-2` или дефолт) обращается с reference. Возможные 
   варианты: Images Edit API, Responses API с image input + 
   generation tool, Chat Completions с image input. Выбор за 
   разработчиком, главное чтобы reference-flow реально работал 
   и был отличим от text-only по результату.

2. **Не все модели возвращают `revised_prompt`** — это поле 
   характерно для DALL-E 3. Для GPT Image моделей может отсутствовать. 
   Логика логирования НЕ должна на него опираться (`revised_prompt` 
   опциональное поле).

3. **Если выбранная модель недоступна** (например, 
   `gpt-image-2` ещё не раскатана на твой аккаунт) — `--model` 
   позволяет переключиться на доступную. Дефолт можно поправить 
   при необходимости.

4. **Если reference вообще нигде не работает как ожидается** — 
   задокументировать в логе что именно происходит (какие endpoints 
   пробовали, какие ошибки, что вернул API), и сообщить отдельно. 
   Не пытаться решить героически — может оказаться, что нужно 
   менять подход (например, на Replicate / Flux). 
   Это решение принимается отдельно, не в рамках MVP.

---

## 8. Definition of Done

- Все acceptance criteria выполнены
- README прогоняется по шагам без сюрпризов
- На 2 персонажах (Борис + Аврора) видно, использовался ли reference 
  или fallback — это понятно из логов (поле `approach`, 
  `requested_approach`, `fallback_trigger`)
- `--dry-run` корректно работает — показывает промпт и не вызывает API
- `--approach reference` гарантирует отсутствие тихого fallback
- Код читаемый, с минимальными комментариями где логика 
  неочевидна (особенно вокруг работы с OpenAI API endpoint и 
  логики fallback в `auto`)
- Никаких других задач помимо описанных в этом ТЗ не делается

После успешной приёмки этого MVP последует расширение: добавление 
оставшихся 6 персонажей в конфиг, добавление 10 локаций с отдельным 
шаблоном промпта, командные опции `--location`, `--all-locations`, 
`--all`. Это будет описано в отдельном ТЗ после результатов MVP.
