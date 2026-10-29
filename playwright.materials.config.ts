import { defineConfig } from '@playwright/test';
import overview from './playwright.overview.config';

process.env.QUIIN_MATERIAL_LIBRARY_E2E = '1';
export default defineConfig({ ...overview, testMatch: 'materials_library.spec.ts' });
