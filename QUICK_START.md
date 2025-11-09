# 🔐 testum - Quick Reference

## Что это?
Веб-сервис для управления SSH ключами и автоматического развертывания на удаленные хосты.

## Быстрый старт

```bash
# 1. Сгенерировать ключ шифрования
make generate-key

# 2. Создать .env и добавить FERNET_KEY
cp .env.example .env
# Редактировать .env, установить FERNET_KEY

# 3. Запустить
make build && make up

# 4. Открыть
open http://localhost:8000
```

## Основные команды

```bash
make help          # Показать все команды
make up            # Запустить сервисы
make down          # Остановить сервисы
make logs          # Просмотр логов
make test          # Запустить тесты
make shell         # Shell в контейнере
```

## URL сервисов

- Web UI: http://localhost:8000
- API: http://localhost:8000/api/
- MinIO: http://localhost:9001 (admin/minioadmin)
- PostgreSQL: localhost:5432
- Redis: localhost:6379

## Основные эндпоинты

```bash
# Auth
POST /api/auth/login

# Keys
GET  /api/keys/
POST /api/keys/
DELETE /api/keys/{id}

# Platforms  
GET  /api/platforms/
POST /api/platforms/
POST /api/platforms/{id}/deploy_keys
POST /api/platforms/{id}/run_command

# Tasks
GET /api/tasks/{task_id}
WS  /ws/tasks/{task_id}
```

## Workflow

1. **Создать SSH ключ** через Web UI или API
2. **Создать платформу** (хост с SSH доступом)
3. **Deploy ключи** на платформу
4. **Мониторить задачу** через WebSocket
5. **Выполнять команды** на платформе

## Структура

```
app/
├── main.py              # Starlette app
├── models.py            # DB models
├── tasks.py             # Celery tasks
├── ssh_helper.py        # SSH operations
├── api/
│   ├── keys.py         # Keys API
│   └── platforms.py    # Platforms API
└── templates/          # Web UI

migrations/             # Alembic
tests/                 # Pytest
```

## Безопасность

- ✅ Fernet encryption для credentials
- ✅ SSH fingerprint verification
- ✅ Atomic write для authorized_keys
- ✅ Audit logging
- ✅ JWT auth (basic)

## Тестирование

```bash
# Все тесты
make test

# С coverage
docker-compose exec app pytest --cov=app

# Lint
make lint
```

## Документация

- `README.md` - Полная документация
- `API_EXAMPLES.md` - Примеры API запросов
- `PROJECT_SUMMARY.md` - Резюме проекта

## Технологии

- Starlette (ASGI web framework)
- Celery (task queue)
- Paramiko (SSH client)
- PostgreSQL (database)
- Redis (pub/sub + broker)
- MinIO (S3 storage)
- WebSocket (real-time streaming)

## Troubleshooting

### Ошибка "FERNET_KEY not configured"
```bash
make generate-key
# Скопировать в .env
```

### Контейнеры не стартуют
```bash
make down
make clean
make build
make up
```

### Миграции не применяются
```bash
docker-compose exec app alembic upgrade head
```

### Celery задачи не выполняются
```bash
docker-compose logs celery_worker
docker-compose restart celery_worker
```

## Поддержка

- GitHub Issues для bug reports
- README.md для детальной документации
- API_EXAMPLES.md для примеров использования

---

**Version**: 0.1.0  
**Status**: MVP Ready  
**License**: MIT
