# Быстрый деплой в Portainer - Шпаргалка

## 1. Откройте Portainer
http://ваш-сервер:9000

## 2. Stacks → Add stack

**Name**: `testum`

**Method**: Web editor

## 3. Скопируйте docker-compose.portainer.yml

Откройте файл `docker-compose.portainer.yml` из репозитория и вставьте в редактор.

## 4. Environment variables

Добавьте эти переменные (нажмите "+ Add environment variable"):

```
FERNET_KEY=8KMhgoZ3LqvVNxKz4YHzMNJRCq5YUf3yx8WlBKxuX8k=
SECRET_KEY=your-super-secret-key-change-in-production-min-32-chars
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password
SSH_HOST_KEY_POLICY=auto_add
```

## 5. Deploy the stack

Нажмите кнопку внизу страницы.

## 6. Проверка

Дождитесь, когда все 5 контейнеров станут зелеными (это займет 2-3 минуты):
- testum_db (healthy)
- testum_redis (healthy)
- testum_minio (healthy)
- testum_app (running) - ждет установки зависимостей
- testum_celery (running) - ждет установки зависимостей

> **Важно**: Первый запуск медленный из-за клонирования репозитория и установки зависимостей.

## 7. Доступ

- **Web UI**: http://ваш-сервер:8000
- **MinIO Console**: http://ваш-сервер:9011
- **Username**: admin
- **Password**: your_secure_password

---

## Если возникли проблемы

### Контейнер app не запускается
1. Откройте Containers → testum_app → Logs
2. Проверьте, что FERNET_KEY установлен
3. Подождите 1-2 минуты (установка зависимостей)

### Ошибка "connection refused"
Подождите, пока БД станет healthy (~30 секунд)

### Нужно обновить код
1. Portainer → Stacks → testum
2. Stop stack
3. Start stack
(код подтянется из репозитория автоматически через volumes)
