# testum - Remote SSH Execution Platform

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![Python](https://img.shields.io/badge/python-3.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**Платформа для удаленного выполнения команд и кода на SSH-хостах**

Современный веб-интерфейс для централизованного управления удаленными серверами. Выполняйте команды, запускайте скрипты, развертывайте приложения на множестве хостов одновременно с real-time мониторингом.

## 🎯 Возможности

- 🚀 **Удаленное выполнение команд** - запуск на одном или нескольких хостах
- 📜 **Запуск скриптов и кода** - deploy приложений, автоматизация задач
- 📊 **WebSocket стриминг** - вывод команд в реальном времени через БД polling
- 🔑 **Управление SSH ключами** - централизованное хранение и развертывание
- 🖥️ **Управление платформами** - добавление и настройка удаленных хостов
- 🔐 **Безопасность** - JWT авторизация, RBAC, шифрование credentials (Fernet)
- 🌙 **Современный UI** - темная/светлая тема, поддержка EN/RU, Material Design 3
- 📋 **Audit Logs** - полное логирование действий с фильтрами и статистикой
- 🔄 **Auto-Update** - автоматические обновления из GitHub

### 🔮 В планах:
- 🐳 Управление нативными контейнерами (без Docker)
- 🖥️ Создание виртуальных машин (libvirt + KVM + QEMU)

## 🏗️ Архитектура

```
Browser → Nginx (Reverse Proxy + Loading Screen)
            ↓
         Starlette (ASGI) → PostgreSQL
            ↓
            ↓
         AsyncSSH → MinIO (S3 logs)
            ↓
         Remote Hosts (SSH)
```


**Без Redis** - используется только PostgreSQL для очередей и результатов задач

**Особенности деплоя**:
- Nginx показывает красивый loading screen во время первого запуска
- Автоматическая проверка готовности приложения через health check
- Git clone из GitHub при каждом старте контейнера
- Виртуальное окружение Python для изоляции зависимостей

## 🚀 Быстрый старт

### Деплой в Portainer (рекомендуется)

1. Portainer → Stacks → Add stack → Web editor
2. Вставьте содержимое `docker-compose.yml`
3. Environment variables:
   ```bash
   FERNET_KEY=<generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=admin123root@76f1ab574a6b:/app# cat /app/app/api/platforms.py | grep -A 5 "auth_method=" | head -15
            auth_method=platform_data.auth_method.lower(),
            encrypted_password=encrypted_password,
            ssh_key_id=platform_data.ssh_key_id,
        )

        db.add(new_platform)
root@76f1ab574a6b:/app# 

   SECRET_KEY=<random-string>
   ```
4. Deploy!
5. Откройте http://your-server:8000

**Примечание:** При первом запуске контейнер автоматически:
- Установит системные зависимости (gcc, git, postgresql-client)
- Склонирует последнюю версию из GitHub
- Создаст виртуальное окружение Python
- Установит все зависимости из requirements.txt
- Применит миграции базы данных
- Запустит Uvicorn web-сервер

Это может занять 1-2 минуты. Nginx покажет loading screen и автоматически перенаправит на приложение после успешного запуска.

### Локальный запуск

```bash
# 1. Генерация ключа шифрования
make generate-key

# 2. Настройка .env
cp .env.example .env
# Добавьте FERNET_KEY из шага 1

# 3. Скачать шрифты для оффлайн работы (опционально)
./download_fonts.sh

# 4. Запуск
make build
make up

# 5. Доступ
open http://localhost:8000
```

**Доступы по умолчанию:**
- Web UI: http://localhost:8000 (admin / admin123)
- MinIO Console: http://localhost:9011 (minioadmin / minioadmin)

**Примечание:** Шрифты Material Design 3 (Roboto, Material Symbols) скачиваются локально скриптом `download_fonts.sh` для работы без интернета. Если не запустить скрипт, шрифты не будут загружены, но приложение продолжит работать (используя системные шрифты).

## 🧪 Разработка и тестирование

Контейнер приложения собирается только с продакшен-зависимостями, поэтому инструменты разработки вроде `pytest`, `black` и `flake8`
не попадают в финальный образ. Для локальной проверки качества кода используйте команды `make test`, `make lint` или `make format` —
они запускают временный контейнер, ставят необходимые dev-зависимости и выполняют тесты/линтеры.

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
// Подключение к задаче
const ws = new WebSocket('ws://localhost:8000/ws/tasks/{task_id}');

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  
  if (msg.type === 'output') {
    console.log(msg.data);  // Вывод команды
  } else if (msg.type === 'done') {
    console.log('Exit code:', msg.exit_code);
  }
};
```

**Примечание**: WebSocket работает через polling БД (без Redis)

## 🖥️ CLI-клиент testumctl

Testumctl - command-line интерфейс для управления Testum.

### Установка

```bash
# Из корня проекта
chmod +x testumctl
sudo ln -s $(pwd)/testumctl /usr/local/bin/testumctl
```

### Использование

```bash
# Авторизация
testumctl login --url http://localhost:8000 -u admin

