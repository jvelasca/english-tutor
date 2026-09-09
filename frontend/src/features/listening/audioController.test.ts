/**
 * Tests del AudioController 4.0 (V3.28, Bloque B). Corren en entorno Node, así
 * que la reproducción se simula con un elemento de medios doble (`AudioElementLike`):
 * no hay DOM real, pero el contrato del controller (carga, play/pause, seek,
 * velocidad con preservesPitch, bucle de segmento, replay) es verificable.
 */
import { describe, expect, it, vi } from "vitest";
import {
  AudioController,
  clampSegment,
  nearestVariantForRate,
  supportsPreservesPitch,
  VARIANT_SPEED_FACTORS,
  type AudioElementLike,
} from "./audioController";

/** Elemento de medios de doble (duck-typed) con listeners por evento. */
function fakeElement(
  overrides: Partial<AudioElementLike> = {},
): AudioElementLike & { __listeners: Map<string, () => void> } {
  const listeners = new Map<string, () => void>();
  const el: AudioElementLike & { __listeners: Map<string, () => void> } = {
    src: "",
    currentTime: 0,
    duration: 10,
    playbackRate: 1,
    preservesPitch: true,
    paused: true,
    play: vi.fn(async () => {
      el.paused = false;
    }),
    pause: vi.fn(() => {
      el.paused = true;
    }),
    load: vi.fn(() => {}),
    addEventListener: (type: string, listener: () => void) => {
      listeners.set(type, listener);
    },
    removeEventListener: (type: string) => {
      listeners.delete(type);
    },
    ...overrides,
    __listeners: listeners,
  };
  return el;
}

/** Elemento sin `preservesPitch` (navegador antiguo que no lo expone). */
function legacyElement(
  overrides: Partial<AudioElementLike> = {},
): AudioElementLike & { __listeners: Map<string, () => void> } {
  const el = fakeElement(overrides);
  delete (el as { preservesPitch?: boolean }).preservesPitch;
  return el;
}

function trigger(el: AudioElementLike, type: string) {
  const listeners = (el as AudioElementLike & { __listeners?: Map<string, () => void> })
    .__listeners;
  const handler = listeners?.get(type);
  if (handler) handler();
}

describe("nearestVariantForRate", () => {
  it("elige la variante de la escalera más cercana al rate pedido", () => {
    expect(nearestVariantForRate(1.0)).toBe("normal");
    expect(nearestVariantForRate(1.3)).toBe("fast");
    expect(nearestVariantForRate(0.9)).toBe("normal");
    expect(nearestVariantForRate(0.7)).toBe("slow");
  });

  it("respeta la lista de variantes disponibles", () => {
    expect(nearestVariantForRate(1.2, ["normal", "fast"])).toBe("fast");
    expect(nearestVariantForRate(0.7, ["normal", "fast"])).toBe("normal");
  });

  it("degenera a 'normal' sin variantes o con rate inválido", () => {
    expect(nearestVariantForRate(2, [])).toBe("normal");
    expect(nearestVariantForRate(Number.NaN)).toBe("normal");
  });

  it("existe un factor de velocidad por variante (slow<normal<fast)", () => {
    expect(VARIANT_SPEED_FACTORS.slow).toBeLessThan(VARIANT_SPEED_FACTORS.normal);
    expect(VARIANT_SPEED_FACTORS.normal).toBeLessThan(VARIANT_SPEED_FACTORS.fast);
  });
});

describe("clampSegment", () => {
  it("recorta inicio/fin a la duración del audio", () => {
    expect(clampSegment(0, 5, 10)).toEqual({ start: 0, end: 5 });
    expect(clampSegment(-1, 20, 10)).toEqual({ start: 0, end: 10 });
    expect(clampSegment(3, 3.02, 10)).toBeNull(); // segmento vacío
    expect(clampSegment(0, null, 10)).toBeNull(); // sin fin
    expect(clampSegment(0, 8, 10)).toEqual({ start: 0, end: 8 });
  });
});

describe("supportsPreservesPitch", () => {
  it("detecta el atributo en el elemento", () => {
    expect(supportsPreservesPitch(fakeElement())).toBe(true);
    expect(supportsPreservesPitch(legacyElement())).toBe(false);
  });
});

