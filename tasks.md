# Tasks — Constanta

## 1. 🔧 Инфраструктура и настройки
- [x] `STATIC_ROOT` + `collectstatic` настроены; `staticfiles/` больше не хранится в git
- [ ] Внедрить **nginx** для раздачи статики в продакшне (сейчас Whitenoise)
- [ ] Разделить **логи** по модулям, добавить `RotatingFileHandler`
- [ ] Настроить WebSocket (channels) — ASGI настроен, но нет consumer'ов, обмен через HTTP + polling

## 2. 🐛 Ошибки и баги (исправлено)
- [x] **Курсор автообновления** — polling использовал `id` (UUID) как целое число. Переведён на курсор по `created_at` (`api_poll`, `data-cursor` в шаблонах)
- [x] **Дубли постов в каналах** — сортировка/курсор канала исправлены, повторная выдача исключена
- [x] **Вложения из каналов не скачивались** — `download_attachment` теперь проверяет подписку на канал
- [x] **Слабая валидация изображений** — Pillow проверяет файл целиком, а не первые 1024 байта
- [x] **Rate-limit/IP-бан** — общий файловый кэш + `X-Forwarded-For` учитывается только при `USE_X_FORWARDED_FOR=True` (`users/utils.get_client_ip`)
- [x] **Приватные каналы** — добавлена ссылка-приглашение (`invite_token`), подписка по токену
- [x] **`int(user_id)` мог дать 500** — невалидный `user_id` возвращает 400
- [x] Обход `CustomAuthBackend` — `auth_view` использует `AUTHENTICATION_BACKENDS[0]`, неактивные не входят
- [x] Дублирование `_file_hash()` / `generate_file_hash()` — оставлена одна реализация в `chat/utils/file_hash.py`
- [x] `GroupForm` и `GroupEditForm` объединены
- [x] Мёртвые шаблоны `group_create.html` / `group_edit.html` удалены
- [x] `password_done` — `change_password` редиректит на `password_done`
- [x] `STATICFILES_DIRS` определяется один раз
- [x] `is_private` у Channel учитывается в правах доступа

## 3. 🧹 Рефакторинг: users app ✅
Выделено в отдельное приложение `users/`.

- [x] Модели: `User`, `BannedIP`, `Notification`, `AdminLog` → `users/models.py`
- [x] `backends.py`, `middleware.py`, `admin.py`, формы, вьюхи, URL, шаблоны
- [x] `AUTH_USER_MODEL = 'users.User'`, `AUTHENTICATION_BACKENDS`
- [x] Импорты и миграции обновлены

## 4. 🧹 Рефакторинг: остальное
- [x] `chat/models.py` → пакет `chat/models/` (`message.py`, `channel.py`, `group.py`)
- [x] `chat/utils.py` → пакет `chat/utils/` (`file_hash.py`, `mentions.py`, `notifications.py`, `rate_limit.py`)
- [ ] Вынести оставшиеся CSS/JS из шаблонов в `static/css/` и `static/js/` (сейчас часть JS инлайн)
- [x] Общие HTML-блоки вынесены в `templates/parts/`

## 5. 🔐 Безопасность
- [x] `ADMIN_URL` (сложный путь админки) поддерживается через переменную окружения
- [x] Rate limiting на всех API-эндпоинтах + странице входа
- [x] Полная валидация загружаемых изображений
- [x] `X-Forwarded-For` не доверяется без явного включения
- [ ] Внедрить **сквозное шифрование (E2EE)**

## 6. 🧪 Тестирование
- [x] Тесты на регистрацию, вход, сообщения, группы, каналы, API
- [x] Тесты на курсор polling (личные/группы/каналы)
- [x] Тесты на приватные каналы и инвайты
- [x] Тесты на доступ к вложениям каналов
- [x] Тесты на определение клиентского IP / доверие прокси
- [ ] WebSocket и голосовые звонки

## 7. ⚡ Производительность
- [x] N+1 в `main_chat()` — заменён на `Subquery`-аннотацию
- [x] Автообновление переведено на JSON API (`/api/poll/`), без перезагрузки HTML
- [x] Пагинация сообщений (30 на страницу) с подгрузкой старых
- [x] Индекс на `last_seen` (миграция `users/0002`)

## 8. 🚀 Фичи
### Плановые (из README)
- [ ] WebSocket / голосовые звонки
- [ ] Кастомные темы и тёмный режим

### Недостающий функционал
- [ ] Email-верификация при регистрации
- [ ] WebSocket consumer (ASGI настроен, но не используется)
