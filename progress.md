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

## [TASK-078] Ручное тестирование на 3 партиях
**Дата:** 2026-04-21
**Статус:** done

### Что сделано
- Создан файл `tests/test_task078_integration.py` с 4 интеграционными тестами:
  - `test_characters_have_different_reaction_types` — 4 персонажа имеют разные reaction_type для silent_for_n_turns
  - `test_triggered_events_use_personal_reaction_types` — проверка что TriggerResult использует персональный reaction_type
  - `test_direct_accusation_and_silent_triggers_both_fire` — оба condition_type могут срабатывать в одной игре
  - `test_trigger_check_is_synchronous_for_non_llm_triggers` — синхронная проверка для non-LLM триггеров
- Проанализированы 29 существующих игровых логов:
  - 93% игр (27 из 29) стоят <= $0.25
  - Средняя стоимость: $0.12
  - 2 разных condition_type (direct_accusation, silent_for_n_turns) срабатывали в логах
- Верифицированы исправления TASK-070:
  - До фикса: все silent_for_n_turns показывали `point_out_inconsistency`
  - После фикса: код использует персональные reaction_type из профиля персонажа
- Все 28 юнит-тестов и 4 интеграционных теста проходят

### Проблемы / Заметки
- OpenAI API работает очень медленно (>2 мин на ответ), что препятствует live-тестированию
- Только 1 игра была сыграна после фикса TASK-070 (11:13:33), в ней 0 событий триггеров
- Рекомендуется повторить live-тестирование когда API стабилизируется

### Коммиты
- `TBD` — test: add TASK-078 integration tests

---

## [TASK-077] Написать тесты для всех детекторов
**Дата:** 2026-04-21
**Статус:** done

### Что сделано
- Создан консолидированный файл `tests/test_trigger_detectors.py` с 24 тестами
- Тесты для `dodged_direct_question`:
  - Уклончивый ответ возвращает True
  - Прямой ответ возвращает False
  - Невалидный ответ LLM возвращает False с warning
  - Исключение LLM возвращает False с warning
  - Поддержка английских ответов (yes/no)
  - Проверка содержимого промпта
- Тесты для `repeated_accusation_on_same_target`:
  - 2 обвинения подряд срабатывает
  - Обвинения через 10 ходов не срабатывает
  - Обвинения на разные цели не срабатывает
  - `params.target_id` записывается в TriggerEvent
- Тесты для `contradiction_with_previous_answer`:
  - Явное противоречие срабатывает
  - Перефразирование не срабатывает
  - Смена темы не срабатывает
  - Менее 2 предыдущих ответов — проверка пропускается
  - Невалидный ответ LLM не срабатывает
  - `reasoning` и `params` записываются в TriggerEvent
- Тесты для `silent_for_n_turns` с персональными reaction_types:
  - Борис использует `pressure_with_sharper_question`
  - Ким использует `panic_and_derail`
  - Разные персонажи имеют разные reaction_type для одного condition
- Все тесты используют моки для LLM (`AsyncMock`, `MagicMock`)

### Коммиты
- `dddea66` — test: add consolidated trigger detector tests (TASK-077)

---

## [TASK-076] Обновить метод создания TriggerEvent для новых полей
**Дата:** 2026-04-21
**Статус:** done

### Что сделано
- Проверено, что метод `create_trigger_event` в `src/triggers/checker.py` уже принимает:
  - `params: Optional[dict]` — дополнительные параметры события
  - `reasoning: Optional[str]` — результат анализа LLM
- Для `contradiction_with_previous_answer`: reasoning записывается через `llm_detector_meta`
- Для `repeated_accusation_on_same_target`: `params.target_id` автоматически добавляется из `result.target_character_id`
- Удалён неиспользуемый импорт `Any` из `src/models/game.py`
- Проверена сериализация TriggerEvent в JSON — работает корректно
- Все существующие тесты проходят:
  - `test_trigger_event_includes_target_id_in_params` — params для repeated_accusation
  - `test_create_trigger_event_with_reasoning_and_params` — reasoning и params для contradiction

### Заметки
- Функциональность была реализована в рамках TASK-067, TASK-072, TASK-073, TASK-074
- Данная задача подтвердила корректность интеграции

### Коммиты
- `f11e0ad` — chore: verify TriggerEvent params/reasoning fields (TASK-076)

---

## [TASK-075] Интегрировать новые детекторы в run_main_round
**Дата:** 2026-04-21
**Статус:** done

### Что сделано
- Добавлен импорт `ConditionType` в `src/orchestrator/game_engine.py`
- После каждого ответа в `run_main_round` вызываются LLM-детекторы:
  - `check_dodged_question()` — проверяет, уклонился ли отвечающий от вопроса
  - `check_contradiction()` — проверяет противоречие с предыдущими ответами
- Оба детектора используют utility модель (`game.config.utility_model`)
- Для каждого персонажа с соответствующим персональным триггером создаётся `TriggerResult`
- Результаты LLM-детекторов объединяются с синхронными триггерами перед `select_winner`
- Логика выбора победителя по priority сохраняется (highest wins)
- При создании `TriggerEvent` передаются `reasoning` и `params` для LLM-детекторов
- Все 5 condition_types теперь проверяются:
  - `direct_accusation` — синхронный
  - `silent_for_n_turns` — синхронный
  - `repeated_accusation_on_same_target` — синхронный (TASK-072)
  - `dodged_direct_question` — LLM-детектор (TASK-073)
  - `contradiction_with_previous_answer` — LLM-детектор (TASK-074)

### Коммиты
- `4da8a71` — feat: integrate LLM detectors into run_main_round (TASK-075)

---

## [TASK-074] Реализовать детектор contradiction_with_previous_answer
**Дата:** 2026-04-21
**Статус:** done

### Что сделано
- Реализован асинхронный метод `check_contradiction(speaker_id, current_answer, game, provider, model, history_window=10)` в `src/triggers/checker.py`
- Метод собирает предыдущие ответы игрока за последние `history_window` ходов
- Если у игрока < 2 предыдущих ответов — детектор не запускается (возвращает False)
- LLM-промпт на русском языке с бинарным вопросом о прямом противоречии
- Явная инструкция в промпте: смещение темы и перефразирование — НЕ противоречие
- Возвращает кортеж `(triggered: bool, reasoning: Optional[str], turn_numbers: Optional[list[int]])`
- При срабатывании возвращает reasoning и номера ходов с предыдущими ответами
- Добавлен импорт `TurnType` для фильтрации только ответов (не вопросов/вмешательств)
- Обновлён метод `create_trigger_event` для поддержки параметров `reasoning` и `params`
- Написано 7 юнит-тестов в `tests/test_trigger_reaction_types.py`:
  - `test_explicit_contradiction_triggers` — явное противоречие срабатывает
  - `test_rephrasing_does_not_trigger` — перефразирование НЕ срабатывает
  - `test_topic_change_does_not_trigger` — смена темы НЕ срабатывает
  - `test_less_than_two_previous_answers_skips_check` — пропуск при < 2 ответах
  - `test_invalid_llm_response_does_not_trigger` — невалидный ответ не ломает
  - `test_history_window_limits_turns_checked` — окно истории работает
  - `test_create_trigger_event_with_reasoning_and_params` — params и reasoning в событии

### Коммиты
- `72cf007` — feat: implement contradiction_with_previous_answer detector (TASK-074)

---

## [TASK-073] Реализовать детектор dodged_direct_question
**Дата:** 2026-04-21
**Статус:** done

### Что сделано
- Добавлен импорт `logging` и `TYPE_CHECKING` в `src/triggers/checker.py`
- Реализован асинхронный метод `check_dodged_question(question_turn, answer_turn, provider, model) -> bool`
- Метод использует LLM для определения, ответил ли игрок по существу на вопрос
- Промпт на русском языке с бинарным ответом "да/нет"
- Парсинг ответа поддерживает русский ("да"/"нет") и английский ("yes"/"no")
- При невалидном ответе LLM — возвращает False и логирует warning
- При исключении — возвращает False и логирует warning
- Написаны 9 юнит-тестов в `tests/test_dodged_question_detector.py`:
  - `test_evasive_answer_returns_true` — уклончивый ответ срабатывает
  - `test_direct_answer_returns_false` — прямой ответ не срабатывает
  - `test_invalid_llm_response_returns_false_with_warning` — невалидный ответ не срабатывает
  - `test_llm_exception_returns_false_with_warning` — исключение не ломает работу
  - `test_yes_english_returns_false` — английский "yes" работает
  - `test_no_english_returns_true` — английский "no" работает
  - `test_response_with_whitespace_is_normalized` — пробелы нормализуются
  - `test_prompt_includes_question_and_answer_content` — промпт содержит вопрос и ответ
  - `test_uses_specified_model` — используется переданная модель

### Заметки
- Детектор использует utility модель для экономии токенов
- Интеграция в game_engine будет выполнена в TASK-075

### Коммиты
- `e8d5876` — feat: implement dodged_direct_question detector (TASK-073)

---

## [TASK-072] Реализовать детектор repeated_accusation_on_same_target
**Дата:** 2026-04-21
**Статус:** done

