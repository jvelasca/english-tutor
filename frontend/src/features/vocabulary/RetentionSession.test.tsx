// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { RetentionSession } from "./RetentionSession";
import { I18nProvider } from "../../hooks/useI18n";

vi.mock("../../api/vocabulary", () => ({
  getRetentionDue: vi.fn(),
  reviewRetentionCard: vi.fn(),
}));

vi.mock("../../components/ItemReplayButton", () => ({
  ItemReplayButton: () => <button type="button">audio</button>,
}));

import {
  getRetentionDue,
  reviewRetentionCard,
} from "../../api/vocabulary";

function renderSession(ui: ReactElement) {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      {ui}
    </I18nProvider>,
  );
}

describe("RetentionSession", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("muestra CTA cuando hay cartas due y grade avanza la cola", async () => {
    vi.mocked(getRetentionDue)
      .mockResolvedValueOnce({
        due_count: 1,
        limit: 15,
        fsrs_version: "test",
        items: [
          {
            word: "airport",
            translation: "aeropuerto",
            definition: "",
            due_at: "",
            stability: 0.1,
            retrievability: 1,
            why: "retention-import",
            reps: 0,
          },
        ],
      })
      .mockResolvedValue({
        due_count: 0,
        limit: 15,
        fsrs_version: "test",
        items: [],
      });
    vi.mocked(reviewRetentionCard).mockResolvedValue({
      word: "airport",
      grade: 3,
      due_at: "",
      next_in_days: 2,
      stability: 1,
      retrievability: 1,
      reps: 1,
    });

    renderSession(<RetentionSession userId="u1" />);

    expect(await screen.findByText(/Start session/i)).toBeTruthy();
    fireEvent.click(screen.getByText(/Start session/i));
    expect(screen.getByText("airport")).toBeTruthy();
    fireEvent.click(screen.getByText(/Show answer/i));
    expect(screen.getByText("aeropuerto")).toBeTruthy();
    fireEvent.click(screen.getByText("Good"));
    await waitFor(() => {
      expect(reviewRetentionCard).toHaveBeenCalledWith("u1", "airport", 3);
    });
  });
});
