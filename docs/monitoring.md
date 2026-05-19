# Мониторинг (Grafana + Prometheus + Loki)

## Архитектура

```
                        ┌──────────────────────────────────────────┐
                        │              Grafana :3000                │
                        │  ┌─────────────────┐ ┌────────────────┐  │
                        │  │  Дашборд метрик  │ │  Дашборд логов │  │
                        │  └────────┬────────┘ └───────┬────────┘  │
                        └───────────┼──────────────────┼───────────┘
                                    │                  │
                       ┌────────────▼──────┐  ┌───────▼────────┐
                       │ Prometheus :9090   │  │   Loki :3100   │
                       │ (метрики)          │  │   (логи)       │
                       └────────────┬──────┘  └───────▲────────┘
                                    │                  │
                          scrape /metrics         push логов
                                    │                  │
                       ┌────────────▼──────┐  ┌───────┴────────┐
                       │   API :8000       │  │ Promtail :9080  │
                       │   (FastAPI)       │  │ (сборщик логов) │
                       └───────────────────┘  └────────────────┘
```

- **Prometheus** скрейпит метрики с эндпоинта `GET /metrics` каждые 15 секунд
- **Promtail** собирает stdout-логи Docker-контейнеров и пушит их в Loki
- **Loki** хранит и индексирует логи
- **Grafana** визуализирует данные из обоих источников

## Запуск

Все сервисы мониторинга входят в `docker-compose.yml` и стартуют автоматически:

```bash
docker compose up -d
```

| Сервис     | URL                      | Логин/Пароль по умолчанию |
|------------|--------------------------|---------------------------|
| Grafana    | http://localhost:3000     | admin / admin             |
| Prometheus | http://localhost:9090     | —                         |
| Loki       | http://localhost:3100     | —                         |

Порты настраиваются через `.env`:

```env
GRAFANA_PORT=3000
PROMETHEUS_PORT=9090
LOKI_PORT=3100
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin
```

## Prometheus

### Конфигурация

Файл `infra/prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "ege-api"
    metrics_path: /metrics
    static_configs:
      - targets: ["api:8000"]
```

### Доступные метрики

API экспортирует три метрики через `GET /metrics`:

| Метрика                          | Тип       | Labels                          | Описание                              |
|----------------------------------|-----------|---------------------------------|---------------------------------------|
| `tasks_generated_total`          | Counter   | `task_type`, `status`           | Количество сгенерированных заданий    |
| `llm_calls_total`               | Counter   | `call_type`, `provider`, `status` | Количество вызовов LLM              |
| `task_generation_duration_seconds` | Histogram | —                               | Длительность генерации (секунды)     |

Значения labels:

- `task_type`: `"7"`, `"11"`
- `status`: `"accepted"`, `"rejected"`, `"error"`, `"success"`
- `call_type`: `"wording_generation"`, `"semantic_validation"`
- `provider`: `"yandexgpt"`, `"gigachat"`, `"mock"`

### Полезные PromQL-запросы

**Общее количество заданий за последний час:**
```promql
increase(tasks_generated_total[1h])
```

**Доля успешных заданий (rate):**
```promql
sum(rate(tasks_generated_total{status="accepted"}[5m]))
/
sum(rate(tasks_generated_total[5m]))
```

**Количество ошибок LLM по провайдерам:**
```promql
sum by (provider) (rate(llm_calls_total{status="error"}[5m]))
```

**Средняя длительность генерации:**
```promql
rate(task_generation_duration_seconds_sum[5m])
/
rate(task_generation_duration_seconds_count[5m])
```

**95-й перцентиль длительности генерации:**
```promql
histogram_quantile(0.95, rate(task_generation_duration_seconds_bucket[5m]))
```

**Соотношение генерации к валидации:**
```promql
sum by (call_type) (rate(llm_calls_total[5m]))
```

## Loki + Promtail

### Как работает

1. **Promtail** подключается к Docker-сокету и автоматически собирает stdout/stderr всех контейнеров
2. Логи от сервиса `api` парсятся как JSON (поля `level`, `logger`, `message`, `request_id`, `timestamp`)
3. Parsed-поля `level` и `logger` становятся Loki-лейблами для фильтрации

### Конфигурация Promtail

Файл `infra/promtail/promtail-config.yml`:

```yaml
server:
  http_listen_port: 9080

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
    relabel_configs:
      - source_labels: ['__meta_docker_container_name']
        regex: '/(.*)'
        target_label: container
      - source_labels: ['__meta_docker_compose_service']
        target_label: service
    pipeline_stages:
      - match:
          selector: '{service="api"}'
          stages:
            - json:
                expressions:
                  level: level
                  logger: logger
                  message: message
                  request_id: request_id
                  timestamp: timestamp
            - labels:
                level:
                logger:
            - timestamp:
                source: timestamp
                format: "2006-01-02T15:04:05.000000"
```

### Конфигурация Loki

Файл `infra/loki/loki-config.yml`:

```yaml
auth_enabled: false

server:
  http_listen_port: 3100

schema_config:
  configs:
    - from: "2026-01-01"
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

storage_config:
  filesystem:
    directory: /loki/chunks

limits_config:
  reject_old_samples: true
  reject_old_samples_max_age: 168h
  ingestion_rate_mb: 4
  ingestion_burst_size_mb: 6
```

### Полезные LogQL-запросы

**Все логи API:**
```logql
{service="api"}
```