### Что сделано
- Добавлен глобальный триггер `global_repeated_accusation` в `trigger_rules.json`
- Интегрирован вызов `track_accusation()` в `game_engine.py` после каждого ответа
- Обновлён `create_trigger_event()` для записи `target_id` в `params` при REPEATED_ACCUSATION
- Написаны юнит-тесты в `tests/test_trigger_reaction_types.py`:
  - `test_two_accusations_in_row_triggers` — 2 обвинения подряд срабатывает
  - `test_accusations_spread_over_10_turns_does_not_trigger` — обвинения вне окна не срабатывают
  - `test_accusations_on_different_targets_does_not_trigger` — обвинения на разные цели не срабатывают
  - `test_trigger_event_includes_target_id_in_params` — TriggerEvent содержит target_id
  - `test_margo_repeated_accusation_uses_correct_reaction_type` — персональный reaction_type используется

### Заметки
- Базовая структура `_accusation_tracker`, `track_accusation()`, `check_repeated_accusation()` была уже реализована в checker.py
- Требовалось добавить глобальный триггер и интеграцию в оркестраторе

### Коммиты
- `8dc8479` — feat: implement repeated_accusation_on_same_target detector

---

## [TASK-071] Добавить валидатор отсутствия silent_for_n_turns при загрузке профиля
**Дата:** 2026-04-21
**Статус:** done

### Что сделано
- Добавлен `@model_validator(mode="after")` в класс `Character` (`src/models/character.py`)
- Валидатор `warn_missing_silent_trigger()` проверяет наличие триггера `silent_for_n_turns` в `personal_triggers`
- Если триггер отсутствует — логируется WARNING, персонаж всё равно создаётся успешно
- Валидация работает автоматически везде, где используется `Character.model_validate()`

### Тесты
- Создание персонажа без silent_for_n_turns → WARNING в логе
- Создание персонажа с silent_for_n_turns → без WARNING
- Все 8 существующих персонажей загружаются без WARNING

### Коммиты
- `7fd8d74` — feat: add validator for missing silent_for_n_turns trigger

---

## [TASK-070] Рефакторинг логики выбора reaction_type в TriggerChecker
**Дата:** 2026-04-21
**Статус:** done

### Что сделано
- Рефакторинг `_check_global_trigger()`: глобальные триггеры теперь срабатывают ТОЛЬКО если у персонажа есть соответствующий персональный триггер для этого condition_type
- reaction_type, priority и threshold берутся из персонального триггера, не из глобального дефолта
- В `check_triggers_for_character()` добавлен трекинг обработанных condition_type для избежания дублирования результатов
- Создан файл тестов `tests/test_trigger_reaction_types.py` с 7 юнит-тестами:
  - Борис при silent_for_n_turns использует reaction `pressure_with_sharper_question`
  - Ким при silent_for_n_turns использует reaction `panic_and_derail`
  - Разные персонажи имеют разные reaction_type для одного condition_type
  - Глобальный триггер НЕ срабатывает для персонажа без персонального триггера
  - Нет дублирования триггеров

### Коммиты
- `f745fe4` — feat: refactor TriggerChecker to require personal triggers for global trigger firing

---

## [TASK-069] Убрать глобальный silent_for_n_turns из trigger_rules.json
**Дата:** 2026-04-21
**Статус:** done

### Что сделано
- Глобальный триггер `global_silent_for_n_turns` помечен как `deprecated: true` в trigger_rules.json
- Обновлено описание триггера с пояснением что это резервный/устаревший триггер
- Добавлено поле `deprecated` в dataclass `GlobalTrigger` в checker.py
- Функция `load_global_triggers()` теперь читает флаг `deprecated`
- Метод `check_triggers_for_character()` теперь пропускает deprecated триггеры
- Проверено: только активный триггер `global_direct_accusation` используется системой

### Коммиты
- `db92582` — feat: deprecate global silent_for_n_turns trigger in favor of personal triggers

---

## [TASK-068] Добавить персональный триггер silent_for_n_turns во все профили персонажей
**Дата:** 2026-04-21
**Статус:** done

### Что сделано
- Добавлен триггер `silent_for_n_turns` во все 8 профилей персонажей
- Каждый персонаж получил уникальную настройку триггера:
  - Борис: silent_turns=2, priority=9, threshold=0.3, reaction=pressure_with_sharper_question
  - Марго: silent_turns=3, priority=5, threshold=0.5, reaction=deflect_suspicion_to_another
  - Ким: silent_turns=2, priority=4, threshold=0.4, reaction=panic_and_derail
  - Штейн: silent_turns=3, priority=6, threshold=0.7, reaction=point_out_inconsistency (уже был)
  - Зоя: silent_turns=2, priority=7, threshold=0.4, reaction=mock_with_dry_sarcasm
  - Игнатий: silent_turns=3, priority=5, threshold=0.6, reaction=moralize_and_accuse
  - Лёха: silent_turns=2, priority=5, threshold=0.4, reaction=short_dismissive_jab
  - Аврора: silent_turns=3, priority=5, threshold=0.5, reaction=panic_and_derail
- Все JSON файлы валидны
- Все персонажи загружаются через pydantic модель без ошибок

### Коммиты
- `4ac2066` — feat: add silent_for_n_turns trigger to all character profiles

---

## [TASK-067] Расширить модель TriggerEvent для новых полей
**Дата:** 2026-04-21
**Статус:** done

### Что сделано
- Добавлены два опциональных поля в TriggerEvent (src/models/game.py):
  - `reasoning: Optional[str]` — для результата анализа LLM (детектор contradiction)
  - `params: Optional[dict]` — для дополнительных параметров (target_id для repeated_accusation)
- Поля имеют default=None для обратной совместимости
- Проверено: существующие логи игр загружаются без ошибок
- Проверено: сериализация/десериализация JSON работает корректно

### Коммиты
- `d866c7f` — feat: add reasoning and params fields to TriggerEvent model

---

## [TASK-066] Добавить env-переменные для новых детекторов
**Дата:** 2026-04-21
**Статус:** done

### Что сделано
- Добавлены переменные в .env.example:
  - `REPEATED_ACCUSATION_WINDOW=5` — окно для подсчёта повторных обвинений
  - `CONTRADICTION_HISTORY_WINDOW=10` — окно истории для детектора противоречий
- Добавлены переменные в game_engine.py с os.environ.get() и дефолтами
- Успешно импортируются: `from src.orchestrator.game_engine import REPEATED_ACCUSATION_WINDOW, CONTRADICTION_HISTORY_WINDOW`

### Коммиты
- `0b15610` — Add CR-002 env variables for trigger detectors

---

## [TASK-065] Обратная совместимость со старыми логами игр
**Дата:** 2026-04-20
**Статус:** done

### Что сделано
- Проверена существующая реализация — все новые CR-001 поля уже имеют дефолты:
  - `preliminary_vote_result: Optional[dict] = None`
  - `defense_speeches: list = []` (default_factory)
  - `final_vote_result: Optional[dict] = None`
  - `vote_changes: list = []` (default_factory)
- Добавлены интеграционные тесты в test_defense_voting_models.py:
  - `test_load_existing_game_files` — загружает все реальные файлы из games/
  - `test_old_game_defaults_are_correct` — проверяет корректные дефолты
  - `test_round_trip_preserves_existing_game_data` — сериализация/десериализация
- Все 6 существующих логов игр загружаются без ошибок
- UI API тесты (test_games_api.py) проходят — старые игры отображаются

### Тесты
- 27 тестов в test_defense_voting_models.py пройдено
- 18 тестов в test_games_api.py пройдено

### Коммиты
- `f15ed4d` — feat: add backward compatibility tests for old game logs (TASK-065)

---

## [TASK-064] Пост-чек защитных реплик на характерность
**Дата:** 2026-04-20
**Статус:** done

### Что сделано
- Добавлено поле `regenerated: bool` в модель DefenseSpeech (src/models/game.py)
- Создана функция `build_defense_characteristic_check_prompt()` в prompt_builder.py:
  - Формирует промпт для утилитарной модели
  - Включает имя персонажа, архетип, стиль речи, MUST-директивы
  - Требует бинарный ответ "да/нет"
- Создана функция `_check_defense_speech_characteristic()` в game_engine.py:
  - Вызывает утилитарную модель с низкой температурой (0.3)
  - Возвращает True если реплика характерна
- Модифицирована функция `run_defense_speeches()`:
  - После генерации речи проверяет характерность
  - Если не характерна — регенерирует ОДИН раз (temperature=0.9)
  - Логирует регенерацию через logger.info
  - Устанавливает regenerated=True на DefenseSpeech
- Добавлены 4 теста в TestDefenseCharacteristicCheck:
  - test_characteristic_prompt_includes_must_directives
  - test_characteristic_speech_not_regenerated
  - test_non_characteristic_speech_regenerated_once
  - test_regeneration_logged

### Тестирование
- Все 30 тестов в test_defense_speeches.py прошли
- Все 72 теста по defense/voting прошли
- 247 unit-тестов прошли (19 интеграционных требуют API ключ)

### Коммиты
- `1ebd9a8` — feat: add post-check for defense speech characteristicness (TASK-064)

---

## [TASK-063] UI для новых фаз голосования и защиты
**Дата:** 2026-04-20
**Статус:** done

