# Чеклист деплоя Testum в Portainer

## Перед деплоем

- [ ] У меня есть доступ к Portainer
- [ ] Я сгенерировал FERNET_KEY (или использую тестовый)
- [ ] Я выбрал пароль для админа

## Создание стека

- [ ] Открыл Portainer → Stacks → Add stack
- [ ] Имя стека: `testum`
- [ ] Метод: Web editor
- [ ] Скопировал содержимое `docker-compose.portainer.yml`

## Environment Variables (ОБЯЗАТЕЛЬНО!)

- [ ] `FERNET_KEY` = `8KMhgoZ3LqvVNxKz4YHzMNJRCq5YUf3yx8WlBKxuX8k=`
- [ ] `SECRET_KEY` = `your-super-secret-key-change-in-production`
- [ ] `ADMIN_USERNAME` = `admin`
- [ ] `ADMIN_PASSWORD` = `your_secure_password`
- [ ] `SSH_HOST_KEY_POLICY` = `auto_add`

⚠️ **БЕЗ FERNET_KEY ПРИЛОЖЕНИЕ НЕ ЗАПУСТИТСЯ!**

## После деплоя

- [ ] Дождался 2-3 минуты
- [ ] Проверил, что все 5 контейнеров запущены:
  - [ ] testum_db (healthy)
  - [ ] testum_redis (healthy)
  - [ ] testum_minio (healthy)
  - [ ] testum_app (running)
  - [ ] testum_celery (running)

## Проверка логов testum_app

Должен увидеть:
- [ ] "Installing system dependencies..."
- [ ] "Cloning repository..."
- [ ] "Installing Python packages..."
- [ ] "Running database migrations..."
- [ ] "Starting application..."
- [ ] "Uvicorn running on http://0.0.0.0:8000"

## Доступ

- [ ] Web UI открывается: http://ваш-сервер:8000
- [ ] MinIO Console открывается: http://ваш-сервер:9011
- [ ] Могу войти с admin / your_secure_password

## Если что-то не так

### Ошибка: "FERNET_KEY environment variable is required"
→ Вернись в Stacks → testum → Editor → Environment variables → Добавь FERNET_KEY

### Ошибка: "destination path already exists"
→ Удали стек и создай заново (это очистит /tmp)

### Контейнер app постоянно перезапускается
→ Проверь логи: Containers → testum_app → Logs

### Порты 9000/9001 заняты
→ Уже исправлено в docker-compose.portainer.yml (используются 9010/9011)

---

## Быстрая команда для генерации ключей

**FERNET_KEY**:
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

**SECRET_KEY**:
```python
import secrets
print(secrets.token_urlsafe(32))
```
