# Portainer Deployment Checklist

## Pre-Deployment

- [ ] Portainer установлен и доступен
- [ ] Docker daemon работает
- [ ] Есть доступ к GitHub Container Registry или локальному registry

## Step 1: Build & Push Image

### Option A: GitHub Actions (автоматически)
- [ ] Push код в репозиторий
- [ ] Проверить Actions: https://github.com/4stm4/ocultum/actions
- [ ] Дождаться успешной сборки образа
- [ ] Образ доступен: `ghcr.io/4stm4/ocultum-app:latest`

### Option B: Локальная сборка
```bash
cd testup
docker build -t ghcr.io/4stm4/ocultum-app:latest .
echo $GITHUB_TOKEN | docker login ghcr.io -u 4stm4 --password-stdin
docker push ghcr.io/4stm4/ocultum-app:latest
```

- [ ] Образ собран
- [ ] Образ залогинен в registry
- [ ] Образ запушен

## Step 2: Generate Secrets

```bash
# Генерация FERNET_KEY
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Генерация SECRET_KEY
openssl rand -hex 32
```

- [ ] FERNET_KEY сгенерирован
- [ ] SECRET_KEY сгенерирован
- [ ] ADMIN_PASSWORD придуман
- [ ] Все ключи сохранены в безопасном месте

## Step 3: Deploy in Portainer

1. **Open Portainer**: http://your-portainer:9000

2. **Create Stack**:
   - [ ] Stacks → Add Stack
   - [ ] Name: `ocultum`
   - [ ] Build method: Web editor или Git repository

3. **Add docker-compose.yml content**:
   - [ ] Скопировать из `testup/docker-compose.yml`
   - [ ] Или указать Git URL

4. **Set Environment Variables**:
   ```
   FERNET_KEY=<generated-key>
   SECRET_KEY=<generated-key>
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=<strong-password>
   SSH_HOST_KEY_POLICY=auto_add
   ```
   - [ ] Все переменные добавлены
   - [ ] Пароли изменены с дефолтных

5. **Deploy Stack**:
   - [ ] Нажать "Deploy the stack"
   - [ ] Дождаться завершения

## Step 4: Verify Deployment

### Check Containers
В Portainer → Containers проверить статус:
- [ ] ✅ ocultum_db (healthy)
- [ ] ✅ ocultum_redis (healthy)
- [ ] ✅ ocultum_minio (healthy)
- [ ] ✅ ocultum_app (healthy)
- [ ] ✅ ocultum_celery (running)

### Check Logs
- [ ] ocultum_app: нет ошибок, есть "Application started"
- [ ] ocultum_celery: нет ошибок, есть "celery@... ready"
- [ ] ocultum_db: нет ошибок, "database system is ready"

### Test Services
```bash
# Health check
curl http://your-server:8000/health
# Expected: {"status": "healthy", ...}

# Web UI
curl http://your-server:8000
# Expected: HTML page

# MinIO
curl http://your-server:9001
# Expected: MinIO login page
```

- [ ] Health check OK
- [ ] Web UI открывается
- [ ] MinIO доступен

## Step 5: First Login

### API Login
```bash
curl -X POST http://your-server:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'
```

- [ ] Логин успешен
- [ ] Получен JWT token

### Web UI Login
- [ ] Открыть http://your-server:8000
- [ ] Войти с admin credentials
- [ ] Проверить доступность всех страниц

## Step 6: Post-Deployment

### Security Hardening
- [ ] Изменены все дефолтные пароли
- [ ] HTTPS настроен (Traefik/Nginx)
- [ ] Firewall правила настроены
- [ ] MinIO доступ ограничен

### Monitoring Setup
- [ ] Настроены алерты в Portainer
- [ ] Log rotation настроен
- [ ] Backup стратегия определена

### Documentation
- [ ] Команда знает, где документация
- [ ] Учетные данные сохранены в password manager
- [ ] Runbook создан для операционной команды

## Troubleshooting

### Если контейнеры не запускаются:
1. Проверить логи: Portainer → Containers → [container] → Logs
2. Проверить переменные окружения
3. Проверить доступность образа в registry
4. Проверить health checks

### Если база данных не инициализируется:
```bash
docker exec -it ocultum_app alembic upgrade head
```

### Если Celery не подключается к Redis:
```bash
docker exec -it ocultum_redis redis-cli ping
# Expected: PONG
```

## Emergency Rollback

Если что-то пошло не так:

1. **Stop Stack**:
   - Portainer → Stacks → ocultum → Stop

2. **Restore Previous Version**:
   - Change image tag to previous version
   - Update stack

3. **Restore Database** (если нужно):
   ```bash
   cat backup.sql | docker exec -i ocultum_db psql -U postgres ocultum
   ```

## Success Criteria

✅ Все контейнеры запущены и healthy  
✅ Web UI доступен и работает  
✅ API отвечает корректно  
✅ SSH операции выполняются (добавить ключ, подключиться к платформе)  
✅ WebSocket стриминг работает  
✅ Задачи Celery выполняются  
✅ MinIO хранит артефакты  

---

**Deployment Complete!** 🚀

See also:
- PORTAINER_DEPLOYMENT.md - подробные инструкции
- QUICK_START.md - быстрый старт для разработки
- API_EXAMPLES.md - примеры использования API
