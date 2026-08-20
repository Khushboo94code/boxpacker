"""ASGI config for the boxpacker project."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "boxpacker.settings")

application = get_asgi_application()
