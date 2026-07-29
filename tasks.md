# Tasks — Constanta

## 1. 🔧 Инфраструктура и настройки
- [ ] Внедрить **nginx** для раздачи статики / настроить `STATIC_ROOT` для `collectstatic`
- [ ] Разделить **логи** по модулям, добавить `RotatingFileHandler`
- [ ] Проверить интеграцию **Jinja2** как альтернативу Django Templates
- [ ] Настроить WebSocket (channels) — ASGI настроен, но нет consumer'ов, весь обмен через HTTP POST + polling

## 2. 🐛 Ошибки и баги

### Высокий приоритет
- [ ] **Обход `CustomAuthBackend`** — `auth_view()` в `users/views/auth.py:36,52` хардкодит `backend='django.contrib.auth.backends.ModelBackend'`, неактивные пользователи могут войти
- [ ] **Слабая валидация файлов** — `chat/views/api.py:73-87` проверяет только magic-байты (32 байта), без полной валидации содержимого
- [ ] **Нет rate limiting на API** — только страница входа защищена, все `/api/*` эндпоинты без ограничений
- [ ] **`is_private` у Channel не проверяется** — поле хранится, но нигде не учитывается в правах доступа

### Средний приоритет
- [ ] **Дублирование `_file_hash()`** — `chat/models.py:_file_hash()` и `chat/utils.py:generate_file_hash()` делают одно и то же
- [ ] **Дублирование форм** — `GroupForm` и `GroupEditForm` в `chat/forms.py` идентичны
- [ ] **Мёртвый шаблон `group_create.html`** — `create_group` редиректит, не рендерит форму
- [ ] **Мёртвый шаблон `group_edit.html`** — `edit_group` редиректит на `group_chat`
- [ ] **`password_done.html` существует, но `change_password` редиректит на `profile`, а не на `password_done`**
- [ ] **Дублирование проверок `is_owner`/`is_admin`** в `group_chat()` (group.py:27-28 и 38-43)
- [ ] **`STATICFILES_DIRS` переопределяется 3 раза** (settings.py:176, 177, 190) — работает только последнее
- [ ] **В шаблонах ссылаются на несуществующие URL-имена** (`friends_add`, `friends_remove`, `superadmin_*` и др.)

## 3. 🧹 Рефакторинг: вынести `users` app ✅
Выделено в отдельное приложение `users/`. Требуется верификация:

### Модели и бэкенды ✅
- [x] Перенести `User`, `BannedIP`, `Notification`, `AdminLog` → `users/models.py`
- [x] `backends.py` → `users/backends.py`
- [x] `IPBanMiddleware` → `users/middleware.py`
- [x] `chat/admin.py` → убрать регистрацию User/BannedIP, перенести в `users/admin.py`

### Вьюхи, формы, URL ✅
- [x] Перенести `auth.py` + `profile.py` → `users/views/`
- [x] Перенести формы: `RegistrationForm`, `LoginForm`, `ProfileForm`, `ChangeUsernameForm`, `ChangePasswordForm`
- [x] Перенести URL-паттерны: auth, logout, profile, change-username, change-password, password-done, users

### Шаблоны ✅
- [x] Перенести: `auth.html`, `profile.html`, `users_catalog.html`, `change_username.html`, `change_password.html`, `banned.html`, `public_profile.html`
- [ ] `profile_edit.html`, `user_detail.html`, `friends.html`, `settings.html` — не найдены (возможно, не существуют)
- [ ] superadmin-шаблоны: `panel.html`, `user_edit.html`, `user_delete.html`, `ban_confirm.html` — не найдены

### Конфигурация ✅
- [x] `AUTH_USER_MODEL` → `'users.User'`
- [x] `AUTHENTICATION_BACKENDS` → `'users.backends.CustomAuthBackend'` + fallback
- [x] Добавить `'users.apps.UsersConfig'` в `INSTALLED_APPS`

### Импорты и миграции ✅
- [x] Обновить импорты `User` во всех файлах `chat/`
- [x] Обновить импорты в шаблонах (`{% url %}` и контекст)
- [x] Пересоздать все миграции с нуля + `db.sqlite3`

## 4. 🧹 Рефакторинг: остальное
- [ ] Разделить `chat/models.py` → `models/` (пакет)
- [ ] Разделить `chat/utils.py` → `utils/` (пакет)
- [ ] Вынести CSS/JS в `static/css/` и `static/js/`
- [ ] Вынести повторяющиеся HTML-блоки в `templates/parts/`
- [ ] Удалить мёртвые шаблоны: `group_create.html`, `group_edit.html`
- [ ] Удалить дубликат `_file_hash()` / `generate_file_hash()`, оставить один
- [ ] Объединить `GroupForm` и `GroupEditForm`

## 5. 🔐 Безопасность
- [ ] Скрыть `/admin/` (IP-белый список или сложный путь `ADMIN_URL`)
- [ ] Внедрить **сквозное шифрование (E2EE)**
- [ ] Усилить валидацию типов загружаемых файлов (проверять весь файл, а не 32 байта)
- [ ] Добавить rate limiting на все API-эндпоинты
- [ ] Исправить `auth_view` — убрать хардкод `backend=` или использовать `CustomAuthBackend`
- [ ] Реализовать проверку `is_private` для Channel

## 6. 🧪 Тестирование
- [ ] Покрыть ключевые сценарии (регистрация, отправка сообщений, группы)
- [ ] Дописать тесты для API-эндпоинтов
- [ ] Написать тест на обход `CustomAuthBackend`
- [ ] Написать тест на rate limiting API

## 7. ⚡ Производительность
- [ ] **N+1 запрос в `main_chat()`** — для каждого друга отдельный запрос `last_message`
- [ ] **Автообновление через polling** — `templates/index.html:463` загружает полную HTML-страницу каждые 2с (заменить на JSON API)
- [ ] **Нет пагинации сообщений** — `main_chat` загружает только 50 сообщений без "load more"
- [ ] **Добавить индекс на `last_seen`** — для оптимизации `is_online` и heartbeat

## 8. 🚀 Фичи

### Плановые (из README)
- [ ] **WebSocket / голосовые звонки**
- [ ] **Кастомные темы оформления** и тёмный режим

### Недостающий функционал
- [ ] **Модель `Friendship`** — не реализована, хотя `MAX_FRIENDS_PER_USER` задан
- [ ] **Email-верификация** — регистрация создаёт пользователей без подтверждения email
- [ ] **WebSocket consumer** — ASGI настроен, но не используется для реального времени
