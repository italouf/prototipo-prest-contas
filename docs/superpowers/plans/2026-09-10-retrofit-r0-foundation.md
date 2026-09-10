# Retrofit Visual QuIIN — R0 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estabelecer a fundação do Design System QuIIN (Tailwind v4 + cotton + HTMX + Alpine), com tokens, fontes, primitivos e página de catálogo `/dev/design-system/`, sem quebrar o back-end nem os testes existentes.

**Architecture:** Build CSS via `django-tailwind-cli` (binário standalone, sem Node); componentes em `templates/components/` com `django-cotton`; fragmentos HTMX com `django-template-partials`; assets JS vendorizados em `static/js/vendor/`; fontes geradas localmente por script e servidas pelo Whitenoise.

**Tech Stack:** Django 5.2.17, Python 3.14, Tailwind CSS v4 (standalone), django-cotton 2.7.2, django-htmx 1.29.0, django-template-partials 25.3, HTMX 2.0.10, Alpine 3.17.2, Chart.js 4.5.1, Playwright 1.62 + @axe-core/playwright.

**Spec:** `docs/superpowers/specs/2026-09-10-retrofit-visual-design.md`

## Global Constraints

- Executar comandos Python via `.venv\Scripts\python.exe` (Windows/PowerShell).
- Não alterar URLs, views e regras de negócio existentes; mudanças de back-end apenas aditivas.
- Nenhum CDN em runtime; nenhum Node em runtime (Node só para testes de QA).
- Source CSS do Tailwind **fora** de `STATICFILES_DIRS` (evita check `django_tailwind_cli.W001`).
- Classes Tailwind sempre literais (nunca concatenar strings dinâmicas).
- Os 8 testes E2E existentes (`tests/e2e/portal.spec.ts`, `dashboard.spec.ts`) devem ficar verdes em todas as tarefas.
- Commits em pt-BR no padrão Conventional Commits usado no repositório.
- Evidências visuais em `docs/retrofit/evidencias/<conjunto>/*.png`.

---

## Estrutura de arquivos (mapa)

| Arquivo | Responsabilidade |
|---|---|
| `requirements.txt` / `requirements-dev.txt` | deps de runtime e dev do front-end |
| `config/settings.py` | apps, middleware e settings de Tailwind/cotton |
| `assets/styles/input.css` | entry do Tailwind (`@import`, `@source`, layers) |
| `assets/styles/theme.css` | tokens `@theme` da marca + dark variant |
| `static/css/fonts.css` | `@font-face` estável (não processado pelo Tailwind) |
| `scripts/convert_fonts.py` | OTF→woff2 (Myriad) e cópia (Panton/JetBrains) |
| `scripts/vendor_assets.ps1` | download pinado de htmx/alpine/chart.js |
| `static/icons/sprite.svg` | sprite de ícones (stroke currentColor) |
| `templates/components/ui/*.html` | primitivos do design system |
| `templates/base.html` | head/tailwind/scripts/dark toggle (shell completa no R1) |
| `templates/dev/design_system.html` | catálogo interno (DEBUG-only) |
| `apps/core/dev_views.py` | view do catálogo |
| `apps/core/tests_frontend.py` | testes Django da stack/componentes |
| `tests/e2e/design_system.spec.ts` | E2E + axe do catálogo |
| `tests/e2e/screenshots.spec.ts` | evidências visuais reutilizáveis |

---

## Task 0: Baseline e evidências "antes"

**Files:**
- Create: `tests/e2e/screenshots.spec.ts`
- Create (gerado): `docs/retrofit/evidencias/antes/*.png`

**Interfaces:**
- Produces: `screenshots.spec.ts` reutilizável com `EVIDENCIA_DIR` (usado nas Tasks 6 e em loops futuros).

- [ ] **Step 1: Criar o spec de captura de evidências**

```ts
// tests/e2e/screenshots.spec.ts
import { test, type Page } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const dir = process.env.EVIDENCIA_DIR ?? 'docs/retrofit/evidencias/atuais';

async function login(page: Page) {
  await page.goto('/accounts/login/');
  await page.getByLabel('Usuário').fill('erica');
  await page.getByLabel('Senha').fill('erica123');
  await page.getByRole('button', { name: /entrar/i }).click();
  await page.waitForURL('**/');
}

test('captura evidencias visuais das paginas principais', async ({ page }) => {
  fs.mkdirSync(dir, { recursive: true });
  await page.setViewportSize({ width: 1440, height: 900 });

  await page.goto('/accounts/login/');
  await page.screenshot({ path: path.join(dir, 'login.png'), fullPage: true });

  await login(page);
  const paginas: Array<[string, string]> = [
    ['dashboard', '/'],
    ['pilar-pdi', '/pilar/1/'],
    ['lancamento', '/lancamentos/2/1/'],
    ['aprovacao', '/aprovacao/2/'],
    ['financeiro-importar', '/financeiro/importar/'],
    ['crm-at-funil', '/crm-at/funil/'],
    ['talentos-organograma', '/talentos/organograma/'],
    ['auditoria', '/auditoria/'],
    ['relatorio-mensal', '/relatorio/mensal/2/'],
  ];
  for (const [nome, url] of paginas) {
    await page.goto(url);
    await page.screenshot({ path: path.join(dir, `${nome}.png`), fullPage: true });
  }
});
```

- [ ] **Step 2: Garantir banco seedado e rodar as suítes existentes**

Run:
```powershell
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py seed_demo
.venv\Scripts\python.exe manage.py test
npx playwright test tests/e2e/portal.spec.ts tests/e2e/dashboard.spec.ts
```
Expected: suíte Django com 0 falhas; 8 E2E verdes.

- [ ] **Step 3: Capturar evidências "antes"**

Run:
```powershell
$env:EVIDENCIA_DIR="docs/retrofit/evidencias/antes"; npx playwright test tests/e2e/screenshots.spec.ts
```
Expected: 10 PNGs em `docs/retrofit/evidencias/antes/`.

- [ ] **Step 4: Commit**

```powershell
git add tests/e2e/screenshots.spec.ts docs/retrofit/evidencias/antes
git commit -m "test(ui): baseline visual e captura de evidencias antes do retrofit"
```

---

## Task 1: Dependências, settings e integração de loaders

**Files:**
- Modify: `requirements.txt`
- Create: `requirements-dev.txt`
- Modify: `config/settings.py`
- Create/Modify: `apps/core/tests_frontend.py`

**Interfaces:**
- Produces: `Template` renderiza `{% partialdef %}`; settings `TAILWIND_CLI_SRC_CSS`, `COTTON_DIR` disponíveis para as tasks seguintes.

- [ ] **Step 1: Escrever o teste que falha**

```python
# apps/core/tests_frontend.py
"""Testes da stack de front-end do retrofit (R0)."""
from django.conf import settings
from django.template import Context, Template
from django.test import SimpleTestCase


class FrontendStackTestes(SimpleTestCase):
    def test_apps_de_frontend_instaladas(self):
        for app in ("django_cotton", "django_tailwind_cli", "django_htmx", "template_partials"):
            self.assertIn(app, settings.INSTALLED_APPS)

    def test_htmx_middleware_instalado(self):
        self.assertIn("django_htmx.middleware.HtmxMiddleware", settings.MIDDLEWARE)

    def test_source_css_fora_dos_arquivos_estaticos(self):
        origem = (settings.BASE_DIR / settings.TAILWIND_CLI_SRC_CSS).resolve()
        for static_dir in settings.STATICFILES_DIRS:
            self.assertFalse(
                origem.is_relative_to(static_dir.resolve()),
                f"{origem} não pode ficar dentro de {static_dir} (check W001)",
            )

    def test_partials_renderizam_com_a_stack_instalada(self):
        html = Template(
            "{% load partials %}"
            "{% partialdef saudacao %}ola{% endpartialdef %}"
            "{% partial saudacao %}"
        ).render(Context())
        self.assertEqual(html, "ola")
```

