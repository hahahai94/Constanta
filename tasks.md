# Tasks — Constanta

## 1. 🔧 Инфраструктура и настройки
- [ ] Переехать с `pip` на **UV**
- [ ] Внедрить **nginx** для раздачи статики / настроить `STATIC_ROOT` для `collectstatic`
- [ ] Разделить **логи** по модулям, добавить `RotatingFileHandler`
- [ ] Проверить интеграцию **Jinja2** как альтернативу Django Templates

## 2. 🐛 Ошибки в коде
- [ ] `STATICFILES_DIRS` переопределяется **3 раза** (settings.py:176, 177, 190) — работает только последнее
- [ ] Дублирование проверок `is_owner`/`is_admin` в `group_chat()` (group.py:27-28 и 38-43)
- [ ] **N+1 запрос** в `main_chat()` — для каждого друга отдельный запрос `last_message`
- [ ] Шаблон `password_done.html` не существует, но вьюха `password_done()` на него ссылается
- [ ] В шаблонах ссылаются на несуществующие URL-имена (`friends_add`, `friends_remove`, `superadmin_*` и др.)
- [ ] В `chat/views/api.py:206` — `FileResponse` не импортирован

## 3. 🧹 Рефакторинг: вынести `users` app
Выделить всё, что связано с пользователями, в отдельное приложение `users/`:

### Модели и бэкенды
- [ ] Перенести `User`, `Friendship`, `BannedIP`, `Notification`, `AdminLog` → `users/models.py`
- [ ] `backends.py` → `users/backends.py`
- [ ] `IPBanMiddleware` → `users/middleware.py`
- [ ] `chat/admin.py` → убрать регистрацию User/BannedIP, перенести в `users/admin.py`

### Вьюхи, формы, URL
- [ ] Перенести `auth.py` + `profile.py` → `users/views/`
- [ ] Перенести формы: `RegistrationForm`, `LoginForm`, `ProfileForm`, `ChangeUsernameForm`, `ChangePasswordForm`, `AddFriendForm`
- [ ] Перенести URL-паттерны: auth, logout, profile, change-username, change-password, password-done, users

### Шаблоны
- [ ] Перенести: `auth.html`, `profile.html`, `profile_edit.html`, `user_detail.html`, `users_catalog.html`, `friends.html`, `change_username.html`, `change_password.html`, `banned.html`, `settings.html`
- [ ] Перенести superadmin-шаблоны: `panel.html`, `user_edit.html`, `user_delete.html`, `ban_confirm.html`

### Конфигурация
- [ ] `AUTH_USER_MODEL` → `'users.User'`
- [ ] `AUTHENTICATION_BACKENDS` → `'users.backends.CustomAuthBackend'`
- [ ] Добавить `'users.apps.UsersConfig'` в `INSTALLED_APPS`

### Импорты и миграции
- [ ] Обновить импорты `User` во всех файлах `chat/` (views, forms, utils, tests, admin, middleware)
- [ ] Обновить импорты в шаблонах (`{% url %}` и контекст)
- [ ] **Пересоздать все миграции с нуля + пересоздать `db.sqlite3`** *(данные теряются — это OK, одноразово)*

## 4. 🧹 Рефакторинг: остальное
- [ ] Разделить `chat/models.py` → `models/` (пакет)
- [ ] Разделить `chat/utils.py` → `utils/` (пакет)
- [ ] Вынести CSS/JS в `static/css/` и `static/js/`
- [ ] Вынести повторяющиеся HTML-блоки в `templates/parts/`

## 5. 🔐 Безопасность
- [ ] Скрыть `/admin/` (IP-белый список или сложный путь)
- [ ] Внедрить **сквозное шифрование (E2EE)**
- [ ] Валидация типов загружаемых файлов на сервере

## 6. 🧪 Тестирование
- [ ] Покрыть ключевые сценарии (регистрация, отправка сообщений, группы)
- [ ] Дописать тесты для API-эндпоинтов

## 7. 🚀 Фичи (из README)
- [ ] Голосовые звонки
- [ ] Кастомные темы оформления
