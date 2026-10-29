import { defineConfig, devices } from '@playwright/test';

process.env.QUIIN_OPERATION_E2E = '1';
export default defineConfig({
  testDir: './tests/e2e', testMatch: 'operation.spec.ts', workers: 1, fullyParallel: false,
  timeout: 60_000, expect: { timeout: 10_000 }, reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:8014', trace: 'retain-on-failure' },
  webServer: {
    command: '".venv/Scripts/python.exe" -B scripts/overview_e2e_server.py',
    url: 'http://127.0.0.1:8014/accounts/login/', reuseExistingServer: false, timeout: 180_000,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
