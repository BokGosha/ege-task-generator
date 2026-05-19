# Схема базы данных

## ER-диаграмма

```
Task (1) ──→ (*) TaskIteration (1) ──→ (1) TaskQuality (1) ──→ (*) RejectionReason
  │                   │
  ├──→ (*) LlmCall  ←─┘
  └──→ (*) ParamGenerationAudit
```

## Таблицы

### tasks

Корневая сущность — одна запись = одна генерация задания.

| Колонка          | Тип        | Описание                               |
|------------------|------------|----------------------------------------|
| id               | UUID (PK)  | Идентификатор                          |
| task_type        | int        | Тип задания (7 или 11)                 |
| subtype          | varchar(64)| Подтип задания                         |
| parameters       | JSONB      | Сгенерированные параметры              |
| reference_answer | bigint     | Правильный ответ                       |
| status           | varchar(20)| accepted / rejected / error            |
| final_wording    | text       | Итоговая формулировка задания          |
| total_iterations | int        | Количество LLM-итераций                |
| error_code       | varchar(64)| Код ошибки (при status=error)          |
| error_message    | text       | Текст ошибки                           |
| created_at       | timestamp  | Дата создания                          |
| updated_at       | timestamp  | Дата обновления                        |

Индексы: (task_type, created_at), (status), (created_at DESC).

### task_iterations

Одна итерация цикла генерация → валидация (до 3 на задание).

| Колонка          | Тип        | Описание                               |
|------------------|------------|----------------------------------------|
| id               | UUID (PK)  | Идентификатор                          |
| task_id          | UUID (FK)  | Ссылка на tasks                        |
| iteration_number | int        | Номер итерации (1–3)                   |
| wording          | text       | Сгенерированная формулировка           |
| status           | varchar(20)| accepted / rejected / error            |
| failure_stage    | varchar(20)| generation / validation (при ошибке)   |
| failure_reason   | text       | Описание ошибки                        |
| started_at       | timestamp  | Начало итерации                        |
| finished_at      | timestamp  | Конец итерации                         |

Уникальный индекс: (task_id, iteration_number).

### task_quality

Профиль качества формулировки по 5 критериям.

| Колонка                    | Тип        | Описание                    |
|----------------------------|------------|-----------------------------|
| id                         | UUID (PK)  | Идентификатор               |
| iteration_id               | UUID (FK)  | Ссылка на task_iterations   |
| clarity_pass / message     | bool / text| Ясность                    |
| unambiguity_pass / message | bool / text| Однозначность              |
| consistency_pass / message | bool / text| Непротиворечивость         |
| answer_format_pass / message| bool / text| Формат ответа             |
| language_correctness_pass / message| bool / text| Языковая корректность|
| verdict                    | varchar(20)| accepted / rejected         |
| diagnostic_message         | text       | Общий вердикт              |

### rejection_reasons

Причины отклонения по конкретным критериям.

| Колонка            | Тип        | Описание                        |
|--------------------|------------|---------------------------------|
| id                 | UUID (PK)  | Идентификатор                   |
| quality_profile_id | UUID (FK)  | Ссылка на task_quality          |
| criterion          | varchar(50)| Название критерия               |
| description        | text       | Пояснение от LLM-валидатора     |

### llm_calls

Аудит-лог каждого обращения к LLM.

| Колонка            | Тип        | Описание                        |
|--------------------|------------|---------------------------------|
| id                 | UUID (PK)  | Идентификатор                   |
| task_id            | UUID (FK)  | Ссылка на tasks                 |
| iteration_id       | UUID (FK)  | Ссылка на task_iterations       |
| call_type          | varchar(50)| wording_generation / semantic_validation |
| provider           | varchar(50)| yandexgpt / gigachat / mock     |
| model_name         | varchar(100)| Название модели               |
| request_payload    | JSONB      | Отправленный запрос             |
| response_payload   | JSONB      | Полученный ответ                |
| status             | varchar(20)| success / error / timeout       |
| error_message      | text       | Текст ошибки (если есть)        |
| prompt_tokens      | int        | Токены запроса                  |
| completion_tokens  | int        | Токены ответа                   |
| estimated_cost_rub | float      | Оценка стоимости в рублях       |
| duration_ms        | int        | Время выполнения (мс)           |

### param_generation_audit

Аудит неудачных попыток генерации параметров.

| Колонка          | Тип        | Описание                         |
|------------------|------------|----------------------------------|
| id               | UUID (PK)  | Идентификатор                    |
| task_id          | UUID (FK)  | Ссылка на tasks                  |
| attempt_number   | int        | Номер попытки (1–5)              |
| rejection_reason | text       | Причина отклонения параметров    |

### task_statistics

Placeholder-таблица для статистики. В текущей версии статистика вычисляется
динамически из основных таблиц (tasks, task_iterations, llm_calls).

| Колонка          | Тип        | Описание                         |
|------------------|------------|----------------------------------|
| id               | UUID (PK)  | Идентификатор                    |
| task_type        | int        | Тип задания                      |
| subtype          | varchar(64)| Подтип задания                   |
| status           | varchar(20)| Статус задания                   |
| quality_verdict  | varchar(20)| Вердикт качества                 |
| created_at       | timestamp  | Дата создания                    |
| updated_at       | timestamp  | Дата обновления                  |

## Миграции

Управление схемой через Alembic:

```bash
# Применить все миграции
cd backend && alembic upgrade head

# Создать новую миграцию
cd backend && alembic revision --autogenerate -m "описание"

# Откатить на шаг назад
cd backend && alembic downgrade -1
```
