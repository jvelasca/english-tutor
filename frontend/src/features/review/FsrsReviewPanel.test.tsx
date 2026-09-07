// @vitest-environment jsdom
/**
 * Vitest de `FsrsReviewPanel` (V3.18, M4/D3 — solo verificación de frontend):
 * el servidor ya excluye las cartas `objective` de la cola FSRS (`get_fsrs_due`
 * las siembra solo para continuidad de scheduling y nunca las devuelve al panel
 * autograduable). Aquí se verifica que el panel pinta la cola de skill/lexicon
 * (nunca un tipo `objective`) y que el copy de vacío es honesto cuando no hay
 * cartas pendientes.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { I18nProvider } from "../../hooks/useI18n";
import { FsrsReviewPanel } from "./FsrsReviewPanel";
import type { FsrsDue } from "../../types/api";

function card(targetType: string, targetId: string) {
  return {
    target_type: targetType,
    target_id: targetId,
    label: targetType === "skill" ? "Grammar: present simple" : "Phrase: hold on",
    state: "review",
    difficulty: 0.4,
    stability: 12.0,
    reps: 2,
    lapses: 0,
    due_at: "2026-01-01T00:00:00+00:00",
    last_review_at: "2026-01-01T00:00:00+00:00",
    last_evidence_at: "2026-01-01T00:00:00+00:00",
    last_grade: 3,
    why: "scheduled",
    fsrs_version: "1.0",
    explain: {
      what: {
        target_type: targetType,
        target_id: targetId,
        label: targetType === "skill" ? "Grammar: present simple" : "Phrase: hold on",
      },
      why: "scheduled",
      when: { due_at: "2026-01-01T00:00:00+00:00", due: true, next_in_days: 0.5 },
      how_strong: {
        stability: 12.0,
        retrievability: 0.9,
        difficulty: 0.4,
        state: "review",
        reps: 2,
        lapses: 0,
      },
      last_evidence: { at: "2026-01-01T00:00:00+00:00", grade: 3, grade_label: "Good" },
      next_evidence: { due_at: "2026-01-02T00:00:00+00:00", suggested_interval_days: 1 },
      fsrs_version: "1.0",
    },
  };
}

const QUEUE_SKILL_LEXICON: FsrsDue = {
  due_count: 2,
  cards: [card("skill", "g1"), card("lexicon", "p1")],
  fsrs_version: "1.0",
};

const QUEUE_EMPTY: FsrsDue = {
  due_count: 0,
  cards: [],
  fsrs_version: "1.0",
};

function stubFetch(data: FsrsDue) {
  const fn = vi.fn().mockResolvedValue({ ok: true, json: async () => data });
  vi.stubGlobal("fetch", fn);
  return fn;
}

function renderPanel(ui: ReactElement) {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      {ui}
    </I18nProvider>,
  );
}

describe("FsrsReviewPanel sin cartas objective (V3.18, M4/D3)", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("la cola solo trae skill/lexicon: pinta la primera carta sin ningún objective", async () => {
    stubFetch(QUEUE_SKILL_LEXICON);
    renderPanel(<FsrsReviewPanel userId="u1" />);

    expect(await screen.findByText("Due now: 2")).toBeTruthy();
    // La carta actual es la skill; nunca aparece un tipo objective.
    expect(await screen.findByText(/Grammar: present simple/)).toBeTruthy();
    expect(screen.queryByText(/objective/)).toBeNull();
  });

  it("sin cartas pendientes el copy de vacío es honesto", async () => {
    stubFetch(QUEUE_EMPTY);
    renderPanel(<FsrsReviewPanel userId="u1" />);

    expect(await screen.findByText(/Nothing due right now/)).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });
});
