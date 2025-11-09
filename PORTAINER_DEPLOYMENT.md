# Развертывание Ocultum в Portainer

## Предварительные требования

1. Portainer установлен и запущен
2. Docker daemon доступен
3. Доступ к GitHub Container Registry (или собственный registry)

## Шаг 1: Подготовка Docker образа

### Вариант A: Сборка локально и push в registry

```bash
# Сборка образа
cd /Users/aleksejzaharcenko/work/ocultum/testup
docker build -t ocultum-app:latest .

# Tag для GitHub Container Registry
docker tag ocultum-app:latest ghcr.io/4stm4/ocultum-app:latest

# Login в GHCR (требуется Personal Access Token)
echo $GITHUB_TOKEN | docker login ghcr.io -u 4stm4 --password-stdin

# Push в registry
docker push ghcr.io/4stm4/ocultum-app:latest
```

### Вариант B: Использовать локальный registry

```bash
# Запустить локальный registry (если еще не запущен)
docker run -d -p 5000:5000 --name registry registry:2

# Tag для локального registry
docker tag ocultum-app:latest localhost:5000/ocultum-app:latest

# Push в локальный registry
docker push localhost:5000/ocultum-app:latest

# В docker-compose.yml использовать:
# image: localhost:5000/ocultum-app:latest
```

## Шаг 2: Генерация FERNET_KEY

```bash
# На Mac/Linux с Python
python3 << 'EOF'
from cryptography.fernet import Fernet
print(f"FERNET_KEY={Fernet.generate_key().decode()}")
EOF

# Или онлайн:
# https://cryptography.io/en/latest/fernet/
# Или просто используйте пример:
# FERNET_KEY=8KMhgoZ3LqvVNxKz4YHzMNJRCq5YUf3yx8WlBKxuX8k=
```

**Сохраните сгенерированный ключ!**

## Шаг 3: Развертывание в Portainer

### Метод 1: Через Portainer UI (Stack)

1. Откройте Portainer: `http://your-portainer-url:9000`

2. Перейдите в **Stacks** → **Add Stack**

3. Имя стека: `ocultum`

4. Build method: **Web editor**

5. Скопируйте содержимое `docker-compose.yml` в редактор

6. В разделе **Environment variables** добавьте:

```
FERNET_KEY=8KMhgoZ3LqvVNxKz4YHzMNJRCq5YUf3yx8WlBKxuX8k=
SECRET_KEY=your-long-secret-key-for-jwt-min-32-characters
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password
SSH_HOST_KEY_POLICY=auto_add
```

7. Нажмите **Deploy the stack**

### Метод 2: Через Git Repository

1. Создайте файл `.env` в репозитории (не коммитьте в git!):

```bash
FERNET_KEY=your-generated-key
SECRET_KEY=your-secret-key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=secure-password
SSH_HOST_KEY_POLICY=auto_add
```

2. В Portainer: **Stacks** → **Add Stack**

3. Build method: **Repository**

4. Repository URL: `https://github.com/4stm4/ocultum`

5. Repository reference: `hexagonal-architecture`

6. Compose path: `testup/docker-compose.yml`

7. Добавьте environment variables (как в методе 1)

8. Deploy

## Шаг 4: Проверка развертывания

### Проверка контейнеров

В Portainer проверьте, что все контейнеры запущены:
- ✅ `ocultum_db` (PostgreSQL)
- ✅ `ocultum_redis` (Redis)
- ✅ `ocultum_minio` (MinIO)
- ✅ `ocultum_app` (Web App)
- ✅ `ocultum_celery` (Celery Worker)

### Проверка логов

1. Откройте **Containers** → `ocultum_app` → **Logs**
2. Проверьте отсутствие ошибок
3. Должно быть: `Application started in production mode`

### Проверка health checks

Все сервисы должны иметь статус **healthy** (зеленый значок)

## Шаг 5: Доступ к сервисам

После успешного развертывания:

- **Web UI**: `http://your-server:8000`
- **API**: `http://your-server:8000/api/`
- **Health Check**: `http://your-server:8000/health`
- **MinIO Console**: `http://your-server:9001` (minioadmin / minioadmin)

