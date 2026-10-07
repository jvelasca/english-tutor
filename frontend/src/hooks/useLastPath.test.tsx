// @vitest-environment jsdom
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getSettings } from "../api/settings";
import { writeLastPath } from "../utils/lastPlace";
import { useLastPath } from "./useLastPath";

vi.mock("../api/settings", () => ({
  getSettings: vi.fn().mockResolvedValue({ settings: {} }),
  saveSettings: vi.fn().mockResolvedValue({ settings: {} }),
}));

describe("useLastPath", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.location.hash = "#/";
    vi.mocked(getSettings).mockResolvedValue({ settings: {} });
  });

  it("al abrir la raíz vuelve a la última ruta de ese usuario", () => {
    writeLastPath("u1", "/diccionario");
    renderHook(() => useLastPath("u1", "/", false));
    expect(window.location.hash).toBe("#/diccionario");
  });

  it("un enlace que ya trae camino no se sustituye", () => {
    window.location.hash = "#/aprender/listening";
    writeLastPath("u1", "/diccionario");
    renderHook(() => useLastPath("u1", "/aprender/listening", false));
    expect(window.location.hash).toBe("#/aprender/listening");
  });

  it("si no hay copia local, manda la ruta guardada en el perfil", async () => {
    vi.mocked(getSettings).mockResolvedValue({ settings: { last_path: "/traductor" } });
    renderHook(() => useLastPath("u1", "/", false));
    await waitFor(() => expect(window.location.hash).toBe("#/traductor"));
  });
});
