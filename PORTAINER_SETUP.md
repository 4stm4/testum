# Развертывание Testum через Portainer - Пошаговая инструкция

## Шаг 1: Подготовка переменных окружения

### Генерация FERNET_KEY

Выполните в терминале с Python:
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

Или используйте готовый ключ (для тестирования):
```
FERNET_KEY=8KMhgoZ3LqvVNxKz4YHzMNJRCq5YUf3yx8WlBKxuX8k=
```

## Шаг 2: Создание стека в Portainer

1. **Откройте Portainer**: http://ваш-сервер:9000

2. **Перейдите в Stacks** → Нажмите **"Add stack"**

3. **Name**: `testum`

4. **Build method**: Выберите **"Repository"**

5. **Заполните поля репозитория**:
   ```
   Repository URL: https://github.com/4stm4/testum
   Repository reference: refs/heads/main
   Compose path: docker-compose.yml
   ```

6. **Environment variables** - Нажмите "+ Add environment variable" и добавьте:

   ```
   FERNET_KEY=8KMhgoZ3LqvVNxKz4YHzMNJRCq5YUf3yx8WlBKxuX8k=
   SECRET_KEY=change-me-to-random-string-at-least-32-chars
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=your_secure_password
   SSH_HOST_KEY_POLICY=auto_add
   ```

7. **Нажмите "Deploy the stack"**

Portainer автоматически:
- ✅ Склонирует репозиторий с GitHub
- ✅ Соберет Docker образ из Dockerfile
- ✅ Запустит все 5 контейнеров

## Шаг 3: Проверка развертывания

### Проверьте статус контейнеров

В Portainer перейдите в **Containers** и убедитесь, что все 5 контейнеров запущены:

- ✅ `testum_db` (PostgreSQL) - должен быть **healthy**
- ✅ `testum_redis` (Redis) - должен быть **healthy**
- ✅ `testum_minio` (MinIO) - должен быть **healthy**
- ✅ `testum_app` (FastAPI) - должен быть **running**
- ✅ `testum_celery` (Celery Worker) - должен быть **running**

### Проверьте логи

1. Откройте **Containers** → `testum_app` → **Logs**
2. Должны увидеть:
   ```
   INFO:     Started server process
   INFO:     Uvicorn running on http://0.0.0.0:8000
   ```

3. Если есть ошибки - проверьте, что все environment variables установлены

## Шаг 4: Доступ к приложению

После успешного развертывания сервисы доступны по адресам:

- **Web UI**: http://ваш-сервер:8000
- **API Docs**: http://ваш-сервер:8000/docs
- **MinIO Console**: http://ваш-сервер:9001

**Логин по умолчанию** (если использовали настройки выше):
- Username: `admin`
- Password: `your_secure_password`

**MinIO** (для управления файлами):
- Username: `minioadmin`
- Password: `minioadmin`

## Troubleshooting

### Ошибка "image not found" или "pull access denied"

**Причина**: Portainer пытается скачать образ вместо сборки

**Решение**: Убедитесь, что в docker-compose.yml есть секции `build`:

```yaml
app:
  build:
    context: .
    dockerfile: Dockerfile
  image: testum-app:latest
```

### Ошибка "FERNET_KEY not configured"

**Причина**: Не установлена переменная окружения

**Решение**: 
1. Перейдите в Portainer → Stacks → testum → Editor
2. Добавьте `FERNET_KEY` в Environment variables
3. Нажмите "Update the stack"

### Контейнер app падает с ошибкой "connection refused"

**Причина**: База данных или Redis еще не готовы

**Решение**: Подождите 30-60 секунд. Контейнер app должен автоматически перезапуститься после того, как БД станет healthy

### Ошибка при сборке "BuildKit error"

**Причина**: Конфликт с Docker BuildKit

**Решение**: Уже исправлено в текущей версии docker-compose.yml

## Обновление приложения

Когда в репозитории появятся обновления:

1. Перейдите в Portainer → **Stacks** → `testum`
2. Нажмите **"Pull and redeploy"**
3. Portainer автоматически:
   - Скачает последние изменения из GitHub
   - Пересоберет образ
   - Перезапустит контейнеры

## Удаление стека

Если нужно полностью удалить приложение:

1. Portainer → Stacks → testum
2. Нажмите **"Delete this stack"**
3. Отметьте **"Also remove associated volumes"** если хотите удалить данные
4. Подтвердите удаление

---

## Быстрая справка по переменным окружения

| Переменная | Обязательная | Описание | Пример |
|------------|--------------|----------|--------|
| `FERNET_KEY` | ✅ Да | Ключ шифрования (32 байта base64) | `8KMhg...X8k=` |
| `SECRET_KEY` | Рекомендуется | JWT secret key | `my-secret-key-123` |
| `ADMIN_USERNAME` | Нет | Имя администратора | `admin` |
| `ADMIN_PASSWORD` | Нет | Пароль администратора | `secure_pass` |
| `SSH_HOST_KEY_POLICY` | Нет | Политика проверки SSH ключей | `auto_add` |

---

**Готово!** Ваше приложение Testum развернуто и готово к использованию.
