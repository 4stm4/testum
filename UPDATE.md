# Обновление существующего деплоя

## Если вы уже задеплоили testum и видите ошибку SQLAlchemy

### Ошибка
```
sqlalchemy.exc.InvalidRequestError: Attribute name 'metadata' is reserved when using the Declarative API.
```

### Решение

1. **Удалите текущий стек в Portainer**:
   - Portainer → Stacks → testum → Delete this stack
   - ⚠️ Отметьте "Also remove associated volumes" чтобы очистить старую БД

2. **Создайте новый стек**:
   - Stacks → Add stack → Web editor
   - Скопируйте обновленный `docker-compose.yml`
   - Deploy

3. **Готово!**
   - Миграция `002_rename_metadata_column.py` автоматически применится
   - Приложение запустится без ошибок

---

## Если НЕ хотите удалять volumes (сохранить данные)

1. **Остановите стек**:
   - Portainer → Stacks → testum → Stop

2. **Обновите код**:
   - Stacks → testum → Editor
   - Скопируйте новый `docker-compose.yml`
   - Update the stack

3. **Миграция применится автоматически** при старте контейнера app

---

## Что изменилось

- Поле `TaskRun.metadata` → `TaskRun.task_metadata`
- Это исправляет конфликт с зарезервированным атрибутом SQLAlchemy
- Все существующие данные сохранятся (колонка просто переименовывается)

---

## Проверка

После обновления в логах должно быть:
```
Running database migrations...
INFO  [alembic.runtime.migration] Running upgrade 001 -> 002, Rename metadata to task_metadata
Starting application...
✅ Uvicorn running on http://0.0.0.0:8000
```
