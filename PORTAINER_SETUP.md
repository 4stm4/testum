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

### Генерация SECRET_KEY

Вариант 1 - Python (рекомендуется):
```python
import secrets
print(secrets.token_urlsafe(32))
```

Вариант 2 - OpenSSL:
```bash
openssl rand -base64 32
```

Вариант 3 - Онлайн:
Перейдите на https://randomkeygen.com/ и скопируйте любой длинный ключ

Или используйте готовый ключ (для тестирования):
```
SECRET_KEY=your-super-secret-key-change-in-production-min-32-chars
```

## Шаг 2: Создание стека в Portainer

### ✅ Простой метод: Используйте готовый docker-compose

1. **Откройте Portainer**: http://ваш-сервер:9000

2. **Перейдите в Stacks** → Нажмите **"Add stack"**

3. **Name**: `testum`

4. **Build method**: Выберите **"Web editor"**

5. **Скопируйте содержимое `docker-compose.yml`** из репозитория:
   
   https://raw.githubusercontent.com/4stm4/testum/main/docker-compose.yml

6. **НЕ НУЖНО добавлять переменные окружения** - они уже прописаны в файле!
   
   > ⚠️ **Внимание**: В файле используются ТЕСТОВЫЕ credentials. Для production измените их прямо в файле перед деплоем:
   > - `ADMIN_PASSWORD: admin123` → измените на свой
   > - `FERNET_KEY: ...` → можете оставить или сгенерировать новый

7. **Нажмите "Deploy the stack"**

Portainer автоматически:
- ✅ Склонирует репозиторий с GitHub внутри контейнера
- ✅ Установит все зависимости
- ✅ Запустит все 5 контейнеров

> **Примечание**: Первый запуск займет 2-3 минуты (установка зависимостей и клонирование репозитория).

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
- **MinIO Console**: http://ваш-сервер:9011

**Логин по умолчанию** (если использовали настройки выше):
- Username: `admin`
- Password: `your_secure_password`

**MinIO** (для управления файлами):
- Username: `minioadmin`
- Password: `minioadmin`

> **Примечание**: MinIO использует порты 9010 (API) и 9011 (Console) вместо стандартных 9000/9001, чтобы избежать конфликтов.

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

### Ошибка "FERNET_KEY not configured" или "FERNET_KEY environment variable is required"

**Причина**: Не установлена переменная окружения FERNET_KEY

**Решение**: 
1. Перейдите в Portainer → Stacks → testum → Editor
2. Прокрутите вниз до раздела "Environment variables"
3. Убедитесь, что добавлена переменная:
   - **name**: `FERNET_KEY`
   - **value**: `8KMhgoZ3LqvVNxKz4YHzMNJRCq5YUf3yx8WlBKxuX8k=` (или свой сгенерированный)
4. Нажмите "Update the stack"
5. Или удалите и создайте стек заново с переменными

### Контейнер app падает с ошибкой "connection refused"

**Причина**: База данных или Redis еще не готовы

**Решение**: Подождите 30-60 секунд. Контейнер app должен автоматически перезапуститься после того, как БД станет healthy

### Ошибка при сборке "BuildKit error"

**Причина**: Конфликт с Docker BuildKit

**Решение**: Уже исправлено в текущей версии docker-compose.yml

## Обновление приложения

Когда в репозитории появятся обновления:

### Способ 1: Пересоздать стек (рекомендуется)

1. Перейдите в Portainer → **Stacks** → `testum`
2. Нажмите **"Stop"**
3. Нажмите **"Start"** (или удалите и создайте заново)
4. Контейнеры автоматически скачают последнюю версию кода из GitHub

### Способ 2: Перезапустить контейнеры

1. Portainer → **Containers**
2. Выберите `testum_app` → **Restart**
3. Выберите `testum_celery` → **Restart**

> **Примечание**: При каждом запуске контейнеры клонируют свежую версию кода из GitHub

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
