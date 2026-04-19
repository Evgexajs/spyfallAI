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
