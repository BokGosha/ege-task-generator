# Нагрузочные тесты генератора задач

Сценарий для [Locust](https://locust.io/), проверяющий, что бэкенд держит
целевую нагрузку **10–50 одновременных пользователей** без 5xx и без
лавинообразного роста latency.

## Установка

```bash
pip install locust
```

`locust` намеренно **не** добавлен в `backend/requirements.txt`: это
инструмент тестирования, не нужен в production-образе.

## Подготовка окружения

1. Поднять стек:
   ```bash
   docker compose up -d
   ```
2. Дождаться, пока `api` пройдёт healthcheck:
   ```bash
   docker compose ps api
   ```
3. **Важно**: для нагрузочного теста используйте `LLM_GENERATION_PROVIDER=mock`
   и `LLM_VALIDATION_PROVIDER=mock` в `backend/.env`. Иначе тест будет
   прогонять реальные деньги через YandexGPT/GigaChat и упрётся в их квоты,
   а не в защиты приложения.
4. Если хотите проверить именно поведение с реальным LLM — поднимайте
   `LLM_TIMEOUT_SECONDS` и квоты провайдера, и **уменьшайте** число
   виртуальных пользователей.

## Запуск

### Интерактивный режим (Web UI)

```bash
locust -f tests/load/locustfile.py --host http://localhost:8000
```

Затем открыть http://localhost:8089 и задать параметры в UI.

### Готовые профили (headless)

**Smoke** — быстрая проверка, что вообще ничего не сломано:
```bash
locust -f tests/load/locustfile.py \
  --host http://localhost:8000 \
  --headless --users 5 --spawn-rate 1 --run-time 2m
```

**Целевой профиль** — 50 пользователей, плавная рампа, 5 минут:
```bash
locust -f tests/load/locustfile.py \
  --host http://localhost:8000 \
  --headless --users 50 --spawn-rate 1 --run-time 5m \
  --html tests/load/report-target.html
```

**Стресс** — намеренно перегружаем, смотрим управляемую деградацию:
```bash
locust -f tests/load/locustfile.py \
  --host http://localhost:8000 \
  --headless --users 100 --spawn-rate 2 --run-time 10m \
  --html tests/load/report-stress.html
```

## Что считать успехом

| Метрика | Целевой профиль (50 vusers) | Где смотреть |
|---|---|---|
| HTTP 5xx | ~0 | Locust report, Grafana |
| HTTP 429 | допустимо у клиентов сверх лимита | Locust засчитывает 429 как success |
| p95 latency `/generate` | стабилен, не растёт лавинообразно | Locust + `task_generation_duration_seconds` |
| `llm_calls_total{status="error"}` | редкие всплески, ловятся ретраем | Grafana / Prometheus |
| Соединений к Postgres | `< (DB_POOL_SIZE + DB_MAX_OVERFLOW) × workers` | `SELECT count(*) FROM pg_stat_activity WHERE datname='ege_tasks';` |

Скрипт автоматически фейлит прогон (`exit code != 0`), если:
- доля ошибок выше 1%, либо
- p95 выше 180 секунд.

## Корреляция с логами и метриками

- Сценарий читает заголовок `X-Request-ID` и пишет его в текст ошибки.
  По нему можно искать в Grafana → Loki:
  `{container="generator-api-1"} |= "<request_id>"`
- Параллельно держите открытой Grafana (`http://localhost:3000`) и смотрите:
  - `histogram_quantile(0.95, rate(task_generation_duration_seconds_bucket[1m]))`
  - `sum by (status) (rate(tasks_generated_total[1m]))`
  - `sum by (provider, status) (rate(llm_calls_total[1m]))`

## Chaos-проверка таймаута

Чтобы убедиться, что зависший провайдер не положит сервис:

1. Временно подменить тело `_do_call` в `MockLlmAdapter` на
   `await asyncio.sleep(120)`.
2. Запустить smoke-профиль.
3. Запросы должны завершаться через `LLM_TIMEOUT_SECONDS` с
   `LLM_TIMEOUT`/HTTP 504, а не висеть бесконечно.
4. Откатить подмену.
