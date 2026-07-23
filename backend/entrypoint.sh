#!/bin/sh
set -e

if [ "$1" = "web" ]; then
  python manage.py migrate --noinput
  exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
elif [ "$1" = "worker" ]; then
  exec python manage.py consume_inference_logs
else
  exec "$@"
fi