describe("AudioController", () => {
  it("notifica playing al reproducir y al pausar", async () => {
    const el = fakeElement();
    const onPlayingChange = vi.fn();
    const ctrl = new AudioController(el, { onPlayingChange });
    await ctrl.play("http://audio/1.wav");
    expect(el.src).toBe("http://audio/1.wav");
    trigger(el, "play"); // el navegador emite `play` al comenzar
    expect(onPlayingChange).toHaveBeenLastCalledWith(true);
    ctrl.pause();
    trigger(el, "pause"); // y `pause` al pausar
    expect(onPlayingChange).toHaveBeenLastCalledWith(false);
    ctrl.dispose();
  });

  it("seek recorta el instante a la duración", () => {
    const el = fakeElement({ duration: 10 });
    const ctrl = new AudioController(el);
    ctrl.seek(50);
    expect(el.currentTime).toBe(10);
    ctrl.seek(-3);
    expect(el.currentTime).toBe(0);
    ctrl.dispose();
  });

  it("seek notifica onCurrentTime aunque el audio esté pausado (P2-01)", () => {
    // Pausado: `timeupdate` no se dispara; seek debe notificar el instante
    // para que el estado React (slider/posición) se mantenga consistente.
    const el = fakeElement({ duration: 10, paused: true });
    const onCurrentTime = vi.fn();
    const ctrl = new AudioController(el, { onCurrentTime });
    ctrl.seek(4);
    expect(el.currentTime).toBe(4);
    expect(onCurrentTime).toHaveBeenCalledWith(4);
    // El recorte a duración notifica el instante real (10), no el pedido (50).
    ctrl.seek(50);
    expect(onCurrentTime).toHaveBeenLastCalledWith(10);
    ctrl.dispose();
  });

  it("setRate con preservesPitch usa playbackRate fino", () => {
    const el = fakeElement();
    const ctrl = new AudioController(el);
    const variant = ctrl.setRate(1.5);
    expect(el.playbackRate).toBe(1.5);
    expect(variant).toBeNull(); // la URL actual sigue valiendo
    ctrl.dispose();
  });

  it("setRate sin preservesPitch devuelve la variante y no cambia playbackRate", () => {
    const el = legacyElement();
    const ctrl = new AudioController(el);
    const variant = ctrl.setRate(1.25);
    expect(variant).toBe("fast");
    expect(el.playbackRate).toBe(1);
    ctrl.dispose();
  });

  it("loop fija el segmento y vuelve al inicio al llegar al fin", () => {
    const el = fakeElement({ duration: 10 });
    const ctrl = new AudioController(el);
    el.paused = false;
    ctrl.loop(2, 4);
    expect(ctrl.loopSegment).toEqual({ start: 2, end: 4 });
    el.currentTime = 4;
    trigger(el, "timeupdate");
    expect(el.currentTime).toBe(2); // bucle devuelto al inicio
    ctrl.clearLoop();
    expect(ctrl.loopSegment).toBeNull();
    ctrl.dispose();
  });

  it("replaySegment vuelve al inicio del segmento o del audio", async () => {
    const el = fakeElement({ duration: 10 });
    const ctrl = new AudioController(el);
    el.currentTime = 6;
    ctrl.loop(2, 5);
    await ctrl.replaySegment();
    expect(el.currentTime).toBe(2);
    ctrl.clearLoop();
    el.currentTime = 6;
    await ctrl.replaySegment();
    expect(el.currentTime).toBe(0);
    ctrl.dispose();
  });

  it("load reinicia velocidad y segmento", () => {
    const el = fakeElement({ duration: 10 });
    const ctrl = new AudioController(el);
    ctrl.loop(1, 3);
    ctrl.load("http://audio/2.wav", 1.25);
    expect(el.src).toBe("http://audio/2.wav");
    expect(el.playbackRate).toBe(1.25);
    expect(ctrl.loopSegment).toBeNull();
    ctrl.dispose();
  });

  it("dispose pausa y elimina los listeners", async () => {
    const el = fakeElement();
    const onPlayingChange = vi.fn();
    const ctrl = new AudioController(el, { onPlayingChange });
    await ctrl.play("http://audio/1.wav");
    ctrl.dispose();
    expect(el.pause).toHaveBeenCalled();
    // Tras dispose no hay listeners: un evento no notifica.
    const countBefore = onPlayingChange.mock.calls.length;
    trigger(el, "play");
    expect(onPlayingChange.mock.calls.length).toBe(countBefore);
  });
});
