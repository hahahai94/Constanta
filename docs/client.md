# Аудит клиентской части и шаблонов

## Сводка

Найдено **20+ проблем** различной критичности: от неработающих URL-имён и поломанного JavaScript до отсутствующих контекстных переменных и неподключаемых теговых библиотек.

---

## Найденные проблемы

### [CRITICAL] Несуществующие URL-имена `superadmin_*`

- **Файлы:** `templates/superadmin/panel.html`, `user_edit.html`, `user_delete.html`, `message_edit.html`, `group_edit.html`, `group_delete.html`, `ban_confirm.html`
- **Описание:** Шаблоны панели суперадмина ссылаются на URL-имена: `superadmin_panel`, `superadmin_user_edit`, `superadmin_impersonate`, `superadmin_ban_user`, `superadmin_unban_user`, `superadmin_delete_user`, `superadmin_edit_group`, `superadmin_delete_group`, `superadmin_exit_impersonate`. Ни одно из этих имён не определено ни в одном `urls.py` проекта. Django выбросит `NoReverseMatch` при попытке зайти в любой из этих шаблонов.
- **Рекомендация:** Добавить соответствующие URL-паттерны и вьюхи, либо убрать шаблоны. Если функциональность не реализована — спрятать ссылки.

### [CRITICAL] Файл тегов с неправильным расширением

- **Файл:** `chat/templatetags/custom_filters.py.html`
- **Описание:** Файл имеет расширение `.py.html` вместо `.py`. Django не загрузит его как библиотеку тегов. Любой шаблон с `{% load custom_filters %}` упадёт с `TemplateSyntaxError: 'custom_filters' is not a valid tag library`.
- **Рекомендация:** Переименовать в `custom_filters.py`.

### [CRITICAL] Нет вьюхи для `chat_files.html`

- **Файл:** `templates/chat_files.html`
- **Описание:** Шаблон существует, но нет ни URL-паттерна, ни view-функции, которая бы его рендерила. Контекст (`chat_name`, `chat_type`, `friend_id`, `group_id`, `images_count`, `files_count`, `voice_count`, `files`) никогда не будет передан. Шаблон мёртвый.
- **Рекомендация:** Добавить view и URL, либо удалить шаблон.

### [CRITICAL] Нет вьюхи для `tech.html`

- **Файл:** `templates/tech.html`
- **Описание:** Шаблон использует переменные `python_version`, `db_engine`, `status`, но ни одна view их не передаёт, и ни один URL-паттерн не ссылается на этот шаблон.
- **Рекомендация:** Удалить или реализовать view.

### [CRITICAL] `status_tags.py` — HTML без `mark_safe`

- **Файл:** `chat/templatetags/status_tags.py:9-23`
- **Описание:** Фильтр `user_status` возвращает HTML-строки (`<span class="status-dot online"></span>`). Django по умолчанию экранирует все переменные в шаблонах, поэтому фильтр выведет экранированный текст вместо живого HTML. В шаблонах (`index.html:191`) фильтр вызывается как `{{ active_friend|user_status }}`, но тег не помечен как безопасный.
- **Рекомендация:** Добавить `from django.utils.safestring import mark_safe` и обернуть возвращаемые значения в `mark_safe()`. Или использовать `is_safe=True` в декораторе.

### [HIGH] `scrollToMessage()` ищет `[data-message-id]`, но атрибут не установлен

- **Файлы:** `templates/index.html:404-411`, `templates/group_chat.html:597-606`
- **Описание:** Функция `scrollToMessage()` ищет элемент с атрибутом `data-message-id` через `document.querySelector([data-message-id="${msgId}"])`, но ни один блок сообщения в шаблонах не содержит `data-message-id`. Функция никогда не найдёт элемент.
- **Рекомендация:** Добавить `data-message-id="{{ msg.id }}"` к контейнеру каждого сообщения (например, к `<div class="d-flex ...">` на строках `index.html:209` и `group_chat.html:348`).

### [HIGH] `profile.html` — инпут аватарки вне формы

