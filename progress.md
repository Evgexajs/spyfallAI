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

## [TASK-014] CLI точка входа (Phase 0)
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан src/cli.py с полной CLI точкой входа
- Поддержка параметров: -c (characters), -l (location), -d (duration), -q (max questions)
- Опции --list-characters и --list-locations для просмотра доступных данных
- Функции load_character() и list_available_characters() для загрузки персонажей
- Callback on_turn добавлен в run_main_round и run_final_vote для вывода реплик в реальном времени
- Цветной вывод реплик в консоль с маркерами типа [Q], [A], [V]
- Вызов save_game() по завершении партии

### Проблемы / Заметки
- Полный тест игры требует OPENAI_API_KEY в .env

### Коммиты
- `e6f3503` — Add CLI entry point for Phase 0 (TASK-014)

---

## [TASK-013] Логирование партий в JSON
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан src/storage/game_repository.py с функциями save_game, load_game, list_games
- Создан src/storage/__init__.py с экспортами
- save_game(game) сохраняет в games/{timestamp}_{id}.json
- Логи никогда не перезаписываются (FileExistsError при дубликате)
- Полная структура Game из PRD сериализуется корректно

### Проблемы / Заметки
- Нет

### Коммиты
- `7d09178` — Add game repository for JSON logging (TASK-013)

---

## [TASK-012] Оркестратор: Голосование и Resolution
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Добавлена функция run_final_vote(game, characters, provider) в src/orchestrator/game_engine.py
- Реализован переход в фазу FINAL_VOTE, затем RESOLUTION
- Каждый игрок голосует за подозреваемого через LLM (с парсингом ответа)
- Определение победителя: если обвинённый = шпион → civilians win, иначе → spy win
- При равенстве голосов — случайный выбор среди лидеров
- Запись голосов в GameOutcome.votes и Turn с type=VOTE
- Установка game.ended_at при завершении
- Обновлен __init__.py оркестратора с экспортом run_final_vote

### Проблемы / Заметки
- Нет

### Коммиты
- `abbcd4a` — Add voting and resolution phase (TASK-012)

---

## [TASK-011] Оркестратор: Основной цикл вопрос-ответ
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Добавлена функция run_main_round(game, characters, provider) в src/orchestrator/game_engine.py
- Реализован round-robin цикл: вопрос → ответ → следующий questioner = answerer
- Правило: target выбирается случайно среди всех кроме задающего
- Каждый ход записывается в game.turns как объект Turn
- Условия выхода: таймер (duration_minutes) или лимит вопросов (max_questions)
- Добавлены helper-функции: _transition_phase, _get_secret_info, _build_conversation_history, _get_character_by_id, _select_target
- Обновлен __init__.py оркестратора с экспортом run_main_round

### Проблемы / Заметки
- Нет

### Коммиты
- `ba72820` — Add main round game loop (TASK-011)

---

## [TASK-010] Оркестратор: Setup фаза
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан src/orchestrator/game_engine.py с функцией setup_game(characters, location_id)
- Создан src/orchestrator/__init__.py с экспортами
- Функция load_locations() загружает локации из locations.json
- Случайное назначение шпиона через random.choice
- Раздача ролей мирным игрокам (роли перемешиваются)
- Шпион получает role_id=None, is_spy=True
- Возврат объекта Game с phase_transitions начиная с SETUP

### Проблемы / Заметки
- Исправлен синтаксис типов для Python 3.9 (Optional[Path] вместо Path | None)

### Коммиты
- `e05e1fb` — Add game orchestrator setup phase (TASK-010)

---

## [TASK-009] Сборщик промптов для агентов
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан src/agents/prompt_builder.py с функцией build_system_prompt(character, game, secret_info)
- Создан src/agents/__init__.py с экспортами
- SecretInfo dataclass для секретной информации (is_spy, location, role)
- Секретная информация: шпион получает "ты НЕ знаешь локацию", мирный получает локацию и роль
- Включены few-shot примеры реплик для 8 архетипов персонажей
- MUST/MUST NOT директивы включены в промпт
- Проверено: локация НЕ упоминается в промпте шпиона

### Проблемы / Заметки
- Нет

### Коммиты
- `ceaa10b` — Add prompt builder for agents (TASK-009)

---

## [TASK-008] Базовые локации (2 шт для Phase 0)
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан locations.json с 2 локациями: hospital (Больница), airplane (Самолёт)
- hospital: 4 роли (surgeon, nurse, patient, receptionist)
- airplane: 5 ролей (pilot, flight_attendant, passenger_business, passenger_economy, air_marshal)
- Формат соответствует схеме Location из src/models/location.py
- Все роли имеют уникальные id в рамках своих локаций

### Проблемы / Заметки
- Нет

### Коммиты
- `fd72c39` — Add basic locations for TASK-008

---

## [TASK-007] Персонаж: Ким (параноик)
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан characters/kim.json с полным профилем персонажа
- Заполнены все поля по схеме PRD 8.3: id, display_name, archetype, backstory, voice_style
- 4 MUST директивы (машинно проверяемы: regex на самокоррекцию, слова-смягчители, counter предложений)
- 3 MUST NOT директивы (проверяемы regex на уверенные обвинения)
- 5 detectable_markers: self_correction (regex), hedging_words (regex), nervous_filler (regex), no_confident_accusation (regex), panic_response (binary_llm)
- 2 personal_triggers: direct_accusation, repeated_accusation_on_same_target (оба → panic_and_derail)

### Проблемы / Заметки
- Нет

### Коммиты
- `d8cb50f` — Add Kim character profile for TASK-007

---

## [TASK-006] Персонаж: Зоя (дерзкий циник)
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан characters/zoya.json с полным профилем персонажа
- Заполнены все поля по схеме PRD 8.5: id, display_name, archetype, backstory, voice_style
- 4 MUST директивы (машинно проверяемы: regex на маркеры сарказма, counter предложений)
- 3 MUST NOT директивы (проверяемы regex на пафосные слова)
- 5 detectable_markers: short_reply (counter), sarcasm_markers (regex), question_response (regex), no_pathos (regex), ironic_tone (binary_llm)
- 2 personal_triggers: dodged_direct_question, contradiction_with_previous_answer (оба → mock_with_dry_sarcasm)

### Проблемы / Заметки
- Нет

### Коммиты
- `df757cc` — Add Zoya character profile for TASK-006

---

## [TASK-005] Персонаж: Борис Молот (агрессор)
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан characters/boris_molot.json с полным профилем персонажа
- Заполнены все поля по схеме PRD 8.1: id, display_name, archetype, backstory, voice_style
- 4 MUST директивы (машинно проверяемы: счётчики предложений, regex на имена, цитаты)
- 3 MUST NOT директивы (проверяемы regex на слова-смягчители)
- 5 detectable_markers: short_reply (counter), direct_question (regex), names_addressee (regex), no_hedging (regex), counter_accusation (binary_llm)
- 2 personal_triggers: dodged_direct_question, contradiction_with_previous_answer

### Проблемы / Заметки
- Нет

### Коммиты
- `223b146` — Add Boris Molot character profile for TASK-005

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
- `975f795` — Add Pydantic data models for TASK-004

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
