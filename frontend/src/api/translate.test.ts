import { beforeEach, describe, expect, it, vi } from "vitest";

// Se mockea solo el POST HTTP: la caché por frase debe evitar llamadas repetidas
// (los textos de práctica se repiten mucho en repaso/rutas/dictados).
vi.mock("./client", async () => {
  const actual = await vi.importActual<typeof import("./client")>("./client");
  return { ...actual, postJson: vi.fn() };
});

import { postJson } from "./client";
import { clearTranslationCache, translateText } from "./translate";

const postJsonMock = vi.mocked(postJson);

describe("translateText", () => {
  beforeEach(() => {
    clearTranslationCache();
    postJsonMock.mockReset();
    postJsonMock.mockResolvedValue({ translation: "Un banco" });
  });

  it("traduce una frase llamando al backend", async () => {
    await expect(translateText("Where is the bank?")).resolves.toBe("Un banco");
    expect(postJsonMock).toHaveBeenCalledTimes(1);
    expect(postJsonMock).toHaveBeenCalledWith("/api/translate", {
      text: "Where is the bank?",
      direction: "en-es",
    });
  });

  it("envía la dirección ES→EN cuando se pide (Traductor)", async () => {
    await expect(
      translateText("¿Dónde está el banco?", "es-en"),
    ).resolves.toBe("Un banco");
    expect(postJsonMock).toHaveBeenCalledWith("/api/translate", {
      text: "¿Dónde está el banco?",
      direction: "es-en",
    });
  });

  it("la caché es por dirección: la misma frase en ambas direcciones llama dos veces", async () => {
    await translateText("hola", "es-en");
    await translateText("hola", "en-es");
    expect(postJsonMock).toHaveBeenCalledTimes(2);
  });

  it("usa la caché: repetir la misma frase no vuelve a llamar al backend", async () => {
    await translateText("Where is the bank?");
    await translateText("Where is the bank?");
    expect(postJsonMock).toHaveBeenCalledTimes(1);
  });

  it("normaliza espacios en blanco para la caché", async () => {
    await translateText("Nice to meet you.");
    await translateText("  Nice to meet you.  ");
    expect(postJsonMock).toHaveBeenCalledTimes(1);
  });

  it("una frase distinta sí dispara una nueva llamada", async () => {
    await translateText("Where is the bank?");
    await translateText("How old are you?");
    expect(postJsonMock).toHaveBeenCalledTimes(2);
  });

  it("rechaza si el backend devuelve una traducción vacía", async () => {
    postJsonMock.mockResolvedValue({ translation: "   " });
    await expect(translateText("Where is the bank?")).rejects.toThrow();
  });

  it("rechaza si el backend devuelve un error HTTP", async () => {
    postJsonMock.mockRejectedValue(new Error("HTTP 502"));
    await expect(translateText("Where is the bank?")).rejects.toThrow("502");
  });
});