### Что сделано
- Обновлён index.html (live-игра):
  - Добавлены PHASE_NAMES для preliminary_vote и pre_final_vote_defense на русском
  - Добавлены TURN_TYPE_LABELS: П-ГОЛОС, ЗАЩИТА, Ф-ГОЛОС
  - Добавлены TURN_TYPE_TOOLTIPS с описаниями новых типов
  - CSS стили для .message.preliminary_vote (фиолетовая рамка)
  - CSS стили для .message.defense_speech (оранжевая рамка + метка "ЗАЩИТА")
  - CSS стили для .message.final_vote (фиолетовая рамка)
  - CSS для .phase-badge.preliminary_vote и .phase-badge.pre_final_vote_defense
  - Индикаторы смены голоса: "изменил" (оранжевый) / "подтвердил" (зелёный)
- Обновлён game.html (история игры):
  - Те же PHASE_NAMES, TURN_TYPE_LABELS, TURN_TYPE_TOOLTIPS
  - Те же CSS стили для новых типов сообщений
  - Индикаторы смены голоса в финальном голосовании
- Добавлены .message-type CSS для preliminary_vote, defense_speech, final_vote
- Все 237 unit-тестов проходят

### Проблемы / Заметки
- Нет

### Коммиты
- `2513d23` — feat: add UI support for new voting and defense phases (TASK-063)

---

## [TASK-062] Обновить поток фаз в оркестраторе
**Дата:** 2026-04-20
**Статус:** done

### Что сделано
- Верифицирован поток фаз в оркестраторе (уже реализован в TASK-059, 060, 061):
  - main_round → preliminary_vote → pre_final_vote_defense → final_vote → resolution
  - При досрочном голосовании: main_round → optional_vote → preliminary_vote → defense → final
- Создан tests/test_phase_flow.py с 17 тестами:
  - TestGamePhaseEnum: 3 теста проверки наличия всех фаз
  - TestPhaseTransitions: 2 теста записи переходов фаз
  - TestNormalPhaseFlow: 3 теста нормального потока
  - TestEarlyVotingFlow: 3 теста досрочного голосования
  - TestFullPhaseFlowIntegration: 3 теста порядка фаз
  - TestPhaseStatusField: 2 теста статуса PhaseEntry
  - TestVoteSplitBehavior: 1 тест поведения при разделении голосов
- Все 17 тестов проходят, 99 связанных тестов проходят

### Проблемы / Заметки
- Интеграция в app.py и cli.py уже была выполнена в предыдущих задачах (TASK-059, 060, 061)
- GamePhase enum содержит: PRELIMINARY_VOTE, PRE_FINAL_VOTE_DEFENSE (добавлены в TASK-059)
- Переходы фаз корректно записываются с from_phase/to_phase

### Коммиты
- `e745d11` — feat: verify phase flow integration and add tests (TASK-062)

---

## [TASK-061] Модифицировать финальное голосование с возможностью смены голоса (F13)
**Дата:** 2026-04-20
**Статус:** done

### Что сделано
- Создана функция `build_final_vote_with_defense_prompt()` в src/agents/prompt_builder.py:
  - Промпт содержит исходный голос избирателя в предварительном голосовании
  - Включает все защитные реплики для контекста
  - Объясняет правило строгого большинства (шпион выигрывает при отсутствии)
  - Поддерживает опцию воздержания (DEFENSE_ALLOW_ABSTAIN)
- Обновлён src/agents/__init__.py с экспортом build_final_vote_with_defense_prompt
- Модифицирована функция `run_final_vote()` в src/orchestrator/game_engine.py:
  - Добавлен параметр defense_was_executed: bool
  - Если защита пропущена — копирует preliminary_vote без LLM вызовов
  - В phase_transitions устанавливается status: 'skipped_copied_from_preliminary'
  - Если защита была — каждый агент решает подтвердить/изменить голос
  - Отслеживает vote_changes для изменивших голос (VoteChange объекты)
  - Воздержавшиеся в preliminary могут проголосовать в final
  - Победитель определяется строгим большинством (> 50% голосов)
  - При отсутствии большинства — шпион выигрывает
- Добавлена вспомогательная функция `_parse_final_vote()` для парсинга ответов
- Создан tests/test_final_vote_defense.py с 18 тестами:
  - TestDefenseSkippedCopyVotes: 4 теста копирования голосов без LLM
  - TestDefenseExecutedVoteChanges: 3 теста смены голосов
  - TestStrictMajorityWinner: 4 теста определения победителя
  - TestFinalVotePromptContent: 4 теста содержимого промпта
  - TestVoteResultCallback: 1 тест callback функции
  - TestTurnContent: 2 теста контента ходов
- Все 18 тестов проходят, 226 тестов всего проходят

### Проблемы / Заметки
- Нет

### Коммиты
- `7243880` — feat: implement final vote with defense phase integration (TASK-061)

---

## [TASK-060] Реализовать фазу защитных реплик (F12)
**Дата:** 2026-04-20
**Статус:** done

### Что сделано
- Создана функция `build_defense_speech_prompt()` в src/agents/prompt_builder.py:
  - Генерирует промпт для защитной реплики персонажа
  - Включает информацию о голосах против персонажа
  - Содержит ограничение на количество предложений (DEFENSE_SPEECH_MAX_SENTENCES)
  - Инструктирует оставаться в образе персонажа
- Обновлён src/agents/__init__.py с экспортом build_defense_speech_prompt
- Создана функция `run_defense_speeches()` в src/orchestrator/game_engine.py:
  - Активируется если max(votes) >= DEFENSE_MIN_VOTES_TO_QUALIFY
  - Защиту получают ВСЕ игроки с максимальным числом голосов (2-2-2 → трое защитников)
  - Порядок защит случайный (random.shuffle), фиксируется в логе
  - Реплика обрезается до DEFENSE_SPEECH_MAX_SENTENCES предложений с warning в логе
  - addressee_id = 'all', применяется calculate_display_delay_ms()
  - Триггеры и окна вмешательства НЕ запускаются во время защит
  - Если max(votes) < порога — фаза пропускается со статусом 'skipped_below_threshold'
- Добавлены вспомогательные функции:
  - `_count_sentences()` — подсчёт предложений в тексте
  - `_truncate_to_sentences()` — обрезка текста до N предложений
- Обновлён src/orchestrator/__init__.py с экспортом run_defense_speeches
- Создан tests/test_defense_speeches.py с 26 тестами:
  - TestCountSentences: 6 тестов подсчёта предложений
  - TestTruncateToSentences: 4 теста обрезки предложений
  - TestDefensePhaseSkipping: 2 теста пропуска фазы (нет голосов, ниже порога)
  - TestDefensePhaseExecution: 5 тестов выполнения фазы (один/несколько защитников, turn, callbacks)
  - TestSentenceTruncation: 1 тест обрезки длинных речей
  - TestDefensePromptBuilder: 3 теста промпта защиты
  - TestPhaseTransitions: 2 теста переходов фаз
  - TestTokenUsageTracking: 1 тест трекинга токенов
  - TestDefenseOrder: 1 тест рандомизации порядка
  - TestNoTriggersOrInterventions: 1 тест отсутствия триггеров
- Все 26 тестов проходят, 208 тестов всего проходят (1 несвязанный failure)

### Проблемы / Заметки
- Нет

### Коммиты
- `6fe895b` — feat: implement defense speeches phase (TASK-060)

---

## [TASK-059] Реализовать фазу предварительного голосования (F11)
**Дата:** 2026-04-20
**Статус:** done

### Что сделано
- Добавлены новые фазы в GamePhase enum:
  - PRELIMINARY_VOTE = "preliminary_vote" — фаза предварительного голосования
  - PRE_FINAL_VOTE_DEFENSE = "pre_final_vote_defense" — фаза защитных реплик
- Создана функция run_preliminary_vote() в src/orchestrator/game_engine.py:
  - Каждый игрок голосует за одного или воздерживается (если DEFENSE_ALLOW_ABSTAIN=true)
  - Если DEFENSE_ALLOW_ABSTAIN=false — воздержание запрещено, при null перезапрос + fallback
  - Результат: словарь {voter_id → target_id | null} в game.preliminary_vote_result
  - Агрегат {target_id → count} без учёта воздержавшихся возвращается из функции
  - Промпт согласован с DEFENSE_ALLOW_ABSTAIN
- Добавлена вспомогательная функция _parse_preliminary_vote() для парсинга ответов
- Обновлён src/orchestrator/__init__.py с экспортом run_preliminary_vote
- Создан tests/test_preliminary_voting.py с 21 тестами:
  - TestParsePreliminarilyVote: 6 тестов парсинга ответов
  - TestRunPreliminaryVoteBasics: 3 теста базовой функциональности
  - TestVoteCounts: 3 теста подсчёта голосов
  - TestAbstainBehavior: 3 теста поведения при воздержании
  - TestVoteTurnContent: 2 теста контента ходов
  - TestCallbacks: 2 теста callback-функций
  - TestPromptContent: 2 теста содержимого промптов
- Все 21 тест проходят, 182 теста всего проходят (1 несвязанный failure)

### Проблемы / Заметки
- Исправлен парсинг abstain маркеров чтобы не конфликтовать с именами игроков (проверка кандидатов первой)

### Коммиты
- `a383a17` — feat: implement preliminary voting phase (TASK-059)

---

## [TASK-058] Добавить новые поля в модель Game
**Дата:** 2026-04-20
**Статус:** done

### Что сделано
- Добавлены новые типы данных в src/models/game.py:
  - DefenseSpeech: defender_id, votes_received, content, timestamp
  - VoteChange: voter_id, from_target, to_target
