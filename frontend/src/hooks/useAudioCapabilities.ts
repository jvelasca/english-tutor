import { useMemo } from "react";
import {
  detectAudioCapabilities,
  type AudioCapabilities,
} from "../utils/browserCapabilities";

/**
 * Estado de las capacidades de audio del navegador (secure context, micrófono,
 * MediaRecorder, AudioContext). Las capacidades no cambian durante la vida de la
 * página salvo cambio de permiso; se calculan una vez por montaje.
 */
export function useAudioCapabilities(): AudioCapabilities {
  return useMemo(() => detectAudioCapabilities(), []);
}
