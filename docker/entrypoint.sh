#!/bin/sh
set -eu

export PORT="${PORT:-8080}"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.prod}"

echo "Preparing nginx for PORT=${PORT}"
envsubst '${PORT}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf
# Railway healthchecks hit the public PORT; nginx is the only public listener.
rm -f /etc/nginx/sites-enabled/default /etc/nginx/sites-available/default

echo "Running database migrations"
python manage.py migrate --noinput

echo "Collecting static files"
python manage.py collectstatic --noinput

echo "Starting supervisord (nginx + gunicorn)"
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