# Список платформ
testumctl platforms list
testumctl platforms list --json  # JSON формат

# Добавить платформу (пароль)
testumctl platforms add \
  --name server-01 \
  --host 192.168.1.100 \
  --username ubuntu \
  --auth-method password

# Добавить платформу (SSH ключ)
testumctl platforms add \
  --name server-02 \
  --host 192.168.1.101 \
  --username ubuntu \
  --auth-method key \
  --ssh-key-id 1

# Удалить платформу
testumctl platforms remove <platform_id>

# Выполнить команду
testumctl exec <platform_id> "uptime"
testumctl exec <platform_id> "df -h" --wait  # Ждать завершения
```

### Конфигурация

Токен авторизации хранится в `~/.testum/config.json` с правами `0600`.

## 📥 Backup & Restore

### Экспорт конфигурации

```bash
curl -X GET http://localhost:8000/api/backup/export \
  -H "Authorization: Bearer <token>" \
  -o backup.yaml
```

### Импорт конфигурации

```bash
curl -X POST http://localhost:8000/api/backup/import \
  -H "Authorization: Bearer <token>" \
  -F "file=@backup.yaml"
```

**Формат YAML**:
- Metadata (version, timestamp, author)
- Платформы (без паролей)
- SSH ключи (без приватных ключей)
- Пользователи (только список, без паролей)

## 🔀 GitOps Import

Импорт конфигурации из Git репозитория.

### API

```bash
curl -X POST http://localhost:8000/api/gitops/import \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "git_url": "https://github.com/user/repo.git",
    "branch": "main",
    "config_path": "testum-config.yaml",
    "username": "git_username",
    "token": "git_token",
    "dry_run": true
  }'
```

### Формат конфигурации

Создайте `testum-config.yaml` в Git репозитории:

```yaml
ssh_keys:
  - name: prod-key
    public_key: "ssh-rsa AAAA..."
    description: Production SSH key

platforms:
  - name: web-server-01
    host: 192.168.1.100
    port: 22
    username: ubuntu
    auth_method: key
    ssh_key_name: prod-key  # Ссылка на SSH ключ по имени
    description: Production web server
  
  - name: db-server-01
    host: 192.168.1.101
    port: 22
    username: postgres
    auth_method: password
    description: Production database server
```

### Альтернативные пути

GitOps автоматически ищет конфигурацию в:
- `testum-config.yaml` (по умолчанию)
- `testum.yaml`
- `testum-config.yml`
- `config/testum.yaml`
- `.testum/config.yaml`

### Dry Run

Используйте `"dry_run": true` для проверки без импорта:
- Проверяет доступность репозитория
- Валидирует формат конфигурации
- Показывает, что будет импортировано
- Не вносит изменения в БД

**Примечание**: WebSocket работает через polling БД (без Redis)
  } else if (msg.type === 'status') {
    console.log(`Status: ${msg.status}`);
  } else if (msg.type === 'done') {
    console.log(`Completed with exit code: ${msg.exit_code}`);
    ws.close();
  }
};
```

**Примечание**: WebSocket работает через polling БД (без Redis)

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
├── ssh_helper.py        # AsyncSSH операции
├── crypto.py            # Fernet шифрование
├── audit.py             # Audit logging helper
├── api/                 # API endpoints
│   ├── keys.py
│   ├── platforms.py
│   ├── audit.py         # Audit logs API
│   ├── backup.py        # Backup/Restore API
│   ├── gitops.py        # GitOps Import API
│   └── users.py         # User management
└── templates/           # Jinja2 шаблоны
    ├── audit.html       # Audit logs UI
    └── ...
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

### Реализовано (100% MVP готово) 🎉
- ✅ Multi-user с RBAC (Admin/Operator/Viewer)
- ✅ Async SSH (asyncssh)
- ✅ WebSocket real-time streaming (через БД polling)
- ✅ Audit Logs UI с фильтрами и статистикой
- ✅ Rate limiting и pagination
- ✅ Material Design 3 UI
- ✅ Экспорт audit-логов (JSON/CSV)
- ✅ Backup/Restore конфигурации (YAML)
- ✅ CLI-клиент testumctl
- ✅ GitOps Import (импорт из Git репозитория)

### Планы (v2.0)
- 🔮 Нативные контейнеры (Docker API)
- 🔮 VM управление (libvirt + KVM + QEMU)
- 🔮 HashiCorp Vault интеграция
- 🔮 Scheduled tasks (cron-like)
- 🔮 Webhooks и интеграции

## 📝 Лицензия

MIT License

## 🤝 Контрибьюция

Issues и Pull Requests приветствуются!

---

**Версия**: 0.1.0 | **Дата**: Ноябрь 2025 | **Статус**: MVP
