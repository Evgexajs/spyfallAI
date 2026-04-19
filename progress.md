# Progress Log — SpyfallAI

Этот файл ведётся агентами для логирования прогресса по задачам.

---

## Формат записи

```
## [TASK-XXX] Название задачи
**Дата:** YYYY-MM-DD
**Агент:** (опционально)
**Статус:** done | blocked | in_progress

### Что сделано
- Пункт 1
- Пункт 2

### Проблемы / Заметки
- (если были)

### Коммиты
- `abc1234` — описание
```

---

## История

(записи добавляются сверху, самые новые — первыми)

---

## [TASK-004] Pydantic модели данных
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан src/models/__init__.py с экспортом всех моделей
- Создан src/models/character.py — Character, Trigger, Marker, ConditionType, ReactionType, MarkerMethod, LLMOverride
- Создан src/models/location.py — Location, Role с валидацией уникальности role_id
- Создан src/models/game.py — Game, Player, Turn, TurnType, GamePhase, ConfidenceLevel, ConfidenceEntry, TriggerEvent, PhaseEntry, GameOutcome, GameConfig
- Все модели имеют Pydantic валидацию: границы значений, обязательные поля, кросс-валидация (ровно 1 шпион, уникальные роли)

### Проблемы / Заметки
- Добавлен LLMOverride как отдельная модель для llm_override в Character

### Коммиты
- (будет добавлен после коммита)

---

## [TASK-003] Конфигурация llm_config.json
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан llm_config.json по структуре из PRD (providers, roles, per_character_overrides)
- Указаны провайдеры: openai, anthropic с соответствующими api_key_env
- Роли: main (gpt-4o), utility (gpt-4o-mini)
- Добавлен класс LLMConfig для загрузки и валидации конфига
- Добавлена функция create_provider для создания провайдера по роли/персонажу
- Обновлены экспорты в src/llm/__init__.py

### Проблемы / Заметки
- Anthropic провайдер пока не реализован (raise LLMError)
- per_character_overrides пустой, будет заполняться при создании персонажей

### Коммиты
- `138e332` — Add llm_config.json and config loading for TASK-003

---

## [TASK-002] LLM адаптер для OpenAI
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан src/llm/adapter.py с абстрактным базовым классом LLMProvider
- Реализован OpenAIProvider с поддержкой async вызовов
- Добавлена обработка ошибок: LLMError, LLMTimeoutError
- Обработка таймаутов через asyncio.wait_for и openai timeout
- Создан src/llm/__init__.py с экспортом публичного API

### Проблемы / Заметки
- Тестовый вызов API (шаги 2-3) требует настроенного OPENAI_API_KEY в .env
- Код успешно обрабатывает отсутствие ключа (выбрасывает LLMError)

### Коммиты
- `187808d` — Add LLM adapter with OpenAI provider for TASK-002

---

## [TASK-001] Инициализация структуры проекта
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создана структура директорий: src/, characters/, games/
- Создан pyproject.toml с зависимостями (openai, python-dotenv, pydantic)
- Создан .env.example со всеми переменными окружения из PRD
- Создан .gitignore с .env и стандартными Python-исключениями
- Добавлен src/__init__.py для корректной работы как Python-пакета

### Проблемы / Заметки
- Python 3.11+ не установлен в системе, использован Python 3.9.6
- pyproject.toml адаптирован под Python >=3.9 вместо >=3.11

### Коммиты
- `ea573f0` — Initialize project structure with pyproject.toml and env config