- [ ] **Step 2: Rodar o teste para ver falhar**

Run: `.venv\Scripts\python.exe manage.py test apps.core.tests_frontend -v 2`
Expected: FAIL/ERROR (settings ausentes).

- [ ] **Step 3: Instalar dependências e atualizar requirements**

Editar `requirements.txt` (entre `Django==5.2.17` e `gunicorn==23.0.0`):
```text
django-cotton==2.7.2
django-htmx==1.29.0
django-tailwind-cli==4.8.0
django-template-partials==25.3
```

Criar `requirements-dev.txt`:
```text
# Ferramentas de desenvolvimento do retrofit visual (não usadas em runtime).
fonttools>=4.59,<5
brotli>=1.1,<2
```

Run:
```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

- [ ] **Step 4: Configurar o Django**

Em `config/settings.py`, em `INSTALLED_APPS`, logo após `"django.contrib.staticfiles",`:
```python
    "django_cotton",
    "django_tailwind_cli",
    "django_htmx",
    "template_partials",
```

Em `MIDDLEWARE`, logo após `"django.contrib.auth.middleware.AuthenticationMiddleware",`:
```python
    "django_htmx.middleware.HtmxMiddleware",
```

No fim do arquivo:
```python
# ---------- Front-end (retrofit visual) ----------
TAILWIND_CLI_VERSION = "latest"  # pinado na Task 3 após o primeiro download
TAILWIND_CLI_SRC_CSS = "assets/styles/input.css"
TAILWIND_CLI_DIST_CSS = "css/tailwind.css"

COTTON_DIR = "components"
COTTON_SNAKE_CASED_NAMES = False
```

- [ ] **Step 5: Validar**

Run:
```powershell
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py test apps.core.tests_frontend -v 2
```
Expected: `check` sem erros; 4 testes PASS.

Se `test_partials_renderizam_com_a_stack_instalada` falhar por conflito de loaders (cotton × template-partials), aplicar o fallback: trocar `"template_partials"` por `"template_partials.apps.SimpleAppConfig"` em `INSTALLED_APPS` e, após o bloco `TEMPLATES` de settings, adicionar:
```python
from template_partials.apps import wrap_loaders  # noqa: E402

wrap_loaders("django")
```
Rodar novamente e registrar no commit qual caminho foi usado.

- [ ] **Step 6: Commit**

```powershell
git add requirements.txt requirements-dev.txt config/settings.py apps/core/tests_frontend.py
git commit -m "build(ui): django-tailwind-cli, cotton, htmx e template-partials"
```

---

## Task 2: Pipeline de fontes e assets vendorizados

**Files:**
- Create: `scripts/convert_fonts.py`
- Create: `scripts/vendor_assets.ps1`
- Create: `static/icons/sprite.svg`
- Modify: `apps/core/tests_frontend.py`

**Interfaces:**
- Produces: `static/fonts/{panton,myriad-pro,jetbrains-mono}/*.woff2`, `static/js/vendor/{htmx.min.js,alpine.min.js,chart.umd.js}`, `static/icons/sprite.svg`.

- [ ] **Step 1: Escrever os testes que falham**

Adicionar em `apps/core/tests_frontend.py`:
```python
class FontesTestes(SimpleTestCase):
    def test_fontes_geradas_para_uso_local(self):
        if not (settings.BASE_DIR / "font").exists():
            self.skipTest("font/ ausente (ambiente sem fontes locais)")
        for rel in (
            "static/fonts/panton/Panton-Regular.woff2",
            "static/fonts/myriad-pro/MyriadPro-Regular.woff2",
            "static/fonts/jetbrains-mono/JetBrainsMono-Regular.woff2",
        ):
            self.assertTrue((settings.BASE_DIR / rel).exists(), f"{rel} não gerado")


class AssetsVendorizadosTestes(SimpleTestCase):
    def test_assets_presentes(self):
        for rel in (
            "static/js/vendor/htmx.min.js",
            "static/js/vendor/alpine.min.js",
            "static/js/vendor/chart.umd.js",
            "static/icons/sprite.svg",
        ):
            caminho = settings.BASE_DIR / rel
            self.assertTrue(caminho.exists(), f"{rel} ausente")
            self.assertGreater(caminho.stat().st_size, 500, f"{rel} vazio")
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python.exe manage.py test apps.core.tests_frontend.FontesTestes apps.core.tests_frontend.AssetsVendorizadosTestes -v 2`
Expected: FAIL (arquivos ausentes).

- [ ] **Step 3: Criar o script de fontes**

```python
# scripts/convert_fonts.py
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
    for pasta, mapa in (("panton", PANTON), ("jetbrains-mono", JETBRAINS)):
        for nome, rel in mapa.items():
            origem = FONT_DIR / rel
            destino = _destino(pasta, nome if pasta == "panton" else f"JetBrainsMono-{nome}")
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
```

Run:
```powershell
.venv\Scripts\python.exe scripts/convert_fonts.py
.venv\Scripts\python.exe scripts/convert_fonts.py --check
```

- [ ] **Step 4: Criar o script de vendorização**

```powershell
# scripts/vendor_assets.ps1
# Baixa assets JS pinados para static/js/vendor/ (executar uma vez; arquivos são commitados).
$ErrorActionPreference = "Stop"
$destino = Join-Path $PSScriptRoot "..\static\js\vendor"
New-Item -ItemType Directory -Force -Path $destino | Out-Null

$assets = @(
  @{ Url = "https://unpkg.com/htmx.org@2.0.10/dist/htmx.min.js"; Arquivo = "htmx.min.js" },
  @{ Url = "https://unpkg.com/alpinejs@3.17.2/dist/cdn.min.js"; Arquivo = "alpine.min.js" },
  @{ Url = "https://unpkg.com/chart.js@4.5.1/dist/chart.umd.js"; Arquivo = "chart.umd.js" }
)

foreach ($asset in $assets) {
  $caminho = Join-Path $destino $asset.Arquivo
  Invoke-WebRequest -Uri $asset.Url -OutFile $caminho
  Write-Output ("{0} ({1:N0} bytes)" -f $asset.Arquivo, (Get-Item $caminho).Length)
}
```

Run: `powershell -ExecutionPolicy Bypass -File scripts/vendor_assets.ps1`

- [ ] **Step 5: Criar o sprite de ícones**

```svg
<!-- static/icons/sprite.svg — traços herdam currentColor do <svg> consumidor -->
<svg xmlns="http://www.w3.org/2000/svg">
  <symbol id="check" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></symbol>
  <symbol id="x" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></symbol>
  <symbol id="alert" viewBox="0 0 24 24"><path d="M12 4l9 16H3z"/><path d="M12 10v5"/><path d="M12 18h.01"/></symbol>
  <symbol id="info" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 8h.01"/></symbol>
  <symbol id="search" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></symbol>
  <symbol id="sun" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></symbol>
  <symbol id="moon" viewBox="0 0 24 24"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></symbol>
  <symbol id="menu" viewBox="0 0 24 24"><path d="M4 6h16M4 12h16M4 18h16"/></symbol>
  <symbol id="chevron-down" viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></symbol>
  <symbol id="chevron-right" viewBox="0 0 24 24"><path d="M9 6l6 6-6 6"/></symbol>
  <symbol id="external" viewBox="0 0 24 24"><path d="M14 4h6v6"/><path d="M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></symbol>
  <symbol id="plus" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></symbol>
  <symbol id="arrow-right" viewBox="0 0 24 24"><path d="M5 12h14"/><path d="M13 6l6 6-6 6"/></symbol>
</svg>
```

- [ ] **Step 6: Rodar os testes**

Run: `.venv\Scripts\python.exe manage.py test apps.core.tests_frontend -v 2`
Expected: 6 testes PASS.

- [ ] **Step 7: Commit**

```powershell
git add scripts/convert_fonts.py scripts/vendor_assets.ps1 static/icons/sprite.svg static/js/vendor apps/core/tests_frontend.py
git commit -m "feat(ui): pipeline de fontes e assets vendorizados do design system"
```

---

## Task 3: Tokens QuIIN e build Tailwind v4

**Files:**
- Create: `assets/styles/theme.css`
- Create: `assets/styles/input.css`
- Create: `static/css/fonts.css`
- Modify: `apps/core/tests_frontend.py`
- Modify: `config/settings.py` (pin da versão)
- Modify: `docs/superpowers/specs/2026-09-10-retrofit-visual-design.md` (fontes em `fonts.css`)

**Interfaces:**
- Consumes: fontes da Task 2.
- Produces: utilidades `bg-quiin-*`, `text-pillar-*`, `font-display`, `font-sans`, `font-mono`, `bg-surface`, `text-text` etc.

- [ ] **Step 1: Escrever o teste que falha**

Adicionar em `apps/core/tests_frontend.py`:
```python
class TailwindBuildTestes(SimpleTestCase):
    def test_css_build_inclui_tokens_quiin(self):
        caminho = settings.BASE_DIR / "static" / "css" / "tailwind.css"
        self.assertTrue(caminho.exists(), "rode manage.py tailwind build")
        conteudo = caminho.read_text(encoding="utf-8").lower()
        self.assertIn("--color-quiin-navy", conteudo)
        self.assertIn("#04047e", conteudo)
        self.assertIn("--font-display", conteudo)
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python.exe manage.py test apps.core.tests_frontend.TailwindBuildTestes -v 2`
Expected: FAIL (tailwind.css ausente).

- [ ] **Step 3: Criar tokens e entry CSS**

```css
/* assets/styles/theme.css — tokens da marca QuIIN (Tailwind v4 CSS-first) */
@theme {
  --color-quiin-navy: #04047e;
  --color-quiin-deep-purple: #1b1641;
  --color-quiin-royal: #0f3b94;
  --color-quiin-blue: #144fad;
  --color-quiin-sky: #1d72b9;
  --color-quiin-quantum-green: #2ebf7d;
  --color-quiin-violet: #3b249c;
  --color-quiin-mist: #dedfe8;

  --color-surface: #f7f8fb;
  --color-surface-2: #ffffff;
  --color-border: #dedfe8;
  --color-text: #1b1641;
  --color-text-muted: #5b5f7a;
  --color-focus: #1d72b9;

  --color-status-rascunho: #64748b;
  --color-status-enviado: #144fad;
  --color-status-aprovado: #1f9d67;
  --color-status-devolvido: #b45309;
  --color-status-pendente: #b45309;
  --color-status-fechado: #1f9d67;
  --color-status-aberto: #0f3b94;
  --color-status-planejado: #64748b;

  --color-pillar-pdi: #3b249c;
  --color-pillar-formacao: #144fad;
  --color-pillar-startups: #1d72b9;
  --color-pillar-at: #0f3b94;
  --color-pillar-infra: #04047e;
  --color-pillar-outrasfontes: #2ebf7d;

  --font-display: "Panton", "Myriad Pro", system-ui, sans-serif;
  --font-sans: "Myriad Pro", system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, "Cascadia Code", monospace;
}

