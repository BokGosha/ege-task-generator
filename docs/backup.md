# Резервное копирование и восстановление

## Автоматическое резервное копирование

Бэкапы создаются автоматически:

- **Docker Compose:** сервис `backup` — `pg_dump` ежедневно в 3:00, хранение 7 дней
- **Kubernetes:** CronJob `postgres-backup` — аналогичное расписание

Файлы бэкапов хранятся в формате custom (`-Fc`), имя: `ege_tasks_20260401_030000.dump`.

### Настройка расписания

```env
BACKUP_SCHEDULE=0 3 * * *      # cron-выражение (Docker)
BACKUP_RETENTION_DAYS=7         # автоудаление старых дампов
```

В K8s расписание задаётся в `k8s/backup.yaml` → `spec.schedule`.

## Ручное резервное копирование

### Docker Compose

```bash
# Custom-формат (сжатый, для pg_restore)
docker compose exec db pg_dump -U postgres -Fc ege_tasks > backup.dump

# SQL-формат (читаемый, для psql)
docker compose exec db pg_dump -U postgres ege_tasks > backup.sql
```

### Kubernetes

```bash
# Найти имя пода
kubectl get pods -n ege-generator -l app=postgres

# Создать дамп
kubectl exec -n ege-generator <pod> -- pg_dump -U postgres -Fc ege_tasks > backup.dump
```

## Восстановление

### Docker Compose

```bash
# 1. Остановить API
docker compose stop api

# 2. Пересоздать базу
docker compose exec db dropdb -U postgres ege_tasks
docker compose exec db createdb -U postgres ege_tasks

# 3. Восстановить
docker compose exec -T db pg_restore -U postgres -d ege_tasks < backup.dump

# 4. Запустить API (миграции применятся автоматически)
docker compose start api
```

### Kubernetes

```bash
# 1. Масштабировать API в 0
kubectl scale deployment api -n ege-generator --replicas=0

# 2. Скопировать дамп в под
kubectl cp backup.dump ege-generator/<postgres-pod>:/tmp/backup.dump

# 3. Пересоздать и восстановить
kubectl exec -n ege-generator <postgres-pod> -- dropdb -U postgres ege_tasks
kubectl exec -n ege-generator <postgres-pod> -- createdb -U postgres ege_tasks
kubectl exec -n ege-generator <postgres-pod> -- pg_restore -U postgres -d ege_tasks /tmp/backup.dump

# 4. Вернуть API
kubectl scale deployment api -n ege-generator --replicas=2
```

## Проверка после восстановления

```sql
-- Проверить наличие таблиц
SELECT tablename FROM pg_tables WHERE schemaname = 'public';

-- Проверить количество записей
SELECT count(*) FROM tasks;
SELECT count(*) FROM task_iterations;
SELECT count(*) FROM llm_calls;

-- Проверить целостность FK
SELECT t.id FROM tasks t
LEFT JOIN task_iterations ti ON ti.task_id = t.id
WHERE t.total_iterations > 0 AND ti.id IS NULL;

-- Проверить версию миграции
SELECT version_num FROM alembic_version;
```

```bash
# Smoke-тест API
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/statistics
```
