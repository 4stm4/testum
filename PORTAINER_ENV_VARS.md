# Как правильно добавить переменные окружения в Portainer

## КРИТИЧЕСКИ ВАЖНО! ⚠️

Без правильных переменных окружения контейнер не запустится!

## Шаг за шагом

### 1. При создании стека

После того как вы вставили содержимое `docker-compose.portainer.yml` в Web editor:

1. **Прокрутите ВНИЗ** - не нажимайте сразу "Deploy"!
2. Найдите раздел **"Environment variables"**
3. Нажмите **"+ Add an environment variable"** или **"+ add environment variable"**

### 2. Добавьте КАЖДУЮ переменную отдельно

**Переменная 1:**
- name: `FERNET_KEY`
- value: `8KMhgoZ3LqvVNxKz4YHzMNJRCq5YUf3yx8WlBKxuX8k=`

Нажмите "+ Add an environment variable"

**Переменная 2:**
- name: `SECRET_KEY`
- value: `your-super-secret-key-change-in-production-min-32-chars`

Нажмите "+ Add an environment variable"

**Переменная 3:**
- name: `ADMIN_USERNAME`
- value: `admin`

Нажмите "+ Add an environment variable"

**Переменная 4:**
- name: `ADMIN_PASSWORD`
- value: `your_secure_password`

Нажмите "+ Add an environment variable"

**Переменная 5:**
- name: `SSH_HOST_KEY_POLICY`
- value: `auto_add`

### 3. Проверьте перед деплоем

У вас должно быть видно **5 переменных** в списке:
- ✅ FERNET_KEY
- ✅ SECRET_KEY
- ✅ ADMIN_USERNAME
- ✅ ADMIN_PASSWORD
- ✅ SSH_HOST_KEY_POLICY

### 4. Теперь можно деплоить

Нажмите **"Deploy the stack"** внизу страницы.

---

## Если вы уже создали стек БЕЗ переменных

### Способ 1: Добавить переменные в существующий стек

1. Portainer → **Stacks** → найдите стек `testum`
2. Нажмите на название стека
3. Нажмите **"Editor"** (вверху)
4. Прокрутите вниз до **"Environment variables"**
5. Добавьте все 5 переменных (см. выше)
6. Нажмите **"Update the stack"**
7. Контейнеры автоматически перезапустятся

### Способ 2: Удалить и создать заново (надежнее)

1. Portainer → **Stacks** → `testum`
2. Нажмите **"Delete this stack"**
3. Создайте новый стек, следуя инструкциям выше
4. **НЕ ЗАБУДЬТЕ** добавить все 5 переменных!

---

## Как проверить, что переменные установлены

После деплоя:

1. Portainer → **Containers** → `testum_app`
2. Нажмите **"Logs"**
3. Ищите строку: `=== Checking environment variables ===`
4. Должно быть: `FERNET_KEY is set: YES`

Если видите `NO - FERNET_KEY is missing!` - значит переменные не добавлены!

---

## Частые ошибки

### ❌ "Я добавил переменные, но они не работают"
- Проверьте, что вы нажали "Deploy the stack" или "Update the stack"
- Проверьте, что не опечатались в названии переменной (FERNET_KEY, не FERNET-KEY)

### ❌ "Контейнер постоянно перезапускается"
- Откройте логи (Containers → testum_app → Logs)
- Ищите ошибку "FERNET_KEY is missing"
- Добавьте переменные (способ 1 или 2 выше)

### ❌ "ValueError: FERNET_KEY environment variable is required"
- Переменные не были добавлены или не сохранены
- Следуйте инструкции "Способ 2: Удалить и создать заново"

---

## Альтернатива: Использовать .env файл (НЕ рекомендуется для Portainer)

В Portainer через Web editor **.env файлы НЕ РАБОТАЮТ**!
Используйте только "Environment variables" в интерфейсе Portainer.

---

## Проверочный чек-лист

Перед нажатием "Deploy":
- [ ] Я вижу раздел "Environment variables"
- [ ] Я добавил FERNET_KEY
- [ ] Я добавил SECRET_KEY
- [ ] Я добавил ADMIN_USERNAME
- [ ] Я добавил ADMIN_PASSWORD
- [ ] Я добавил SSH_HOST_KEY_POLICY
- [ ] Всего 5 переменных в списке
- [ ] Я нажал "Deploy the stack"

✅ Если все галочки стоят - можно деплоить!
