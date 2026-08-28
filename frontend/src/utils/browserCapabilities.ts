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

export type MicPermissionState = "granted" | "denied" | "prompt" | "unknown";

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

/**
 * Estado de permiso del micrófono según la Permissions API.
 *
 * Devuelve `"unknown"` cuando la API no está disponible (p. ej. Safari no
 * expone `navigator.permissions.query({ name: "microphone" })`).
 */
export async function queryMicrophonePermission(): Promise<MicPermissionState> {
  if (
    typeof navigator === "undefined" ||
    typeof navigator.permissions === "undefined" ||
    typeof navigator.permissions.query !== "function"
  ) {
    return "unknown";
  }
  try {
    const status = await navigator.permissions.query({
      name: "microphone" as PermissionName,
    });
    return status.state as MicPermissionState;
  } catch {
    return "unknown";
  }
}

/**
 * Observa cambios que pueden hacer que el micrófono pase de no disponible a
 * disponible (o viceversa) sin recargar la página: cambio de permiso, cambio de
 * dispositivo (`devicechange`), volver a la pestaña (`visibilitychange`) o
 * recuperar el foco (`focus`).
 *
 * Devuelve una función de limpieza que elimina todos los listeners. Es el
 * mecanismo que resuelve el caso "permiso denegado → ajustes → conceder →
 * volver", donde un `useMemo(..., [])` mantendría un estado obsoleto.
 */
export function watchMicrophoneAvailability(onChange: () => void): () => void {
  const handleVisibility = () => {
    if (document.visibilityState === "visible") onChange();
  };
  const handleFocus = () => onChange();

  document.addEventListener("visibilitychange", handleVisibility);
  window.addEventListener("focus", handleFocus);

  let removeDeviceChange = () => {};
  if (
    typeof navigator !== "undefined" &&
    navigator.mediaDevices &&
    typeof navigator.mediaDevices.addEventListener === "function"
  ) {
    navigator.mediaDevices.addEventListener("devicechange", onChange);
    removeDeviceChange = () =>
      navigator.mediaDevices.removeEventListener("devicechange", onChange);
  }

  let removePermissionChange = () => {};
  let permissionStatus: PermissionStatus | null = null;
  if (
    typeof navigator !== "undefined" &&
    navigator.permissions &&
    typeof navigator.permissions.query === "function"
  ) {
    void navigator.permissions
      .query({ name: "microphone" as PermissionName })
      .then((status) => {
        permissionStatus = status;
        if (typeof status.addEventListener === "function") {
          status.addEventListener("change", onChange);
          removePermissionChange = () =>
            status.removeEventListener("change", onChange);
        }
      })
      .catch(() => {});
  }

  return () => {
    document.removeEventListener("visibilitychange", handleVisibility);
    window.removeEventListener("focus", handleFocus);
    removeDeviceChange();
    removePermissionChange();
    void permissionStatus;
  };
}
