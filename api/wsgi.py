# -*- coding: utf-8 -*-

# import os
# import sys
# import platform

# #путь к проекту
# sys.path.insert(0, '/var/www/etl/backend/api')
# #путь к фреймворку
# sys.path.insert(0, '/var/www/etl/backend/api/api')
# #путь к виртуальному окружению
# sys.path.insert(0, '/var/www/etl/backend/api-etl/lib/python{0}/site-packages'.format(platform.python_version()[0:3]))
# os.environ["DJANGO_SETTINGS_MODULE"] = "api.settings"

# from django.core.wsgi import get_wsgi_application
# application = get_wsgi_application()

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')

application = get_wsgi_application()
