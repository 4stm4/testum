# Testum

Платформа для централизованного управления удалёнными серверами через SSH. Выполняйте команды, разворачивайте SSH-ключи, запускайте автоматизации — с real-time мониторингом через браузер или CLI.

## Возможности

- Выполнение команд и скриптов на удалённых хостах
- Развёртывание SSH-ключей на группы серверов
- Real-time вывод задач через WebSocket
- Автоматизации с расписанием (cron)
- Управление пользователями и RBAC (Admin / Operator / Viewer)
- Шифрование всех credentials через Fernet
- Backup / Restore конфигурации в YAML
- GitOps-импорт платформ и ключей из Git-репозитория
- Audit-лог всех действий с фильтрами и экспортом
- CLI-клиент `testumctl`

## Стек

| Слой | Технология |
|---|---|
| Web / API | Starlette + Uvicorn |
| База данных | PostgreSQL + SQLAlchemy + Alembic |
| Очередь задач | pyjobkit 1.0 |
| SSH | asyncssh |
| Хранилище артефактов | MinIO (S3-совместимый) |
| Шифрование | cryptography (Fernet) |
| Аутентификация | JWT (HTTP-only cookie) |

## Архитектура

```
src/
├── core/           # Доменная логика, интерфейсы (чистый Python, без зависимостей)
├── adapters/       # Реализации: postgres, minio, ssh, smtp, scheduler
├── ports/
│   ├── api/        # HTTP JSON API (Starlette роутеры)
│   ├── web/        # Браузерный UI (Jinja2 + статика)
│   ├── ws/         # WebSocket стриминг задач
│   └── cli/        # testumctl — CLI-клиент
└── app/            # Точка сборки: FastAPI-приложение, конфиг, движок задач
```

## Быстрый старт (Docker Compose)

### 1. Генерация ключей

```bash
# Fernet — шифрование credentials
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# SECRET_KEY — подпись JWT
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 2. Настройка окружения

Скопируйте переменные в `docker-compose.yml` или `.env`:

```bash
FERNET_KEY=<из шага 1>
SECRET_KEY=<из шага 1>
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
```

> По умолчанию в `docker-compose.yml` уже прописаны тестовые значения — смените их перед продакшен-деплоем.

### 3. Запуск

```bash
# Собрать образ worker-а и поднять все сервисы
docker compose up -d --build

# Просмотр логов
docker compose logs -f app worker
```

Сервисы:
| Сервис | Порт | Назначение |
|---|---|---|
| Nginx (loading screen) | 8000 | Ждёт готовности app, редиректит |
| App | 8001 | Web UI + REST API |
| Worker | — | Обработчик фоновых задач (SSH) |
| PostgreSQL | 5432 | БД |
| MinIO | 9010 / 9011 | S3-хранилище / консоль |

После запуска откройте http://localhost:8001 (логин: admin / admin123).

### Makefile

```bash
make build      # Пересобрать Docker-образы
make up         # Запустить все сервисы
make down       # Остановить
make logs       # Следить за логами
make migrate    # Применить миграции Alembic
make migration MSG="описание"  # Создать новую миграцию
make shell      # Bash внутри контейнера app
make db-shell   # psql внутри контейнера db
make test       # Запустить тесты
make lint       # flake8 + black --check
make format     # black (форматирование)
make clean      # Удалить контейнеры и тома
make generate-key  # Напечатать новый FERNET_KEY
```

## Деплой в Portainer

1. Portainer → Stacks → Add stack → Web editor
2. Вставьте содержимое `docker-compose.yml`
3. Задайте Environment variables:
   ```
   FERNET_KEY=...
   SECRET_KEY=...
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=yourpassword
   ```
4. Deploy → откройте http://your-server:8001

## Локальная разработка

```bash
# Зависимости
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.dev.txt

# Поднять только инфраструктуру
docker compose up -d db minio

# Миграции
PYTHONPATH=src DATABASE_URL=postgresql://postgres:postgres@localhost:5432/testum \
  alembic upgrade head

