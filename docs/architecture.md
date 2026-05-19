# Архитектура системы

## Обзор

EGE Task Generator — система автоматической генерации заданий ЕГЭ по информатике
(задания 7 и 11) с валидацией качества через LLM.

## Стек технологий

- **Backend:** Python 3.11+, FastAPI >= 0.115, Uvicorn
- **ORM / БД:** SQLAlchemy >= 2.0 (async), asyncpg, PostgreSQL 15, Alembic
- **Валидация:** Pydantic >= 2.0
- **LLM-провайдеры:** YandexGPT (yandex-ai-studio-sdk), GigaChat (gigachat)
- **Мониторинг:** Prometheus, Grafana, python-json-logger
- **Экспорт:** ReportLab (PDF), JSON, TXT
- **Инфраструктура:** Docker Compose, Kubernetes

## Структура проекта

```
backend/app/
├── api/v1/              # HTTP-эндпоинты (tasks, statistics, export)
├── core/                # Конфигурация, БД, ошибки, логирование, метрики
├── generators/          # Генераторы параметров заданий (task7, task11)
├── middleware/          # ASGI-middleware (request_id)
├── models/              # SQLAlchemy ORM-модели
├── resources/           # Статические ресурсы (openapi.yaml, prompts/, fonts/)
├── schemas/             # Pydantic-схемы запросов/ответов
├── services/            # Бизнес-логика (оркестратор, LLM-адаптеры, экспорт)
└── main.py              # Точка входа FastAPI
```

## Конвейер генерации задания

```
POST /api/v1/tasks/generate
        │
        ▼
┌─────────────────┐
│  Валидация       │ → InvalidTaskTypeError / InvalidSubtypeError
│  task_type       │
└────────┬────────┘
         ▼
┌─────────────────┐
│  Генерация       │ → до 5 попыток, аудит каждой
│  параметров      │ → ParamRetryExhaustedError
└────────┬────────┘
         ▼
┌─────────────────────────────────────┐
│  LLM-итерации (до 3)               │
│  ┌───────────────────────────────┐  │
│  │ Генерация формулировки (LLM)  │  │
│  └──────────────┬────────────────┘  │
│                 ▼                    │
│  ┌───────────────────────────────┐  │
│  │ Валидация формулировки (LLM)  │  │
│  │ 5 критериев качества          │  │
│  └──────────────┬────────────────┘  │
│                 ▼                    │
│         accepted → завершение       │
│         rejected → повтор с feedback│
└─────────────────────────────────────┘
         │
         ▼
   Финальный статус:
   accepted / rejected / error
```

## Схема данных

```
Task (1) ──→ (*) TaskIteration ──→ (1) TaskQuality ──→ (*) RejectionReason
  │                  │
  ├──→ (*) LlmCall ←─┘
  └──→ (*) ParamGenerationAudit
```

- **Task** — корневая сущность, хранит параметры, ответ, формулировку, статус
- **TaskIteration** — один цикл генерация + валидация (до 3 на задание)
- **TaskQuality** — профиль качества по 5 критериям
- **RejectionReason** — причины отклонения по каждому критерию
- **LlmCall** — аудит-лог каждого LLM-вызова (провайдер, токены, время)
- **ParamGenerationAudit** — аудит неудачных попыток генерации параметров

## Инфраструктура

```
┌────────────┐     ┌─────────┐     ┌────────────┐
│   Grafana  │────→│Prometheus│────→│  API :8000 │
│   :3000    │     │  :9090   │     │  /metrics  │
└────────────┘     └─────────┘     └─────┬──────┘
                                         │
                                   ┌─────▼──────┐
                                   │ PostgreSQL  │
                                   │   :5432     │
                                   └─────┬──────┘
                                         │
                                   ┌─────▼──────┐
                                   │   Backup    │
                                   │  (cron)     │
                                   └─────────────┘
```
