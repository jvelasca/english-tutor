import { describe, expect, it } from "vitest";
import { MIN_SPEECH_MS, SILENCE_MS, SILENCE_THRESHOLD } from "../../utils/vad";
import {
  INITIAL_TURN_VAD_STATE,
  nextTurnVadState,
  type TurnVadState,
} from "./useVoiceTurn";

/** Energía claramente por encima / por debajo del umbral de voz. */
const LOUD = SILENCE_THRESHOLD + 0.2;
const QUIET = 0;

describe("nextTurnVadState", () => {
  it("no cierra el turno mientras solo hay silencio", () => {
    const quiet = nextTurnVadState(
      { ...INITIAL_TURN_VAD_STATE },
      QUIET,
      1000,
    );
    expect(quiet.end).toBe(false);
    expect(quiet.state.speechDetected).toBe(false);
    expect(quiet.state.silenceStartMs).toBeNull();
  });

  it("cierra el turno tras hablar y superar el silencio mínimo", () => {
    let state: TurnVadState = { ...INITIAL_TURN_VAD_STATE };
    state = nextTurnVadState(state, LOUD, 0).state;
    expect(state.speechDetected).toBe(true);
    expect(state.speechStartMs).toBe(0);

    // Habla sostenida el tiempo mínimo para ser un turno válido.
    state = nextTurnVadState(state, LOUD, MIN_SPEECH_MS + 50).state;
    expect(state.silenceStartMs).toBeNull();

    // Empieza el silencio.
    state = nextTurnVadState(state, QUIET, MIN_SPEECH_MS + 100).state;
    expect(state.silenceStartMs).toBe(MIN_SPEECH_MS + 100);

    // Antes de completar SILENCE_MS aún no cierra.
    const almost = nextTurnVadState(
      state,
      QUIET,
      MIN_SPEECH_MS + 100 + SILENCE_MS - 1,
    );
    expect(almost.end).toBe(false);

    // Al completarlo, cierra.
    const done = nextTurnVadState(
      state,
      QUIET,
      MIN_SPEECH_MS + 100 + SILENCE_MS,
    );
    expect(done.end).toBe(true);
  });

  it("descarta un pico de ruido más corto que MIN_SPEECH_MS", () => {
    let state: TurnVadState = { ...INITIAL_TURN_VAD_STATE };
    state = nextTurnVadState(state, LOUD, 0).state;
    // Solo 100 ms de "voz" y luego silencio largo.
    state = nextTurnVadState(state, QUIET, 100).state;
    const done = nextTurnVadState(state, QUIET, 100 + SILENCE_MS);
    expect(done.end).toBe(false);
    expect(done.state).toEqual(INITIAL_TURN_VAD_STATE);
  });

  it("reinicia la cuenta del silencio si vuelve la voz", () => {
    let state: TurnVadState = { ...INITIAL_TURN_VAD_STATE };
    state = nextTurnVadState(state, LOUD, 0).state;
    state = nextTurnVadState(state, LOUD, MIN_SPEECH_MS + 50).state;
    state = nextTurnVadState(state, QUIET, MIN_SPEECH_MS + 100).state;
    expect(state.silenceStartMs).not.toBeNull();
    // Vuelve a hablar antes de completar el silencio.
    state = nextTurnVadState(state, LOUD, MIN_SPEECH_MS + 300).state;
    expect(state.silenceStartMs).toBeNull();
    expect(state.speechDetected).toBe(true);
  });
});
