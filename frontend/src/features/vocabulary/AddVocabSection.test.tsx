// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { AddVocabSection } from "./AddVocabSection";
import { I18nProvider } from "../../hooks/useI18n";

vi.mock("../../api/vocabulary", () => ({
  listVocabCollections: vi.fn(),
  addVocabularyItem: vi.fn(),
  addVocabularyBulk: vi.fn(),
  enrollVocabCollection: vi.fn(),
}));

import {
  addVocabularyItem,
  enrollVocabCollection,
  listVocabCollections,
} from "../../api/vocabulary";

function renderSection(ui: ReactElement) {
  return render(
    <I18nProvider lang="en" setLang={() => {}}>
      {ui}
    </I18nProvider>,
  );
}

/** Pack temático mínimo, con la forma que sirve `GET /api/vocabulary/collections`. */
const PACK = {
  id: 7,
  title: "Travel",
  title_es: "Viaje",
  kind: "theme_pack",
  cefr_hint: "A1-A2",
  item_count: 12,
  enrolled: false,
  created_at: "",
};

describe("AddVocabSection", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("una respuesta sin `collections` no tumba la sección", async () => {
    // El fallo que se está fijando: `setPacks(data.collections)` dejaba el estado
    // en `undefined` y el `packs.filter` de la lista de temas lanzaba al PINTAR.
    // Un fallo al pintar no rompe «la lista de packs»: rompe la pantalla entera
    // del diccionario, y con ella todo lo que el alumno tenía delante. Lo encontró
    // la suite visual (que mockea `/api/**` con respuestas vacías) y no un test
    // unitario, porque ninguna unidad se había pedido esto.
    vi.mocked(listVocabCollections).mockResolvedValue({} as never);

    renderSection(<AddVocabSection userId="u1" />);

    // Lo que importa: la sección sigue en pie y ofrece sus tres caminos.
    expect(await screen.findByText("Single word")).toBeTruthy();
    expect(screen.getByText("Paste a list")).toBeTruthy();
    expect(screen.getByText("Theme packs")).toBeTruthy();
  });

  it("con packs servidos pinta el tema y activarlo manda la inscripción", async () => {
    vi.mocked(listVocabCollections).mockResolvedValue({
      collections: [PACK],
    } as never);
    vi.mocked(enrollVocabCollection).mockResolvedValue({
      collection_id: 7,
      count: 12,
    } as never);

    renderSection(<AddVocabSection userId="u1" />);

    expect(await screen.findByText("Travel")).toBeTruthy();
    expect(screen.getByText(/12/)).toBeTruthy();
    fireEvent.click(screen.getByText("Activate"));
    await waitFor(() => {
      expect(enrollVocabCollection).toHaveBeenCalledWith("u1", 7);
    });
  });

  it("añadir una palabra avisa con la forma servida y no inventa el nombre", async () => {
    vi.mocked(listVocabCollections).mockResolvedValue({ collections: [] } as never);
    // Respuesta sin `added` (contrato incompleto): el aviso cae al término tecleado
    // en vez de reventar al leer `out.added[0]`.
    vi.mocked(addVocabularyItem).mockResolvedValue({} as never);

    renderSection(<AddVocabSection userId="u1" />);
    await screen.findByText("Single word");

    fireEvent.change(screen.getByPlaceholderText("English word"), {
      target: { value: "river" },
    });
    fireEvent.click(screen.getByText("Add"));

    expect(
      await screen.findByText(/Added “river” to your personal dictionary\./),
    ).toBeTruthy();
  });
});
