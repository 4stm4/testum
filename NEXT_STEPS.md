# Следующие шаги для деплоя Ocultum

## ✅ Что уже сделано

1. ✅ Все 42 файла проекта закоммичены в git
2. ✅ Docker-compose адаптирован для Portainer
3. ✅ GitHub Actions workflow создан для автоматической сборки
4. ✅ Документация по деплою в Portainer готова
5. ✅ Чеклист для деплоя создан

## 📋 Следующие действия

### 1. Push в GitHub

```bash
# Проверить, что вы на правильной ветке
git branch

# Push в удаленный репозиторий
git push origin hexagonal-architecture
```

**Что произойдет:**
- GitHub Actions автоматически запустит сборку Docker образа
- Образ будет опубликован в GitHub Container Registry (GHCR)
- Образ будет доступен по адресу: `ghcr.io/4stm4/ocultum-app:hexagonal-architecture`

### 2. Настройка GitHub Container Registry

#### Опция A: Public образ (рекомендуется для тестирования)

1. Перейти на https://github.com/4stm4/ocultum/packages
2. Найти пакет `ocultum-app`
3. Settings → Change visibility → Public

#### Опция B: Private образ (для production)

Если образ останется private, нужно настроить Portainer с credentials:

1. GitHub → Settings → Developer settings → Personal access tokens
2. Generate new token (classic) с scope `read:packages`
3. В Portainer:
   - Registries → Add registry
   - Type: Custom Registry
   - Name: GitHub Container Registry
   - Registry URL: `ghcr.io`
   - Username: `4stm4`
   - Password: `<your-github-token>`

### 3. Проверка сборки

После push проверить:

1. **GitHub Actions**: https://github.com/4stm4/ocultum/actions
   - Дождаться завершения workflow "Build and Publish Docker Image"
   - Статус должен быть ✅ green

2. **Container Registry**: https://github.com/4stm4?tab=packages
   - Проверить, что образ появился
   - Проверить tags (должен быть `hexagonal-architecture`)

### 4. Деплой в Portainer

#### Шаг 4.1: Подготовка переменных окружения

```bash
# Генерация FERNET_KEY
python3 -c "from cryptography.fernet import Fernet; print(f'FERNET_KEY={Fernet.generate_key().decode()}')"

# Генерация SECRET_KEY
python3 -c "import secrets; print(f'SECRET_KEY={secrets.token_urlsafe(32)}')"

# Или используйте openssl:
openssl rand -hex 32
```

**Сохраните эти ключи!**

#### Шаг 4.2: Создание Stack в Portainer

1. Открыть Portainer: `http://your-portainer-server:9000`

2. **Stacks** → **Add Stack**

3. **Настройки стека:**
   - Name: `ocultum`
   - Build method: **Git Repository** (рекомендуется) или **Web editor**

4. **Если выбран Git Repository:**
   - Repository URL: `https://github.com/4stm4/ocultum`
   - Repository reference: `hexagonal-architecture`
   - Compose path: `testup/docker-compose.yml`
   - Authentication: None (если репозиторий public)

5. **Если выбран Web editor:**
   - Скопировать содержимое файла `testup/docker-compose.yml`

6. **Environment variables** (добавить следующие переменные):

```env
FERNET_KEY=<generated-key-from-step-4.1>
SECRET_KEY=<generated-key-from-step-4.1>
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<strong-secure-password>
SSH_HOST_KEY_POLICY=auto_add
POSTGRES_PASSWORD=<secure-db-password>
MINIO_SECRET_KEY=<secure-minio-password>
```

7. **Deploy the stack**

#### Шаг 4.3: Проверка деплоя

После деплоя проверить в Portainer → Containers:

| Container | Status | Health |
|-----------|--------|--------|
| ocultum_db | Running | Healthy ✅ |
| ocultum_redis | Running | Healthy ✅ |
| ocultum_minio | Running | Healthy ✅ |
| ocultum_app | Running | Healthy ✅ |
| ocultum_celery | Running | - |

