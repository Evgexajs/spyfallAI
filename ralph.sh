#!/bin/bash
set -e

TASKS_FILE="${1:-tasks.json}"

if [[ ! -f "$TASKS_FILE" ]]; then
    echo "Файл задач не найден: $TASKS_FILE" >&2
    exit 1
fi

echo "Работаю по: $TASKS_FILE"
RESULT_FILE=$(mktemp -t ralph_result.XXXXXX)

# Cleanup при выходе
cleanup() {
    rm -f "$RESULT_FILE"
}
trap cleanup EXIT

# Спиннер с таймером
show_spinner() {
    local pid=$1
    local spin='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    local i=0
    local start=$SECONDS

    while kill -0 "$pid" 2>/dev/null; do
        local elapsed=$((SECONDS - start))
        printf "\r  [%s] Работаю... %02d:%02d " "${spin:i++%10:1}" $((elapsed/60)) $((elapsed%60))
        sleep 0.1
    done
    printf "\r%-50s\n" ""  # очистить строку
}

# Agent selection:
# - Set RALPH_AGENT=claude or RALPH_AGENT=codex to force.
# - Otherwise auto-detect (prefers Claude if available).
resolve_agent() {
    if [[ -n "${RALPH_AGENT:-}" ]]; then
        echo "$RALPH_AGENT"
        return 0
    fi
    if command -v claude >/dev/null 2>&1; then
        echo "claude"
        return 0
    fi
    if command -v codex >/dev/null 2>&1; then
        echo "codex"
        return 0
    fi
    return 1
}

run_agent() {
    local agent="$1"
    local prompt="$2"

    case "$agent" in
        claude)
            claude --permission-mode bypassPermissions -p "$prompt"
            ;;
        codex)
            local output_file
            output_file="$(mktemp -t ralph_codex.XXXXXX)"
            # Use non-interactive Codex exec and capture only the last message.
            codex exec --full-auto --color never -C "$PWD" --output-last-message "$output_file" "$prompt" >/dev/null
            cat "$output_file"
            rm -f "$output_file"
            ;;
        *)
            echo "Unsupported agent: $agent" >&2
            return 1
            ;;
    esac
}

# Функция проверки наличия pending задач
has_pending_tasks() {
    local pending_count
    pending_count=$(grep -c '"status": "pending"' "$TASKS_FILE" 2>/dev/null) || pending_count=0
    [[ "$pending_count" -gt 0 ]]
}

iteration=1

while has_pending_tasks; do
    echo "Итерация $iteration"
    echo "-----------------------------------"

    # Показываем текущий статус задач
    pending=$(grep -c '"status": "pending"' "$TASKS_FILE" 2>/dev/null) || pending=0
    done_count=$(grep -c '"status": "done"' "$TASKS_FILE" 2>/dev/null) || done_count=0
    echo "Задач pending: $pending, done: $done_count"
    echo "-----------------------------------"

    agent=$(resolve_agent) || {
        echo "Не найден поддерживаемый агент. Установите 'claude' или 'codex', либо задайте RALPH_AGENT." >&2
        exit 1
    }

    echo "Запускаю $agent..."

    prompt=$(cat <<EOF
@${TASKS_FILE} @progress.md @CLAUDE.md
1. Найди ПЕРВУЮ по номеру задачу со статусом "pending", у которой все dependencies имеют статус "done".
   НЕ пропускай задачи — бери строго первую подходящую.
2. Работай ТОЛЬКО над этой одной задачей.

## Используй специализированных агентов (Agent tool):

- **Explore** — исследование кодовой базы, поиск файлов, понимание архитектуры.
  Используй ПЕРЕД началом работы если задача затрагивает незнакомый код.

- **Plan** — планирование сложных задач.
  Используй если задача требует изменений в 3+ файлах или затрагивает архитектуру.

- **backend-architect** — работа с API, базой данных, серверной логикой.
  Используй для задач категории "api", "storage", "core".

- **frontend-developer** — работа с UI, CSS, TypeScript в web/.
  Используй для задач категории "ui", "debug-ui".

- **code-architect** — проектирование структуры новых модулей, рефакторинг архитектуры.

- **solution-architect** — выбор технологий, оценка вариантов реализации, архитектурные решения.
  Используй когда задача требует выбора между несколькими подходами.

- **prd-specialist** — создание PRD документов, бизнес-требования, user stories.
  Используй для задач категории "documentation" связанных с PRD.

## Порядок работы:
1. Прочитай задачу и определи её тип/категорию
2. Если нужно — запусти Explore агента для исследования кода
3. Если задача сложная (3+ файлов) — запусти Plan агента
4. Выполни задачу (сам или через специализированного агента)
5. Проверь: npm run lint && npm run typecheck && npm test
6. Обнови статус задачи в tasks.json на "done"
7. Добавь запись в progress.md
8. Сделай git commit

ВАЖНО: Работай только над ОДНОЙ задачей за раз.
Когда задача выполнена, выведи <promise>COMPLETE</promise>.
EOF
)

    # Запускаем агента с выводом на экран и в файл
    run_agent "$agent" "$prompt" 2>&1 | tee "$RESULT_FILE"

    result=$(cat "$RESULT_FILE")

    echo ""
    echo "-----------------------------------"

    # Проверяем на rate limit
    if [[ "$result" == *"hit your limit"* ]] || [[ "$result" == *"rate limit"* ]] || [[ "$result" == *"resets"* ]]; then
        echo "⚠️  Rate limit! Останавливаюсь."
        say -v Milena "[[volm 0.3]] Лимит исчерпан. Жду сброса."
        exit 1
    fi

    if [[ "$result" == *"<promise>COMPLETE</promise>"* ]]; then
        echo "✓ TASK выполнен!"
        # Проверяем, остались ли ещё pending задачи
        remaining=$(grep -c '"status": "pending"' "$TASKS_FILE" 2>/dev/null) || remaining=0
        if [[ "$remaining" -eq 0 ]]; then
            echo "🎉 Все задачи выполнены!"
            say -v Milena "[[volm 0.3]] Хозяин, я всё сделал!"
            exit 0
        fi
        echo "Осталось задач: $remaining. Продолжаю..."
        say -v Milena "[[volm 0.3]] Задача готова. Продолжаю работу."
    fi

    ((iteration++))
done

echo "Все задачи выполнены! Итераций: $((iteration-1))"
say -v Milena "[[volm 0.3]] Хозяин, я сделал!"
