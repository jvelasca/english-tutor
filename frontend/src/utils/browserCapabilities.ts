/**
 * Detección de capacidades de audio del navegador y secure context.
 *
 * El acceso a `navigator.mediaDevices.getUserMedia` debe estar siempre protegido:
 * en una LAN servida por HTTP plano (`http://192.168.x.x:5173`) el navegador NO
 * considera la conexión un "secure context", por lo que `navigator.mediaDevices`
 * es `undefined` y llamar a `getUserMedia` produce el error:
 * `Cannot read properties of undefined (reading 'getUserMedia')`.
 *
 * Esta capa centraliza la detección, distingue la causa del fallo y expone un
 * único punto de entrada (`getMicrophoneStream`) para toda la app.
 */

export type MicUnavailableReason =
  | "not_secure_context"
  | "no_media_devices"
  | "no_get_user_media"
  | "no_media_recorder"
  | "permission_denied"
  | "no_microphone"
  | "not_supported"
  | "unknown";

export interface AudioCapabilities {
  secureContext: boolean;
  mediaDevices: boolean;
  getUserMedia: boolean;
  mediaRecorder: boolean;
  audioContext: boolean;
  /** True cuando el navegador permite grabar audio en este contexto. */
  supported: boolean;
  /** Causa de indisponibilidad cuando `supported` es false. */
  unavailableReason: MicUnavailableReason | null;
}

export class MicUnavailableError extends Error {
  readonly reason: MicUnavailableReason;

  constructor(reason: MicUnavailableReason) {
    super(`Microphone unavailable: ${reason}`);
    this.name = "MicUnavailableError";
    this.reason = reason;
  }
}

export function detectAudioCapabilities(): AudioCapabilities {
  if (typeof window === "undefined") {
    return {
      secureContext: false,
      mediaDevices: false,
      getUserMedia: false,
      mediaRecorder: false,
      audioContext: false,
      supported: false,
      unavailableReason: "not_supported",
    };
  }

  const secureContext = window.isSecureContext === true;
  const mediaDevices =
    typeof navigator !== "undefined" && !!navigator.mediaDevices;
  const getUserMedia =
    mediaDevices && typeof navigator.mediaDevices?.getUserMedia === "function";
  const mediaRecorder = typeof MediaRecorder !== "undefined";
  const audioContext =
    typeof AudioContext !== "undefined" ||
    typeof (window as unknown as { webkitAudioContext?: unknown })
      .webkitAudioContext !== "undefined";

  let unavailableReason: MicUnavailableReason | null = null;
  if (!secureContext) {
    unavailableReason = "not_secure_context";
  } else if (!mediaDevices) {
    unavailableReason = "no_media_devices";
  } else if (!getUserMedia) {
    unavailableReason = "no_get_user_media";
  } else if (!mediaRecorder) {
    unavailableReason = "no_media_recorder";
  }

  return {
    secureContext,
    mediaDevices,
    getUserMedia,
    mediaRecorder,
    audioContext,
    supported: secureContext && getUserMedia && mediaRecorder,
    unavailableReason,
  };
}

/** Clasifica el error lanzado por `getUserMedia` en una causa legible. */
export function micErrorReason(err: unknown): MicUnavailableReason {
  const e = err as { name?: string; message?: string };
  const name = e?.name ?? "";
  const message = e?.message ?? "";
  const text = `${name} ${message}`.toLowerCase();

  if (
    name === "NotAllowedError" ||
    name === "PermissionDeniedError" ||
    text.includes("permission") ||
    text.includes("denied")
  ) {
    return "permission_denied";
  }
  if (
    name === "NotFoundError" ||
    name === "DevicesNotFoundError" ||
    text.includes("not found") ||
    text.includes("no microphone")
  ) {
    return "no_microphone";
  }
  if (
    name === "NotSupportedError" ||
    name === "OverconstrainedError" ||
    name === "NotReadableError" ||
    name === "TrackStartError"
  ) {
    return "not_supported";
  }
  return "unknown";
}

/**
 * Solicita el micrófono comprobando antes el secure context y las APIs
 * disponibles. Lanza `MicUnavailableError` (con `reason`) en lugar de exponer
 * el `TypeError` crudo de `undefined.getUserMedia`.
 */
export async function getMicrophoneStream(): Promise<MediaStream> {
  const caps = detectAudioCapabilities();
  if (!caps.secureContext) {
    throw new MicUnavailableError("not_secure_context");
  }
  if (!caps.mediaDevices) {
    throw new MicUnavailableError("no_media_devices");
  }
  if (!caps.getUserMedia) {
    throw new MicUnavailableError("no_get_user_media");
  }
  try {
    return await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    throw new MicUnavailableError(micErrorReason(err));
  }
}
