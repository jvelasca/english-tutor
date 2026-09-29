// @vitest-environment jsdom
/**
 * Vitest de `DictionaryWarmupAction` (V3.88.0).
 *
 * El bloque arranca el trabajo de fondo del backend y sigue su progreso. Lo que
 * se fija aquí es que la espera sea VISIBLE (spinner → reloj si se alarga) y que
 * el resultado declare la verdad: cuántas quedaron listas y cuántas no. Nada de
 * fingir que el precalentado terminó bien cuando el modelo local no dio cupo.
 */
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../../hooks/useI18n";
import { DictionaryWarmupAction } from "./DictionaryWarmupAction";
import type { DictionaryWarmupJob } from "../../types/api";

const mocks = vi.hoisted(() => ({
  startDictionaryWarmup: vi.fn(),
  getDictionaryWarmupJob: vi.fn(),
}));

vi.mock("../../api/vocabulary", () => ({
  startDictionaryWarmup: mocks.startDictionaryWarmup,
  getDictionaryWarmupJob: mocks.getDictionaryWarmupJob,
}));

function job(overrides: Partial<DictionaryWarmupJob> = {}): DictionaryWarmupJob {
  return {
    id: "j1",
    status: "running",
    total: 3,
    prepared: 0,
    skipped: 0,
    pending: 3,
    error: null,
    ...overrides,
  };
}

function renderAction(userId: string | null = "u1") {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      <DictionaryWarmupAction userId={userId} />
    </I18nProvider>,
  );
}

async function clickStart() {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: "Pre-load now" }));
  });
}

describe("DictionaryWarmupAction", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it("declara la espera mientras el trabajo corre y luego el resultado real", async () => {
    mocks.startDictionaryWarmup.mockResolvedValue(job());
    mocks.getDictionaryWarmupJob
      .mockResolvedValueOnce(job({ prepared: 2, pending: 1 }))
      .mockResolvedValue(
        job({ status: "done", prepared: 3, skipped: 0, pending: 0 }),
      );

    renderAction();
    await clickStart();

    // En curso: región viva con `aria-busy` y la etiqueta del precalentado.
    expect(screen.getByRole("status").getAttribute("aria-busy")).toBe("true");
    expect(screen.getByText("Pre-loading your words…")).toBeTruthy();

    await act(async () => {
      vi.advanceTimersByTime(1500);
    });
    expect(screen.getByText("2 of 3 reviewed")).toBeTruthy();

    await act(async () => {
      vi.advanceTimersByTime(1500);
    });
    expect(screen.getByText(/3 words ready/)).toBeTruthy();
    // Ya no hay trabajo en vuelo: el aviso de espera desaparece.
    expect(screen.queryByText("Pre-loading your words…")).toBeNull();
  });

  it("avisa de que va para largo cuando el trabajo se alarga (reloj)", async () => {
    mocks.startDictionaryWarmup.mockResolvedValue(job());
    // El trabajo sigue corriendo en cada poll: es el caso lento real.
    mocks.getDictionaryWarmupJob.mockResolvedValue(job({ prepared: 1, pending: 2 }));

    renderAction();
    await clickStart();

    await act(async () => {
      vi.advanceTimersByTime(4000);
    });

    expect(screen.getByText(/Still working/)).toBeTruthy();
  });

  it("sin palabras en el léxico lo dice tal cual, sin fingir trabajo", async () => {
    mocks.startDictionaryWarmup.mockResolvedValue(
      job({ status: "done", total: 0, pending: 0 }),
    );

    renderAction();
    await clickStart();

    expect(screen.getByText(/There is nothing to pre-load yet/)).toBeTruthy();
    expect(mocks.getDictionaryWarmupJob).not.toHaveBeenCalled();
  });

  it("un fallo al arrancar se declara y deja reintentar", async () => {
    mocks.startDictionaryWarmup.mockRejectedValue(new Error("down"));

    renderAction();
    await clickStart();

    expect(screen.getByRole("alert").textContent).toContain(
      "Couldn't pre-load your words",
    );
    expect(
      (screen.getByRole("button", { name: "Pre-load now" }) as HTMLButtonElement)
        .disabled,
    ).toBe(false);
  });

  it("sin perfil no ofrece una acción muerta", () => {
    renderAction(null);
    expect(screen.queryByRole("button", { name: "Pre-load now" })).toBeNull();
  });
});
