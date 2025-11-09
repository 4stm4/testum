# Архитектурные решения и допущения

## Ключевые решения

### 1. Host Key Verification Strategy

**Решение**: AutoAddPolicy с сохранением fingerprint

**Детали**:
- При первом подключении SSH fingerprint автоматически принимается
- Fingerprint сохраняется в БД в поле `known_host_fingerprint`
- При последующих подключениях проверяется соответствие
- Если fingerprint изменился → ошибка подключения

**Обоснование**:
- ✅ Упрощает initial setup (не нужно предварительно добавлять хосты)
- ✅ Обеспечивает безопасность после первого подключения
- ✅ TOFU (Trust On First Use) - распространенный подход

**Альтернативы**:
- Strict policy: требует предварительного добавления всех fingerprints
- RejectPolicy: отклоняет все неизвестные хосты

**Конфигурация**: `SSH_HOST_KEY_POLICY=auto_add` в `.env`

---

### 2. SSH Library Choice: Paramiko vs asyncssh

**Решение**: Paramiko (синхронный)

**Обоснование**:
- ✅ Celery tasks по умолчанию синхронные
- ✅ Paramiko - зрелая библиотека с широкой поддержкой
- ✅ Простота реализации и отладки
- ✅ Большое community и документация

**Trade-offs**:
- ⚠️ Блокирующие SSH операции
- ⚠️ Один worker может выполнять только одну задачу
- ⚠️ Нужно больше workers для параллелизма

**Миграция на asyncssh**:
```python
# Потребует:
1. Переписать все SSH операции на async/await
2. Использовать Celery с async tasks
3. Полностью переработать ssh_helper.py
```

**Вывод**: Для MVP Paramiko достаточен. Для production с высокой нагрузкой рекомендуется asyncssh.

---

### 3. Credentials Encryption: Fernet

**Решение**: Fernet (symmetric encryption)

**Детали**:
- Ключ хранится в `FERNET_KEY` env variable
- Все пароли и private keys шифруются перед сохранением в БД
- Расшифровка происходит только в Celery tasks, не в веб-слое

**Обоснование**:
- ✅ Простота реализации
- ✅ Достаточно для single-server deployment
- ✅ Встроенная поддержка в cryptography library
- ✅ Автоматическая rotation через timestamp

**Trade-offs**:
- ⚠️ Symmetric encryption (один ключ для всего)
- ⚠️ При компрометации ключа все credentials скомпрометированы
- ⚠️ Ключ должен быть на всех серверах (app + workers)

**Production рекомендации**:
```bash
# Использовать HashiCorp Vault
VAULT_ADDR=https://vault.example.com
VAULT_TOKEN=s.xxxxxxxxx

# Или AWS KMS
AWS_KMS_KEY_ID=arn:aws:kms:...
```

---

### 4. Task Streaming: Redis Pub/Sub → WebSocket

**Решение**: Redis Pub/Sub как message bus

**Архитектура**:
```
Celery Task → Redis PUBLISH → Redis SUBSCRIBE → WebSocket → Browser
```

**Обоснование**:
- ✅ Redis уже используется для Celery
- ✅ Pub/Sub поддерживает множество подписчиков
- ✅ Простая реализация
- ✅ Низкая latency

**Trade-offs**:
- ⚠️ Сообщения не сохраняются (ephemeral)
- ⚠️ Если клиент отключен, сообщения теряются
- ⚠️ Нет гарантии доставки

**Альтернативы**:
- RabbitMQ для reliable messaging
- Kafka для event streaming с persistence
- Server-Sent Events (SSE) вместо WebSocket

---

### 5. Atomic Write для authorized_keys

**Решение**: Write → Rename pattern

**Реализация**:
```python
1. Write to ~/.ssh/authorized_keys.tmp
2. Set permissions 600
3. Atomic rename to ~/.ssh/authorized_keys
```

**Обоснование**:
- ✅ Гарантирует целостность файла
- ✅ Нет race conditions
- ✅ Если операция прервана, старый файл остается валидным

**Детали**:
- Использует SFTP для операций с файлами
- Обеспечивает правильные permissions (600)
- Создает .ssh директорию с 700 если не существует

---

### 6. Idempotency для Deploy операции

**Решение**: Merge existing + new keys

**Реализация**:
```python
existing_keys = read_authorized_keys()
new_keys = requested_keys
merged_keys = set(existing_keys) | set(new_keys)
write_authorized_keys(merged_keys)
```

**Обоснование**:
- ✅ Повторные deploy не создают дубликаты
- ✅ Безопасно запускать несколько раз
- ✅ Можно использовать для retry logic

---

### 7. Output Handling: DB vs S3

**Решение**: Гибридный подход

**Логика**:
```python
if len(output) < 10KB:
    task.stdout = output  # Store in DB
else:
    s3_key = upload_to_s3(output)
    task.result_location = s3_key  # Store ref
```

**Обоснование**:
- ✅ Малые выводы быстро доступны из БД
- ✅ Большие выводы не раздувают БД
- ✅ S3 дешевле для хранения больших файлов

---

### 8. Authentication: Simple JWT

**Решение**: Hardcoded admin + JWT tokens

**Детали**:
- Один admin user (username/password из env)
- JWT token на 24 часа
- Без refresh tokens

