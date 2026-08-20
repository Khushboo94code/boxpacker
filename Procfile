web: python manage.py collectstatic --noinput && python manage.py migrate --noinput && python manage.py seed_boxes && gunicorn boxpacker.wsgi --bind 0.0.0.0:$PORT --workers 3
