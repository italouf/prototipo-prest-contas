import path from 'node:path';
import { defineConfig } from '@playwright/test';

/**
 * L0 — Exploração do mockup (fora da suite do portal).
 * Serve mockup/ estaticamente e extrai a matriz dos 10 estados + comportamentos.
 * Evidências: docs/retrofit/evidencias/dashboard-anual/loop-0/
 */
const RAIZ = path.resolve(__dirname, '..', '..');

export default defineConfig({
  testDir: './',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  timeout: 120_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: 'http://127.0.0.1:8099',
  },
  webServer: {
    command: `cmd /d /c "cd /d ${RAIZ} && .venv\\Scripts\\python.exe -m http.server 8099 --directory mockup"`,
    url: 'http://127.0.0.1:8099/gestao_quiin_dashboard_17092026.html',
    reuseExistingServer: true,
    timeout: 30_000,
  },
  projects: [{ name: 'chromium', use: { viewport: { width: 1440, height: 900 } } }],
});
