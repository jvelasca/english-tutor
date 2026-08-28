import { afterEach, describe, expect, it, vi } from "vitest";
import {
  detectAudioCapabilities,
  getMicrophoneStream,
  micErrorReason,
  MicUnavailableError,
} from "./browserCapabilities";

function stubBrowser(overrides: {
  secureContext?: boolean;
  mediaDevices?: unknown;
  mediaRecorder?: boolean;
  audioContext?: boolean;
}) {
  const win = { isSecureContext: overrides.secureContext ?? true };
  vi.stubGlobal("window", win);
  vi.stubGlobal("navigator", { mediaDevices: overrides.mediaDevices });
  if (overrides.mediaRecorder) vi.stubGlobal("MediaRecorder", class {});
  if (overrides.audioContext) vi.stubGlobal("AudioContext", class {});
}

describe("detectAudioCapabilities", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("detecta not_secure_context cuando la conexión no es segura", () => {
    stubBrowser({ secureContext: false });
    const caps = detectAudioCapabilities();
    expect(caps.secureContext).toBe(false);
    expect(caps.supported).toBe(false);
    expect(caps.unavailableReason).toBe("not_secure_context");
  });

  it("detecta no_media_devices cuando mediaDevices es undefined", () => {
    stubBrowser({ mediaDevices: undefined });
    const caps = detectAudioCapabilities();
    expect(caps.supported).toBe(false);
    expect(caps.unavailableReason).toBe("no_media_devices");
  });

  it("detecta no_get_user_media cuando falta getUserMedia", () => {
    stubBrowser({ mediaDevices: {} });
    const caps = detectAudioCapabilities();
    expect(caps.unavailableReason).toBe("no_get_user_media");
  });

  it("detecta no_media_recorder cuando falta MediaRecorder", () => {
    stubBrowser({ mediaDevices: { getUserMedia: () => {} } });
    const caps = detectAudioCapabilities();
    expect(caps.unavailableReason).toBe("no_media_recorder");
  });

  it("marca supported=true con secure context + getUserMedia + MediaRecorder", () => {
    stubBrowser({
      mediaDevices: { getUserMedia: () => {} },
      mediaRecorder: true,
      audioContext: true,
    });
    const caps = detectAudioCapabilities();
    expect(caps.supported).toBe(true);
    expect(caps.unavailableReason).toBeNull();
  });
});

describe("micErrorReason", () => {
  it("clasifica permiso denegado", () => {
    expect(micErrorReason({ name: "NotAllowedError" })).toBe("permission_denied");
    expect(micErrorReason({ name: "PermissionDeniedError" })).toBe(
      "permission_denied",
    );
  });

  it("clasifica ausencia de micrófono", () => {
    expect(micErrorReason({ name: "NotFoundError" })).toBe("no_microphone");
  });

  it("clasifica no soportado", () => {
    expect(micErrorReason({ name: "NotSupportedError" })).toBe("not_supported");
  });

  it("devuelve unknown para errores no reconocidos", () => {
    expect(micErrorReason({ name: "SomethingElse" })).toBe("unknown");
  });
});

describe("getMicrophoneStream", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("lanza MicUnavailableError sin secure context", async () => {
    stubBrowser({ secureContext: false });
    await expect(getMicrophoneStream()).rejects.toBeInstanceOf(
      MicUnavailableError,
    );
    await expect(getMicrophoneStream()).rejects.toMatchObject({
      reason: "not_secure_context",
    });
  });

  it("lanza MicUnavailableError cuando mediaDevices es undefined", async () => {
    stubBrowser({ mediaDevices: undefined });
    await expect(getMicrophoneStream()).rejects.toMatchObject({
      reason: "no_media_devices",
    });
  });

  it("lanza MicUnavailableError cuando getUserMedia es undefined", async () => {
    stubBrowser({ mediaDevices: {} });
    await expect(getMicrophoneStream()).rejects.toMatchObject({
      reason: "no_get_user_media",
    });
  });

  it("mapea permiso denegado a permission_denied", async () => {
    const getUserMedia = vi.fn().mockRejectedValue({ name: "NotAllowedError" });
    stubBrowser({ mediaDevices: { getUserMedia } });
    await expect(getMicrophoneStream()).rejects.toMatchObject({
      reason: "permission_denied",
    });
  });

  it("mapea dispositivo no encontrado a no_microphone", async () => {
    const getUserMedia = vi.fn().mockRejectedValue({ name: "NotFoundError" });
    stubBrowser({ mediaDevices: { getUserMedia } });
    await expect(getMicrophoneStream()).rejects.toMatchObject({
      reason: "no_microphone",
    });
  });

  it("devuelve el stream cuando el micrófono está disponible", async () => {
    const stream = { getTracks: () => [] };
    const getUserMedia = vi.fn().mockResolvedValue(stream);
    stubBrowser({ mediaDevices: { getUserMedia } });
    await expect(getMicrophoneStream()).resolves.toBe(stream);
  });
});