- **Файл:** `templates/profile.html:20`
- **Описание:** Поле `<input type="file" id="avatar-upload">` находится внутри `<label>` в блоке-шапке (строки 11-24), который расположен ДО открывающего тега `<form>` (строка 27). При отправке формы файл аватарки не будет включён в POST-запрос. При этом view `profile_view()` ожидает `request.FILES.get('avatar')`.
- **Рекомендация:** Перенести `<input type="file" id="avatar-upload">` внутрь формы, либо отправлять его отдельным AJAX-запросом.

### [HIGH] `profile.html` — нет вывода Django messages

- **Файл:** `templates/profile.html`
- **Описание:** View `profile_view()` устанавливает `messages.success(request, 'Профиль обновлён!')`, но в шаблоне нет блока `{% if messages %}`. Пользователь никогда не увидит сообщение об успехе или ошибке.
- **Рекомендация:** Добавить блок вывода messages (как в `auth.html:17-24`).

### [HIGH] `group_chat.html` — хардкод URL вместо `{% url %}`

- **Файл:** `templates/group_chat.html:719`
- **Описание:** В JavaScript-функции `saveGroupSettings()` URL для API указан как `'/groups/{{ group.id }}/settings/'`. Это ломается при изменении префикса URL и не использует механизм revers'ов Django.
- **Рекомендация:** Заменить на `'{% url "api_update_group" group.id %}'`.

### [HIGH] `chat_files.html` — необъявленная переменная `event`

- **Файл:** `templates/chat_files.html:109`
- **Описание:** Функция `filterFiles(type)` на строке 109 обращается к `event.target.classList.add('active')`, но `event` не передан как параметр и не является глобальной переменной. В строгом режиме (use strict) это выбросит `ReferenceError`.
- **Рекомендация:** Изменить сигнатуру на `function filterFiles(type, event)` и во всех `onclick` передавать `event`: `onclick="filterFiles('all', event)"`.

### [HIGH] Неправильное наследование блоков `container_class`

- **Файлы:** `templates/group_edit.html:4`, `templates/chat_files.html:4`, `templates/superadmin/panel.html:4`, `templates/superadmin/group_edit.html:4`, `templates/superadmin/group_delete.html:4`
- **Описание:** Шаблоны определяют блок `{% block container_class %}container{% endblock %}`, но базовый шаблон `base.html` не содержит такого блока. Это не вызывает ошибки, но блок игнорируется.
- **Рекомендация:** Либо добавить блок в `base.html`, либо убрать из дочерних шаблонов.

### [HIGH] `parts/reply.html` — нигде не используется

- **Файл:** `templates/parts/reply.html`
- **Описание:** Шаблон-фрагмент для ответов на сообщения не включается ни в один из основных шаблонов (`{% include %}`). При этом функциональность ответа реализована встроенным кодом в `index.html` и `group_chat.html`. Файл является мёртвым кодом.
- **Рекомендация:** Удалить или подключить через `{% include %}` в нужных шаблонах, удалив дублирующийся код.

### [MEDIUM] Нет вывода messages в ряде шаблонов

- **Файлы:** `templates/change_username.html`, `templates/change_password.html`, `templates/password_done.html`, `templates/groups.html`, `templates/profile.html`
- **Описание:** Соответствующие view устанавливают Django messages (успех/ошибка), но шаблоны не содержат блока `{% if messages %}` для их отображения. Пользователь не видит сообщения.
- **Рекомендация:** Добавить блок вывода messages в каждый из этих шаблонов.

### [MEDIUM] `group_create.html` — отсутствует загрузка `{% load static %}`

- **Файл:** `templates/group_create.html:1-2`
- **Описание:** Шаблон расширяет `base.html`, но не загружает `{% load static %}`. Хотя сам не использует статику напрямую, это нарушает конвенцию и может вызвать проблемы при наследовании.
- **Рекомендация:** Добавить `{% load static %}` после `{% extends %}`.

### [MEDIUM] `base.html` — отсутствует `<meta name="description">`

- **Файл:** `templates/base.html:5-7`
- **Описание:** В `<head>` есть `charset` и `viewport`, но нет `description`, `keywords`, `og:*` и favicon. Это не влияет на функциональность, но плохо для SEO.
- **Рекомендация:** Добавить базовые meta-теги.

### [MEDIUM] Inline CSS в `<body>` вместо `<head>`

