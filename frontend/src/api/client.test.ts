import { afterEach, describe, expect, it, vi } from "vitest";
import { apiUrl } from "./client";

describe("apiUrl", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("mantiene la ruta relativa por defecto (sin VITE_API_BASE_URL)", () => {
    expect(apiUrl("/api/health")).toBe("/api/health");
  });

  it("prefija VITE_API_BASE_URL cuando está definida", () => {
    vi.stubEnv("VITE_API_BASE_URL", "http://127.0.0.1:8000");
    expect(apiUrl("/api/health")).toBe("http://127.0.0.1:8000/api/health");
  });
});
