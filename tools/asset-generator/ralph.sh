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

# Agent selection:
# - Ralph now runs through Codex only.
# - RALPH_AGENT is kept for compatibility, but only "codex" is supported.
resolve_agent() {
    if [[ -n "${RALPH_AGENT:-}" && "${RALPH_AGENT}" != "codex" ]]; then
        echo "Unsupported agent: $RALPH_AGENT" >&2
        return 1
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
        codex)
            local output_file
            output_file="$(mktemp -t ralph_codex.XXXXXX)"
            codex exec --dangerously-bypass-approvals-and-sandbox --color never -C "$PWD" --output-last-message "$output_file" "$prompt" >/dev/null
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
        echo "Не найден Codex CLI. Установите 'codex' или задайте RALPH_AGENT=codex." >&2
        exit 1
    }

    echo "Запускаю $agent..."

    prompt=$(cat <<EOF
@${TASKS_FILE} @progress.md @../../docs/asset-generator-spec-mvp-v0.2.md
1. Найди ПЕРВУЮ по номеру задачу со статусом "pending", у которой все dependencies имеют статус "done".
   НЕ пропускай задачи — бери строго первую подходящую.
2. Работай ТОЛЬКО над этой одной задачей.

## Контекст проекта:
Asset Generator — CLI утилита для генерации картинок персонажей через OpenAI Image API.
Это часть проекта SpyfallAI (визуализатор игровых партий).

Стек: Python 3.11+, OpenAI API (gpt-image-2), python-dotenv.
Структура: config/ (characters.json), prompts/ (шаблоны), reference/ (эталон стиля), output/ (результаты).

## Ключевые концепции:
- Reference image: первый сгенерированный персонаж используется как стилевой эталон
- Три режима --approach: auto (reference с fallback), reference (без fallback), text-only
- Fallback срабатывает ТОЛЬКО на reference-flow ошибки, НЕ на 429/network/auth
- JSON-лог каждого запроса с обязательными и опциональными полями
- MVP: только 2 персонажа (boris_molot, aurora), без локаций

## Работай в режиме Codex:

- Исследуй кодовую базу перед изменениями, если задача затрагивает незнакомый код.
- Для сложных задач сначала составь короткий план и затем реализуй его.
- Следуй существующей архитектуре проекта и локальным паттернам.

## Порядок работы:
1. Прочитай задачу и определи её тип/категорию
2. Если нужно — исследуй код и связанные файлы
3. Если задача сложная (3+ файлов) — составь план
4. Выполни задачу
5. Проверь код: python -m py_compile generate_assets.py (если есть)
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
            say -v Milena "[[volm 0.3]] Хозяин, генератор ассетов готов!"
            exit 0
        fi
        echo "Осталось задач: $remaining. Продолжаю..."
        say -v Milena "[[volm 0.3]] Задача готова. Продолжаю работу."
    fi

    ((iteration++))
done

echo "Все задачи выполнены! Итераций: $((iteration-1))"
say -v Milena "[[volm 0.3]] Хозяин, генератор ассетов готов!"
