# Como rodar (Windows / Linux / macOS)

## 1. Criar ambiente virtual

```text
python -m venv .venv
```

Windows:

```text
.venv\Scripts\activate
```

Linux/macOS:

```text
source .venv/bin/activate
```

## 2. Instalar dependências

```text
pip install -r requirements.txt
```

(Somente Django; SQLite e a lib `csv` são nativos do Python.)

## 3. Migrar o banco

```text
python manage.py migrate
```

## 4. Rodar o seed de demonstração

```text
python manage.py seed_demo
```

Idempotente — pode rodar quantas vezes quiser.

## 5. Rodar o servidor local

```text
python manage.py runserver
```

Acesse: http://127.0.0.1:8000/

## 6. Usuários demo

| Usuário | Senha | Perfil |
|---|---|---|
| erica | erica123 | Master |
| clarissa | clarissa123 | Admin |
| focal_pdi | focal123 | PontoFocal (PDI) |
| focal_formacao | focal123 | PontoFocal (Formação) |
| focal_startups | focal123 | PontoFocal (Startups) |
| focal_at | focal123 | PontoFocal (AT) |
| lideranca | lider123 | Liderança |
| auditor | auditor123 | Auditor |

## 7. Testes

```text
python manage.py collectstatic --no-input --clear   # manifest do Whitenoise (necessário)
python manage.py test
```

## 8. Roteiro de validação manual

1. Login com cada perfil demo.
2. Master: abrir período 2026-06 (já aberto no seed) e fechar o 2026-05.
3. PontoFocal (focal_pdi): lançar indicadores do PDI e enviar.
4. Master/Admin: aprovar ou devolver em Aprovação.
5. Dashboard geral e por pilar: meta × realizado × percentual.
6. Financeiro: importar `data/seed/financeiro_demo.csv` no período 2026-06.
7. Relatório Mensal: gerar e usar Imprimir → Salvar como PDF.
8. Auditoria: consultar histórico com o usuário auditor.

## 8.1 Front-end (retrofit visual)

```text
pip install -r requirements.txt
pip install -r requirements-dev.txt         # fonttools/brotli (conversão de fontes)
python scripts/convert_fonts.py             # gera static/fonts/*.woff2 a partir de font/
powershell -File scripts/vendor_assets.ps1  # baixa htmx/alpine/chart.js pinados (uma vez)
python manage.py tailwind build             # gera static/css/tailwind.css
python manage.py tailwind watch             # dev: rebuild automático
python manage.py tailwind runserver         # dev: runserver + watcher
```

- `font/` (origem) e derivados licenciados não são versionados; a UI usa apenas
  **Montserrat variável** (OFL) e **JetBrains Mono** (OFL), ambas commitadas em
  `static/fonts/`.
- O script baixa automaticamente a **Montserrat variável** (OFL, google/fonts)
  quando ausente e converte para woff2; JetBrains Mono vem de `font/`.
- Catálogo do design system (somente DEBUG): http://127.0.0.1:8000/dev/design-system/
- Em Windows, se o console falhar com emojis do CLI do Tailwind, use `PYTHONUTF8=1`.

## 9. Testes E2E (Playwright, opcional)

Requer Node.js já presente (o projeto contém `playwright.config.ts`).

```text
npx playwright install chromium
python manage.py migrate && python manage.py seed_demo
python manage.py tailwind build
python manage.py runserver
npx playwright test
```

O servidor Django pode continuar rodando; o Playwright reutiliza a porta 8000.
