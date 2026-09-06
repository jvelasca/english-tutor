import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      // Mismo alias `@` → `src` que `vite.config.ts` (los componentes de UI y
      // los tests de componente lo usan).
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "node",
    // Los tests de componente (DOM/jsdom) se marcan por archivo con
    // `// @vitest-environment jsdom` (ver *.test.tsx de features/review y
    // components). El resto de la suite sigue en entorno node.
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
