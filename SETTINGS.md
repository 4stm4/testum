# Settings Page

## Overview

Страница Settings позволяет администратору управлять настройками своей учетной записи.

## Доступ

**URL:** `/settings`

**Требуется авторизация:** Да

## Функционал

### 📊 Account Information

Отображает текущую информацию о пользователе:
- **Current Username** - текущий логин (извлекается из JWT токена)
- **Account Type** - тип аккаунта (Administrator)

### ⚙️ Application Settings (Read-Only)

Показывает основные настройки приложения:
- **Environment** - режим работы (production/development)
- **Secret Key** - скрыт для безопасности
- **Fernet Encryption Key** - скрыт, используется для шифрования credentials

### 🗄️ Database Settings (Read-Only)

Отображает конфигурацию подключений к базам данных:
- **Database URL** - PostgreSQL connection string (пароли замаскированы)
- **Redis URL** - Redis connection string (пароли замаскированы)

### 📨 Task Queue Settings (Read-Only)

Конфигурация Celery:
- **Broker URL** - Redis broker для очереди задач
- **Result Backend** - Redis backend для результатов

### 📦 Storage Settings (Read-Only)

Настройки MinIO S3-совместимого хранилища:
- **MinIO Endpoint** - адрес сервера MinIO
- **Bucket Name** - имя bucket для хранения артефактов
- **Access Key** - скрыт для безопасности
- **Secure Connection (TLS)** - использование TLS

### 🔐 SSH Settings (Read-Only)

Настройки SSH подключений:
- **Host Key Policy** - политика проверки host keys (auto_add = TOFU)

### 🔄 Change Username

Форма для изменения имени пользователя.

**Поля:**
- `Current Password` - текущий пароль для подтверждения
- `New Username` - новое имя пользователя (минимум 3 символа)

**Процесс:**
1. Введите текущий пароль
2. Введите новый username
3. Нажмите "Update Username"
4. После успешного обновления вы будете автоматически разлогинены
5. Войдите заново с новым username

**API Endpoint:** `POST /api/auth/change-username`

### 🔒 Change Password

Форма для изменения пароля.

**Поля:**
- `Current Password` - текущий пароль
- `New Password` - новый пароль (минимум 8 символов)
- `Confirm New Password` - подтверждение нового пароля

**Валидация:**
- Пароль должен быть минимум 8 символов
- Новый пароль и подтверждение должны совпадать
- Требуется правильный текущий пароль

**Процесс:**
1. Введите текущий пароль
2. Введите новый пароль дважды
3. Нажмите "Update Password"
4. После успешного обновления вы будете автоматически разлогинены
5. Войдите заново с новым паролем

**API Endpoint:** `POST /api/auth/change-password`

## API Endpoints

### GET /api/settings

Получение текущих системных настроек (без чувствительных данных).

**Response (200 OK):**
```json
{
  "app_env": "production",
  "admin_username": "admin",
  "database_url": "postgresql://postgres:••••••@db:5432/testum",
  "redis_url": "redis://••••••@redis:6379/0",
  "celery_broker_url": "redis://••••••@redis:6379/0",
  "celery_result_backend": "redis://••••••@redis:6379/0",
  "minio_endpoint": "minio:9000",
  "minio_bucket": "testum-artifacts",
  "minio_secure": false,
  "ssh_host_key_policy": "auto_add"
}
```

**Примечания:**
- Пароли в connection strings автоматически маскируются
- Access/Secret keys не возвращаются в ответе
- Требуется авторизация

### POST /api/auth/change-username

Изменение username администратора.

**Request:**
```json
{
  "current_password": "admin123",
  "new_username": "newadmin"
}
```

**Response (200 OK):**
```json
{
  "message": "Username change requested",
  "note": "Please update ADMIN_USERNAME environment variable in your deployment configuration"
}
```

**Response (400 Bad Request):**
```json
{
  "error": "Username must be at least 3 characters"
}
```

**Response (401 Unauthorized):**
```json
{
  "error": "Invalid current password"
}
```

### POST /api/auth/change-password

Изменение пароля администратора.

**Request:**
```json
{
  "current_password": "admin123",
  "new_password": "newSecurePassword123"
}
```

**Response (200 OK):**
```json
{
  "message": "Password change requested",
  "note": "Please update ADMIN_PASSWORD environment variable in your deployment configuration"
}
```

**Response (400 Bad Request):**
```json
{
  "error": "Password must be at least 8 characters"
}
```

**Response (401 Unauthorized):**
```json
{
  "error": "Invalid current password"
}
```

## Важные замечания

### ⚠️ Текущая реализация (MVP)

В текущей версии (v0.1.0) учетные данные хранятся в **environment variables** (`ADMIN_USERNAME` и `ADMIN_PASSWORD` в `docker-compose.yml`).

**Что происходит при изменении:**

1. **Изменение username/password через UI:**
   - API endpoint проверяет текущий пароль
   - Возвращает успешный ответ
   - **НО**: изменения НЕ сохраняются автоматически

2. **Для применения изменений нужно:**
   - Вручную обновить `ADMIN_USERNAME` или `ADMIN_PASSWORD` в `docker-compose.yml`
   - Перезапустить контейнеры: `docker-compose restart app`

### 🔄 Workflow для изменения credentials

**Шаг 1:** Используйте Settings UI для валидации нового username/password

**Шаг 2:** Обновите `docker-compose.yml`:
```yaml
services:
  app:
    environment:
      - ADMIN_USERNAME=newadmin  # ← обновите здесь
      - ADMIN_PASSWORD=newSecurePassword123  # ← обновите здесь
```

