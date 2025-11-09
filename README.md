# testum - SSH Key & Platform Management System

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![Python](https://img.shields.io/badge/python-3.11-blue)

Минимальный, но полнофункциональный веб-сервис для управления SSH public-ключами и платформами (хостами), с возможностью развертывания ключей на удаленных хостах и выполнения команд.

## 🚀 Быстрый старт (2 минуты)

### Деплой в Portainer:

1. Portainer → Stacks → Add stack → Web editor
2. Скопируйте [`docker-compose.yml`](docker-compose.yml)
3. Deploy!
4. Откройте http://ваш-сервер:8000 (admin / admin123)

📖 **Подробная инструкция**: [QUICK_TEST.md](QUICK_TEST.md) или [PORTAINER_SETUP.md](PORTAINER_SETUP.md)

---

## 🎯 Возможности

- ✅ **CRUD SSH Public Keys** - создание, просмотр, удаление SSH ключей
- ✅ **CRUD Platforms** - управление платформами (хосты с SSH доступом)
- ✅ **Deploy Keys** - атомарное развертывание ключей на платформы с idempotency
- ✅ **Run Commands** - асинхронное выполнение команд на платформах
- ✅ **WebSocket Streaming** - real-time стриминг вывода задач
- ✅ **Encryption** - безопасное шифрование credentials (Fernet)
- ✅ **S3 Storage** - хранение артефактов в MinIO
- ✅ **Audit Logging** - полное логирование действий
- ✅ **Web UI** - простой веб-интерфейс для управления

## 🏗️ Архитектура

### Стек технологий

- **Web Framework**: Starlette (ASGI) + Jinja2 + Uvicorn
- **Database**: PostgreSQL + SQLAlchemy + Alembic
- **Task Queue**: Celery + Redis
- **SSH Operations**: Paramiko (синхронно в Celery tasks)
- **WebSocket**: Starlette WebSocket + Redis Pub/Sub
- **Storage**: MinIO (S3-compatible)
- **Encryption**: Fernet (symmetric encryption)
- **Testing**: Pytest + pytest-asyncio

### Компоненты

```
┌─────────────┐
│   Browser   │
│   (UI)      │
└──────┬──────┘
       │
       │ HTTP/WebSocket
       ▼
┌─────────────┐     ┌──────────┐
│  Starlette  │────▶│PostgreSQL│
│    (ASGI)   │     └──────────┘
└──────┬──────┘
       │
       │ Task Queue
       ▼
┌─────────────┐     ┌──────────┐
│   Celery    │────▶│  Redis   │
│   Worker    │     │ (Pub/Sub)│
└──────┬──────┘     └──────────┘
       │
       │ SSH
       ▼
┌─────────────┐     ┌──────────┐
│  Paramiko   │────▶│  MinIO   │
│ (SSH Client)│     │  (S3)    │
└─────────────┘     └──────────┘
```

## 🚀 Быстрый старт

### Для локальной разработки

Требования: Docker и Docker Compose, Python 3.11+

См. [QUICK_START.md](QUICK_START.md) для подробных инструкций.

### Для деплоя в Portainer

1. **Быстрый чеклист**: [PORTAINER_CHECKLIST.md](PORTAINER_CHECKLIST.md)
2. **Подробные инструкции**: [PORTAINER_DEPLOYMENT.md](PORTAINER_DEPLOYMENT.md)

**Кратко:**
```bash
# 1. Push код в репозиторий (GitHub Actions соберет образ автоматически)
git push

# 2. В Portainer создайте stack с docker-compose.yml из репозитория
# 3. Добавьте environment variables из .env.portainer
# 4. Deploy stack!
```

### Локальный запуск (legacy)

### 1. Клонирование и настройка

```bash
cd testup
```

### 2. Генерация ключа шифрования

```bash
make generate-key
```

Скопируйте сгенерированный `FERNET_KEY` и добавьте в `.env` файл.

### 3. Создание .env файла

```bash
cp .env.example .env
```

Отредактируйте `.env` и установите:
- `FERNET_KEY` - ключ шифрования (из шага 2)
- `ADMIN_USERNAME` и `ADMIN_PASSWORD` - учетные данные администратора

### 4. Запуск сервисов

```bash
make build
make up
```

Сервисы будут доступны:
- **Web UI**: http://localhost:8000
- **API**: http://localhost:8000/api/
- **MinIO Console**: http://localhost:9001 (admin/minioadmin)
- **PostgreSQL**: localhost:5432

### 5. Проверка работоспособности

```bash
curl http://localhost:8000/health
```

## 📚 API Документация

### Аутентификация

```bash
# Получить JWT token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

### SSH Keys

```bash
# Список ключей
curl http://localhost:8000/api/keys/

# Создать ключ
curl -X POST http://localhost:8000/api/keys/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-key",
    "public_key": "ssh-rsa AAAAB3NzaC1yc2E... user@host"
  }'