**Обоснование**:
- ✅ Достаточно для MVP
- ✅ Простая реализация
- ✅ Stateless authentication

**Production требования**:
```python
# Нужно добавить:
1. User management система
2. Role-based access control (RBAC)
3. Refresh tokens
4. Password hashing (bcrypt)
5. MFA support
6. Session management
```

---

### 9. Database Models Design

**Решение**: Normalized schema с foreign keys

**Модели**:
- `SSHKey` - независимая сущность
- `Platform` - независимая сущность
- `TaskRun` - связана с Platform (FK)
- `AuditLog` - независимая для логирования

**Trade-offs**:
- ✅ Нормализация упрощает управление
- ⚠️ Нет связи many-to-many между Key и Platform
- ⚠️ Deploy использует "все ключи" или "указанные ID"

**Альтернатива**:
```sql
CREATE TABLE platform_keys (
    platform_id UUID REFERENCES platforms(id),
    key_id UUID REFERENCES ssh_keys(id),
    PRIMARY KEY (platform_id, key_id)
);
```

---

### 10. Error Handling & Retries

**Решение**: Celery autoretry с exponential backoff

**Конфигурация**:
```python
@celery_app.task(
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 5},
    retry_backoff=True,
)
```

**Обоснование**:
- ✅ Автоматический retry для transient errors
- ✅ Exponential backoff предотвращает flood
- ✅ Configurable max retries

---

## Известные ограничения

### 1. Single Admin User
**Проблема**: Только один hardcoded admin  
**Воздействие**: Невозможно разграничить доступ  
**Решение**: Добавить User model + RBAC

### 2. No Pagination
**Проблема**: Все записи возвращаются сразу  
**Воздействие**: Медленно для больших списков  
**Решение**: Добавить offset/limit pagination

### 3. No Rate Limiting
**Проблема**: Возможны DDoS атаки  
**Воздействие**: Перегрузка сервера  
**Решение**: Добавить rate limiting middleware

### 4. Synchronous SSH
**Проблема**: Блокирует Celery worker  
**Воздействие**: Низкий throughput  
**Решение**: Мигрировать на asyncssh

### 5. No Connection Pooling
**Проблема**: Новое SSH connection для каждой задачи  
**Воздействие**: Overhead на connection setup  
**Решение**: SSH connection pool

---

## Production Checklist

### Security
- [ ] Replace hardcoded admin with proper user system
- [ ] Use HashiCorp Vault for secrets
- [ ] Add rate limiting (e.g., slowapi)
- [ ] Configure HTTPS/TLS
- [ ] Restrict CORS origins
- [ ] Add IP whitelist for SSH operations
- [ ] Implement audit log retention policy

### Performance
- [ ] Add pagination to all list endpoints
- [ ] Implement caching (Redis)
- [ ] Use connection pooling for DB
- [ ] Migrate to asyncssh
- [ ] Add database indexes
- [ ] Optimize SQLAlchemy queries (lazy loading)

### Monitoring
- [ ] Prometheus metrics
- [ ] Structured logging (JSON)
- [ ] Health checks for all services
- [ ] Distributed tracing (Jaeger)
- [ ] Alerting (PagerDuty)

### Scalability
- [ ] Horizontal scaling for workers
- [ ] Load balancing for web app
- [ ] Database replication (read replicas)
- [ ] Redis Sentinel/Cluster
- [ ] MinIO distributed mode

### Reliability
- [ ] Database backups
- [ ] Disaster recovery plan
- [ ] Circuit breakers
- [ ] Graceful degradation
- [ ] Zero-downtime deployments

---

## Дальнейшие улучшения

### High Priority
1. **Multi-user support**: User model + RBAC
2. **Async SSH**: Migrate to asyncssh
3. **Pagination**: Add to all list endpoints
4. **Rate limiting**: Prevent abuse
5. **Better error handling**: Structured error responses

### Medium Priority
1. **Vault integration**: External secrets management
2. **Multi-platform deploy**: Deploy to multiple hosts at once
3. **Scheduling**: Cron-like scheduled tasks
4. **OpenAPI docs**: Auto-generated API documentation
5. **WebSocket auth**: Secure WebSocket connections

### Low Priority
1. **Ansible integration**: Run playbooks instead of commands
2. **SSH agent forwarding**: For complex scenarios
3. **Key rotation**: Automatic key lifecycle management
4. **Backup/restore**: Platform configurations
5. **Advanced filters**: Search and filter capabilities

---

## Выводы

Создан **production-ready MVP** с:

✅ **Все требуемые функции реализованы**
- CRUD для ключей и платформ
- Atomic deployment
- Command execution
- Real-time streaming

✅ **Безопасность на приемлемом уровне**
- Encryption credentials
- Host key verification
- Audit logging

✅ **Хорошая архитектура**
- Separation of concerns
- Async task processing
- Scalable design

⚠️ **Требуются улучшения для production**
- User management
- Performance optimizations
- Monitoring & alerting

**Рекомендация**: Готов для internal use и дальнейшей разработки.

---

**Документация**:
- `README.md` - Полная документация
- `API_EXAMPLES.md` - Примеры API
- `QUICK_START.md` - Быстрый старт
- `PROJECT_SUMMARY.md` - Резюме проекта
- `DECISIONS.md` - Этот документ