**Шаг 3:** Перезапустите приложение:
```bash
docker-compose restart app worker
```

**Шаг 4:** Войдите с новыми credentials

### 🚀 Будущая реализация (v0.2.0)

Миграция `003_add_users_table.py` уже подготовлена для поддержки базы данных пользователей:

- Хранение пользователей в PostgreSQL
- Хеширование паролей (bcrypt)
- Изменение credentials без перезапуска
- Множественные пользователи
- Роли и права доступа

**Для активации:**
```bash
# Запустить миграцию
alembic upgrade head

# Обновить код для работы с User model
# См. app/models.py и app/auth.py
```

## UI Features

### Дизайн
- Темная тема в стиле Portainer
- Три карточки: Account Info, Change Username, Change Password
- Валидация на клиенте и сервере
- Информационное сообщение о необходимости обновления env vars

### UX
- Автоматический logout после успешного изменения
- Показ текущего username из JWT токена
- Loading states для кнопок
- Сообщения об ошибках и успехе
- Подтверждение паролем для изменения username

## Security

### Best Practices

1. **Требуется текущий пароль:**
   - Для изменения username требуется подтверждение паролем
   - Защита от CSRF атак при открытой сессии

2. **Минимальная длина:**
   - Username: минимум 3 символа
   - Password: минимум 8 символов

3. **Автоматический logout:**
   - После изменения credentials сессия сбрасывается
   - Предотвращает использование старых токенов

4. **Client-side validation:**
   - Проверка совпадения паролей
   - Проверка минимальной длины
   - Немедленная обратная связь

### Recommendations

Для production среды:

1. **Используйте сильные пароли:**
   ```
   - Минимум 12 символов
   - Заглавные и строчные буквы
   - Цифры и специальные символы
   ```

2. **Регулярно меняйте credentials:**
   - Рекомендуется менять пароль каждые 90 дней

3. **Защитите docker-compose.yml:**
   ```bash
   # Ограничьте доступ к файлу
   chmod 600 docker-compose.yml
   ```

4. **Используйте secrets management:**
   - Docker Secrets (Swarm mode)
   - HashiCorp Vault
   - AWS Secrets Manager

5. **Логируйте изменения:**
   - Audit log уже существует в системе
   - Отслеживайте изменения credentials

## Troubleshooting

### Проблема: Изменил password в UI, но не могу войти

**Решение:**
Изменения в UI не применяются автоматически. Необходимо обновить `ADMIN_PASSWORD` в `docker-compose.yml` и перезапустить контейнеры.

### Проблема: Забыл новый пароль после изменения

**Решение:**
1. Откройте `docker-compose.yml`
2. Проверьте значение `ADMIN_PASSWORD`
3. Используйте это значение для входа
4. Или установите новый пароль в `docker-compose.yml`
5. Перезапустите: `docker-compose restart app`

### Проблема: После изменения username получаю 401

**Решение:**
Убедитесь, что обновили `ADMIN_USERNAME` в `docker-compose.yml` и перезапустили контейнеры.

## Testing

### Тестирование изменения password

```bash
# 1. Текущие credentials
USERNAME="admin"
OLD_PASSWORD="admin123"
NEW_PASSWORD="newPassword123"

# 2. Login с текущими credentials
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USERNAME\",\"password\":\"$OLD_PASSWORD\"}" \
  | jq -r .access_token)

# 3. Изменить password
curl -X POST http://localhost:8000/api/auth/change-password \
  -H "Content-Type: application/json" \
  -H "Cookie: access_token=$TOKEN" \
  -d "{\"current_password\":\"$OLD_PASSWORD\",\"new_password\":\"$NEW_PASSWORD\"}"

# 4. Обновить docker-compose.yml
# 5. Перезапустить контейнеры
# 6. Login с новым password
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USERNAME\",\"password\":\"$NEW_PASSWORD\"}"
```

### Тестирование изменения username

```bash
# 1. Текущие credentials
OLD_USERNAME="admin"
NEW_USERNAME="newadmin"
PASSWORD="admin123"

# 2. Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$OLD_USERNAME\",\"password\":\"$PASSWORD\"}" \
  | jq -r .access_token)

# 3. Изменить username
curl -X POST http://localhost:8000/api/auth/change-username \
  -H "Content-Type: application/json" \
  -H "Cookie: access_token=$TOKEN" \
  -d "{\"current_password\":\"$PASSWORD\",\"new_username\":\"$NEW_USERNAME\"}"

# 4. Обновить docker-compose.yml
# 5. Перезапустить контейнеры
# 6. Login с новым username
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$NEW_USERNAME\",\"password\":\"$PASSWORD\"}"
```

## Future Enhancements

### Planned for v0.2.0

- [ ] Database-backed user storage
- [ ] Password hashing with bcrypt
- [ ] Real-time credential updates (no restart required)
- [ ] Password strength meter in UI
- [ ] Password history (prevent reuse)
- [ ] Two-factor authentication (2FA)
- [ ] Session management (view/revoke active sessions)
- [ ] Email notifications on credential changes
- [ ] Password reset via email
- [ ] Multiple admin users
- [ ] Role-based access control (RBAC)

### Planned for v0.3.0

- [ ] LDAP/Active Directory integration
- [ ] OAuth2 providers (Google, GitHub, etc.)
- [ ] API keys for programmatic access
- [ ] Audit trail for all credential changes
- [ ] Compliance features (password policy enforcement)
