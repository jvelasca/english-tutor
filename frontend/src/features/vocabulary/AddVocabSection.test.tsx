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

  it("«Mis listas» son filas con recuento y el repaso salta a Flashcards con esa lista", async () => {
    const USER_LIST = {
      id: 3,
      kind: "user_list",
      slug: "",
      title: "My basics",
      title_es: "",
      cefr_hint: "",
      item_count: 4,
      enrolled: true,
      is_global: false,
    };
    vi.mocked(listVocabCollections).mockResolvedValue({
      collections: [USER_LIST],
    } as never);
    const onStudy = vi.fn();

    renderSection(<AddVocabSection userId="u1" onStudy={onStudy} />);

    // Antes: una insignia «My basics (4)» sin ninguna acción.
    expect(await screen.findByText("My basics")).toBeTruthy();
    expect(screen.getByText("4 items")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Review list" }));

    // V3.78.0: aquí ya no se califica ninguna tarjeta. La lista se identifica y
    // el contenedor es quien decide a dónde lleva (la pestaña Flashcards).
    expect(onStudy).toHaveBeenCalledWith({
      collectionId: 3,
      label: "My basics",
    });
  });

  it("un pack ya activo declara el estado y se repasa en Flashcards en vez de reactivarse", async () => {
    vi.mocked(listVocabCollections).mockResolvedValue({
      collections: [{ ...PACK, enrolled: true }],
    } as never);
    const onStudy = vi.fn();

    renderSection(<AddVocabSection userId="u1" onStudy={onStudy} />);

    expect(await screen.findByText("In my dictionary")).toBeTruthy();
    // Reactivar era idempotente (añadía 0): ya no se ofrece como acción.
    expect(screen.queryByText("Activate")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Review" }));

    expect(onStudy).toHaveBeenCalledWith({
      collectionId: 7,
      label: "Travel",
    });
  });

  it("sin contenedor de estudio el repaso no se ofrece (no hay a dónde ir)", async () => {
    // El diccionario incrustado en una ruta de destreza no tiene pestaña
    // Flashcards. Un botón que no lleva a ninguna parte es peor que no tenerlo.
    vi.mocked(listVocabCollections).mockResolvedValue({
      collections: [{ ...PACK, enrolled: true }],
    } as never);

    renderSection(<AddVocabSection userId="u1" />);

    expect(await screen.findByText("In my dictionary")).toBeTruthy();
    const review = screen.getByRole("button", { name: "Review" }) as HTMLButtonElement;
    expect(review.disabled).toBe(true);
  });
});
