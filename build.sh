#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input

if [ -n "$DATABASE_URL" ]; then
  python manage.py migrate
else
  echo "No DATABASE_URL set. Skipping migrations."
fi

