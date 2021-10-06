import os
from datetime import timedelta
# from rest_framework_jwt import VerifyJSONWebTokenSerializer


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'e8a6a589-0ff0-4951-8089-c476ca081f8f'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

SITE_ID = 2

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField' 

ALLOWED_HOSTS = ['localhost', 'green-node.ru', 'altekloads.com', 'twilio.com', 'cnulogistics.com']

AUTH_USER_MODEL = 'app.User'

# Application definition

INSTALLED_APPS = [
    'daphne',
    'channels',
    'app',
    'authentication',
    'rest_framework',
    'rest_framework.authtoken',
    'celery',
    'twilio',

    'dj_rest_auth',
    'allauth',
    'allauth.account',
    'dj_rest_auth.registration',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'corsheaders',

    'django.contrib.sites',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

REST_AUTH_SERIALIZERS = {
    'LOGIN_SERIALIZER': 'rest_auth.serializers.LoginSerializer',
    'TOKEN_SERIALIZER': 'rest_auth.serializers.TokenSerializer',
    'JWT_SERIALIZER': 'rest_auth.serializers.JWTSerializer'
}
REST_AUTH_REGISTER_SERIALIZERS = {
    'REGISTER_SERIALIZER': 'rest_auth.registration.serializers.RegisterSerializer'
}

REST_AUTH_TOKEN_CREATOR = 'rest_auth.utils.default_create_token'

REST_USE_JWT = True
# USER_DETAILS_SERIALIZER = app.serializers.UserSerializer
REST_AUTH_REGISTER_SERIALIZERS = {
    'REGISTER_SERIALIZER': 'app.system_api.register_serializer.RegisterSerializer',
}

SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = '1234567890987654321.apps.googleusercontent.com' 
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = '1234567890987654321'

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_USERNAME_REQUIRED = False

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES':[
        'rest_framework.permissions.IsAdminUser',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_jwt.authentication.JSONWebTokenAuthentication',
        'rest_framework.authentication.BasicAuthentication',
        # 'rest_framework.authentication.SessionAuthentication',
    ),
}

DEFAULT_PARSER_CLASSES = (
    'rest_framework.parsers.JSONParser',
    'rest_framework.parsers.FormParser',
    'rest_framework.parsers.MultiPartParser',
)

JWT_ALLOW_REFRESH = True
JWT_AUTH = {
    'JWT_EXPIRATION_DELTA': timedelta(days=7),
    'JWT_REFRESH_EXPIRATION_DELTA': timedelta(days=7),
}


# SIMPLE_JWT = {
#     'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
#     'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
#     'SLIDING_TOKEN_LIFETIME': timedelta(days=1),
#     'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=7),
# }

CORS_ORIGIN_ALLOW_ALL = True

ROOT_URLCONF = 'api.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'api.wsgi.application'
ASGI_APPLICATION = 'api.routing.application'

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
            "capacity": 1500,  
            "expiry": 10
        },
    },
}

# Database
# https://docs.djangoproject.com/en/2.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2', # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': 'name',
        'USER': 'user',
        'PASSWORD': 'password',
        'HOST': '127.0.0.1',
        'PORT': '5432',
    }
}


# Password validation
# https://docs.djangoproject.com/en/2.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/var/tmp/django_cache',
    }
}



# Internationalization
# https://docs.djangoproject.com/en/2.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.0/howto/static-files/

STATIC_URL = '/backend/api/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

MEDIA_URL = '/backend/api/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

TEMPLATE_CONTEXT_PROCESSORS = ("django.core.context_processors.static",)

# TEMPLATES_DIRS = (os.path.join(BASE_DIR, 'templates'))
STATIC_DIRS = (os.path.join(BASE_DIR, 'static'))
# STATICFILES_DIRS = (os.path.join(BASE_DIR, 'static'),)


EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_HOST_USER = "Development@etlgroupllc.com"
EMAIL_HOST_PASSWORD = "pWnVnr0Lb7n1AF2RFnDI"
EMAIL_USE_TLS = True


BING_API_KEY = "1234567890987654321"


GMAPS_API_KEY = "1234567890987654321"


PUBSUB_PROJECT_ID = 'altek-mail-1604991451587'
PUBSUB_TOPIC_ID = 'loads_parsing'


CELERY_BROKER_URL = 'redis://localhost:6379'  
CELERY_RESULT_BACKEND = 'redis://localhost:6379'  
CELERY_ACCEPT_CONTENT = ['application/json']  
CELERY_RESULT_SERIALIZER = 'json'  
CELERY_TASK_SERIALIZER = 'json'  


