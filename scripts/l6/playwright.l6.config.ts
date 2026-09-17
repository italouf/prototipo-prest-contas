import path from 'node:path';
import { defineConfig } from '@playwright/test';

/** L4 â€” EvidÃªncia visual da navegaÃ§Ã£o (Django local). */
const RAIZ = path.resolve(__dirname, '..', '..');

export default defineConfig({
  testDir: './',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  timeout: 60_000,
  use: { baseURL: 'http://127.0.0.1:8000' },
  webServer: {
    command: `cmd /d /c "cd /d ${RAIZ} && .venv\\Scripts\\python.exe manage.py runserver 127.0.0.1:8000 --noreload"`,
    url: 'http://127.0.0.1:8000/accounts/login/',
    reuseExistingServer: true,
    timeout: 60_000,
  },
  projects: [{ name: 'chromium', use: { viewport: { width: 1440, height: 900 } } }],
});