# Запуск app (в отдельном терминале)
PYTHONPATH=src \
  FERNET_KEY=<key> SECRET_KEY=<key> ADMIN_USERNAME=admin ADMIN_PASSWORD=admin123 \
  DATABASE_URL=postgresql://postgres:postgres@localhost:5432/testum \
  MINIO_ENDPOINT=localhost:9010 MINIO_ACCESS_KEY=minioadmin MINIO_SECRET_KEY=minioadmin \
  uvicorn app.main:app --reload --port 8000

# Запуск worker (в отдельном терминале)
PYTHONPATH=src \
  FERNET_KEY=<key> DATABASE_URL=postgresql://postgres:postgres@localhost:5432/testum \
  MINIO_ENDPOINT=localhost:9010 MINIO_ACCESS_KEY=minioadmin MINIO_SECRET_KEY=minioadmin \
  python -m app.worker_launcher
```

### Тесты

```bash
# Unit + integration (без E2E и MinIO)
pytest tests/ --ignore=tests/e2e --ignore=tests/test_minio.py -q

# С измерением покрытия
pytest tests/ --ignore=tests/e2e --ignore=tests/test_minio.py \
    --cov=src --cov-report=term-missing --cov-report=html

# E2E (требует запущенного приложения + Playwright Chromium)
pytest tests/e2e/ --browser=chromium --timeout=60
```

## Покрытие тестами (Coverage)

> Данные актуальны на последний запуск `pytest --cov=src`. Генерируется автоматически.

**Итого: 62.5%** по исходному коду `src/` (unit + integration тесты, без E2E).

| Слой / Модуль | Покрытие |
|---|---|
| `app/audit.py` | 100% |
| `app/pagination.py` | 100% |
| `app/security.py` | 100% |
| `core/domain/` | 100% |
| `adapters/ufw/status_parser.py` | 100% |
| `adapters/postgres/orm_models.py` | 97% |
| `app/rate_limiter.py` | 97% |
| `app/config.py` | 97% |
| `ports/api/scripts.py` | 95% |
| `ports/api/users.py` | 92% |
| `ports/api/audit.py` | 89% |
| `ports/api/keys.py` | 89% |
| `ports/api/nervum.py` | 88% |
| `ports/api/schemas.py` | 90% |
| `adapters/nervum/sync.py` | 61% |
| `ports/api/automations.py` | 79% |
| `ports/api/backup.py` | 61% |
| `ports/api/platforms.py` | 37%* |
| `ports/api/virt.py` | 29%* |
| `ports/api/gitops.py` | 23%* |

\* Низкое покрытие обусловлено зависимостью от реальной инфраструктуры (SSH, libvirt, git). Покрываются E2E-тестами на реальном окружении.

### Тестовая база

| Тип | Файлы | Тестов |
|---|---|---|
| Unit / Integration | `tests/test_*.py` | ~305 |
| E2E (Playwright) | `tests/e2e/test_*.py` | ~650 |
| **Итого** | | **~955** |

Подробный HTML-отчёт покрытия: `htmlcov/index.html` (генерируется локально).

## Конфигурация (переменные окружения)

### Обязательные

| Переменная | Описание |
|---|---|
| `FERNET_KEY` | 32-байтовый Fernet-ключ (base64). Шифрует все credentials |
| `SECRET_KEY` | Секрет для подписи JWT |
| `ADMIN_USERNAME` | Логин администратора по умолчанию |
| `ADMIN_PASSWORD` | Пароль администратора по умолчанию |
| `DATABASE_URL` | PostgreSQL DSN: `postgresql://user:pass@host/db` |

### Опциональные

