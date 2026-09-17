# L3 — app-header (evidência)

Data: 2026-09-17 · Commit: `feat(dashboard)` (LOOP 3)

## Entregas
- `app_header` global substitui o `topbar` em todas as páginas: identidade
  "Gestão do QuIIN" (H1 no painel, p nas demais), busca, papel, tema, logout
  preservados; linha 2 (filtros ANO + base + chips + toolbar) só no painel.
- View `/` reescrita: `?ano=todos|2024..2027&base=fin|fis`, aliases
  (financeiro/fisico) ⇒ 302 canônico, inválido ⇒ 302 padrão,
  `?periodo=` legado ⇒ 301 ano equivalente; `HX-Request` ⇒ fragmento
  (`_fragmento`: painel + controles via OOB) com `hx-push-url`.
- Dashboard mensal movido intacto para `/prestacao/mensal/` (view `mensal`,
  template `dashboard/mensal.html`); forms internos re-apontados p/ `core:mensal`.
- Painel L3 provisório (`_panel.html`) com testids finais e valores do DTO.
- `aria-current` (não `aria-pressed`) no segmento ativo — axe exigiu.
- Toolbar L3: Restaurar e Imprimir funcionais; Editar/CSV/download
  desabilitados com `title` (chegam no L7).

## Verificação
- Django: `apps.core` + `apps.planning` + `apps.periods` → 81/81 OK
  (inclui 9 testes novos da view: padrão, deep-link, 302, alias, 301, HX, papéis, login, mensal).
- e2e: 68/68 (62 existentes + 6 novos `dashboard_anual` T01–T03,T06–T08);
  specs antigas re-apontadas (`/prestacao/mensal/`, heading, `app-header`).
- axe em `/` limpo após correção do `aria-current`.
- DoD L3: deep-link ✅, troca de estado c/ URL ✅, chips coerentes ✅, 0 erro console ✅.
- Evidência visual: `header-painel-padrao.png`, `header-painel-2026-fis.png`.
