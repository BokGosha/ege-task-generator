# API Reference

Базовый путь: `/api/v1`

Интерактивная документация доступна по адресам `/docs` (Swagger) и `/redoc`.

## Генерация заданий

### POST /tasks/generate

Генерация одного задания ЕГЭ по информатике.

**Запрос:**
```json
{
  "task_type": 7,
  "subtype": "image_size"
}
```

| Поле      | Тип          | Описание                              |
|-----------|--------------|---------------------------------------|
| task_type | int          | Тип задания: 7 или 11                |
| subtype   | string/null  | Подтип (если null — выбирается случайно) |

**Подтипы задания 7:** image_size, colors_count, sound_self_duration, packet_size,
cards_count, traffic_saving, sound_bit_depth, sound_duration

**Подтипы задания 11:** min_alphabet_size, max_serial_length, min_serial_length,
max_extra_bytes

**Ответ (200):**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_type": 7,
  "subtype": "image_size",
  "status": "accepted",
  "parameters": { ... },
  "reference_answer": 42,
  "final_wording": "Фотографию размером ...",
  "quality_profile": {
    "clarity": { "pass": true, "message": null },
    "unambiguity": { "pass": true, "message": null },
    "consistency": { "pass": true, "message": null },
    "answer_format": { "pass": true, "message": null },
    "language_correctness": { "pass": true, "message": null },
    "verdict": "accepted",
    "diagnostic_message": "Формулировка пригодна."
  },
  "rejection_reasons": [],
  "iterations": [
    { "attempt_no": 1, "status": "accepted", "quality_verdict": "accepted", "failure_reason": null }
  ],
  "created_at": "2026-04-01T12:00:00"
}
```

### GET /tasks

Краткий список заданий с фильтрами и пагинацией.

| Параметр     | Тип      | По умолчанию | Описание              |
|--------------|----------|-------------|-----------------------|
| page         | int      | 1           | Номер страницы        |
| page_size    | int      | 20          | Размер страницы (1–100) |
| status       | string   | —           | accepted/rejected/error |
| task_type    | int      | —           | Фильтр по типу       |
| created_from | datetime | —           | Начало периода        |
| created_to   | datetime | —           | Конец периода         |

### GET /tasks/history

История генераций с пагинацией. Параметры: page, page_size, task_type, subtype, status.

### GET /tasks/{task_id}

Полная карточка задания по UUID. Возвращает 404 с кодом `TASK_NOT_FOUND`, если не найдено.

## Статистика

### GET /statistics

Агрегированная статистика генерации.

| Параметр | Тип      | Описание             |
|----------|----------|----------------------|
| from     | datetime | Начало периода       |
| to       | datetime | Конец периода        |

**Ответ:** total_tasks, status_shares (accepted/rejected/error), avg_iterations,
top_rejection_reasons, by_task_type, model_stats.

## Экспорт

### GET /export/tasks/{task_id}

Экспорт задания в файл.

| Параметр | Тип  | По умолчанию | Описание           |
|----------|------|--------------|--------------------|
| format   | enum | json         | json, txt или pdf  |

## Служебные эндпоинты

| Эндпоинт   | Описание                      |
|------------|-------------------------------|
| GET /       | Проверка работоспособности API |
| GET /health | Health check для мониторинга  |
| GET /metrics| Prometheus-метрики            |

## Коды ошибок

| Код                       | HTTP | Описание                           |
|---------------------------|------|------------------------------------|
| INVALID_TASK_TYPE         | 400  | Неподдерживаемый тип задания       |
| INVALID_SUBTYPE           | 400  | Неподдерживаемый подтип            |
| INVALID_DATE_RANGE        | 400  | Некорректный диапазон дат          |
| PARAM_RETRY_EXHAUSTED     | 500  | Не удалось сгенерировать параметры |
| LLM_GENERATION_FAILED     | 500  | Сбой генерации формулировки        |
| LLM_VALIDATION_FAILED     | 500  | Сбой валидации формулировки        |
| LLM_TIMEOUT               | 504  | Таймаут LLM-провайдера             |
| TASK_NOT_FOUND            | 404  | Задание не найдено                 |

Формат ошибки:
```json
{
  "error": {
    "code": "INVALID_TASK_TYPE",
    "message": "Тип задания 99 не поддерживается.",
    "details": { "task_id": "..." }
  }
}
```
