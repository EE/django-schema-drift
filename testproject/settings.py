import os

SECRET_KEY = 'test'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
INSTALLED_APPS = ['schema_drift', 'testproject.testapp']
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'schema_drift'),
        'USER': os.environ.get('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'postgres'),
        'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
    },
}
