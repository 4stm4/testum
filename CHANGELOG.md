# Changelog

## 2025-11-09 - Упрощение деплоя

### Изменено
- ✅ Оставлен единственный `docker-compose.yml` с жестко прописанными переменными окружения
- ✅ Все переменные (FERNET_KEY, SECRET_KEY, etc.) прописаны в файле - не нужно добавлять вручную
- ✅ Упрощена документация - удалены дубликаты и устаревшие файлы
- ✅ Добавлена секция быстрого старта в README.md

### Удалено
- ❌ `docker-compose.portainer.yml` (объединен с основным)
- ❌ `docker-compose.test.yml` (объединен с основным)
- ❌ Дубликаты документации (DEPLOYMENT_CHECKLIST, PORTAINER_ENV_VARS, и др.)

### Деплой
Теперь для деплоя в Portainer нужно:
1. Скопировать `docker-compose.yml`
2. Нажать Deploy
3. Готово!

Переменные окружения добавлять НЕ НУЖНО - они уже в файле.

### Credentials по умолчанию
- Username: `admin`
- Password: `admin123`
- FERNET_KEY: `8KMhgoZ3LqvVNxKz4YHzMNJRCq5YUf3yx8WlBKxuX8k=`

⚠️ **Для production измените пароль в docker-compose.yml перед деплоем!**
