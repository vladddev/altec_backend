from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab
from . import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')

app = Celery('api')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()



app.conf.beat_schedule = {
    'every-minyte-beat': {
        'task': 'every_minute',
        'schedule': crontab(minute='*')
    },
    'load-expired': {
        'task': 'load_expired',
        'schedule': crontab(minute='*/5')
    },
    'send-email-notices-15m': {
        'task': 'update_load_location_email_15min',
        'schedule': crontab(minute='*/15')
    },
    'send-email-notices-30m': {
        'task': 'update_load_location_email_30min',
        'schedule': crontab(minute='*/30')
    },
    'send-email-notices-1h': {
        'task': 'update_load_location_email_1h',
        'schedule': crontab(hour='*')
    },
    'send-email-notices-2h': {
        'task': 'update_load_location_email_2h',
        'schedule': crontab(hour='*/2')
    },
    'send-email-notices-3h': {
        'task': 'update_load_location_email_3h',
        'schedule': crontab(hour='*/3')
    },
    'send-email-notices-4h': {
        'task': 'update_load_location_email_4h',
        'schedule': crontab(hour='*/4')
    },
    'update-pubsub': {
        'task': 'update_pubsub',
        'schedule': crontab(minute=0, hour=0, day_of_week='*')
    },
    'geo-push-request': {
        'task': 'geo_push_request',
        'schedule': crontab(minute='*/15')
    },
}