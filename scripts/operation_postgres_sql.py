"""Gera DDL PostgreSQL da migração de Operação sem abrir conexão ou aplicar SQL."""
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.db.backends.postgresql.base import DatabaseWrapper
from django.db.migrations.loader import MigrationLoader

target = ("entries", "0002_baseoperacional_indicadoroperacional_and_more")
loader = MigrationLoader(None)
state = loader.project_state([target])
connection = DatabaseWrapper({"NAME": "offline", "OPTIONS": {}, "TIME_ZONE": None}, alias="offline")
connection.ops.compose_sql = lambda sql, params: sql if not params else (_ for _ in ()).throw(ValueError("DDL com parâmetros inesperados"))
with connection.schema_editor(collect_sql=True, atomic=False) as editor:
    for name in ("BaseOperacional", "IndicadorOperacional", "LancamentoOperacional", "ProjetoFinanceiroFonte"):
        editor.create_model(state.apps.get_model("entries", name))
path = root / ".worktrees/operation-postgres.sql"
path.parent.mkdir(exist_ok=True)
path.write_text("\n".join(editor.collected_sql), encoding="utf-8")
print(f"{len(editor.collected_sql)} comandos DDL gerados em {path}")