# Удалить ключ
curl -X DELETE http://localhost:8000/api/keys/{key_id}
```

### Platforms

```bash
# Список платформ
curl http://localhost:8000/api/platforms/

# Создать платформу (password auth)
curl -X POST http://localhost:8000/api/platforms/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "server-01",
    "host": "192.168.1.100",
    "port": 22,
    "username": "ubuntu",
    "auth_method": "password",
    "password": "secret123"
  }'

# Создать платформу (private key auth)
curl -X POST http://localhost:8000/api/platforms/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "server-02",
    "host": "192.168.1.101",
    "port": 22,
    "username": "ubuntu",
    "auth_method": "private_key",
    "private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\n..."
  }'

# Получить платформу
curl http://localhost:8000/api/platforms/{platform_id}

# Удалить платформу
curl -X DELETE http://localhost:8000/api/platforms/{platform_id}
```

### Actions

```bash
# Deploy всех ключей на платформу
curl -X POST http://localhost:8000/api/platforms/{platform_id}/deploy_keys \
  -H "Content-Type: application/json" \
  -d '{}'

# Deploy конкретных ключей
curl -X POST http://localhost:8000/api/platforms/{platform_id}/deploy_keys \
  -H "Content-Type: application/json" \
  -d '{
    "key_ids": ["uuid1", "uuid2"]
  }'

# Выполнить команду
curl -X POST http://localhost:8000/api/platforms/{platform_id}/run_command \
  -H "Content-Type: application/json" \
  -d '{
    "command": "uptime",
    "timeout": 60
  }'

# Проверить статус задачи
curl http://localhost:8000/api/tasks/{task_id}
```

### WebSocket Streaming

```javascript
// Подключиться к стриму задачи
const ws = new WebSocket('ws://localhost:8000/ws/tasks/{task_id}');

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log(`[${message.type}] ${message.payload}`);
};
```

## 🔒 Безопасность

### Шифрование Credentials

- Все пароли и приватные ключи шифруются с помощью **Fernet** (symmetric encryption)
- Ключ шифрования (`FERNET_KEY`) хранится в переменных окружения
- Никогда не записывайте секреты в логи

### SSH Host Key Verification

По умолчанию используется политика `auto_add`:
- При первом подключении fingerprint хоста сохраняется
- При последующих подключениях проверяется соответствие
- Если fingerprint изменился - подключение отклоняется

Настраивается через `SSH_HOST_KEY_POLICY` в `.env`:
- `auto_add` - автоматически принимать новые хосты (по умолчанию)
- `strict` - отклонять неизвестные хосты

### Atomic Write

Развертывание ключей использует атомарную запись:
1. Запись в временный файл `~/.ssh/authorized_keys.tmp`
2. Установка прав 600
3. Atomic rename в `~/.ssh/authorized_keys`

### Idempotency

Повторное развертывание одних и тех же ключей не создает дубликатов.

## 🧪 Тестирование

### Запуск тестов

```bash
make test
```

### Запуск с coverage

```bash
docker-compose exec app pytest tests/ -v --cov=app --cov-report=html
```

Coverage отчет будет доступен в `htmlcov/index.html`.

### Линтинг

```bash
make lint
```

### Форматирование кода

```bash
make format
```

## 📦 Makefile команды

```bash
make help          # Показать все доступные команды
make build         # Собрать Docker образы
make up            # Запустить все сервисы
make down          # Остановить все сервисы
make logs          # Просмотр логов
make test          # Запустить тесты
make lint          # Запустить линтеры
make format        # Отформатировать код
make migrate       # Применить миграции
make migration     # Создать новую миграцию
make generate-key  # Сгенерировать Fernet ключ
make clean         # Очистить контейнеры и volumes
make shell         # Открыть shell в app контейнере
make db-shell      # Открыть psql shell
make redis-cli     # Открыть redis-cli
```

## 🗄️ Структура базы данных

### SSHKey
- `id` (UUID, PK)
- `name` (string)
- `public_key` (text)
- `created_by` (string, nullable)
- `created_at` (timestamp)

### Platform
- `id` (UUID, PK)
- `name` (string, unique)
- `host` (string)
- `port` (int, default 22)
- `username` (string)
- `auth_method` (enum: 'password' | 'private_key')
- `encrypted_password` (bytes, nullable)
- `encrypted_private_key` (bytes, nullable)
- `known_host_fingerprint` (string, nullable)
- `created_at` (timestamp)

### TaskRun
- `id` (UUID, PK)
- `celery_task_id` (string, unique)
- `type` (enum: 'deploy' | 'run_command')
- `platform_id` (UUID, FK, nullable)
- `status` (enum: 'pending' | 'running' | 'success' | 'failed')
- `result_location` (string, S3 key, nullable)
- `stdout` (text, nullable)
- `stderr` (text, nullable)
- `error_message` (text, nullable)
- `metadata` (JSON, nullable)
- `started_at`, `finished_at`, `created_at` (timestamps)

### AuditLog
- `id` (UUID, PK)
- `user` (string)
- `action` (string)
- `object_type` (string)
- `object_id` (string, nullable)
- `meta` (JSON, nullable)
- `timestamp` (timestamp)

## 🔧 Конфигурация

Все настройки через переменные окружения (`.env`):

```bash
# Application
APP_ENV=development
SECRET_KEY=your-secret-key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123

