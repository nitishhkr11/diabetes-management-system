import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig, devices } from "@playwright/test";
const venvRel = process.platform === "win32" ? ".venv\\Scripts\\python.exe" : ".venv/bin/python";
const localPy = resolve(process.cwd(), "..", venvRel);
const sharedPy = resolve(process.cwd(), "..", "..", "diabetes-management-system-antigravity", venvRel);
const py = process.env.GLUCOGUIDE_PYTHON || process.env.PYTHON || (existsSync(localPy) ? localPy : existsSync(sharedPy) ? sharedPy : "python");
const distDir = process.env.NEXT_DIST_DIR || ".next";
const port = process.env.E2E_PORT || "3000";
const nextCommand = existsSync(resolve(process.cwd(), `${distDir}/standalone/server.js`))
  ? `node ${distDir}/standalone/server.js`
  : existsSync(resolve(process.cwd(), `${distDir}/BUILD_ID`))
    ? `npm run start -- --port ${port}`
  : "npm run dev -- --hostname 127.0.0.1";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  workers: 1,
  reporter: "list",
  use: { baseURL: process.env.E2E_BASE_URL || `http://127.0.0.1:${port}`, trace: "retain-on-failure", ...devices["Desktop Chrome"] },
  webServer: [
    { command: `"${py}" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`, cwd: "..", url: "http://127.0.0.1:8000/health/live", reuseExistingServer: !process.env.CI, timeout: 120_000 },
    {
      command: nextCommand,
      url: process.env.E2E_BASE_URL || `http://127.0.0.1:${port}`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: { API_BASE_URL: process.env.API_BASE_URL || "http://127.0.0.1:8000", PORT: port, HOSTNAME: "127.0.0.1", NEXT_DIST_DIR: distDir },
    },
  ],
});
