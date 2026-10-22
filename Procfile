web: gunicorn core.wsgi:application --bind 0.0.0.0:$PORT --workers 3
worker: celery -A core worker -l info -P solo
beat: celery -A core beat -l info
