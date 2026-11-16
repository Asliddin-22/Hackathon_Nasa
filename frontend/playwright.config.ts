import {defineConfig} from '@playwright/test';
import {mkdtempSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

const database = process.env.GRAVITYGUARD_E2E_DATABASE || join(mkdtempSync(join(tmpdir(),'gravityguard-e2e-')),'health.db');
process.env.GRAVITYGUARD_E2E_DATABASE = database;
export default defineConfig({
 testDir:'./e2e',fullyParallel:false,workers:1,timeout:45000,retries:0,
 use:{baseURL:'http://127.0.0.1:5174',headless:true,channel:process.env.PLAYWRIGHT_BROWSER==='chromium'?undefined:'chrome',launchOptions:{args:['--no-sandbox']},screenshot:'only-on-failure',trace:'retain-on-failure'},
 webServer:[
  {command:'../.venv/bin/python -m uvicorn backend.app.main:app --app-dir .. --host 127.0.0.1 --port 8002',env:{DATABASE_URL:`sqlite:///${database}`,DEMO_PASSWORD:'demo-orbit-2026',SEED_DEMO:'true',MODEL_API_KEY:'mock-browser-key',ENABLE_LLM:'false'},url:'http://127.0.0.1:8002/api/health',reuseExistingServer:false},
  {command:'../.venv/bin/python e2e/serve_mock_conversation.py',env:{DATABASE_URL:`sqlite:///${database}.conversation`,DEMO_PASSWORD:'demo-orbit-2026',SEED_DEMO:'true',MODEL_API_KEY:'mock-browser-key',ENABLE_LLM:'true'},url:'http://127.0.0.1:8003/api/health',reuseExistingServer:false},
  {command:'npm run dev -- --port 5174 --strictPort',env:{VITE_BACKEND_URL:'http://127.0.0.1:8002'},url:'http://127.0.0.1:5174',reuseExistingServer:false}
 ]
});
