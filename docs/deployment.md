# Развёртывание

## Требования

- Docker и Docker Compose
- (для K8s) kubectl + кластер Kubernetes
- TLS-сертификат для HTTPS (Let's Encrypt или собственный)

## Быстрый старт (Docker Compose)

```bash
# 1. Скопировать и заполнить переменные окружения
cp .env.example .env
# Заполнить GIGACHAT_CREDENTIALS, YANDEXGPT_API_KEY, SECRET_KEY

# 2. Положить TLS-сертификаты (см. раздел HTTPS ниже)
cp fullchain.pem infra/nginx/ssl/cert.pem
cp privkey.pem infra/nginx/ssl/key.pem

# 3. Запустить все сервисы
docker compose up -d

# 4. Проверить
curl https://localhost/health
```

Сервисы:

| Сервис     | Порт    | Назначение                       |
|------------|---------|----------------------------------|
| nginx      | 80, 443 | Обратный прокси, TLS-терминация  |
| api        | (8000)  | FastAPI-приложение (внутренний)   |
| db         | 5432    | PostgreSQL 15                    |
| prometheus | 9090    | Сбор метрик                      |
| grafana    | (3000)  | Дашборды через /grafana/ (внутренний) |
| backup     | —       | Автобэкап БД (ежедневно в 3:00)  |

Порты настраиваются через `.env` (HTTP_PORT, HTTPS_PORT, POSTGRES_PORT, PROMETHEUS_PORT).

## Переменные окружения

### Обязательные

| Переменная           | Описание                                    |
|---------------------|---------------------------------------------|
| GIGACHAT_CREDENTIALS | Base64 от ClientID:ClientSecret             |
| YANDEXGPT_API_KEY    | API-ключ YandexGPT                          |
| YANDEXGPT_FOLDER_ID  | ID каталога Yandex Cloud                    |
| SECRET_KEY           | Секретный ключ приложения                   |

### Опциональные

| Переменная              | По умолчанию      | Описание                    |
|------------------------|--------------------|-----------------------------|
| LLM_GENERATION_PROVIDER | gigachat          | Провайдер генерации         |
| LLM_VALIDATION_PROVIDER | yandexgpt         | Провайдер валидации         |
| POSTGRES_USER           | postgres          | Пользователь БД             |
| POSTGRES_PASSWORD       | postgres          | Пароль БД                   |
| POSTGRES_DB             | ege_tasks         | Имя базы данных             |
| DEBUG                   | false             | Режим отладки (DEBUG логи)  |
| MAX_RETRIES             | 3                 | Макс. попыток генерации     |
| BACKUP_RETENTION_DAYS   | 7                 | Хранение бэкапов (дни)      |
| GRAFANA_ADMIN_USER      | admin             | Логин Grafana               |
| GRAFANA_ADMIN_PASSWORD  | admin             | Пароль Grafana              |
| HTTP_PORT               | 80                | Порт HTTP (редирект на HTTPS)|
| HTTPS_PORT              | 443               | Порт HTTPS                  |

## HTTPS

### Docker Compose

Nginx выступает обратным прокси и терминирует TLS. HTTP-запросы на порт 80
автоматически перенаправляются на HTTPS (443).

```
Клиент ──HTTPS:443──→ Nginx ──HTTP:8000──→ API (внутренняя сеть Docker)
```

Сертификаты размещаются в `infra/nginx/ssl/`:
- `cert.pem` — сертификат (или fullchain)
- `key.pem` — приватный ключ

**Самоподписанный сертификат (для разработки):**

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout infra/nginx/ssl/key.pem -out infra/nginx/ssl/cert.pem \
  -subj "/CN=localhost"
```

**Let's Encrypt (для продакшена):**

```bash
certbot certonly --standalone -d ege.example.com
cp /etc/letsencrypt/live/ege.example.com/fullchain.pem infra/nginx/ssl/cert.pem
cp /etc/letsencrypt/live/ege.example.com/privkey.pem infra/nginx/ssl/key.pem
```

### Kubernetes

Ingress с TLS настроен в `k8s/ingress.yaml`. Требуется Ingress Controller
(например, ingress-nginx) и TLS-секрет:

```bash
# Создать TLS-секрет из сертификатов
kubectl create secret tls ege-tls \
  -n ege-generator \
  --cert=fullchain.pem \
  --key=privkey.pem

# Применить Ingress
kubectl apply -f k8s/ingress.yaml
```

Для автоматического обновления сертификатов рекомендуется cert-manager:
```bash
# Установить cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml
```

## Развёртывание в Kubernetes

```bash
# 1. Заполнить секреты
vi k8s/secrets.yaml   # stringData — plaintext, K8s сам закодирует

# 2. Применить манифесты
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/backup.yaml
kubectl apply -f k8s/api.yaml        # включает Job миграции
kubectl apply -f k8s/prometheus.yaml
kubectl apply -f k8s/grafana.yaml

# 3. Проверить
kubectl get pods -n ege-generator
```

Манифесты:

| Файл            | Ресурсы                                          |
|-----------------|--------------------------------------------------|
| namespace.yaml  | Namespace `ege-generator`                        |
| configmap.yaml  | Несекретные настройки (DB name, LLM-провайдеры)  |
| secrets.yaml    | Креды БД, API-ключи, пароль Grafana              |
| postgres.yaml   | Deployment + PVC + Service                       |
| api.yaml        | Job (миграции) + Deployment (2 реплики) + Service |
| prometheus.yaml | ServiceAccount + RBAC + Deployment + PVC + Service |
| grafana.yaml    | Deployment + PVC + Service + datasource provisioning |
| backup.yaml     | CronJob (ежедневно в 3:00) + PVC                |
| ingress.yaml    | Ingress с TLS-терминацией                        |

## Миграции базы данных

```bash
# Docker — выполняются автоматически при старте api
# Ручной запуск:
docker compose exec api sh -c "cd backend && alembic upgrade head"

# K8s — выполняются через Job перед запуском подов API
kubectl get jobs -n ege-generator
```

## Мониторинг

### Prometheus-метрики (GET /metrics)

| Метрика                           | Тип       | Описание                           |
|-----------------------------------|-----------|------------------------------------|
| tasks_generated_total             | Counter   | Всего сгенерированных заданий      |
| llm_calls_total                   | Counter   | Всего LLM-вызовов                  |
| task_generation_duration_seconds  | Histogram | Длительность генерации             |

Labels: task_type, status, call_type, provider.

### Логирование

Структурированные JSON-логи в stdout. Формат:

```json
{"timestamp": "2026-04-01 12:00:00", "level": "INFO", "logger": "backend.app.services.task_orchestrator", "message": "Задание завершено: task_id=abc, status=accepted, duration=12.34s"}
```

Уровни: DEBUG (при debug=true), INFO, WARNING, ERROR.
