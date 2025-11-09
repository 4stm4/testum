# testum - Remote SSH Execution Platform

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![Python](https://img.shields.io/badge/python-3.11-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**Платформа для удаленного выполнения команд и кода на SSH-хостах**

Современный веб-интерфейс для централизованного управления удаленными серверами. Выполняйте команды, запускайте скрипты, развертывайте приложения на множестве хостов одновременно с real-time мониторингом.

## 🎯 Возможности

- 🚀 **Удаленное выполнение команд** - запуск на одном или нескольких хостах
- 📜 **Запуск скриптов и кода** - deploy приложений, автоматизация задач
- ⏱️ **Асинхронное выполнение** - фоновые задачи с real-time мониторингом
- 📊 **WebSocket стриминг** - вывод команд в реальном времени
- 🔑 **Управление SSH ключами** - централизованное хранение и развертывание
- 🖥️ **Управление платформами** - добавление и настройка удаленных хостов
- 🔐 **Безопасность** - JWT авторизация, шифрование credentials (Fernet)
- 🌙 **Современный UI** - темная/светлая тема, поддержка EN/RU
- 🔄 **Auto-Update** - автоматические обновления из GitHub

### 🔮 В планах:
- 🐳 Управление нативными контейнерами (без Docker)
- 🖥️ Создание виртуальных машин (libvirt + KVM + QEMU)

## 🏗️ Архитектура

```
Browser (UI) → Starlette (ASGI) → PostgreSQL
                     ↓
                  Celery Worker → Redis (Queue + Pub/Sub)
                     ↓
                Paramiko (SSH) → MinIO (S3 logs)
                     ↓
              Remote Hosts (SSH)
```

**Стек**: Starlette, PostgreSQL, Celery, Redis, MinIO, Paramiko, Jinja2

## 🚀 Быстрый старт

### Деплой в Portainer (рекомендуется)

1. Portainer → Stacks → Add stack → Web editor
2. Вставьте содержимое `docker-compose.yml`
3. Environment variables:
   ```bash
   FERNET_KEY=<generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=admin123
   SECRET_KEY=<random-string>
   ```
4. Deploy!
5. Откройте http://your-server:8000

### Локальный запуск

```bash
# 1. Генерация ключа шифрования
make generate-key

# 2. Настройка .env
cp .env.example .env
# Добавьте FERNET_KEY из шага 1

# 3. Запуск
make build
make up

# 4. Доступ
open http://localhost:8000
```

**Доступы по умолчанию:**
- Web UI: admin / admin123
- MinIO Console: http://localhost:9001 (minioadmin / minioadmin)

## 📖 Использование

### Добавление хоста

1. **Platforms** → **Add Platform**
2. Укажите: name, host, port, username
3. Выберите метод авторизации:
   - **Password** - простой пароль
   - **Private Key** - SSH приватный ключ

### Развертывание SSH ключей

1. **SSH Keys** → **Add Key** - добавьте публичный ключ
2. **Platforms** → выберите хост → **Deploy Keys**
3. Ключи атомарно добавятся в `~/.ssh/authorized_keys`

### Выполнение команд

1. **Platforms** → выберите хост → **Run Command**
2. Введите команду, например: `uptime`, `df -h`, `docker ps`
3. Наблюдайте вывод в real-time через WebSocket

## 🔒 Безопасность

- **Шифрование**: Все пароли и ключи шифруются Fernet (symmetric encryption)
- **JWT авторизация**: HTTP-only cookies, защита всех роутов
- **SSH Host Key Verification**: Автоматическое сохранение fingerprint при первом подключении
- **Atomic Write**: Безопасное обновление `authorized_keys` через temp file + rename
- **Audit Logging**: Полное логирование действий пользователей

## 📚 API

### Аутентификация

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

### Управление платформами

```bash
# Список
curl http://localhost:8000/api/platforms/

# Создать
curl -X POST http://localhost:8000/api/platforms/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "server-01",
    "host": "192.168.1.100",
    "port": 22,
    "username": "ubuntu",
    "auth_method": "password",
    "password": "secret"
  }'

# Выполнить команду
curl -X POST http://localhost:8000/api/platforms/{id}/run_command \
  -H "Content-Type: application/json" \
  -d '{"command": "uptime", "timeout": 60}'
```

### WebSocket стриминг

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/tasks/{task_id}');
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log(`[${msg.type}] ${msg.payload}`);
};
```

## 🛠️ Разработка

### Команды Makefile

```bash
make help          # Справка
make build         # Собрать образы
make up            # Запустить сервисы
make down          # Остановить
make logs          # Просмотр логов
make test          # Запустить тесты
make shell         # Shell в app контейнере
make db-shell      # PostgreSQL shell
make migrate       # Применить миграции
make migration     # Создать миграцию
```

### Тестирование

```bash
make test                                          # Все тесты
docker-compose exec app pytest tests/ -v --cov   # С coverage
```

### Структура проекта

```
app/
├── main.py              # Starlette приложение
├── models.py            # SQLAlchemy модели
├── schemas.py           # Pydantic схемы
├── tasks.py             # Celery задачи
├── ssh_helper.py        # Paramiko операции
├── crypto.py            # Fernet шифрование
├── api/                 # API endpoints
│   ├── keys.py
│   └── platforms.py
└── templates/           # Jinja2 шаблоны
```

## 🔧 Конфигурация

Основные переменные `.env`:

```bash
# ОБЯЗАТЕЛЬНО
FERNET_KEY=<32-byte-urlsafe-base64>  # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
SECRET_KEY=<random-string>

# Database
DATABASE_URL=postgresql://postgres:postgres@db:5432/testum

# Redis
REDIS_URL=redis://redis:6379/0

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# SSH
SSH_HOST_KEY_POLICY=auto_add  # или 'strict'
```

## 📊 База данных

### Таблицы

- **SSHKey** - публичные SSH ключи
- **Platform** - удаленные хосты с credentials
- **TaskRun** - история выполнения задач
- **AuditLog** - журнал действий
- **User** - пользователи (готова миграция для multi-user)

### Миграции

```bash
make migration MSG="Add new feature"  # Создать
make migrate                           # Применить
```

## 🚧 Ограничения и планы

### Текущие ограничения
- Один admin пользователь (миграция для multi-user готова)
- Синхронные SSH операции (блокируют Celery worker)
- Нет pagination для больших списков
- Нет rate limiting

### Планы развития
- ✅ Multi-user с RBAC (миграция готова)
- 🔄 Async SSH (asyncssh)
- 🔄 Pagination и rate limiting
- 🔮 Нативные контейнеры
- 🔮 VM управление (libvirt + KVM + QEMU)
- 🔮 HashiCorp Vault интеграция

## 📝 Лицензия

MIT License

## 🤝 Контрибьюция

Issues и Pull Requests приветствуются!

---

**Версия**: 0.1.0 | **Дата**: Ноябрь 2025 | **Статус**: MVP
