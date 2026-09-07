// @vitest-environment node
/**
 * Tests de V3.21 (V20-05): resolución del modelo conversacional por defecto.
 *
 * La fuente única es `config.DEFAULT_MODEL` del backend expuesto como
 * `default_model` en `/api/models`. El helper debe preferir ese valor (si está
 * utilizable), caer al primer modelo ofertado, y usar un fallback local solo
 * cuando el backend no responde.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../api/chat", () => ({
  getModels: vi.fn(),
  streamChat: vi.fn(),
}));

import { getModels } from "../api/chat";
import {
  fallbackChatModel,
  resetDefaultModelCache,
  resolveDefaultChatModel,
} from "./models";

const getModelsMock = vi.mocked(getModels);

afterEach(() => {
  resetDefaultModelCache();
  vi.clearAllMocks();
});

describe("resolveDefaultChatModel", () => {
  it("prefiere el default_model del backend si está utilizable", async () => {
    getModelsMock.mockResolvedValue({
      models: ["llama3.1:8b", "qwen2.5-coder:1.5b"],
      default_model: "llama3.1:8b",
    });
    await expect(resolveDefaultChatModel()).resolves.toBe("llama3.1:8b");
  });

  it("cae al primer modelo cuando el default_model no está en la lista", async () => {
    getModelsMock.mockResolvedValue({
      models: ["qwen3:4b", "llama3.1:8b"],
      default_model: "un-modelo-ausente:0",
    });
    await expect(resolveDefaultChatModel()).resolves.toBe("qwen3:4b");
  });

  it("cae al primer modelo cuando el backend no expone default_model", async () => {
    getModelsMock.mockResolvedValue({
      models: ["qwen3:4b", "llama3.1:8b"],
    });
    await expect(resolveDefaultChatModel()).resolves.toBe("qwen3:4b");
  });

  it("usa el fallback local cuando el backend no responde", async () => {
    getModelsMock.mockRejectedValue(new Error("ollama caído"));
    await expect(resolveDefaultChatModel()).resolves.toBe(fallbackChatModel());
  });

  it("cachea la resolución (una sola llamada a /api/models)", async () => {
    getModelsMock.mockResolvedValue({
      models: ["llama3.1:8b", "qwen3:4b"],
      default_model: "qwen3:4b",
    });
    await resolveDefaultChatModel();
    await resolveDefaultChatModel();
    expect(getModelsMock).toHaveBeenCalledTimes(1);
  });
});