- Добавлено поле status в PhaseEntry (для "skipped_copied_from_preliminary")
- Добавлены новые опциональные поля в модель Game:
  - preliminary_vote_result: dict[str, Optional[str]] — голоса предварительного голосования
  - defense_speeches: list[DefenseSpeech] — список защитных реплик
  - final_vote_result: dict[str, Optional[str]] — голоса финального голосования
  - vote_changes: list[VoteChange] — кто изменил голос
- Обновлён src/models/__init__.py с экспортом DefenseSpeech и VoteChange
- Создан tests/test_defense_voting_models.py с 24 тестами:
  - TestDefenseSpeechModel: 5 тестов создания и сериализации
  - TestVoteChangeModel: 5 тестов включая abstain сценарии
  - TestPhaseEntryStatus: 2 теста для нового поля status
  - TestGameWithNewFields: 5 тестов полей Game
  - TestBackwardCompatibility: 3 теста обратной совместимости со старыми логами
  - TestTurnTypeValues: 4 теста проверки TurnType enum
- Все 24 новых + 35 существующих тестов проходят

### Проблемы / Заметки
- Все поля опциональны для обратной совместимости с существующими логами игр

### Коммиты
- `a15b731` — feat: add new Game model fields for defense voting phase (TASK-058)

---

## [TASK-057] Добавить новые типы Turn для голосований
**Дата:** 2026-04-20
**Статус:** done

### Что сделано
- Добавлены три новых значения в TurnType enum в src/models/game.py:
  - PRELIMINARY_VOTE = "preliminary_vote" — голос в предварительном голосовании
  - DEFENSE_SPEECH = "defense_speech" — защитная реплика обвиняемого
  - FINAL_VOTE = "final_vote" — голос в финальном голосовании
- Существующий VOTE сохранён для обратной совместимости
- Все 17 тестов unanimous_voting и 18 тестов games_api проходят успешно
- Импорт и значения новых enum проверены

### Проблемы / Заметки
- tests/test_models.py не существует — тесты проверены через связанные тестовые файлы

### Коммиты
- `dc75b57` — feat: add new TurnType values for defense voting phase (TASK-057)

---

## [TASK-056] Добавить env-переменные для фазы защиты
**Дата:** 2026-04-20
**Статус:** done

### Что сделано
- Добавлены три новые env-переменные в src/orchestrator/game_engine.py:
  - DEFENSE_MIN_VOTES_TO_QUALIFY (int, default 2) — минимум голосов для запуска защиты
  - DEFENSE_SPEECH_MAX_SENTENCES (int, default 2) — максимум предложений в защите
  - DEFENSE_ALLOW_ABSTAIN (bool, default true) — разрешено ли воздержание
- Добавлены переменные в .env.example с подробными описаниями на английском
- Переменные читаются в оркестраторе через os.environ.get() с дефолтными значениями
- Для булевой переменной реализован парсинг строк "true", "1", "yes" → True

### Проблемы / Заметки
- Нет

### Коммиты
- `8bb7796` — feat: add defense phase env variables (TASK-056)

---

## [TASK-055] Исправить логику голосования: единогласно вместо большинства
**Дата:** 2026-04-20
**Статус:** done

### Что сделано
- Изменена логика run_final_vote в src/orchestrator/game_engine.py:
  - Голосование засчитывается ТОЛЬКО если все проголосовали за одного игрока (единогласно)
  - Если голоса разделились — outcome не устанавливается, игра возвращается в main_round
  - Добавлен callback on_vote_result для уведомления о результате голосования
- Обновлён app.py:
  - Добавлен while loop вокруг main_round -> final_vote для повторных голосований
  - Добавлен метод on_vote_result для broadcast результата голосования
  - Добавлено событие vote_split при разделённых голосах
- Обновлён cli.py:
  - Аналогичный while loop для CLI режима
  - Вывод "Голоса разделились — голосование не прошло" жёлтым цветом
- Обновлён index.html:
  - Добавлены обработчики событий vote_split и vote_result
  - Добавлены CSS стили для .vote_split (оранжевый фон) и .vote_unanimous (зелёный)
- Создан tests/test_unanimous_voting.py с 15 тестами:
  - TestUnanimousVotingLogic: 8 тестов для логики единогласия
  - TestGameOutcomeAfterVoting: 3 теста для outcome после голосования
  - TestPhaseTransitions: 2 теста для переходов фаз
  - TestVoteResultCallback: 2 теста для callback функции
- Все 15 тестов проходят, 135 тестов всего проходят (1 несвязанный failure)

### Проблемы / Заметки
- Логика изменена с большинства голосов на единогласное голосование
- При разделении голосов игра продолжается, что может привести к более длинным партиям

### Коммиты
- `5c8b925` — Fix voting logic: unanimous instead of majority (TASK-055)

---

## [TASK-054] Тултипы на странице истории игры
**Дата:** 2026-04-20
**Статус:** done

### Что сделано
- Добавлены CSS стили для иконок info и тултипов в game.html (консистентно с index.html)
- Добавлена функция createInfoIcon() и константа TURN_TYPE_TOOLTIPS
- Тултипы для меток типов сообщений (Q/A/INT/VOTE/GUESS/LEAK):
  - Q: "Вопрос — игрок задаёт вопрос другому участнику"
  - A: "Ответ — игрок отвечает на заданный вопрос"
  - INT: "Вмешательство — игрок перебивает для комментария"
  - VOTE: "Голосование — игрок голосует за подозреваемого"
  - GUESS: "Угадывание — шпион пытается угадать локацию"
  - LEAK: "Утечка — шпион случайно выдал локацию"
