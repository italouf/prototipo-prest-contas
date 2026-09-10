"""Converte/copia fontes de font/ para static/fonts/ (idempotente).

Uso:
    python scripts/convert_fonts.py           # gera o que faltar
    python scripts/convert_fonts.py --force   # regera tudo
    python scripts/convert_fonts.py --check   # não gera; falha se faltar algo
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FONT_DIR = BASE_DIR / "font"
OUT_DIR = BASE_DIR / "static" / "fonts"

PANTON = {
    "Light": "panton/WEB/Panton-Trial-Light.woff2",
    "Regular": "panton/WEB/Panton-Trial-Regular.woff2",
    "SemiBold": "panton/WEB/Panton-Trial-SemiBold.woff2",
    "Bold": "panton/WEB/Panton-Trial-Bold.woff2",
    "Black": "panton/WEB/Panton-Trial-Black.woff2",
}
JETBRAINS = {
    "Regular": "JetBrainsMono-2.304/fonts/webfonts/JetBrainsMono-Regular.woff2",
    "Medium": "JetBrainsMono-2.304/fonts/webfonts/JetBrainsMono-Medium.woff2",
    "Bold": "JetBrainsMono-2.304/fonts/webfonts/JetBrainsMono-Bold.woff2",
}
MYRIAD = {
    "Light": "myriad-pro/MyriadPro-Light.otf",
    "Regular": "myriad-pro/MYRIADPRO-REGULAR.OTF",
    "SemiBold": "myriad-pro/MYRIADPRO-SEMIBOLD.OTF",
    "Bold": "myriad-pro/MYRIADPRO-BOLD.OTF",
}


def _destino(pasta: str, nome: str) -> Path:
    return OUT_DIR / pasta / f"{nome}.woff2"


def _precisa_gerar(origem: Path, destino: Path, force: bool) -> bool:
    if not origem.exists():
        return False
    if force or not destino.exists():
        return True
    return origem.stat().st_mtime > destino.stat().st_mtime


def processar(force: bool = False) -> list[str]:
    gerados: list[str] = []
    for pasta, mapa, prefixo in (
        ("panton", PANTON, "Panton"),
        ("jetbrains-mono", JETBRAINS, "JetBrainsMono"),
    ):
        for nome, rel in mapa.items():
            origem = FONT_DIR / rel
            destino = _destino(pasta, f"{prefixo}-{nome}")
            if _precisa_gerar(origem, destino, force):
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(origem.read_bytes())
                gerados.append(str(destino.relative_to(BASE_DIR)))
    for nome, rel in MYRIAD.items():
        origem = FONT_DIR / rel
        destino = _destino("myriad-pro", f"MyriadPro-{nome}")
        if _precisa_gerar(origem, destino, force):
            from fontTools.ttLib import TTFont

            destino.parent.mkdir(parents=True, exist_ok=True)
            fonte = TTFont(str(origem))
            fonte.flavor = "woff2"
            fonte.save(str(destino))
            fonte.close()
            gerados.append(str(destino.relative_to(BASE_DIR)))
    return gerados


def faltantes() -> list[str]:
    esperados = (
        [("panton", f"Panton-{n}") for n in PANTON]
        + [("jetbrains-mono", f"JetBrainsMono-{n}") for n in JETBRAINS]
        + [("myriad-pro", f"MyriadPro-{n}") for n in MYRIAD]
    )
    return [f"{p}/{n}.woff2" for p, n in esperados if not _destino(p, n).exists()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="regera tudo")
    parser.add_argument("--check", action="store_true", help="não gera; falha se faltar")
    args = parser.parse_args()

    if not FONT_DIR.exists():
        print("font/ ausente — nada a fazer (fallback system-ui).")
        return 0
    if args.check:
        ausentes = faltantes()
        if ausentes:
            print("Faltando: " + ", ".join(ausentes))
            return 1
        print("Fontes ok.")
        return 0
    gerados = processar(force=args.force)
    print(f"{len(gerados)} arquivo(s) gerado(s).")
    for caminho in gerados:
        print(f"  {caminho}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