# Encryption (ОБЯЗАТЕЛЬНО!)
FERNET_KEY=your-fernet-key-32-bytes-urlsafe-base64

# Database
DATABASE_URL=postgresql://postgres:postgres@db:5432/testum

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=testum-artifacts
MINIO_SECURE=false

# SSH
SSH_HOST_KEY_POLICY=auto_add  # or 'strict'
```

## 🐛 Отладка

### Просмотр логов

```bash
# Все сервисы
make logs

# Конкретный сервис
docker-compose logs -f app
docker-compose logs -f celery_worker
```

### Доступ к контейнерам

```bash
# Shell в app контейнере
make shell

# PostgreSQL
make db-shell

# Redis
make redis-cli
```

### Проверка Celery задач

```bash
# В redis-cli
KEYS task:*
GET task:{task_id}
```

## 🚧 Известные ограничения

1. **Аутентификация**: Простая JWT аутентификация без refresh tokens
2. **Пользователи**: Один hardcoded админ (для MVP)
3. **SSH**: Синхронные операции в Celery (блокируют worker)
4. **Rate Limiting**: Отсутствует
5. **Pagination**: Не реализована для больших списков

## 🎯 Дальнейшие улучшения

### High Priority
- [ ] Полноценная система пользователей и ролей
- [ ] Async SSH операции (asyncssh вместо Paramiko)
- [ ] Rate limiting и throttling
- [ ] Pagination для API
- [ ] Улучшенная обработка ошибок и retry логика
- [ ] Метрики и мониторинг (Prometheus)

### Medium Priority
- [ ] Интеграция с HashiCorp Vault для секретов
- [ ] Multi-platform deployment (deploy на несколько хостов одновременно)
- [ ] Scheduling задач (periodic tasks)
- [ ] WebSocket authentication
- [ ] API versioning
- [ ] OpenAPI/Swagger документация

### Low Priority
- [ ] Интеграция с Ansible playbooks
- [ ] SSH agent forwarding
- [ ] Key rotation механизм
- [ ] Backup/restore функции
- [ ] Advanced audit logging с экспортом

## 🤝 Допущения и решения

### Host Key Verification
По умолчанию используется `AutoAddPolicy` для автоматического принятия новых хостов. При первом подключении fingerprint сохраняется в БД и проверяется при последующих подключениях.

**Trade-off**: Упрощает первоначальную настройку, но требует доверия при первом подключении (TOFU - Trust On First Use).

### Paramiko vs asyncssh
Используется **Paramiko** (синхронный) внутри Celery tasks.

**Почему не asyncssh?**
- Celery tasks по умолчанию синхронные
- Paramiko более зрелая библиотека с широкой поддержкой
- Для async нужна полная переработка task execution

**Trade-off**: Блокирующие SSH операции, но проще в реализации.

### Credentials Storage
Используется **Fernet** (symmetric encryption) для шифрования.

**Почему не асимметричное шифрование?**
- Проще в реализации и управлении
- Достаточно для single-server deployment
- Для production рекомендуется HashiCorp Vault

## 📝 Лицензия

MIT License

## 📧 Контакты

Для вопросов и предложений создавайте issues в репозитории.

---

**Версия**: 0.1.0  
**Дата**: 9 ноября 2025 г.  
**Статус**: MVP / Development
