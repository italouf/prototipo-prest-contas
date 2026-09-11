"""Converte/copia fontes de font/ para static/fonts/ (idempotente).

Uso:
    python scripts/convert_fonts.py           # gera o que faltar (baixa Montserrat se necessário)
    python scripts/convert_fonts.py --force   # regera tudo
    python scripts/convert_fonts.py --check   # não gera; falha se faltar algo
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FONT_DIR = BASE_DIR / "font"
OUT_DIR = BASE_DIR / "static" / "fonts"

MONTSSERRAT_URL = (
    "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf"
)
MONTSSERRAT_ORIGEM = FONT_DIR / "montserrat" / "Montserrat[wght].ttf"

JETBRAINS = {
    "Regular": "JetBrainsMono-2.304/fonts/webfonts/JetBrainsMono-Regular.woff2",
    "Medium": "JetBrainsMono-2.304/fonts/webfonts/JetBrainsMono-Medium.woff2",
    "Bold": "JetBrainsMono-2.304/fonts/webfonts/JetBrainsMono-Bold.woff2",
}


def _destino(pasta: str, nome: str) -> Path:
    return OUT_DIR / pasta / f"{nome}.woff2"


def _precisa_gerar(origem: Path, destino: Path, force: bool) -> bool:
    if not origem.exists():
        return False
    if force or not destino.exists():
        return True
    return origem.stat().st_mtime > destino.stat().st_mtime


def _baixar_montserrat() -> bool:
    """Baixa a Montserrat variável (OFL) do repositório google/fonts."""
    if MONTSSERRAT_ORIGEM.exists():
        return True
    destino = MONTSSERRAT_ORIGEM
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        print("Baixando Montserrat variável (google/fonts, OFL)…")
        with urllib.request.urlopen(MONTSSERRAT_URL, timeout=90) as resposta:
            destino.write_bytes(resposta.read())
        return True
    except Exception as exc:  # pragma: no cover - rede
        print(f"Aviso: não foi possível baixar a Montserrat ({exc}). Usando fallback.")
        return False


def _converter(origem: Path, destino: Path) -> None:
    from fontTools.ttLib import TTFont

    destino.parent.mkdir(parents=True, exist_ok=True)
    fonte = TTFont(str(origem))
    fonte.flavor = "woff2"
    fonte.save(str(destino))
    fonte.close()


def processar(force: bool = False) -> list[str]:
    gerados: list[str] = []
    for pasta, mapa, prefixo in (("jetbrains-mono", JETBRAINS, "JetBrainsMono"),):
        for nome, rel in mapa.items():
            origem = FONT_DIR / rel
            destino = _destino(pasta, f"{prefixo}-{nome}")
            if _precisa_gerar(origem, destino, force):
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(origem.read_bytes())
                gerados.append(str(destino.relative_to(BASE_DIR)))
    if _baixar_montserrat():
        destino = _destino("montserrat", "Montserrat-Variable")
        if _precisa_gerar(MONTSSERRAT_ORIGEM, destino, force):
            _converter(MONTSSERRAT_ORIGEM, destino)
            gerados.append(str(destino.relative_to(BASE_DIR)))
    return gerados


def faltantes() -> list[str]:
    esperados = (
        [("jetbrains-mono", f"JetBrainsMono-{n}") for n in JETBRAINS]
        + [("montserrat", "Montserrat-Variable")]
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
