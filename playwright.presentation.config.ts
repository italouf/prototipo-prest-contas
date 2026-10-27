import { defineConfig } from '@playwright/test';
import * as path from 'node:path';
import base from './playwright.config';

// A dedicated port and SQLite copy keep browser fixtures away from the working database.
const database = path.resolve('.worktrees/presentation-validation.sqlite3').replaceAll('\\', '/');
process.env.DATABASE_URL = `sqlite:///${database}`;
process.env.QUIIN_PRESENTATION_E2E = '1';

export default defineConfig({
  ...base,
  testMatch: /dashboard_r2\.spec\.ts/,
  use: { ...base.use, baseURL: 'http://127.0.0.1:8012' },
  webServer: {
    command: '".venv/Scripts/python.exe" scripts/presentation_e2e_server.py',
    url: 'http://127.0.0.1:8012/accounts/login/',
    reuseExistingServer: false,
    timeout: 90_000,
  },
});
