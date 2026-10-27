"""Servidor de E2E da apresentação, com cópia isolada do SQLite local."""
import os
from pathlib import Path
import sqlite3
import sys


root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
target = root / ".worktrees" / "presentation-validation.sqlite3"
target.parent.mkdir(exist_ok=True)
if target.resolve() == (root / "db.sqlite3").resolve():
    raise RuntimeError("O banco de teste deve ser uma cópia independente.")
if (root / "db.sqlite3").exists():
    with sqlite3.connect((root / "db.sqlite3").as_uri() + "?mode=ro", uri=True) as source:
        with sqlite3.connect(target) as destination:
            source.backup(destination)
os.environ["DATABASE_URL"] = f"sqlite:///{target.as_posix()}"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.core.management import call_command

django.setup()
call_command("migrate", interactive=False, verbosity=0)
call_command("runserver", "127.0.0.1:8012", use_reloader=False)
