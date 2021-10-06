import os
import sys
import platform

sys.path.insert(0, '/var/www/etl/backend/api-etl/lib/python{0}/site-packages'.format(platform.python_version()[0:3]))



import django


from channels.routing import get_default_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.settings")

django.setup()

application = get_default_application()