**Проверка логов:**
- ocultum_app → Logs: должно быть "Application started in production mode"
- ocultum_celery → Logs: должно быть "celery@... ready"

#### Шаг 4.4: Тестирование сервиса

```bash
# Health check
curl http://your-server:8000/health

# Ожидаемый ответ:
# {"status": "healthy", "timestamp": "2025-01-09T..."}

# Login
curl -X POST http://your-server:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'

# Ожидаемый ответ:
# {"access_token": "eyJ...", "token_type": "bearer"}
```

**Web UI:**
- Открыть в браузере: `http://your-server:8000`
- Войти с admin credentials

### 5. Troubleshooting

#### Если GitHub Actions не запустился:

```bash
# Проверить, что workflow файл в правильном месте
ls -la testup/.github/workflows/docker-publish.yml

# Проверить синтаксис workflow
cat testup/.github/workflows/docker-publish.yml
```

#### Если образ не собирается:

Проверить логи GitHub Actions:
1. GitHub → Actions → Build and Publish Docker Image
2. Посмотреть детали ошибки

Типичные проблемы:
- ❌ Dockerfile не найден → проверить context в workflow
- ❌ Permission denied → включить "Read and write permissions" в Settings → Actions → General

#### Если Portainer не может скачать образ:

```bash
# Проверить доступность образа
docker pull ghcr.io/4stm4/ocultum-app:hexagonal-architecture

# Если ошибка authentication:
# → Образ private, нужно добавить registry в Portainer (см. шаг 2, опция B)
```

#### Если контейнеры не запускаются в Portainer:

1. **Проверить логи**: Containers → [container] → Logs
2. **Проверить переменные окружения**: Stacks → ocultum → Editor → Environment variables
3. **Проверить health checks**: Containers → [container] → Inspect → Health

Типичные ошибки:
- `FERNET_KEY not configured` → Добавить FERNET_KEY в env variables
- `connection refused` → Подождать, пока зависимые сервисы станут healthy
- `database migration failed` → Выполнить вручную: `docker exec -it ocultum_app alembic upgrade head`

## 📚 Полезные ссылки

- **Быстрый чеклист**: [PORTAINER_CHECKLIST.md](PORTAINER_CHECKLIST.md)
- **Подробная документация**: [PORTAINER_DEPLOYMENT.md](PORTAINER_DEPLOYMENT.md)
- **API примеры**: [API_EXAMPLES.md](API_EXAMPLES.md)
- **Архитектурные решения**: [DECISIONS.md](DECISIONS.md)
- **Локальная разработка**: [QUICK_START.md](QUICK_START.md)

## 🎯 Краткий путь (TL;DR)

```bash
# 1. Push в GitHub
git push origin hexagonal-architecture

# 2. Дождаться сборки образа в GitHub Actions

# 3. В Portainer создать stack с:
#    - Repository: https://github.com/4stm4/ocultum
#    - Branch: hexagonal-architecture
#    - Path: testup/docker-compose.yml
#    - Environment: FERNET_KEY, SECRET_KEY, ADMIN_PASSWORD

# 4. Deploy stack

# 5. Проверить health:
curl http://your-server:8000/health

# 6. Открыть UI:
open http://your-server:8000
```

## ✅ Success Criteria

- [ ] Code pushed to GitHub
- [ ] GitHub Actions build successful
- [ ] Docker image available in GHCR
- [ ] Stack deployed in Portainer
- [ ] All containers healthy
- [ ] Health check returns 200 OK
- [ ] Web UI accessible
- [ ] Can login with admin credentials
- [ ] Can create SSH key
- [ ] Can create platform
- [ ] Can deploy key to platform
- [ ] Can execute command on platform

**Готово к деплою!** 🚀

Если что-то пошло не так, см. раздел Troubleshooting выше или полную документацию в PORTAINER_DEPLOYMENT.md.