## Шаг 6: Первый запуск

### Проверка здоровья

```bash
curl http://your-server:8000/health
```

Ожидаемый ответ:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-09T12:00:00"
}
```

### Авторизация

```bash
curl -X POST http://your-server:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "your-password"
  }'
```

## Обновление стека

### Обновление образа

1. Пересобрать и push новый образ:
```bash
docker build -t ghcr.io/4stm4/ocultum-app:latest .
docker push ghcr.io/4stm4/ocultum-app:latest
```

2. В Portainer:
   - Перейдите в **Stacks** → `ocultum`
   - Нажмите **Pull and redeploy**
   - Или нажмите **Editor** → **Update the stack**

### Rolling update (без downtime)

```bash
# В Portainer через API или CLI
docker service update --image ghcr.io/4stm4/ocultum-app:latest ocultum_app
```

## Troubleshooting

### Контейнер не запускается

1. Проверьте логи:
   - Portainer → Containers → ocultum_app → Logs

2. Частые проблемы:
   - ❌ `FERNET_KEY not configured` → Установите FERNET_KEY в env
   - ❌ `connection refused` → Проверьте health checks БД/Redis
   - ❌ `module not found` → Пересоберите образ

### База данных не инициализируется

```bash
# Выполните миграции вручную
docker exec -it ocultum_app alembic upgrade head
```

### Celery задачи не выполняются

1. Проверьте логи worker:
```bash
docker logs ocultum_celery
```

2. Проверьте подключение к Redis:
```bash
docker exec -it ocultum_redis redis-cli ping
```

### MinIO недоступен

1. Проверьте health check:
```bash
docker exec -it ocultum_minio curl -f http://localhost:9000/minio/health/live
```

2. Создайте bucket вручную:
```bash
# Через MinIO Console http://your-server:9001
# Или через mc cli
```

## Мониторинг

### Prometheus metrics (будущее)

Добавьте в docker-compose.yml:
```yaml
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
```

### Grafana (будущее)

```yaml
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
```

## Backup

### Backup базы данных

```bash
docker exec ocultum_db pg_dump -U postgres ocultum > backup.sql
```

### Backup MinIO

```bash
docker exec ocultum_minio mc mirror /data /backup
```

### Restore

```bash
# PostgreSQL
cat backup.sql | docker exec -i ocultum_db psql -U postgres ocultum

# MinIO
docker exec ocultum_minio mc mirror /backup /data
```

## Production настройки

### Обязательно измените:

1. **ADMIN_PASSWORD** - сильный пароль
2. **SECRET_KEY** - длинный случайный ключ
3. **FERNET_KEY** - новый уникальный ключ
4. **MINIO_ROOT_PASSWORD** - если доступен извне
5. **POSTGRES_PASSWORD** - если доступен извне

### Рекомендуется:

1. Настроить HTTPS (обратный прокси: Traefik/Nginx)
2. Ограничить доступ по IP
3. Настроить мониторинг и алерты
4. Регулярные backups
5. Log rotation

## Масштабирование

### Увеличение Celery workers

В Portainer → Containers → ocultum_celery:
- Duplicate/Clone: **Scale** → 3 replicas

Или в docker-compose.yml:
```yaml
celery_worker:
  deploy:
    replicas: 3
```

### Load balancer для app

Используйте Traefik или Nginx перед ocultum_app.

## Полезные команды Portainer CLI

```bash
# Список стеков
curl -H "X-API-Key: your-api-key" http://portainer:9000/api/stacks

# Удалить стек
curl -X DELETE -H "X-API-Key: your-api-key" \
  http://portainer:9000/api/stacks/{stack-id}

# Обновить стек
curl -X PUT -H "X-API-Key: your-api-key" \
  -d @stack.json http://portainer:9000/api/stacks/{stack-id}
```

## Безопасность в Portainer

1. Используйте **RBAC** для ограничения доступа
2. Включите **Webhook** для автодеплоя
3. Используйте **Secrets** для sensitive данных
4. Настройте **Registry** authentication

---

**Готово!** Ваш Ocultum сервис развернут в Portainer.

Для вопросов и поддержки: см. README.md и QUICK_START.md
