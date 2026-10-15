# Constanta Messenger

Репозиторий проекта Constanta — веб-мессенджера на Django. Проект ориентирован на высокую скорость работы, безопасность данных и масштабируемость: личные чаты, группы и каналы, вложения, упоминания и уведомления.

## Технологический стек

- **Python** 3.14+
- **Django** — основной бэкенд-фреймворк
- **Gunicorn** — WSGI-сервер для продакшн-развёртывания
- **Whitenoise** — раздача статики из приложения
- **Pillow** — обработка изображений и аватаров
- **environs** + **dj-database-url** — конфигурация через переменные окружения
- **django-cors-headers** — CORS
- **psycopg2-binary** — драйвер PostgreSQL

## Инструкция по локальному развёртыванию

### 1. Виртуальное окружение

```bash
python -m venv venv

# Windows (Command Prompt)
venv\Scripts\activate

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Mac/Linux
source venv/bin/activate
```

### 2. Установка зависимостей

Через [uv](https://docs.astral.sh/uv/) (рекомендуется, используется `uv.lock`):

```bash
uv sync
```

Или через pip:

```bash
pip install django environs dj-database-url django-cors-headers pillow whitenoise psycopg2-binary
```

### 3. Переменные окружения

Скопируйте пример конфигурации и заполните значения:

```bash
cp .env.example .env
```

Обязательные переменные:

- `SECRET_KEY` — секретный ключ Django (обязателен, приложение не запустится без него)
- `DEBUG` — `True` для локальной разработки
- `ALLOWED_HOSTS` — список хостов через запятую
- `DATABASE_URL` — строка подключения к БД (по умолчанию `sqlite:///db.sqlite3`)

Дополнительные (см. `.env.example` и `Constanta/settings.py`): `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`, `CACHE_BACKEND`, `CACHE_LOCATION`, `USE_X_FORWARDED_FOR`, `TIMEZONE`, `LANGUAGE_CODE`.

### 4. Инициализация БД и запуск

```bash
python manage.py migrate
python manage.py runserver
```

Приложение будет доступно по адресу http://127.0.0.1:8000/

### 5. Тесты

```bash
python manage.py test
```

## Развёртывание (production)

- Перед сборкой статики задайте `DEBUG=False`; статика собирается командой `python manage.py collectstatic` (каталог `staticfiles/` генерируется, в git не хранится).
- Запуск: `gunicorn Constanta.wsgi`.
- **За прокси**: включите `USE_X_FORWARDED_FOR=True` **и обязательно** перечислите адреса прокси в `TRUSTED_PROXIES` (например `TRUSTED_PROXIES=127.0.0.1,10.0.0.5`). По умолчанию заголовок игнорируется, а от недоверенного источника игнорируется всегда: nginx дописывает `X-Forwarded-For`, поэтому его левое значение подделывается клиентом, и доверять можно только адресу, который действительно видел прокси.
- **Rate-limit / кеш**: по умолчанию используется файловый кэш (`CACHE_LOCATION`, по умолчанию `.cache/` в корне проекта) — общий для воркеров на одном хосте. Для нескольких хостов задайте `CACHE_BACKEND` (например, `django_redis.cache.RedisCache`) и `CACHE_LOCATION`.
- Секретный путь админки можно изменить через переменную `ADMIN_URL`.

## Функциональность

- Личные чаты с доставкой новых сообщений (polling), ответами и вложениями
- Группы: роли (владелец/админ/участник), управление составом
- Каналы: публичные и приватные (подписка по ссылке-приглашению), публикации
- Упоминания пользователей и `@all`, уведомления
- Бан по IP, rate-limit API, CSP, кастомная аутентификация

## Дорожная карта

- Сквозное шифрование (E2EE)
- Голосовые и видеозвонки
- Кастомные темы оформления и тёмный режим
- Перевод реального времени на WebSocket (ASGI уже настроен)