@custom-variant dark (&:where(.dark, .dark *));

@layer base {
  .dark {
    --color-surface: #0f0d22;
    --color-surface-2: #1b1641;
    --color-border: #2e2a52;
    --color-text: #eef0f7;
    --color-text-muted: #a7abc4;
  }
}
```

```css
/* assets/styles/input.css — entry do Tailwind (fora de static/) */
@import "tailwindcss";
@import "./theme.css";

@source "../../templates";
@source "../../apps";

@layer base {
  html { color-scheme: light; }
  html.dark { color-scheme: dark; }
  body {
    background-color: var(--color-surface);
    color: var(--color-text);
    font-family: var(--font-sans);
    -webkit-font-smoothing: antialiased;
  }
  h1, h2, h3, h4 { font-family: var(--font-display); }
  :focus-visible {
    outline: 2px solid var(--color-focus);
    outline-offset: 2px;
    border-radius: 2px;
  }
  ::selection { background: color-mix(in srgb, var(--color-quiin-sky) 30%, transparent); }
  [x-cloak] { display: none !important; }
}

@layer utilities {
  .numerico { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
}

@media print {
  .no-print, .topbar, .footer { display: none !important; }
  body { background: #fff; }
}
```

```css
/* static/css/fonts.css — self-hosted (geradas por scripts/convert_fonts.py) */
@font-face { font-family: "Panton"; src: url("../fonts/panton/Panton-Light.woff2") format("woff2"); font-weight: 300; font-display: swap; }
@font-face { font-family: "Panton"; src: url("../fonts/panton/Panton-Regular.woff2") format("woff2"); font-weight: 400; font-display: swap; }
@font-face { font-family: "Panton"; src: url("../fonts/panton/Panton-SemiBold.woff2") format("woff2"); font-weight: 600; font-display: swap; }
@font-face { font-family: "Panton"; src: url("../fonts/panton/Panton-Bold.woff2") format("woff2"); font-weight: 700; font-display: swap; }
@font-face { font-family: "Panton"; src: url("../fonts/panton/Panton-Black.woff2") format("woff2"); font-weight: 900; font-display: swap; }

@font-face { font-family: "Myriad Pro"; src: url("../fonts/myriad-pro/MyriadPro-Light.woff2") format("woff2"); font-weight: 300; font-display: swap; }
@font-face { font-family: "Myriad Pro"; src: url("../fonts/myriad-pro/MyriadPro-Regular.woff2") format("woff2"); font-weight: 400; font-display: swap; }
@font-face { font-family: "Myriad Pro"; src: url("../fonts/myriad-pro/MyriadPro-SemiBold.woff2") format("woff2"); font-weight: 600; font-display: swap; }
@font-face { font-family: "Myriad Pro"; src: url("../fonts/myriad-pro/MyriadPro-Bold.woff2") format("woff2"); font-weight: 700; font-display: swap; }

@font-face { font-family: "JetBrains Mono"; src: url("../fonts/jetbrains-mono/JetBrainsMono-Regular.woff2") format("woff2"); font-weight: 400; font-display: swap; }
@font-face { font-family: "JetBrains Mono"; src: url("../fonts/jetbrains-mono/JetBrainsMono-Medium.woff2") format("woff2"); font-weight: 500; font-display: swap; }
@font-face { font-family: "JetBrains Mono"; src: url("../fonts/jetbrains-mono/JetBrainsMono-Bold.woff2") format("woff2"); font-weight: 700; font-display: swap; }
```

- [ ] **Step 4: Baixar o CLI e buildar**

Run:
```powershell
.venv\Scripts\python.exe manage.py tailwind setup
.venv\Scripts\python.exe manage.py tailwind build
.venv\Scripts\python.exe manage.py tailwind config
```
Expected: `static/css/tailwind.css` gerado; `config` mostra a versão do CLI/Tailwind.

- [ ] **Step 5: Pinar a versão e revalidar**

Copiar a versão exibida em `tailwind config` e editar `config/settings.py`:
```python
TAILWIND_CLI_VERSION = "4.5.x"  # valor exato retornado por `manage.py tailwind config`
```
Run:
```powershell
.venv\Scripts\python.exe manage.py tailwind build --force
.venv\Scripts\python.exe manage.py test apps.core.tests_frontend -v 2
```
Expected: 7 testes PASS.

- [ ] **Step 6: Ajustar a spec (fontes em arquivo separado)**

Em `docs/superpowers/specs/2026-09-10-retrofit-visual-design.md`, substituir as menções a `@font-face` em `theme.css` por `static/css/fonts.css` (§4.2 e §5.2), mantendo os demais itens.

- [ ] **Step 7: Commit**

```powershell
git add assets static/css/fonts.css static/css/tailwind.css config/settings.py apps/core/tests_frontend.py docs/superpowers/specs/2026-09-10-retrofit-visual-design.md
git commit -m "feat(ui): tokens QuIIN, fontes self-hosted e build Tailwind v4"
```

---

## Task 4: Componentes primitivos (`ui/`) + sprite

**Files:**
- Create: `templates/components/ui/icon.html`
- Create: `templates/components/ui/button.html`
- Create: `templates/components/ui/card.html`
- Create: `templates/components/ui/badge.html`
- Create: `templates/components/ui/input.html`
- Create: `templates/components/ui/select.html`
- Create: `templates/components/ui/table.html`
- Modify: `apps/core/tests_frontend.py`

**Interfaces:**
- Consumes: sprite (Task 2), tokens/utilitários (Task 3).
- Produces: tags `{% c-ui.icon %}`, `<c-ui.button>`, `<c-ui.card>`, `<c-ui.badge>`, `<c-ui.input>`, `<c-ui.select>`, `<c-ui.table>`.

- [ ] **Step 1: Escrever os testes que falham**

Adicionar em `apps/core/tests_frontend.py`:
```python
class ComponentesUITestes(SimpleTestCase):
    def render(self, source, **contexto):
        return Template(source).render(Context(contexto))

    def test_button_primary(self):
        html = self.render('<c-ui.button variant="primary">Salvar</c-ui.button>')
        self.assertIn("bg-quiin-navy", html)
        self.assertIn(">Salvar<", html)

    def test_button_ghost_tamanho_sm(self):
        html = self.render('<c-ui.button variant="ghost" size="sm">Voltar</c-ui.button>')
        self.assertIn("bg-transparent", html)
        self.assertIn("px-3", html)

    def test_button_href_renderiza_link(self):
        html = self.render('<c-ui.button href="/x/">Ir</c-ui.button>')
        self.assertIn('<a href="/x/"', html)

    def test_badge_pilar(self):
        html = self.render('<c-ui.badge pillar="PDI">PDI</c-ui.badge>')
        self.assertIn("text-pillar-pdi", html)

    def test_input_com_erro_tem_aria(self):
        html = self.render('<c-ui.input name="valor" label="Valor" error="Obrigatório" />')
        self.assertIn('aria-invalid="true"', html)
        self.assertIn("Obrigatório", html)

    def test_card_com_slots(self):
        html = self.render('<c-ui.card><c-slot name="header">Topo</c-slot>Corpo</c-ui.card>')
        self.assertIn("Topo", html)
        self.assertIn("Corpo", html)

    def test_table_slots(self):
        html = self.render(
            '<c-ui.table><c-slot name="head"><tr><th>H</th></tr></c-slot>'
            '<c-slot name="body"><tr><td>D</td></tr></c-slot></c-ui.table>'
        )
        self.assertIn("<th>H</th>", html)
        self.assertIn("<td>D</td>", html)

    def test_icon_usa_sprite(self):
        html = self.render('<c-ui.icon name="check" />')
        self.assertIn("icons/sprite.svg#check", html)
        self.assertIn('aria-hidden="true"', html)
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python.exe manage.py test apps.core.tests_frontend.ComponentesUITestes -v 2`
Expected: FAIL (componentes inexistentes).

- [ ] **Step 3: Implementar os componentes**

`templates/components/ui/icon.html`:
```html
<c-vars name size="20" label="" class="" />
{% load static %}
<svg class="inline-block shrink-0 {{ class }}" width="{{ size }}" height="{{ size }}" viewBox="0 0 24 24"
     fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
     {% if label %}role="img" aria-label="{{ label }}"{% else %}aria-hidden="true"{% endif %} {{ attrs }}>
  <use href="{% static 'icons/sprite.svg' %}#{{ name }}"></use>
</svg>
```

`templates/components/ui/button.html`:
```html
<c-vars variant="primary" size="md" type="button" href="" disabled=False loading=False class="" />
{% if href %}
<a href="{{ href }}"
   class="inline-flex items-center justify-center gap-2 rounded-md border font-semibold transition-colors
   {% if variant == 'primary' %}border-quiin-navy bg-quiin-navy text-white hover:bg-quiin-royal{% elif variant == 'secondary' %}border-transparent bg-quiin-blue text-white hover:bg-quiin-sky{% elif variant == 'ghost' %}border-border bg-transparent text-text hover:bg-quiin-mist/40 dark:hover:bg-white/5{% else %}border-transparent bg-red-600 text-white hover:bg-red-700{% endif %}
   {% if size == 'sm' %}px-3 py-1.5 text-sm{% elif size == 'lg' %}px-5 py-3 text-base{% else %}px-4 py-2 text-sm{% endif %}
   {% if disabled or loading %}pointer-events-none opacity-60{% endif %} {{ class }}" {{ attrs }}>
  {% if loading %}<span class="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true"></span>{% endif %}
  {{ icon }}{{ slot }}
</a>
{% else %}
<button type="{{ type }}"
        class="inline-flex items-center justify-center gap-2 rounded-md border font-semibold transition-colors
        {% if variant == 'primary' %}border-quiin-navy bg-quiin-navy text-white hover:bg-quiin-royal{% elif variant == 'secondary' %}border-transparent bg-quiin-blue text-white hover:bg-quiin-sky{% elif variant == 'ghost' %}border-border bg-transparent text-text hover:bg-quiin-mist/40 dark:hover:bg-white/5{% else %}border-transparent bg-red-600 text-white hover:bg-red-700{% endif %}
        {% if size == 'sm' %}px-3 py-1.5 text-sm{% elif size == 'lg' %}px-5 py-3 text-base{% else %}px-4 py-2 text-sm{% endif %}
        {% if disabled or loading %}pointer-events-none opacity-60{% endif %} {{ class }}"
        {% if disabled %}disabled{% endif %} {{ attrs }}>
  {% if loading %}<span class="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true"></span>{% endif %}
  {{ icon }}{{ slot }}
</button>
{% endif %}
```

`templates/components/ui/card.html`:
```html
<c-vars variant="panel" class="" />
<section class="rounded-xl border border-border bg-surface-2 shadow-sm {{ class }}" {{ attrs }}>
  {% if header %}<header class="border-b border-border px-5 py-3 font-display font-semibold">{{ header }}</header>{% endif %}
  <div class="{% if variant == 'action' %}p-4{% else %}p-5{% endif %}">{{ slot }}</div>
  {% if footer %}<footer class="border-t border-border px-5 py-3 text-sm text-text-muted">{{ footer }}</footer>{% endif %}
</section>
```

`templates/components/ui/badge.html`:
```html
<c-vars tone="neutral" pillar="" class="" />
<span class="inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold
{% if pillar == 'PDI' %}border-transparent bg-pillar-pdi/15 text-pillar-pdi
{% elif pillar == 'FORMACAO' %}border-transparent bg-pillar-formacao/15 text-pillar-formacao
{% elif pillar == 'STARTUPS' %}border-transparent bg-pillar-startups/15 text-pillar-startups
{% elif pillar == 'AT' %}border-transparent bg-pillar-at/15 text-pillar-at
{% elif pillar == 'INFRA' %}border-transparent bg-pillar-infra/15 text-pillar-infra
{% elif pillar == 'OUTRASFONTES' %}border-transparent bg-pillar-outrasfontes/15 text-pillar-outrasfontes
{% elif tone == 'success' %}border-transparent bg-quiin-quantum-green/15 text-status-aprovado
{% elif tone == 'warn' %}border-transparent bg-amber-500/15 text-status-pendente
{% elif tone == 'danger' %}border-transparent bg-red-600/10 text-red-700
{% elif tone == 'info' %}border-transparent bg-quiin-royal/10 text-status-aberto
{% else %}border-border bg-quiin-mist/30 text-text-muted{% endif %} {{ class }}" {{ attrs }}>{{ slot }}</span>
```

`templates/components/ui/input.html`:
```html
<c-vars name="" id="" label="" help="" error="" value="" type="text" required=False class="" />
{% with campo_id=id|default:name %}
<div class="{{ class }}">
  {% if label %}<label for="{{ campo_id }}" class="mb-1 block text-sm font-semibold text-text">{{ label }}</label>{% endif %}
  <input id="{{ campo_id }}" name="{{ name }}" type="{{ type }}" value="{{ value }}"
         class="w-full rounded-md border bg-surface-2 px-3 py-2 text-sm text-text placeholder:text-text-muted/70 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus/60 {% if error %}border-red-500{% else %}border-border{% endif %}"
         {% if required %}required{% endif %}
         {% if error %}aria-invalid="true" aria-describedby="{{ campo_id }}-erro"{% elif help %}aria-describedby="{{ campo_id }}-ajuda"{% endif %}
         {{ attrs }}>
  {% if error %}
  <p id="{{ campo_id }}-erro" class="mt-1 text-xs font-medium text-red-600">{{ error }}</p>
  {% elif help %}
  <p id="{{ campo_id }}-ajuda" class="mt-1 text-xs text-text-muted">{{ help }}</p>
  {% endif %}
</div>
{% endwith %}
```

`templates/components/ui/select.html`:
```html
<c-vars name="" id="" label="" help="" error="" required=False class="" />
{% with campo_id=id|default:name %}
<div class="{{ class }}">
  {% if label %}<label for="{{ campo_id }}" class="mb-1 block text-sm font-semibold text-text">{{ label }}</label>{% endif %}
  <select id="{{ campo_id }}" name="{{ name }}"
          class="w-full rounded-md border bg-surface-2 px-3 py-2 text-sm text-text focus:outline-none focus-visible:ring-2 focus-visible:ring-focus/60 {% if error %}border-red-500{% else %}border-border{% endif %}"
          {% if required %}required{% endif %}
          {% if error %}aria-invalid="true" aria-describedby="{{ campo_id }}-erro"{% elif help %}aria-describedby="{{ campo_id }}-ajuda"{% endif %}
          {{ attrs }}>{{ slot }}</select>
  {% if error %}
  <p id="{{ campo_id }}-erro" class="mt-1 text-xs font-medium text-red-600">{{ error }}</p>
  {% elif help %}
  <p id="{{ campo_id }}-ajuda" class="mt-1 text-xs text-text-muted">{{ help }}</p>
  {% endif %}
</div>
{% endwith %}
```

`templates/components/ui/table.html`:
```html
<c-vars caption="" class="" />
<div class="overflow-x-auto rounded-xl border border-border bg-surface-2">
  <table class="w-full border-collapse text-sm {{ class }}" {{ attrs }}>
    {% if caption %}<caption class="px-4 py-3 text-left text-sm text-text-muted">{{ caption }}</caption>{% endif %}
    {% if head %}
    <thead class="bg-quiin-deep-purple text-white [&_th]:px-4 [&_th]:py-2.5 [&_th]:text-left [&_th]:text-xs [&_th]:font-semibold [&_th]:uppercase [&_th]:tracking-wide">{{ head }}</thead>
    {% endif %}
    <tbody class="[&_td]:border-t [&_td]:border-border [&_td]:px-4 [&_td]:py-2.5 [&_td]:align-top">{{ body }}</tbody>
  </table>
</div>
```

- [ ] **Step 4: Rodar os testes**

Run:
```powershell
.venv\Scripts\python.exe manage.py test apps.core.tests_frontend -v 2
.venv\Scripts\python.exe manage.py tailwind build
```
Expected: 15 testes PASS; build sem erros.

- [ ] **Step 5: Commit**

```powershell
git add templates/components apps/core/tests_frontend.py static/css/tailwind.css
git commit -m "feat(ui): primitivos do design system (button, card, badge, input, select, table, icon)"
```

---

## Task 5: `base.html`, dark mode e `/dev/design-system/`

**Files:**
- Modify: `templates/base.html`
- Create: `templates/dev/design_system.html`
- Create: `apps/core/dev_views.py`
- Modify: `config/urls.py`
- Modify: `apps/core/tests_frontend.py`

**Interfaces:**
- Consumes: componentes da Task 4.
- Produces: rota `dev_design_system` (`/dev/design-system/`), `data-testid="dark-toggle"`, `data-testid="page-design-system"` para o E2E da Task 6.

- [ ] **Step 1: Escrever os testes que falham**

Adicionar em `apps/core/tests_frontend.py`:
```python
class DevDesignSystemTestes(TestCase):
    def test_pagina_disponivel_em_debug(self):
        resposta = self.client.get("/dev/design-system/")
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'data-testid="page-design-system"')

    @override_settings(DEBUG=False)
    def test_pagina_indisponivel_fora_de_debug(self):
        resposta = self.client.get("/dev/design-system/")
        self.assertEqual(resposta.status_code, 404)
```
Substituir o bloco de imports do topo do arquivo por:
```python
from django.conf import settings
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase, override_settings
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv\Scripts\python.exe manage.py test apps.core.tests_frontend.DevDesignSystemTestes -v 2`
Expected: FAIL (404 na primeira).

- [ ] **Step 3: Criar view e rota**

`apps/core/dev_views.py`:
```python
"""Páginas internas de desenvolvimento (somente DEBUG)."""
from django.conf import settings
from django.http import Http404
from django.shortcuts import render


def design_system(request):
    if not settings.DEBUG:
        raise Http404("Página disponível apenas em DEBUG.")
    return render(request, "dev/design_system.html")
```

`config/urls.py`, dentro do bloco `if settings.DEBUG:`:
```python
    from apps.core import dev_views

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += [path("dev/design-system/", dev_views.design_system, name="dev_design_system")]
```
(na prática, substituir a linha existente do `urlpatterns += static(...)` por esse bloco)

- [ ] **Step 4: Atualizar `base.html`**

```html
{% load static tailwind_cli %}<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{% block title %}Portal QuIIN{% endblock %}</title>
<link rel="stylesheet" href="{% static 'css/fonts.css' %}">
<link rel="stylesheet" href="{% static 'css/legado.css' %}">
{% tailwind_css %}
<script>
  (function () {
    try {
      var tema = localStorage.getItem('quiin-theme');
      if (tema === 'dark' || (!tema && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.documentElement.classList.add('dark');
      }
    } catch (e) {}
  })();
</script>
</head>
<body hx-headers='{"x-csrftoken": "{{ csrf_token }}"}'>
<a href="#conteudo" class="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-surface-2 focus:px-3 focus:py-2">Pular para o conteúdo</a>
<header class="topbar">
  <div class="topbar-inner">
    <a class="brand" href="{% url 'core:dashboard' %}">
      <span class="brand-mark">Q</span>
      <span class="brand-name">Portal QuIIN</span>
    </a>
    {% if user.is_authenticated %}
    <nav class="nav" aria-label="Navegação principal">
      <a href="{% url 'core:dashboard' %}">Início</a>
      {% if pode_lancar and periodo_aberto_nav and pilares_nav %}
        <a href="{% url 'entries:formulario' periodo_aberto_nav.pk pilares_nav.0.pk %}">Lançamentos</a>
      {% endif %}
      {% if pode_aprovar and periodo_aberto_nav %}
        <a href="{% url 'entries:aprovacao' periodo_aberto_nav.pk %}">Aprovação</a>
      {% endif %}
      {% if pode_importar_financeiro %}
        <a href="{% url 'finance:consolidado' %}">Financeiro</a>
      {% endif %}
      {% if pode_aprovar or pode_lancar %}
        <a href="{% url 'crm_at:funil' %}">Funil AT</a>
      {% endif %}
      {% if pode_aprovar or pode_lancar %}<a href="{% url 'talentos:organograma' %}">Talentos</a>{% endif %}
      {% if ultimo_periodo_nav %}
        <a href="{% url 'reports:mensal' ultimo_periodo_nav.pk %}">Relatório Mensal</a>
      {% endif %}
      {% if pode_ver_auditoria %}
        <a href="{% url 'audit:lista' %}">Auditoria</a>
      {% endif %}
      {% if papel == 'Master' or papel == 'Admin' %}
        <a href="/admin/">Admin</a>
      {% endif %}
    </nav>
    <div class="topbar-user">
      <span class="user-name">{{ user.nome_exibicao }}</span>
      <span class="badge badge-papel">{{ papel }}</span>
      <button type="button" data-testid="dark-toggle" aria-label="Alternar tema"
              class="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border bg-surface-2 text-text"
              x-data="{ escuro: document.documentElement.classList.contains('dark') }"
              @click="escuro = !escuro; document.documentElement.classList.toggle('dark', escuro); localStorage.setItem('quiin-theme', escuro ? 'dark' : 'light')"
              :aria-pressed="escuro">
        <span x-show="!escuro"><c-ui.icon name="sun" size="18" /></span>
        <span x-show="escuro" x-cloak><c-ui.icon name="moon" size="18" /></span>
      </button>
      <form method="post" action="{% url 'accounts:logout' %}">
        {% csrf_token %}
        <button class="btn btn-ghost" type="submit">Sair</button>
      </form>
    </div>
    {% else %}
    <nav class="nav">
      <a href="{% url 'accounts:login' %}">Entrar</a>
    </nav>
    {% endif %}
  </div>
</header>

<main id="conteudo" class="container">
  {% if messages %}
    <div class="messages" role="status">
      {% for message in messages %}
        <div class="alert alert-{{ message.tags|default:'info' }}">{{ message }}</div>
      {% endfor %}
    </div>
  {% endif %}
  {% block content %}{% endblock %}
</main>

<footer class="footer">
  <p>Portal QuIIN — protótipo local de gestão e prestação de contas. Dados fictícios para demonstração.</p>
</footer>
<script src="{% static 'js/vendor/htmx.min.js' %}" defer></script>
<script src="{% static 'js/vendor/alpine.min.js' %}" defer></script>
</body>
</html>
```
Nota: `legado.css` apenas importa `local.css` em `layer(legado)`, mantendo os
templates antigos estilizados enquanto o Tailwind prevalece nos componentes novos.
`local.css`/`legado.css` serão removidos no R6.

- [ ] **Step 5: Criar o catálogo `/dev/design-system/`**

```html
{% extends 'base.html' %}
{% block title %}Design System · Portal QuIIN{% endblock %}
{% block content %}
<div data-testid="page-design-system">
  <h1 class="font-display text-2xl font-bold">Design System QuIIN</h1>
  <p class="mt-1 text-sm text-text-muted">Catálogo interno (somente DEBUG) dos primitivos do retrofit visual.</p>

  <section class="mt-8" aria-labelledby="cores">
    <h2 id="cores" class="font-display text-lg font-semibold">Cores</h2>
    <div class="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
      <div class="rounded-lg border border-border bg-surface-2 p-3"><div class="h-10 rounded bg-quiin-navy"></div><p class="mt-2 text-xs">navy</p></div>
      <div class="rounded-lg border border-border bg-surface-2 p-3"><div class="h-10 rounded bg-quiin-deep-purple"></div><p class="mt-2 text-xs">deep-purple</p></div>
      <div class="rounded-lg border border-border bg-surface-2 p-3"><div class="h-10 rounded bg-quiin-royal"></div><p class="mt-2 text-xs">royal</p></div>
      <div class="rounded-lg border border-border bg-surface-2 p-3"><div class="h-10 rounded bg-quiin-blue"></div><p class="mt-2 text-xs">blue</p></div>
      <div class="rounded-lg border border-border bg-surface-2 p-3"><div class="h-10 rounded bg-quiin-sky"></div><p class="mt-2 text-xs">sky</p></div>
      <div class="rounded-lg border border-border bg-surface-2 p-3"><div class="h-10 rounded bg-quiin-quantum-green"></div><p class="mt-2 text-xs">quantum-green</p></div>
      <div class="rounded-lg border border-border bg-surface-2 p-3"><div class="h-10 rounded bg-quiin-violet"></div><p class="mt-2 text-xs">violet</p></div>
      <div class="rounded-lg border border-border bg-surface-2 p-3"><div class="h-10 rounded bg-quiin-mist"></div><p class="mt-2 text-xs">mist</p></div>
    </div>
  </section>

  <section class="mt-8" aria-labelledby="tipografia">
    <h2 id="tipografia" class="font-display text-lg font-semibold">Tipografia</h2>
    <div class="mt-3 space-y-2 rounded-xl border border-border bg-surface-2 p-5">
      <p class="font-display text-3xl font-bold">Panton — headline executiva</p>
      <p class="text-base">Myriad Pro — corpo de texto e UI.</p>
      <p class="numerico text-sm">R$ 60.000.000,00 · 129 CNPJs · 53,4% (JetBrains Mono)</p>
    </div>
  </section>

  <section class="mt-8" aria-labelledby="botoes">
    <h2 id="botoes" class="font-display text-lg font-semibold">Botões</h2>
    <div class="mt-3 flex flex-wrap items-center gap-3 rounded-xl border border-border bg-surface-2 p-5">
      <c-ui.button variant="primary" data-testid="btn-primary">Primário</c-ui.button>
      <c-ui.button variant="secondary">Secundário</c-ui.button>
      <c-ui.button variant="ghost" data-testid="btn-ghost">Ghost</c-ui.button>
      <c-ui.button variant="danger" size="sm">Perigo sm</c-ui.button>
      <c-ui.button variant="primary" disabled>Desabilitado</c-ui.button>
      <c-ui.button variant="primary" loading>Carregando</c-ui.button>
    </div>
  </section>

  <section class="mt-8" aria-labelledby="badges">
    <h2 id="badges" class="font-display text-lg font-semibold">Badges</h2>
    <div class="mt-3 flex flex-wrap items-center gap-3 rounded-xl border border-border bg-surface-2 p-5">
      <c-ui.badge tone="success" data-testid="badge-aprovado">Aprovado</c-ui.badge>
      <c-ui.badge tone="info">Enviado</c-ui.badge>
      <c-ui.badge>Rascunho</c-ui.badge>
      <c-ui.badge tone="warn">Devolvido</c-ui.badge>
      <c-ui.badge tone="danger">Erro</c-ui.badge>
      <c-ui.badge pillar="PDI">PDI</c-ui.badge>
      <c-ui.badge pillar="FORMACAO">Formação</c-ui.badge>
      <c-ui.badge pillar="STARTUPS">Startups</c-ui.badge>
      <c-ui.badge pillar="AT">AT</c-ui.badge>
      <c-ui.badge pillar="INFRA">Infra</c-ui.badge>
      <c-ui.badge pillar="OUTRASFONTES">Outras Fontes</c-ui.badge>
    </div>
  </section>

  <section class="mt-8" aria-labelledby="cards">
    <h2 id="cards" class="font-display text-lg font-semibold">Cards</h2>
    <div class="mt-3 grid gap-4 md:grid-cols-3">
      <c-ui.card>
        <c-slot name="header">Painel</c-slot>
        Conteúdo de um card de painel padrão.
        <c-slot name="footer">Rodapé opcional</c-slot>
      </c-ui.card>
      <c-ui.card variant="metric">
        <p class="text-xs font-semibold uppercase tracking-wide text-text-muted">Execução acumulada</p>
        <p class="numerico mt-1 text-2xl font-bold">R$ 60 mi</p>
      </c-ui.card>
      <c-ui.card variant="action">
        Ações rápidas com padding reduzido.
      </c-ui.card>
    </div>
  </section>

  <section class="mt-8" aria-labelledby="formularios">
    <h2 id="formularios" class="font-display text-lg font-semibold">Formulários</h2>
    <div class="mt-3 grid gap-4 rounded-xl border border-border bg-surface-2 p-5 md:grid-cols-3">
      <c-ui.input name="demo-nome" label="Nome" help="Texto de ajuda do campo." />
      <c-ui.input name="demo-erro" label="Valor" error="Campo obrigatório." />
      <c-ui.select name="demo-periodo" label="Período">
        <option>2026-06 — Aberto</option>
        <option>2026-05 — Fechado</option>
      </c-ui.select>
    </div>
  </section>

  <section class="mt-8" aria-labelledby="tabela">
    <h2 id="tabela" class="font-display text-lg font-semibold">Tabela</h2>
    <div class="mt-3">
      <c-ui.table caption="Exemplo de tabela com slots head/body">
        <c-slot name="head"><tr><th>Indicador</th><th>Meta</th><th>Realizado</th><th>%</th></tr></c-slot>
        <c-slot name="body">
          <tr><td>CNPJs novos</td><td class="numerico">129</td><td class="numerico">69</td><td class="numerico">53,5%</td></tr>
          <tr><td>Artigos</td><td class="numerico">20</td><td class="numerico">10</td><td class="numerico">50,0%</td></tr>
        </c-slot>
      </c-ui.table>
    </div>
  </section>

  <section class="mt-8 pb-16" aria-labelledby="icones">
    <h2 id="icones" class="font-display text-lg font-semibold">Ícones</h2>
    <div class="mt-3 flex flex-wrap items-center gap-4 rounded-xl border border-border bg-surface-2 p-5 text-text">
      <c-ui.icon name="check" /><c-ui.icon name="x" /><c-ui.icon name="alert" /><c-ui.icon name="info" />
      <c-ui.icon name="search" /><c-ui.icon name="sun" /><c-ui.icon name="moon" /><c-ui.icon name="menu" />
      <c-ui.icon name="chevron-down" /><c-ui.icon name="chevron-right" /><c-ui.icon name="external" />
      <c-ui.icon name="plus" /><c-ui.icon name="arrow-right" />
    </div>
  </section>
</div>
{% endblock %}
```
(remover a linha `{% for icone in ... %}` — placeholder de template **não** é necessário; deixar apenas os `<c-ui.icon>`)

- [ ] **Step 4b: Isolar o CSS legado em cascade layer**

Criar `static/css/legado.css`:
```css
/* CSS legado (pré-retrofit) isolado em layer para o Tailwind prevalecer.
   Remover junto com local.css no R6, quando todas as telas estiverem migradas. */
@import url("local.css") layer(legado);
```

No `base.html`, trocar o link de `css/local.css` por `css/legado.css` (feito no Step 4).

- [ ] **Step 5b: Incluir a página dev nas evidências**

Em `tests/e2e/screenshots.spec.ts`, adicionar à lista `paginas`:
```ts
    ['design-system', '/dev/design-system/'],
```

- [ ] **Step 6: Rodar testes e regressão**

Run:
```powershell
.venv\Scripts\python.exe manage.py test apps.core.tests_frontend -v 2
.venv\Scripts\python.exe manage.py test
.venv\Scripts\python.exe manage.py tailwind build
$env:EVIDENCIA_DIR="docs/retrofit/evidencias/R0-depois"; npx playwright test tests/e2e/screenshots.spec.ts
npx playwright test tests/e2e/portal.spec.ts tests/e2e/dashboard.spec.ts
```
Expected: todos os testes Django e E2E verdes; screenshots "depois" gerados; CSS reconstruído com as classes novas.

- [ ] **Step 7: Commit**

```powershell
git add templates/base.html templates/dev apps/core/dev_views.py apps/core/tests_frontend.py config/urls.py static/css/tailwind.css docs/retrofit/evidencias/R0-depois
git commit -m "feat(ui): shell base com dark mode e catalogo /dev/design-system/"
```

---

## Task 6: E2E do design system (Playwright + axe)

**Files:**
- Modify: `package.json` (+ `package-lock.json`)
- Create: `tests/e2e/design_system.spec.ts`

**Interfaces:**
- Consumes: `data-testid` da Task 5.

- [ ] **Step 1: Escrever o spec que falha**

```ts
// tests/e2e/design_system.spec.ts
import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

test.describe('design system (R0)', () => {
  test('pagina dev renderiza primitivos', async ({ page }) => {
    await page.goto('/dev/design-system/');
    await expect(page.getByTestId('page-design-system')).toBeVisible();
    await expect(page.getByTestId('btn-primary')).toBeVisible();
    await expect(page.getByTestId('btn-ghost')).toBeVisible();
    await expect(page.getByTestId('badge-aprovado')).toBeVisible();
  });

  test('dark mode alterna e persiste', async ({ page }) => {
    await page.goto('/dev/design-system/');
    const html = page.locator('html');
    await expect(html).not.toHaveClass(/dark/);
    await page.getByTestId('dark-toggle').click();
    await expect(html).toHaveClass(/dark/);
    await page.reload();
    await expect(html).toHaveClass(/dark/);
    await page.getByTestId('dark-toggle').click();
    await expect(html).not.toHaveClass(/dark/);
  });

  test('sem violacoes serias de acessibilidade', async ({ page }) => {
    await page.goto('/dev/design-system/');
    const resultado = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
    const graves = resultado.violations.filter((v) => ['critical', 'serious'].includes(v.impact ?? ''));
    expect(graves, JSON.stringify(graves, null, 2)).toEqual([]);
  });
});
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `npx playwright test tests/e2e/design_system.spec.ts`
Expected: FAIL por módulo `@axe-core/playwright` ausente.

- [ ] **Step 3: Adicionar a devDependency** 

Editar `package.json` em `devDependencies`:
```json
    "@axe-core/playwright": "^4.13.0",
```
Run: `npm install`

- [ ] **Step 4: Rodar o E2E completo**

Run: `npx playwright test`
Expected: todos os specs verdes (11 testes).

- [ ] **Step 5: Medir bundles**

Run:
```powershell
function Get-GzipKB($p) {
  $ms = New-Object IO.MemoryStream
  $gz = New-Object IO.Compression.GzipStream($ms, [IO.Compression.CompressionMode]::Compress)
  $b = [IO.File]::ReadAllBytes($p); $gz.Write($b, 0, $b.Length); $gz.Close()
  [math]::Round($ms.Length / 1KB, 1)
}
foreach ($p in @("static/css/tailwind.css","static/js/vendor/htmx.min.js","static/js/vendor/alpine.min.js","static/js/vendor/chart.umd.js")) {
  "{0}: {1} KB gzip" -f $p, (Get-GzipKB $p)
}
```
Anotar os valores para o relatório do R0.

- [ ] **Step 6: Commit**

```powershell
git add package.json package-lock.json tests/e2e/design_system.spec.ts
git commit -m "test(ui): e2e do design system com axe-core"
```

---

## Task 7: Documentação, evidências e verificação final

**Files:**
- Modify: `docs/como-rodar.md`
- Modify: `docs/decisoes.md`
- Modify: `docs/sdd.md`
- Modify: `PRODUCT.md`
- Create: `docs/retrofit/loops.md`
- Modify: `.gitignore`

- [ ] **Step 1: Atualizar `.gitignore`**

```gitignore
.venv/
db.sqlite3
staticfiles/
media/
.env
__pycache__/
*.pyc
node_modules/
test-results/
playwright-report/
# Arquivos excel
*.xlsx
*.xls
*.ods
# Scratch de workspace (briefs, reports e pacotes de review locais)
.superpowers/
# Fontes
font/
static/fonts/panton/
static/fonts/myriad-pro/
# Binário do Tailwind CLI (auto-gerenciado)
.django_tailwind_cli/
```

- [ ] **Step 2: Documentar comandos em `docs/como-rodar.md`**

Adicionar após a seção 8:
```markdown
## 8.1 Front-end (retrofit visual)

```text
pip install -r requirements.txt
pip install -r requirements-dev.txt        # fonttools/brotli (conversão de fontes)
python scripts/convert_fonts.py            # gera static/fonts/*.woff2 a partir de font/
powershell -File scripts/vendor_assets.ps1 # baixa htmx/alpine/chart.js pinados (uma vez)
python manage.py tailwind build            # gera static/css/tailwind.css
python manage.py tailwind watch            # dev: rebuild automático
python manage.py tailwind runserver        # dev: runserver + watcher
```

Catálogo do design system (somente DEBUG): http://127.0.0.1:8000/dev/design-system/
```

- [ ] **Step 3: Registrar decisões em `docs/decisoes.md`**

Adicionar ao fim:
```markdown
## Retrofit visual (R0 — 2026-09-10)

- Stack: Tailwind CSS v4 via `django-tailwind-cli` (binário standalone, sem Node),
  `django-cotton` (componentes), `django-template-partials` (fragmentos HTMX),
  `django-htmx`; HTMX/Alpine/Chart.js vendorizados em `static/js/vendor/`.
- Source CSS em `assets/styles/` (fora de `static/`) para evitar o check W001.
- Fontes: Panton **trial** aceita explicitamente para protótipo local não publicado
  (risco registrado); Myriad Pro licenciada convertida OTF→woff2 por script;
  JetBrains Mono (OFL) commitada. `static/fonts/panton/` e `static/fonts/myriad-pro/`
  ficam fora do git (mesma regra da pasta `font/`).
- Loops do retrofit documentados em `docs/retrofit/loops.md` (R0–R6), sem colidir
  com os LOOP 0–6 do back-end em `docs/loops.md`.
```

- [ ] **Step 4: Atualizar `PRODUCT.md` e `docs/sdd.md`**

Em `PRODUCT.md`, substituir a seção `## Brand Commitments` por:
```markdown
## Brand Commitments

- Identidade visual QuIIN definida: paleta oficial (navy `#04047E`, deep-purple
  `#1B1641`, royal `#0F3B94`, blue `#144FAD`, sky `#1D72B9`, quantum-green
  `#2EBF7D`, violet `#3B249C`, mist `#DEDFE8`).
- Tipografia: Panton (headlines; arquivos trial para uso interno/local),
  Myriad Pro (corpo), JetBrains Mono (dados numéricos).
- `relatorio.html` continua sem valor de referência visual.
```

Em `docs/sdd.md` §9 Premissas, substituir a última premissa por:
```markdown
- Front-end: Tailwind CSS v4 (build via django-tailwind-cli, sem Node em runtime),
  componentes django-cotton, fragmentos django-template-partials, HTMX + Alpine.js
  vendorizados. Retrofit visual em `docs/retrofit/loops.md` (R0–R6).
```

- [ ] **Step 5: Criar `docs/retrofit/loops.md`** com tabela R0–R6 (status R0 = concluído), critérios de aceite, comandos de validação e métricas de bundle medidas na Task 6.

- [ ] **Step 6: Verificação final (evidência antes da afirmação)**

Run:
```powershell
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py tailwind build --force
.venv\Scripts\python.exe manage.py test
npx playwright test
```
Expected: check sem erros; suíte Django verde; 11 E2E verdes.

- [ ] **Step 7: Commit final e pausa**

```powershell
git add .gitignore docs PRODUCT.md
git commit -m "docs(ui): comandos, decisoes e loops do retrofit visual (R0)"
```
Reportar: arquivos, testes, screenshots, métricas de bundle e **aguardar aprovação antes do R1**.

---

## Self-review (cobertura da spec R0)

- Foundation (deps, tokens, tipografia, cores, primitivos, dark mode): Tasks 1–5. ✔
- `/dev/design-system/` renderiza primitivos: Task 5. ✔
- `tailwind build` sem erros: Tasks 3–5. ✔
- E2E `design_system.spec.ts` + axe: Task 6. ✔
- Regressão dos 8 E2E: Tasks 0, 5 e 7. ✔
- Evidências antes/depois e métricas de bundle: Tasks 0, 5 e 6. ✔
- Sem CDN/Node em runtime; source CSS fora de `static/`; URLs intactas: Global Constraints + Tasks 1 e 3. ✔
- Pendência consciente: Lighthouse ≥ 95 fica como verificação opcional no R0 (depende de Chrome local); o gate automatizado é o axe-core (Task 6), como previsto na spec §8/§11.