- **Файлы:** `templates/index.html:5-143`, `templates/group_chat.html:5-254`, `templates/users_catalog.html:5-91`, `templates/tasks/task_lists.html:5-32`, `templates/tasks/task_list_detail.html:5-45`
- **Описание:** Крупные блоки `<style>` находятся внутри `{% block content %}`, который рендерится в `<body>`. Валидный HTML, но не соответствует семантике — стили должны быть в `<head>`.
- **Рекомендация:** Перенести `<style>` в блок `{% block extra_css %}` (определён в `base.html:12`).

### [MEDIUM] `banned.html` — нестандартный фон переопределяет `<body>`

- **Файл:** `templates/banned.html:63-66`
- **Описание:** Стиль на строках 63-66 применяет градиент к `body`, но тэг `<style>` находится внутри `{% block content %}`, то есть внутри `<body>` шаблона `base.html`. Стили сработают, но нарушают структуру.
- **Рекомендация:** Перенести в `{% block extra_css %}`.

### [LOW] `group_edit.html` — аватар группы не обновляется при предпросмотре

- **Файл:** `templates/group_edit.html:17-19`
- **Описание:** При выборе нового файла аватарки нет JavaScript-предпросмотра (в отличие от `group_chat.html`, где это реализовано).
- **Рекомендация:** Добавить JS для предпросмотра (аналогично `group_chat.html:735-742`).

### [LOW] `change_username.html` и `change_password.html` — нет отображения ошибок формы по полям

- **Файлы:** `templates/change_username.html:17-25`, `templates/change_password.html:17-25`
- **Описание:** Вывод `form.errors` есть, но Django 4.x+ группирует ошибки по полям. При невалидной форме пользователь видит общие ошибки, но поля не подсвечиваются красным (`is-invalid`) и нет сообщений рядом с конкретными полями.
- **Рекомендация:** Добавить CSS-класс `is-invalid` к полям при наличии ошибок и выводить `field.errors` рядом с каждым полем.

### [LOW] `auth.html` — режим `reg` не передаётся в POST без параметра

- **Файл:** `templates/auth.html:30`, `users/views/auth.py:14`
- **Описание:** Форма регистрации отображается при `?mode=reg` в GET, но при POST проверка строки 14 (`mode == 'reg' or 'register' in request.POST`) полагается только на наличие кнопки `register` (строка 53 в шаблоне). Если пользователь нажмёт Enter, а не кнопку, `register` может не быть в POST. При этом форма уходит с action без query-параметра, и сервер не знает, что это регистрация.
- **Рекомендация:** Добавить скрытое поле `<input type="hidden" name="mode" value="{{ type }}">` в форму, либо проверять `request.POST.get('mode')`.

### [INFO] `parts/reply.html` — `message-content` не существует

- **Файл:** `templates/parts/reply.html:20`
- **Описание:** JS-код вызывает `document.getElementById('message-content').focus()`, но в существующих шаблонах нет элемента с id `message-content`. Поле ввода имеет id `message-input`.
- **Рекомендация:** Исправить id (или удалить файл, см. выше).

### [INFO] `settings.html` — дублирует функциональность

- **Файл:** `templates/settings.html`
- **Описание:** Шаблон для смены логина/пароля дублирует `change_username.html` и `change_password.html`, но ни одна view не рендерит `settings.html` (нет URL для него).
- **Рекомендация:** Удалить, если не используется.

---

## Общие замечания

1. **Дублирование кода.** JS-функционал (отправка сообщений, эмодзи-пикер, файлы, ответы) полностью продублирован в `index.html` и `group_chat.html` (~250 строк JS в каждом). Рекомендуется вынести общий код в статический JS-файл.
2. **Inline JS в шаблонах.** Весь клиентский JavaScript находится внутри шаблонов, а не в статических `.js`-файлах. Это мешает кешированию, увеличивает размер HTML и усложняет поддержку.
3. **CSS-дублирование.** Стили `.message-bubble`, `.message-own`, `.message-other`, `.emoji-btn`, `.file-tag`, `.reply-panel`, `.reply-quote` и их вариации определены в `style.css` и повторно в инлайн-блоках `index.html` и `group_chat.html`. Следует оставить только в CSS-файле и убрать из шаблонов.
4. **Нет тестирования на клиенте.** Отсутствуют unit-тесты для JS-функций. Критические функции вроде `startReply()`, `cancelReply()`, `scrollToMessage()` не покрыты тестами.