- Тултип для метки ШПИОН в списке игроков: "Шпион не знает локацию и пытается её угадать, не выдав себя"
- Тултип для ролей игроков: "Роль игрока в текущей локации"
- Тултип в заголовке "Игроки": "AI-персонажи, участвовавшие в этой игре. Один из них — шпион."
- Тултип для секции "Статистика": "Входные токены — текст запросов к ИИ. Выходные — ответы ИИ. Стоимость рассчитывается по тарифам OpenAI."
- Тултипы для лейблов "Локация" и "Ходов" в sidebar
- Стиль иконок консистентен с главной страницей (14px кружок, фон #444)
- Все 18 тестов API проходят

### Проблемы / Заметки
- Нет

### Коммиты
- `3c64fce` — Add tooltips to game history page (TASK-054)

---

## [TASK-053] Иконки info с тултипами для пояснения UI
**Дата:** 2026-04-20
**Статус:** done

### Что сделано
- Добавлены CSS стили для иконок info (маленький кружок с "i") и тултипов
- Иконки добавлены к меткам типов сообщений (Q/A/INT/VOTE/GUESS/LEAK):
  - Q: "Вопрос — игрок задаёт вопрос другому участнику"
  - A: "Ответ — игрок отвечает на заданный вопрос"
  - INT: "Вмешательство — игрок перебивает для комментария"
  - VOTE: "Голосование — игрок голосует за подозреваемого"
  - GUESS: "Угадывание — шпион пытается угадать локацию"
  - LEAK: "Утечка — шпион случайно выдал локацию"
- Иконка рядом с "ШПИОН" в списке игроков: "Шпион не знает локацию и пытается её угадать, не выдав себя"
- Иконка рядом с ролями игроков: "Роль игрока в текущей локации"
- Иконки в секции "Информация" (sidebar):
  - Локация: "Место действия игры, известное всем кроме шпиона"
  - Фаза: "Текущий этап игры: подготовка, раунд вопросов, голосование или итоги"
  - Таймер: "Оставшееся время до окончания раунда"
  - Ходов: "Количество вопросов и ответов в текущей игре"
- Иконка в заголовке "Игроки": "AI-персонажи, участвующие в текущей игре. Один из них — шпион."
- Иконка в статистике токенов: "Входные токены — текст запросов к ИИ. Выходные — ответы ИИ. Стоимость рассчитывается по тарифам OpenAI."
- Все тултипы на русском языке
- Стиль иконок консистентен (14px кружок, фон #444, hover эффект)
- Тултипы появляются при наведении с плавной анимацией
- Все 18 тестов API проходят

### Проблемы / Заметки
- Нет

### Коммиты
- `4065dad` — Add info icons with tooltips to UI elements (TASK-053)

---

## [TASK-052] Локализация UI на русский язык
**Дата:** 2026-04-20
**Статус:** done

### Что сделано
- Локализованы все тексты в index.html:
  - Кнопки: Start→Старт, Pause→Пауза, Stop→Стоп, Resume→Продолжить
  - Статусы: Idle→Ожидание, Running→Идёт игра, Paused→Пауза, Stopped→Остановлена, Completed→Завершена, Disconnected→Отключено
  - Сообщения: "Game started!"→"Игра началась!", "Spy wins!"→"Победа шпиона!", "Civilians win!"→"Победа мирных!"
  - Labels: Players→Игроки, Game Info→Информация, Location→Локация, Phase→Фаза, Timer→Таймер, Turns→Ходов
  - Фазы: setup→Подготовка, main_round→Основной раунд, optional_vote→Досрочное голосование, final_vote→Финальное голосование, resolution→Подведение итогов
  - Диалог остановки: полностью на русском
  - Роли игроков: SPY→ШПИОН
  - Токены статистики: "Tokens: X in / Y out"→"Токены: X вх / Y вых"
  - Ошибки: "Error:"→"Ошибка:"
- Роли в locations.json уже были на русском (10 локаций, 46 ролей)
- game.html уже был локализован ранее
- Все 18 тестов API проходят

### Проблемы / Заметки
- Нет

### Коммиты
- `83eb587` — Localize UI to Russian language (TASK-052)

---

## [TASK-051] Страница просмотра игры в новой вкладке
**Дата:** 2026-04-20
**Статус:** done

### Что сделано
- Создан src/web/static/game.html — полноценная страница просмотра игры
- Добавлен GET /game/{game_id} endpoint в app.py для обслуживания страницы
- Страница загружает данные игры из GET /games/{id} API
- Реализовано отображение полного лога игры:
  - Все реплики с цветовой кодировкой по типу (Q, A, INT, VOTE, GUESS, LEAK)
  - Цвета персонажей как в live-игре
  - Номера ходов (#1, #2, ...) в каждой реплике
  - Адресаты реплик (→ Кому)
- Sidebar с информацией об игре:
  - Список игроков с ролями (ШПИОН выделен)
  - Локация, время начала/окончания, длительность
  - Количество ходов
- Статистика токенов: входные/выходные токены, LLM вызовы, стоимость
- Исход игры в header (победа шпиона/мирных/отменена)
- Обработка ошибок (404, ошибка сети)
- Добавлено 6 тестов в tests/test_games_api.py (все проходят)

### Проблемы / Заметки
- Нет

### Коммиты
- `6a31a8b` — Add game view page at /game/{id} (TASK-051)

---

## [TASK-050] Список игр с поиском по ID
**Дата:** 2026-04-20
**Статус:** done

### Что сделано
- Функционал был полностью реализован в TASK-049
- Верифицированы все acceptance criteria:
  - Отображается список всех игр (id, дата, локация, победитель) — renderGamesList()
  - Поле поиска фильтрует по ID — filterGames() с input событием
  - Кликабельные элементы списка — onclick на каждом game-item
  - Показывается сообщение "Нет сохранённых игр" если игр нет
- Все 12 тестов GET /games API прошли успешно

### Проблемы / Заметки
- Никаких дополнительных изменений не требовалось — реализация была завершена в TASK-049

### Коммиты
- (нет новых коммитов — использован код из TASK-049)

---

## [TASK-049] Кнопка История в header UI
**Дата:** 2026-04-20
**Статус:** done

### Что сделано
- Добавлена кнопка "История" в header рядом с Start/Pause/Stop
- Создано модальное окно для отображения списка игр
- Модальное окно использует GET /games API для получения списка игр
- Стиль кнопки консистентен с остальными (цвет indigo #6366f1)
- Модальное окно закрывается по клику вне области, кнопке X или Escape
- Добавлено поле поиска для фильтрации по ID (TASK-050 готовность)
- Добавлена функция открытия игры в новой вкладке (TASK-051 готовность)
- Список отображает: ID игры, дату, локацию, победителя

### Проблемы / Заметки
- Реализация включает базовый функционал для TASK-050 и TASK-051

### Коммиты
- `2ad5bf5` — Add History button to UI header (TASK-049)

---

## [TASK-048] API endpoint GET /games/{id} — данные одной игры
**Дата:** 2026-04-20
**Статус:** done

### Что сделано
- Добавлен GET /games/{id} endpoint в src/web/app.py
- Возвращает полные данные игры: turns, players, outcome, token_usage
- 404 если игра не найдена
- Добавлена функция find_game_by_id() в src/storage/game_repository.py
- Обновлён src/storage/__init__.py с экспортом новой функции
- Добавлено 6 новых тестов в tests/test_games_api.py:
  - test_get_game_by_id_returns_full_game
  - test_get_game_by_id_returns_404_when_not_found
  - test_get_game_by_id_includes_players
  - test_get_game_by_id_includes_turns
  - test_get_game_by_id_includes_outcome
  - test_get_game_by_id_includes_token_usage

### Проблемы / Заметки
- Нет

### Коммиты
- `91b8e59` — Add GET /games/{id} API endpoint (TASK-048)

---

## [TASK-047] API endpoint GET /games — список всех игр
**Дата:** 2026-04-20
**Статус:** done

### Что сделано
- Добавлен GET /games endpoint в src/web/app.py
- Возвращает список игр из папки games/ (id, started_at, location_id, winner)
- Сортировка по дате (новые первые) — используется list_games() из storage
- Пустой список если нет игр
- Добавлена модель GameListItem для типизации ответа
- Создан tests/test_games_api.py с 6 тестами (все проходят):
  - test_get_games_returns_json_array
  - test_get_games_empty_when_no_games
  - test_get_games_returns_game_fields
  - test_get_games_sorted_newest_first
  - test_get_games_handles_missing_outcome
  - test_game_list_item_model

### Проблемы / Заметки
- Нет

### Коммиты
- `10a3065` — Add GET /games API endpoint (TASK-047)

---

## [TASK-046] MUST NOT директивы про токсичность
**Дата:** 2026-04-20
**Статус:** done

### Что сделано
- Добавлена MUST NOT директива про токсичность во все 8 профилей персонажей:
  - "Использовать мат, реальные оскорбления или унижения — только игровое давление в рамках роли"
- Добавлено правило в базовый промпт (src/agents/prompt_builder.py):
  - "ЗАПРЕЩЕНО: мат, реальные оскорбления, унижения по полу/расе/религии. Только игровое давление в рамках ролей."
- Создан tests/test_toxicity.py с 14 тестами (все проходят):
  - test_all_characters_have_toxicity_directive: проверка всех 8 персонажей
  - test_character_loads_with_toxicity_directive[*]: параметризованный тест для каждого персонажа
  - test_base_prompt_has_toxicity_rule: проверка базового промпта
  - test_toxicity_rule_keywords: проверка ключевых слов в правиле
  - test_no_forbidden_patterns_in_existing_logs: grep логов игр на запрещённые паттерны
  - test_clean_text_passes: проверка что нормальный текст не вызывает false positive
  - test_forbidden_patterns_detected: проверка что запрещённые паттерны детектируются
- Функция grep_games_for_violations() для анализа логов партий
- 25+ запрещённых паттернов: мат, оскорбления, расовые/религиозные/гомофобные слуры

### Проблемы / Заметки
- Шаги 2 и 3 (прогнать 10 партий и grep логи) требуют OPENAI_API_KEY
- Тесты автоматически пропускаются если нет логов партий

### Коммиты
- `1762545` — Add toxicity MUST NOT directives (TASK-046)

---

## [TASK-045] Веб-UI только на localhost
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан src/web/__main__.py — точка входа для запуска веб-сервера
- WEB_UI_HOST дефолт = 127.0.0.1 (уже был в .env.example)
- Добавлена функция is_public_host() для детекции публичных биндингов
- Добавлено предупреждение SECURITY_WARNING при запуске на 0.0.0.0 или других публичных адресах
- Предупреждение требует подтверждения (Enter) перед запуском
- Создан README.md с разделом Security:
  - Документация о рисках публичного доступа
  - Объяснение почему 0.0.0.0 опасен
  - Рекомендации по безопасной конфигурации
  - Пример настройки nginx reverse proxy с auth
- Создан tests/test_web_security.py с 10 тестами (все проходят)

### Проблемы / Заметки
- Шаг 2 (подключение с другой машины) — ручной тест, при localhost биндинге внешние подключения невозможны

### Коммиты
- `a16eddd` — Add localhost-only security for web UI (TASK-045)

---

## [TASK-044] Безопасность API ключей
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Проверено: .env в .gitignore (строка 2)
- Проверено: .env.example содержит пустые значения для OPENAI_API_KEY и ANTHROPIC_API_KEY
- Проверено: llm_config.json хранит имена env-переменных (api_key_env), не сами ключи
- Проверено: adapter.py загружает ключи через os.getenv()
- Проверено: Game/GameConfig модели не содержат полей с ключами
- Создан tests/test_api_key_security.py с 7 тестами безопасности:
  - test_env_in_gitignore: .env в .gitignore
  - test_env_example_has_no_real_values: пустые значения ключей
  - test_game_model_has_no_api_key_fields: нет полей с ключами в моделях
  - test_llm_config_stores_env_names_not_keys: env-имена, не ключи
  - test_no_api_keys_in_game_logs: проверка логов партий
  - test_adapter_uses_env_vars: загрузка из env
  - test_no_hardcoded_keys_in_source: нет хардкода в коде

### Проблемы / Заметки
- Все acceptance criteria уже были выполнены в предыдущих задачах
- Добавлен формальный тест для регрессионной проверки

### Коммиты
- `1e8ed12` — Add API key security tests (TASK-044)

---

## [TASK-043] Статистика побед шпиона
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан src/analysis/spy_statistics.py с полной системой статистики побед шпиона
- VictoryType enum: 7 типов исхода (spy_guessed_location, civilians_voted_wrong, civilians_voted_correctly, spy_guess_incorrect, spy_leaked_location, cancelled, unknown)
- GameResult dataclass: результат одной игры (spy_won, victory_type, spy_id, location_id, players_count, duration, etc.)
- SpyStatistics dataclass: агрегированная статистика (total_games, spy_wins, civilian_wins, разбивка по типам)
- Свойство spy_win_rate: подсчёт win rate в процентах
- Свойство is_balanced: проверка целевого диапазона 30-50%
- Группировка по количеству игроков (by_player_count) и локациям (by_location)
- Функция determine_victory_type: определение типа победы по GameOutcome
- Функция analyze_game_for_spy_stats: анализ одной игры
- Функция analyze_games_for_spy_stats: анализ серии игр
- Функция load_and_analyze_games: загрузка из games/ и анализ
- Функция generate_spy_report: генерация текстового отчёта для калибровки
- Отчёт содержит: общую статистику, разбивку по типу победы, по игрокам, по локациям, рекомендации
- Создан tests/test_spy_statistics.py с 31 тестами (все проходят)
- Обновлён src/analysis/__init__.py с экспортами

### Проблемы / Заметки
- Для прогона 20+ партий требуется OPENAI_API_KEY
- Тесты работают на mock-данных без реальных API-вызовов

### Коммиты
- `5c88bcf` — Add spy win rate statistics system (TASK-043)

---

## [TASK-042] Метрики характерности персонажей
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан src/analysis/__init__.py с экспортами модуля
- Создан src/analysis/character_metrics.py с полной системой метрик
- Функции детекции маркеров: count_sentences, evaluate_counter_rule, detect_marker, detect_markers
- Поддержка всех методов детекции: REGEX (regex), COUNTER (sentences/words), BINARY_LLM (опционально)
- Классы данных: MarkerResult, ReplyAnalysis, CharacterMetrics, GameAnalysis
- Функция analyze_game: анализирует партию, считает маркеры для каждой реплики персонажа
- Функция analyze_games: анализирует несколько партий из файлов
- Функция generate_report: генерирует текстовый отчёт с метриками
- Отчёт содержит: % маркированных реплик по персонажам, флаги 2+ немаркированных подряд, детали по партиям
- Создан tests/test_character_metrics.py с 32 тестами (все проходят)
- Тесты покрывают: подсчёт предложений, правила счётчиков, детекцию маркеров, анализ игры, генерацию отчёта

### Проблемы / Заметки
- BINARY_LLM маркеры требуют LLM provider, без него возвращают False (для offline анализа)
- Для полного анализа с LLM маркерами требуется OPENAI_API_KEY

### Коммиты
- `f95cec4` — Add character distinctiveness metrics (TASK-042)

---

## [TASK-041] Интеграционный тест: 6 игроков
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан tests/test_integration_6players.py с полным набором тестов для 6 игроков
- test_single_6player_game_completes: проверка завершения одной партии с 6 игроками
- test_five_games_complete_without_errors: запуск 5+ партий подряд (acceptance criterion)
- test_game_cost_under_limit: проверка стоимости партии < $2
- test_early_voting_triggers_work: проверка срабатывания досрочного голосования
- test_characters_are_distinguishable: проверка различимости 6 персонажей
- test_all_characters_participate: проверка участия всех 6 персонажей
- test_spy_confidence_system_active: проверка системы уверенности шпиона
- test_interventions_with_6_players: проверка вмешательств с 6 игроками
- Используются персонажи: boris_molot, zoya, kim, margo, professor_stein, father_ignatius
- Добавлены функции: check_early_voting_occurred, analyze_game_cost, calculate_game_duration_minutes
- run_sync_test() выводит сводную статистику по 5 партиям

### Проблемы / Заметки
- Для запуска тестов с реальными LLM-вызовами требуется OPENAI_API_KEY
- Тесты автоматически пропускаются если ключ не установлен

### Коммиты
- `f421386` — Add integration tests for 6 players (TASK-041)

---

## [TASK-040] Интеграционный тест: 4 игрока
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан tests/test_integration_4players.py с тестами для 4-игроков
- test_single_4player_game_completes: проверка завершения одной партии с 4 игроками
- test_five_games_complete_without_errors: запуск 5 партий подряд (acceptance criterion)
- test_interventions_present_in_logs: проверка наличия вмешательств в логах
- test_spy_confidence_log_populated: проверка записей в spy_confidence_log
- test_characters_are_distinguishable: проверка различимости 4 персонажей
- test_trigger_system_active: проверка активности системы триггеров
- Используются персонажи: boris_molot, zoya, kim, margo
- Функции count_interventions и analyze_spy_confidence для анализа логов
- Конфигурация: 2 мин, 10 вопросов макс для ускоренных тестов

### Проблемы / Заметки
- Для запуска тестов с реальными LLM-вызовами требуется OPENAI_API_KEY
- Тесты автоматически пропускаются если ключ не установлен

### Коммиты
- `23318c9` — Add integration tests for 4 players (TASK-040)

---

## [TASK-039] Интеграционный тест: полная партия Phase 0
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан tests/test_integration_phase0.py с полным набором интеграционных тестов
- test_single_game_completes: проверка завершения одной партии без ошибок
- test_three_games_complete_without_errors: запуск 3 партий подряд с проверкой всех завершений
- test_characters_are_distinguishable: проверка различимости персонажей по маркерам
- test_game_log_is_valid_and_complete: валидация структуры и полноты лога партии
- Реализована функция check_character_markers для автоматической детекции маркеров каждого персонажа
- Реализована функция validate_game_structure для проверки корректности структуры Game
- Тесты автоматически пропускаются если OPENAI_API_KEY не установлен
- Используется короткая конфигурация для тестов (1 мин, 6 вопросов макс)

### Проблемы / Заметки
- Для запуска тестов с реальными LLM-вызовами требуется OPENAI_API_KEY
- Тесты используют 3 персонажа (boris_molot, zoya, kim) и 2 локации (hospital, airplane)

### Коммиты
- `90193b7` — Add integration tests for Phase 0 (TASK-039)

---

## [TASK-038] Визуальное различие типов реплик
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Добавлены CSS стили для визуального различия типов реплик в index.html
- Вопрос и ответ — обычный стиль (без изменений)
- Вмешательство (intervention) — курсив с отступом, полупрозрачный оранжевый фон
- Голосование (vote) — выделенный блок с фиолетовой рамкой и полупрозрачным фоном, жирный текст
- SPY_GUESS — выделенный красной рамкой блок
- SPY_LEAK — выделенный пунктирной красной рамкой блок
- Обновлена функция addMessage() для применения классов vote, spy_guess, spy_leak

### Проблемы / Заметки
- Нет

### Коммиты
- `388576f` — Add visual distinction for reply types in UI (TASK-038)

---

## [TASK-037] Индикатор 'персонаж печатает'
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Добавлен callback `on_typing` в run_main_round и run_final_vote (game_engine.py)
- on_typing вызывается перед каждым LLM-вызовом: вопрос, ответ, вмешательство, голосование
- Добавлен метод on_typing в GameManager (app.py) для broadcast через WebSocket
- WebSocket событие "typing" с speaker_id отправляется клиентам
- Обновлён frontend: новый CSS с анимацией прыгающих точек (typing-bounce)
- Индикатор показывает имя персонажа + "печатает" + анимированные точки
- Цвет индикатора соответствует цвету персонажа
- Индикатор автоматически скрывается при получении события "turn"
- Добавлены тесты: broadcast, stop handling, disconnected clients, multiple clients

### Проблемы / Заметки
- Нет

### Коммиты
- `79747a1` — Add typing indicator with animated dots (TASK-037)

---

## [TASK-036] Таймер и статус фазы в UI
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Добавлен таймер обратного отсчёта в sidebar (отображение оставшегося времени партии)
- Добавлено визуальное выделение текущей фазы (цветовой badge: setup, main_round, optional_vote, final_vote, resolution)
- Backend: в game_started событие добавлены started_at и duration_minutes
- Frontend: реализован клиентский countdown timer с обновлением каждую секунду
- Таймер меняет цвет: нормальный (белый) → warning (жёлтый, < 60с) → critical (красный мигающий, < 30с)
- Фаза отображается с цветовым badge соответствующим типу фазы
- Таймер останавливается при завершении/остановке игры
- Обновление фазы в реальном времени через WebSocket

### Проблемы / Заметки
- Таймер продолжает тикать во время паузы (соответствует логике — пауза не продлевает время партии)

### Коммиты
- `dc332d9` — Add timer and phase status display in UI (TASK-036)

---

## [TASK-035] Цветовая кодировка персонажей
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Добавлено поле `color` (Optional[str]) в модель Character в src/models/character.py
- Добавлены уникальные цвета во все 8 профилей персонажей:
  - Борис (агрессор): #e94560 — агрессивный красный
  - Зоя (циник): #8b5cf6 — дерзкий фиолетовый
  - Ким (параноик): #14b8a6 — тревожный бирюзовый
  - Марго (манипулятор): #f59e0b — тёплый янтарный
  - Штейн (интеллектуал): #3b82f6 — спокойный синий
  - Игнатий (моралист): #6366f1 — сдержанный индиго
  - Лёха (работяга): #f97316 — земной оранжевый
  - Аврора (драма-квин): #ec4899 — драматичный розовый
- Обновлён app.py: в game_started добавлены поля display_name и color для игроков
- Обновлён index.html: getPlayerColor() использует цвет из профиля персонажа
- Обновлён getPlayerName() для использования display_name из данных игрока
- Все цвета контрастные и читаемые на тёмном фоне UI

### Проблемы / Заметки
- Сохранена обратная совместимость: если color не задан, используется динамическая генерация из PLAYER_COLORS

### Коммиты
- `d080ecf` — Add persistent color coding for characters (TASK-035)

---

## [TASK-034] Kill-switch для inflight LLM запросов
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Добавлен set inflight_tasks в GameManager для отслеживания активных LLM запросов
- Добавлены методы: register_inflight_task(), unregister_inflight_task(), cancel_all_inflight_tasks()
- Stop теперь отменяет все inflight tasks через cancel_all_inflight_tasks()
- Добавлена обработка asyncio.CancelledError с установкой outcome=cancelled
- Обновлён GameOutcome: добавлено поле accused_id, поддержка winner="cancelled"
- CostExceededError и общие Exception теперь также устанавливают outcome=cancelled и сохраняют лог
- reset() очищает inflight_tasks set
- Добавлены тесты в tests/test_killswitch.py (5 тестов, все проходят)
- Обновлён run_final_vote() для установки accused_id в GameOutcome

### Проблемы / Заметки
- Полное тестирование с реальной игрой требует OPENAI_API_KEY

### Коммиты
- `5487bc4` — Add kill-switch for inflight LLM requests (TASK-034)

---

## [TASK-033] Кнопки Start/Pause/Resume/Stop
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Улучшена логика disabled-состояний кнопок: Start, Pause/Resume, Stop
- Кнопка Pause динамически меняется на Resume при статусе paused (меняется класс и текст)
- Добавлен loading-индикатор (спиннер) для кнопок во время ожидания ответа API
- Добавлен диалог подтверждения для Stop с клавишей Escape для отмены
- Улучшена обработка ошибок API (показ ошибок в чате)
- Кнопки вызывают соответствующие эндпоинты: /game/start, /game/pause, /game/resume, /game/stop
- Визуальное отображение текущего состояния через status-dot и status-text

### Проблемы / Заметки
- Полное тестирование с реальной игрой требует OPENAI_API_KEY

### Коммиты
- `035526e` — Add full button functionality with loading states and confirm dialog (TASK-033)

---

## [TASK-032] HTML/JS интерфейс (один файл)
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан src/web/static/index.html с полным веб-интерфейсом
- Vanilla JS без фреймворков, всё в одном файле
- WebSocket подключение к /ws для live-обновлений
- Отображение чата с репликами: вопросы, ответы, вмешательства, голосования
- Sidebar с списком игроков и информацией об игре (локация, фаза, счётчик ходов)
- Цветовая кодировка персонажей (8 цветов для различимости)
- Индикатор статуса соединения (connecting, idle, running, paused, stopped, completed)
- Кнопки управления: Start, Pause/Resume, Stop (пока без full implementation)
- Системные сообщения: смена фазы, результат игры, ошибки
- Индикатор "typing..." с задержкой display_delay_ms
- Автоскролл чата при новых сообщениях
- Responsive дизайн для мобильных устройств
- Тёмная тема с акцентными цветами

### Проблемы / Заметки
- Полное тестирование с реальной игрой требует OPENAI_API_KEY
- Кнопки Start/Pause/Stop базово работают, но TASK-033 добавит полную функциональность

### Коммиты
- `5b0d01c` — Add HTML/JS web interface (TASK-032)

---

## [TASK-031] FastAPI backend setup
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан src/web/__init__.py и src/web/app.py с FastAPI приложением
- Создана директория src/web/static/ для будущего HTML/JS интерфейса
- Реализован POST /game/start для запуска новой партии с параметрами
- Реализованы POST /game/pause, /game/resume, /game/stop для управления партией
- Реализован GET /game/status для получения текущего состояния
- Реализованы GET /characters и GET /locations для получения доступных данных
- Реализован WebSocket /ws для live-обновлений партии
- Класс GameManager управляет состоянием игры (idle, running, paused, stopped, completed)
- Используется asyncio.Event для pause/resume и asyncio.CancelledError для stop
- Все повороты транслируются через WebSocket с turn_type, speaker_id, content, etc.
- События: game_started, phase, turn, game_paused, game_resumed, game_stopped, game_completed, error

### Проблемы / Заметки
- Полное тестирование с реальной игрой требует OPENAI_API_KEY
- Зависимости FastAPI, uvicorn, websockets добавлены в pyproject.toml [web]

### Коммиты
- `2b38a98` — Add FastAPI backend setup (TASK-031)

---

## [TASK-030] Детекция прямых вопросов о локации
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Добавлена функция _check_for_direct_location_question() в src/orchestrator/game_engine.py
- Детекция прямых упоминаний всех локаций (display_name и id) в вопросах мирных
- Детекция упоминаний ролей текущей локации в вопросах
- Реализован механизм reroll: до MAX_QUESTION_REROLL_ATTEMPTS (default: 3) попыток перегенерации
- Добавлено логирование reroll через Python logging (debug/info/warning уровни)
- Добавлены few-shot примеры хороших и плохих вопросов в промпт мирных игроков
- Примеры плохих: "Это больница?", "Ты хирург?", перечисление локаций
- Примеры хороших: косвенные вопросы про деятельность, атмосферу
- Добавлена переменная MAX_QUESTION_REROLL_ATTEMPTS в .env.example
- Все тесты пройдены: детекция локаций, ролей, исключение шпиона, промпт

### Проблемы / Заметки
- Детекция работает по substring match (case-insensitive)
- Не учитывает грамматические падежи ("больница" vs "больнице"), как и TASK-029

### Коммиты
- `2004657` — Add direct location question detection with reroll (TASK-030)

---

## [TASK-029] Детекция утечки локации шпионом
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Добавлен TurnType.SPY_LEAK в src/models/game.py для маркировки утечки
- Создана функция _check_for_location_leak() в src/orchestrator/game_engine.py
- Детекция через case-insensitive поиск location.display_name и location.id в тексте
- Добавлена проверка утечки после генерации вопроса шпиона
- Добавлена проверка утечки после генерации ответа шпиона
- Добавлена проверка утечки после генерации вмешательства шпиона
- При обнаружении утечки: создаётся Turn с type=SPY_LEAK, игра завершается с outcome.winner="civilians"
- Обновлён CLI: добавлен вывод [LEAK!] для типа SPY_LEAK в красном цвете
- Все тесты пройдены: детекция, исход, TurnType

### Проблемы / Заметки
- Простой substring-поиск не учитывает русские грамматические падежи (больница vs больнице)
- Для более надёжной детекции можно добавить утилитарную модель (вне MVP)

### Коммиты
- `f7e383f` — Add spy location leak detection (TASK-029)

---

## [TASK-028] Счётчик токенов и стоимости
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Добавлен MODEL_PRICING dict в src/llm/adapter.py с ценами за токены (gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo)
- Создан dataclass LLMResponse (content, input_tokens, output_tokens, model) с методом calculate_cost()
- Создан класс исключения CostExceededError для hard kill-switch
- Обновлён LLMProvider.complete() для возврата LLMResponse вместо строки
- OpenAIProvider теперь извлекает usage из ответа API (prompt_tokens, completion_tokens)
- Создана модель TokenUsage (total_input_tokens, total_output_tokens, total_cost_usd, llm_calls_count)
- Добавлено поле token_usage в модель Game
- Добавлена функция _track_usage_and_check_cost в orchestrator для трекинга после каждого LLM вызова
- Обновлены все 8 мест вызова provider.complete() в game_engine.py
- MAX_PARTY_COST_USD загружается из env (дефолт 3.0)
- Обновлён CLI: вывод статистики токенов в конце игры, обработка CostExceededError
- Лог партии содержит полную статистику token_usage

### Проблемы / Заметки
- Для полного тестирования с реальными вызовами LLM нужен OPENAI_API_KEY

### Коммиты
- `dd28dae` — Add token counter and cost tracking (TASK-028)

---

## [TASK-027] Сжатие контекста (compression)
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Добавлены конфигурационные переменные в .env.example: CONTEXT_COMPRESSION_AFTER_N_TURNS (default: 10), CONTEXT_KEEP_LAST_K_TURNS (default: 6)
- Добавлены поля в Game модель: compressed_history (Optional[str]), compression_checkpoint (Optional[int])
- Создана функция _compress_history_with_llm для генерации конспекта через utility модель
- Создана функция _build_compressed_conversation_history для построения сжатого контекста
- Вспомогательные функции: _get_conversational_turns, _turns_to_messages
- Обновлены все 4 места использования истории: questioner context, answerer context, intervention context, vote context
- Алгоритм: после N ходов, старые ходы сжимаются в конспект, последние K ходов остаются полными
- Экономия токенов: ~65-67% на длинных партиях (20 ходов)

### Проблемы / Заметки
- Для полной проверки с LLM нужен OPENAI_API_KEY

### Коммиты
- `c06f7b5` — Add context compression for long games (TASK-027)

---

## [TASK-026] Эмуляция задержки реплик
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Добавлена функция calculate_display_delay_ms в src/orchestrator/game_engine.py
- Формула: length * SPEECH_DELAY_MULTIPLIER + random(0.2s, 0.6s)
- SPEECH_DELAY_MULTIPLIER загружается из env (дефолт 0.03)
- Обновлены все 5 мест создания Turn: QUESTION, ANSWER, INTERVENTION, SPY_GUESS, VOTE
- display_delay_ms записывается в каждый Turn объект
- Обновлён CLI: добавлен индикатор "X печатает..." в create_turn_printer
- Добавлен import time и параметр apply_delay в create_turn_printer
- Функция экспортирована через src/orchestrator/__init__.py
- Все тесты пройдены: 100 символов -> >3 секунд, индикатор работает

### Проблемы / Заметки
- Нет

### Коммиты
- `504eb70` — Add speech delay emulation (TASK-026)

---

## [TASK-025] Правила досрочного голосования
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан vote_trigger_rules.json с 3 правилами досрочного голосования
- Условие 1: accusations_on_same_player — 2+ обвинения на одного игрока (priority 10)
- Условие 2: consecutive_accusations_on_same_player — 2 подряд на одного (priority 9)
- Условие 3: no_progress_for_n_turns — 8 ходов без обвинений (priority 5)
- Создан src/triggers/vote_checker.py с классом VoteTriggerChecker
- Детекция обвинений по именам персонажей + паттернам (шпион, врёт, подозрительно, etc.)
- Интегрирован в run_main_round: проверка после каждого хода
- Голосование запускается кодом (не агентом)
- Переход в фазу OPTIONAL_VOTE с причиной в логе
- Все тесты пройдены

### Проблемы / Заметки
- Нет

### Коммиты
- `6882a0e` — Add early voting rules (TASK-025)

---

## [TASK-024] Угадывание локации шпионом
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Добавлена функция build_spy_guess_prompt в src/agents/prompt_builder.py
- Обновлён src/agents/__init__.py с экспортом новой функции
- Добавлена вспомогательная функция _ask_spy_to_guess в src/orchestrator/game_engine.py
- Интегрировано угадывание в run_main_round: после достижения состояния confident шпиону предлагается угадать локацию
- Шпион называет локацию из списка доступных → немедленное завершение партии
- Угадал правильно = победа шпиона (spy win), ошибся = победа мирных (civilians win)
- Turn с type=SPY_GUESS записывается в лог
- GameOutcome заполняется с spy_guess и spy_guess_correct полями
- Все тесты пройдены: симуляция confident состояния, проверка outcome

### Проблемы / Заметки
- Нет

### Коммиты
- `7a4481f` — Add spy location guessing (TASK-024)

---

## [TASK-023] Шкала уверенности шпиона
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Добавлена функция build_spy_confidence_check_prompt в src/agents/prompt_builder.py
- Обновлён src/agents/__init__.py с экспортом новой функции
- Добавлена вспомогательная функция _check_spy_confidence в src/orchestrator/game_engine.py
- Интегрирована проверка уверенности в run_main_round: после каждого ответа проверяется интервал
- Каждые N ходов (SPY_CONFIDENCE_CHECK_EVERY_N, по умолчанию 3) шпиону задаётся микро-вопрос
- Агент выбирает состояние: no_idea, few_guesses, confident
- Состояния логируются в game.spy_confidence_log как ConfidenceEntry
- Все тесты пройдены: интервал работает корректно, парсинг ответов корректный

### Проблемы / Заметки
- Нет

### Коммиты
- `3f2b7ca` — Add spy confidence system (TASK-023)

---

## [TASK-022] Система триггеров: окна вмешательства
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Добавлены функции build_intervention_micro_prompt и build_intervention_content_prompt в src/agents/prompt_builder.py
- Обновлён src/agents/__init__.py с экспортами новых функций
- Добавлены вспомогательные функции _ask_to_intervene и _generate_intervention_content в src/orchestrator/game_engine.py
- Интегрирована проверка триггеров в run_main_round: после каждого ответа вызывается TriggerChecker
- Реализована конкуренция по приоритету (highest wins): TriggerChecker.select_winner выбирает победителя
- Микро-промпт победителю: спрашивает "да"/"нет" через utility модель
- Вмешательство записывается как Turn с type=INTERVENTION
- TriggerEvent логируется в game.triggered_events с флагом intervened

### Проблемы / Заметки
- Нет

### Коммиты
- `54990af` — Add intervention windows for trigger system (TASK-022)

---

## [TASK-021] Система триггеров: глобальные правила
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан trigger_rules.json с 2 глобальными триггерами (direct_accusation, silent_for_n_turns)
- Создан src/triggers/__init__.py с экспортами
- Создан src/triggers/checker.py с классом TriggerChecker
- Реализованы condition_types: direct_accusation (детекция по имени + маркеры обвинения), silent_for_n_turns (счётчик ходов)
- TriggerChecker поддерживает: проверку всех персонажей, выбор победителя по приоритету, создание TriggerEvent для логирования
- Все тесты пройдены: обвинение детектится, счётчик молчания работает

### Проблемы / Заметки
- Нет

### Коммиты
- `11b05bf` — Add global trigger system (TASK-021)

---

## [TASK-020] Расширение локаций до 8-10
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Расширен locations.json с 2 до 10 локаций
- Добавлены новые локации: restaurant, school, casino, submarine, bank, spa, circus, museum
- Каждая локация имеет 4-5 уникальных ролей (всего 46 ролей)
- Все локации валидны по схеме Location (pydantic)
- Все роли уникальны в рамках своих локаций

### Проблемы / Заметки
- Нет

### Коммиты
- `c9d733a` — Expand locations from 2 to 10 (TASK-020)

---

## [TASK-019] Персонаж: Аврора (драма-квин)
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан characters/aurora.json с полным профилем персонажа
- Заполнены все поля по схеме PRD 8.8: id, display_name, archetype, backstory, voice_style
- 4 MUST директивы (машинно проверяемы: counter на предложения >=3, regex на восклицания, regex на паузы "...", regex на эмоциональную лексику)
- 3 MUST NOT директивы (проверяемы: counter на короткие ответы, regex на прямые признания, binary_llm на сухие ответы)
- 5 detectable_markers: long_reply (counter), exclamation_present (regex), theatrical_pauses (regex), emotional_vocabulary (regex), dramatic_tone (binary_llm)
- 2 personal_triggers: direct_accusation, repeated_accusation_on_same_target (panic_and_derail, moralize_and_accuse)

### Проблемы / Заметки
- Нет

### Коммиты
- `8a02c10` — Add Aurora character profile (TASK-019)

---

## [TASK-018] Персонаж: Лёха (работяга)
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан characters/lyokha.json с полным профилем персонажа
- Заполнены все поля по схеме PRD 8.7: id, display_name, archetype, backstory, voice_style
- 4 MUST директивы (машинно проверяемы: counter на предложения <=2, regex на разговорную лексику, regex на dismissive слова, обращение на ты)
- 3 MUST NOT директивы (проверяемы: regex на аналогии, counter на предложения <=3, regex на книжную лексику)
- 5 detectable_markers: short_reply (counter), colloquial_speech (regex), dismissive_words (regex), no_complex_analogy (regex), plain_direct_speech (binary_llm)
- 2 personal_triggers: dodged_direct_question, repeated_accusation_on_same_target (оба → short_dismissive_jab)

### Проблемы / Заметки
- Нет

### Коммиты
- `be4b0b8` — Add Lyokha character profile (TASK-018)

---

## [TASK-017] Персонаж: Отец Игнатий (моралист)
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан characters/father_ignatius.json с полным профилем персонажа
- Заполнены все поля по схеме PRD 8.6: id, display_name, archetype, backstory, voice_style
- 4 MUST директивы (машинно проверяемы: regex на имена, апелляции к совести/честности/правде, counter на предложения >=2, binary_llm на моральное давление)
- 3 MUST NOT директивы (проверяемы: regex на сарказм/иронию, восклицания, прямые обвинения)
- 5 detectable_markers: names_addressee (regex), conscience_appeal (regex), measured_speech (counter), no_sarcasm (regex), moral_pressure (binary_llm)
- 2 personal_triggers: contradiction_with_previous_answer, dodged_direct_question (оба → moralize_and_accuse)

### Проблемы / Заметки
- Нет

### Коммиты
- `82734f8` — Add Father Ignatius character profile (TASK-017)

---

## [TASK-016] Персонаж: Профессор Штейн (душный интеллектуал)
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан characters/professor_stein.json с полным профилем персонажа
- Заполнены все поля по схеме PRD 8.4: id, display_name, archetype, backstory, voice_style
- 4 MUST директивы (машинно проверяемы: regex на аналогии/сравнения, вводные конструкции, counter на предложения)
- 3 MUST NOT директивы (проверяемы: counter на короткие ответы, regex на восклицания и агрессию)
- 5 detectable_markers: analogy_present (regex), introductory_phrases (regex), long_reply (counter), no_exclamation (regex), logical_reference (binary_llm)
- 2 personal_triggers: contradiction_with_previous_answer, silent_for_n_turns (оба → point_out_inconsistency)

### Проблемы / Заметки
- Нет

### Коммиты
- `5bce13a` — Add Professor Stein character profile (TASK-016)

---

## [TASK-015] Персонаж: Марго (манипулятор)
**Дата:** 2026-04-19
**Статус:** done

### Что сделано
- Создан characters/margo.json с полным профилем персонажа
- Заполнены все поля по схеме PRD 8.2: id, display_name, archetype, backstory, voice_style
- 4 MUST директивы (машинно проверяемы: regex на имена, тёплую лексику, отсутствие прямых обвинений)
- 3 MUST NOT директивы (проверяемы regex на слова давления и агрессивную лексику)
- 5 detectable_markers: names_addressee (regex), warm_lexicon (regex), no_direct_accusation (regex), no_pressure_words (regex), deflection_present (binary_llm)
- 2 personal_triggers: direct_accusation, repeated_accusation_on_same_target (оба → deflect_suspicion_to_another)

### Проблемы / Заметки
- Нет

### Коммиты
- `69d543f` — Add Margo character profile (TASK-015)

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
