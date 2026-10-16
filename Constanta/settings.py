import sys
from pathlib import Path
from environs import Env

env = Env()
env.read_env()

BASE_DIR = Path(__file__).resolve().parent.parent

# Тестовый прогон (`manage.py test`) — кэш держим в памяти, чтобы не читать
# устаревшие счётчики rate-limit между запусками.
TESTING = 'test' in sys.argv

SECRET_KEY = env('SECRET_KEY')
DEBUG = env.bool('DEBUG', default=False)

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[
    '127.0.0.1', 'localhost', 'testserver',
])

CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'corsheaders',
    'chat.apps.ChatConfig',
    'users.apps.UsersConfig',
    'tasks.apps.TasksConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'Constanta.middleware.CSPMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'users.middleware.BannedUserMiddleware',
    'users.middleware.IPBanMiddleware',
]

ROOT_URLCONF = 'Constanta.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'users.context_processors.notifications',
            ],
        },
    },
]

WSGI_APPLICATION = 'Constanta.wsgi.application'

# Прогон тестов пишет загруженные файлы во временный каталог, а не в media/
# проекта (problems.md, П-14).
TEST_RUNNER = 'Constanta.test_runner.IsolatedMediaRunner'

DATABASES = {
    'default': env.dj_db_url('DATABASE_URL', default='sqlite:///db.sqlite3')
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO' if not DEBUG else 'DEBUG',
    },
}

LANGUAGE_CODE = env('LANGUAGE_CODE', default='ru')
TIME_ZONE = env('TIMEZONE', default='Asia/Vladivostok')
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage' if not DEBUG else 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

AUTH_USER_MODEL = 'users.User'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

FILE_UPLOAD_MAX_MEMORY_SIZE = env.int('FILE_UPLOAD_MAX_MEMORY_SIZE', default=10 * 1024 * 1024)
DATA_UPLOAD_MAX_MEMORY_SIZE = env.int('DATA_UPLOAD_MAX_MEMORY_SIZE', default=10 * 1024 * 1024)

LOGIN_URL = '/auth/'
LOGIN_REDIRECT_URL = '/main/'
LOGOUT_REDIRECT_URL = '/auth/'

# CustomAuthBackend — наследник ModelBackend, поэтому отдельный ModelBackend
# здесь не нужен и вреден: он использует собственную `user_can_authenticate`,
# которая не знает про бан, и перебор бэкендов пустил бы забаненного
# пользователя внутрь (problems.md, П-4).
AUTHENTICATION_BACKENDS = [
    'users.backends.CustomAuthBackend',
]

EMAIL_HOST = env('EMAIL_HOST', default='')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@constanta.local')

# Общий кэш (rate-limit, сессии-агрегаты) должен быть виден всем воркерам Gunicorn.
# По умолчанию используется файловый кэш (общий для процессов на одном хосте).
# Для нескольких хостов задайте CACHE_BACKEND (например, django_redis) и CACHE_LOCATION.
CACHE_BACKEND = env(
    'CACHE_BACKEND',
    default='django.core.cache.backends.locmem.LocMemCache' if TESTING
    else 'django.core.cache.backends.filebased.FileBasedCache',
)
CACHE_LOCATION = env('CACHE_LOCATION', default='constanta' if TESTING else str(BASE_DIR / '.cache'))

CACHES = {
    'default': {
        'BACKEND': CACHE_BACKEND,
        'LOCATION': CACHE_LOCATION,
    }
}

# Доверять заголовку X-Forwarded-For только если приложение реально стоит за прокси.
# Иначе клиент может подделать IP и обойти IP-бан / rate-limit.
USE_X_FORWARDED_FOR = env.bool('USE_X_FORWARDED_FOR', default=False)

# Заголовку X-Forwarded-For доверяем только от перечисленных адресов прокси.
# Без этого списка включение USE_X_FORWARDED_FOR открывает обход лимитов: nginx
# дописывает заголовок, поэтому его левое значение контролирует клиент.
# Пример: TRUSTED_PROXIES=127.0.0.1,10.0.0.5
TRUSTED_PROXIES = env.list('TRUSTED_PROXIES', default=[])

SESSION_COOKIE_AGE = env.int('SESSION_COOKIE_AGE', default=86400)
SESSION_SAVE_EVERY_REQUEST = env.bool('SESSION_SAVE_EVERY_REQUEST', default=False)
MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'

# 🔒 Безопасность cookie
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'

CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])
CORS_ALLOW_CREDENTIALS = True

# Настройки безопасности вынесены в переменные окружения с безопасными
# значениями по умолчанию. Раньше они включались только по `not DEBUG`, из-за
# чего прод-окружение, унаследовавшее dev-`.env`, оставалось без защиты
# (problems.md, П-26), а жёсткий `SECURE_SSL_REDIRECT` давал цикл редиректов
# за прокси без `X-Forwarded-Proto` (problems.md, П-27).
SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=not DEBUG)
CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=not DEBUG)
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=not DEBUG)
SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=0 if DEBUG else 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    'SECURE_HSTS_INCLUDE_SUBDOMAINS', default=not DEBUG)
SECURE_HSTS_PRELOAD = env.bool('SECURE_HSTS_PRELOAD', default=False)

# Доверять `X-Forwarded-Proto` можно только когда прокси его действительно
# проставляет. Иначе Django не видит HTTPS и `SECURE_SSL_REDIRECT` зацикливается:
# выключите либо редирект, либо эту опцию.
USE_X_FORWARDED_PROTO = env.bool('USE_X_FORWARDED_PROTO', default=not DEBUG)
SECURE_PROXY_SSL_HEADER = (
    ('HTTP_X_FORWARDED_PROTO', 'https') if USE_X_FORWARDED_PROTO else None
)

MAX_GROUPS_PER_USER = env.int('MAX_GROUPS_PER_USER', default=50)
MAX_CHANNELS_PER_USER = env.int('MAX_CHANNELS_PER_USER', default=50)
MAX_MESSAGE_LENGTH = env.int('MAX_MESSAGE_LENGTH', default=2000)
