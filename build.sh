#!/usr/bin/env bash
# Build do Render: instala deps, coleta estáticos, migra e popula base demo sintética.
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input

python manage.py migrate

python manage.py seed_demo
