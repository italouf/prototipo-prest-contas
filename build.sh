#!/usr/bin/env bash
# Build do Render: instala dependências, coleta estáticos e aplica migrações.
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input

python manage.py migrate

# A migração gestao_at.0002 inclui os dados versionados do guia. Não executar
# seed_demo no deploy: ele atualiza registros que já podem ter sido editados.