| Переменная | По умолчанию | Описание |
|---|---|---|
| `MINIO_ENDPOINT` | `minio:9000` | Адрес MinIO |
| `MINIO_ACCESS_KEY` | `minioadmin` | Ключ доступа MinIO |
| `MINIO_SECRET_KEY` | `minioadmin` | Секрет MinIO |
| `MINIO_BUCKET` | `testum-artifacts` | Бакет для хранения вывода задач |
| `MINIO_SECURE` | `false` | TLS для MinIO |
| `SSH_HOST_KEY_POLICY` | `auto_add` | `auto_add` — сохранять fingerprint автоматически, `strict` — проверять |
| `WORKER_MAX_CONCURRENCY` | `4` | Кол-во параллельных задач в worker |
| `WORKER_LEASE_TTL` | `60` | TTL аренды задачи (сек) |
| `WORKER_STOP_TIMEOUT` | `120` | Таймаут graceful-остановки worker (сек) |
| `WORKER_WATCHDOG_INTERVAL` | `15` | Интервал watchdog-а worker (сек) |
| `WORKER_RETRY_POLICY` | `exponential_jitter:1:2:300:0.2` | Retry-политика для упавших задач |

## CLI-клиент testumctl

```bash
# Установка
chmod +x src/ports/cli/testumctl
sudo ln -s "$(pwd)/src/ports/cli/testumctl" /usr/local/bin/testumctl

# Авторизация
testumctl login --url http://localhost:8001 -u admin

# Платформы
testumctl platforms list
testumctl platforms list --json
testumctl platforms add --name web-01 --host 192.168.1.10 --username ubuntu --auth-method password

# Выполнение команд
testumctl exec <platform_id> "uptime"
testumctl exec <platform_id> "df -h" --wait

# SSH-ключи
testumctl keys list
```

Токен сохраняется в `~/.testum/config.json` (права 0600).

## REST API

```bash
BASE=http://localhost:8001

# Авторизация
curl -c cookies.txt -X POST $BASE/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# Список платформ
curl -b cookies.txt $BASE/api/platforms/

# Добавить платформу
curl -b cookies.txt -X POST $BASE/api/platforms/ \
  -H "Content-Type: application/json" \
  -d '{"name":"web-01","host":"192.168.1.10","port":22,"username":"ubuntu","auth_method":"password","password":"secret"}'

# Выполнить команду
curl -b cookies.txt -X POST $BASE/api/platforms/{id}/run_command \
  -H "Content-Type: application/json" \
  -d '{"command":"uptime","timeout":60}'

# Развернуть ключи
curl -b cookies.txt -X POST $BASE/api/platforms/{id}/deploy_keys
```

### WebSocket — стриминг задачи

```javascript
const ws = new WebSocket('ws://localhost:8001/ws/tasks/{task_id}');
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.type === 'output')  console.log(msg.data);
  if (msg.type === 'done')    ws.close();
};
```

## Backup / Restore

```bash
# Экспорт (платформы + ключи + пользователи, без паролей)
curl -b cookies.txt $BASE/api/backup/export -o backup.yaml

# Импорт
curl -b cookies.txt -X POST $BASE/api/backup/import -F "file=@backup.yaml"
```

## GitOps-импорт

```bash
curl -b cookies.txt -X POST $BASE/api/gitops/import \
  -H "Content-Type: application/json" \
  -d '{
    "git_url": "https://github.com/org/infra.git",
    "branch": "main",
    "config_path": "testum-config.yaml",
    "dry_run": true
  }'
```

Формат `testum-config.yaml`:

```yaml
ssh_keys:
  - name: prod-key
    public_key: "ssh-rsa AAAA..."

platforms:
  - name: web-01
    host: 192.168.1.10
    port: 22
    username: ubuntu
    auth_method: key
    ssh_key_name: prod-key
```

GitOps автоматически ищет файл по путям: `testum-config.yaml`, `testum.yaml`, `testum-config.yml`, `config/testum.yaml`, `.testum/config.yaml`.

## Безопасность

- Все пароли и приватные ключи хранятся зашифрованными (Fernet AES-128-CBC)
- JWT передаётся только через HTTP-only cookie
- SSH fingerprint верифицируется при каждом подключении
- Все действия пользователей пишутся в audit-лог

## Лицензия

MIT
