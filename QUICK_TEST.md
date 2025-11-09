# 🚀 БЫСТРЫЙ СТАРТ - Запуск за 2 минуты

## Простой деплой в Portainer

В `docker-compose.portainer.yml` все переменные уже прописаны!

---

## Шаги:

1. **Удалите старый стек** (если есть):
   - Portainer → Stacks → testum → Delete

2. **Создайте новый стек**:
   - Stacks → Add stack
   - Name: `testum`
   - Build method: **Web editor**

3. **Скопируйте содержимое файла `docker-compose.portainer.yml`**
   - Откройте: https://raw.githubusercontent.com/4stm4/testum/main/docker-compose.portainer.yml
   - Скопируйте ВСЁ
   - Вставьте в Web editor

4. **НЕ ДОБАВЛЯЙТЕ переменные окружения** - они уже внутри!

5. **Нажмите "Deploy the stack"**

6. **Дождитесь 2-3 минуты**

7. **Откройте**: http://ваш-сервер:8000
   - Username: `admin`
   - Password: `admin123`

---

## Что внутри:

```yaml
FERNET_KEY: 8KMhgoZ3LqvVNxKz4YHzMNJRCq5YUf3yx8WlBKxuX8k=
SECRET_KEY: test-secret-key-change-me-in-production
ADMIN_USERNAME: admin
ADMIN_PASSWORD: admin123
```

Все переменные жестко прописаны в docker-compose файле!

---

## Для production

Отредактируйте `docker-compose.portainer.yml` перед деплоем:
- Измените `ADMIN_PASSWORD` на свой
- Опционально: сгенерируйте новый `FERNET_KEY` и `SECRET_KEY`

---

## Проверка

В логах `testum_app` должно быть:
```
=== Checking environment variables ===
FERNET_KEY is set: YES  ✅
DATABASE_URL: postgresql://postgres:postgres@db:5432/testum
Running database migrations...
Starting application...
Uvicorn running on http://0.0.0.0:8000
```

✅ **Должно просто заработать!**