**Только ошибки:**
```logql
{service="api", level="ERROR"}
```

**Логи конкретного задания по request_id:**
```logql
{service="api"} |= "request_id" | json | request_id="<uuid>"
```

**Ошибки LLM-генерации:**
```logql
{service="api", logger="backend.app.services.wording_generator"} |= "Ошибка"
```

**Ошибки LLM-валидации:**
```logql
{service="api", logger="backend.app.services.wording_validator"} |= "Ошибка"
```

**Логи оркестратора (весь конвейер):**
```logql
{service="api", logger="backend.app.services.task_orchestrator"}
```

**Частота ошибок за время (для графика):**
```logql
sum(count_over_time({service="api", level="ERROR"}[5m]))
```

**Логи базы данных:**
```logql
{service="db"}
```

## Grafana

### Datasources

Datasources провижинятся автоматически из `infra/grafana/provisioning/datasources/datasource.yml`:

| Имя        | Тип        | URL                    | По умолчанию |
|------------|------------|------------------------|-------------|
| Prometheus | prometheus | http://prometheus:9090  | да          |
| Loki       | loki       | http://loki:3100       | нет         |

### Создание дашборда метрик

1. Открыть Grafana (http://localhost:3000)
2. **Dashboards** -> **New** -> **New Dashboard**
3. **Add visualization**, выбрать datasource **Prometheus**

Рекомендуемые панели:

| Панель                         | Тип          | Запрос (PromQL)                                                                              |
|-------------------------------|--------------|----------------------------------------------------------------------------------------------|
| Заданий за час                | Stat         | `increase(tasks_generated_total[1h])`                                                        |
| Статус заданий                | Pie Chart    | `sum by (status) (increase(tasks_generated_total[24h]))`                                     |
| Доля accepted                 | Gauge        | `sum(rate(tasks_generated_total{status="accepted"}[5m])) / sum(rate(tasks_generated_total[5m]))` |
| Длительность генерации (p95)  | Time Series  | `histogram_quantile(0.95, rate(task_generation_duration_seconds_bucket[5m]))`                 |
| Средняя длительность          | Stat         | `rate(task_generation_duration_seconds_sum[5m]) / rate(task_generation_duration_seconds_count[5m])` |
| LLM-вызовы по провайдерам     | Time Series  | `sum by (provider) (rate(llm_calls_total[5m]))`                                              |
| Ошибки LLM                   | Time Series  | `sum by (provider, call_type) (rate(llm_calls_total{status="error"}[5m]))`                   |
| Задания по типам              | Bar Chart    | `sum by (task_type) (increase(tasks_generated_total[24h]))`                                  |

### Создание дашборда логов

1. **Add visualization**, выбрать datasource **Loki**
2. Тип панели — **Logs**

Рекомендуемые панели:

| Панель                | Запрос (LogQL)                                                        |
|-----------------------|----------------------------------------------------------------------|
| Все логи API          | `{service="api"}`                                                    |
| Поток ошибок          | `{service="api", level="ERROR"}`                                     |
| Конвейер генерации    | `{service="api", logger="backend.app.services.task_orchestrator"}`   |
| Частота ошибок (график) | `sum(count_over_time({service="api", level="ERROR"}[5m]))`          |

### Alerts (опционально)

Примеры Grafana Alert Rules:

**Высокая доля ошибок (> 30% за 5 минут):**
```promql
sum(rate(tasks_generated_total{status="error"}[5m]))
/
sum(rate(tasks_generated_total[5m]))
> 0.3
```

**LLM-провайдер не отвечает (0 успешных вызовов за 10 минут):**
```promql
sum(increase(llm_calls_total{status="success"}[10m])) == 0
```

**Генерация слишком долгая (p95 > 120 секунд):**
```promql
histogram_quantile(0.95, rate(task_generation_duration_seconds_bucket[5m])) > 120
```

## Формат логов

API пишет JSON-логи в stdout. Каждая запись содержит:

```json
{
  "timestamp": "2026-04-01 12:00:00,123",
  "level": "INFO",
  "logger": "backend.app.services.task_orchestrator",
  "message": "Задание завершено: task_id=abc, status=accepted, duration=12.34s",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "service": "ege-api"
}
```

| Поле       | Описание                                    |
|------------|---------------------------------------------|
| timestamp  | Время события                               |
| level      | DEBUG, INFO, WARNING, ERROR                 |
| logger     | Python-модуль, записавший лог               |
| message    | Текст сообщения                             |
| request_id | UUID запроса (из заголовка X-Request-ID)    |
| service    | Всегда `"ege-api"` (статическое поле)       |

## Troubleshooting

**Grafana не видит данные Prometheus:**
```bash
# Проверить, что Prometheus доступен
curl http://localhost:9090/api/v1/targets
# Убедиться, что API target в состоянии UP
```

**Grafana не видит логи в Loki:**
```bash
# Проверить здоровье Loki
curl http://localhost:3100/ready

# Проверить, что Promtail пушит логи
curl http://localhost:9080/targets
```

**Логи API не парсятся как JSON:**
```bash
# Проверить формат логов контейнера
docker compose logs api --tail 5
# Ожидается JSON: {"timestamp": ..., "level": ..., ...}
```

**Метрики не появляются:**
```bash
# Проверить, что API отдаёт метрики
curl http://localhost:8000/metrics | grep tasks_generated
```
