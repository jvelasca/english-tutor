import { defineConfig, devices } from "@playwright/test";

/**
 * Tests visuales (smoke) en 3 breakpoints. Captura screenshots reproducibles de
 * las rutas principales de la app para verificar layout y responsive (premisa 20).
 *
 * Se apoya en el dev server de Vite (reutiliza uno ya corriendo si existe). El
 * backend FastAPI en :8000 se asume arrancado; si no lo está, la app se renderiza
 * igual con estados vacíos (el proxy `/api` devolverá 502 pero la UI no se rompe).
 */
export default defineConfig({
  testDir: "./tests/visual",
  outputDir: "./tests/visual/.artifacts",
  timeout: 30_000,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
    },
    {
      name: "tablet",
      use: { ...devices["Desktop Chrome"], viewport: { width: 768, height: 1024 } },
    },
    {
      name: "mobile",
      use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 } },
    },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
