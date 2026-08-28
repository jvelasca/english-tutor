import { useCallback, useEffect, useState } from "react";
import {
  detectAudioCapabilities,
  queryMicrophonePermission,
  watchMicrophoneAvailability,
  type AudioCapabilities,
  type MicPermissionState,
} from "../utils/browserCapabilities";

export interface AudioCapabilitiesState {
  capabilities: AudioCapabilities;
  permission: MicPermissionState;
  refresh: () => void;
}

/**
 * Estado reactivo de las capacidades de audio del navegador (secure context,
 * micrófono, MediaRecorder, AudioContext) y del permiso del micrófono.
 *
 * A diferencia de un `useMemo(..., [])`, se vuelve a detectar cuando el permiso
 * o el dispositivo cambian (denegado → ajustes → conceder → volver), al
 * recuperar el foco/visibilidad, o de forma manual con `refresh`.
 */
export function useAudioCapabilities(): AudioCapabilitiesState {
  const [capabilities, setCapabilities] = useState<AudioCapabilities>(() =>
    detectAudioCapabilities(),
  );
  const [permission, setPermission] = useState<MicPermissionState>("unknown");

  const refresh = useCallback(() => {
    setCapabilities(detectAudioCapabilities());
    void queryMicrophonePermission().then(setPermission);
  }, []);

  useEffect(() => {
    refresh();
    return watchMicrophoneAvailability(refresh);
  }, [refresh]);

  return { capabilities, permission, refresh };
}
