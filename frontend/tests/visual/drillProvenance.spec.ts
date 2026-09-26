import { expect, test, type Page } from "@playwright/test";

/**
 * V3.69 §F — Contrato de FRONTEND del provenance (red MOCKEADA).
 *
 * El job `playwright` de CI solo levanta el dev server de Vite (no el backend),
 * así que aquí se fija lo que el navegador REAL envía, con `page.route`:
 *
 * 1. el drill devuelve el `decision_id` que le dio la cola en el **GET** del
 *    peldaño (query) y en el **POST** del intento (body);
 * 2. `started` se declara cuando el peldaño **ya está cargado**, no al montar
 *    (la FSM rechaza `computed → started`);
 * 3. `abandoned` se declara al **desmontar** sin haber cerrado la decisión (el
 *    servidor decide si vale: un abandono tardío nunca borra una medición);
 * 4. sin `decision_id` (ítem sin provenance) **no** se declara nada.
 *
 * La verificación real del round-trip contra el backend la hacen E01–E19
 * (`backend/tests/test_adaptive_e2e_v369.py`); esta spec cubre el eslabón del
 * cliente, que era el único tramo sin cobertura de navegador.
 *
 * **HALLAZGO §F-1 (doble montaje de `StrictMode`).** El launcher sirve
 * `npm run dev` (Vite dev ⇒ build de desarrollo), así que React monta, desmonta
 * y vuelve a montar los efectos. El desmontaje del primer montaje declara
 * `abandoned` ANTES de que el peldaño se sirva: `computed → abandoned` es una
 * transición INVÁLIDA y el FSM la rechaza (queda contabilizada como
 * `invalid_transition`, sin tocar la fila). No corrompe el provenance, pero
 * infla un contador de salud en cada montaje de drill. Por eso esta spec NO
 * exige una secuencia exacta de eventos (sería un test frágil y mentiroso):
 * exige que **todos** los eventos viajen con el id servido, que `started` llegue
 * DESPUÉS del GET del peldaño y que el ÚLTIMO evento al salir sea `abandoned`.
 */

const USER = { id: "u1", name: "Test", created_at: "2026-01-01T00:00:00Z" };

/** Consigna del peldaño de recall: la cue es lo que se ve al cargar. */
const PROMPT = {
  word: "river",
  available: true,
  cue: "río",
  cue_kind: "translation",
};

type Call = { method: string; url: string; body: string };

/** Ítem de la cola de repaso (misma forma que sirve `GET /api/learning/review`). */
function reviewItem(decisionId: string | null): Record<string, unknown> {
  return {
    word: "river",
    lexical_unit: "river",
    cefr: "A1",
    kind: "word",
    due_at: "",
    state: "review",
    stability: 1,
    retrievability: 0.4,
    elapsed_days: 9,
    activity: "recall",
    reason: "no_recall_evidence",
    recommended_cue: "translation",
    automatic: false,
    automatic_skills: [],
    priority: 0.5,
    expected_learning_value: 0.5,
    learning_value: null,
    signals: null,
    why: "",
    limiting_skill: "recall",
    skill_priorities: { recall: 0.5 },
    task: {
      skill: "recall",
      activity: "recall",
      reason: "no_recall_evidence",
      support_level: "cued",
    },
    decision: null,
    competence: null,
    evidence: null,
    task_key: "river|recall|cued|lexical:3|recall",
    task_instance_key: "river|recall|cued|lexical:3|recall|",
    served_load: { lexical: 3 },
    assessment_mode: "recall",
    transfer_state: "none",
    // Sin decisión servida (arranque en frío o drill del diccionario) la clave
    // NO viaja: es el caso 4.
    ...(decisionId ? { decision_id: decisionId } : {}),
  };
}

/** Mockea TODO `/api/**` y devuelve el registro de llamadas reales del navegador. */
async function mockApi(
  page: Page,
  options: { decisionId: string | null },
): Promise<Call[]> {
  const calls: Call[] = [];
  // OJO: el matcher debe excluir `/src/api/*.ts` (los MÓDULOS de la app), que un
  // glob `**/api/**` también captura y dejaría la app sin arrancar.
  await page.route(/^https?:\/\/[^/]+\/api\//, (route) => {
    const request = route.request();
    const url = new URL(request.url());
    calls.push({
      method: request.method(),
      url: `${url.pathname}${url.search}`,
      body: request.postData() ?? "",
    });
    const path = url.pathname;
    if (path === "/api/users") return route.fulfill({ json: [USER] });
    // V3.75: la identidad la firma el servidor. Se responde con el MISMO perfil
    // para que `planSession` la adopte; si no, la ProfileGate se abre y el drill
    // no llega a montarse (la suite visual corre sin backend).
    if (path === "/api/session") return route.fulfill({ json: USER });
    if (path === "/api/learning/review") {
      return route.fulfill({
        json: {
          due_count: 1,
          items: [reviewItem(options.decisionId)],
          fsrs_version: "test",
          units: [],
        },
      });
    }
    if (path === "/api/vocabulary/drill/recall") {
      return route.fulfill({ json: PROMPT });
    }
    if (path === "/api/vocabulary/drill/recall-attempt") {
      return route.fulfill({
        json: {
          word: "river",
          correct: true,
          expected: "river",
          delayed: false,
          recall_days: 1,
          error_type: "correct",
        },
      });
    }
    if (path === "/api/vocabulary/drill/decision-lifecycle") {
      return route.fulfill({
        json: {
          applied: true,
          decision_id: options.decisionId ?? "",
          event: "started",
        },
      });
    }
    if (path === "/api/vocabulary/lexicon") {
      // Forma canónica de `Lexicon` (la que itera el diccionario personal).
      return route.fulfill({
        json: {
          summary: {
            total: 0,
            known: 0,
            learning: 0,
            weak: 0,
            mastered: 0,
            by_cefr: [],
          },
          items: [],
        },
      });
    }
    if (path === "/api/vocabulary/drill/candidates") {
      return route.fulfill({ json: { words: [] } });
    }
    if (path === "/api/settings") return route.fulfill({ json: { settings: {} } });
    if (path.startsWith("/api/voices")) return route.fulfill({ json: [] });
    return route.fulfill({ json: {} });
  });
  return calls;
}

function lifecycleCalls(calls: Call[]): Call[] {
  return calls.filter((call) =>
    call.url.startsWith("/api/vocabulary/drill/decision-lifecycle"),
  );
}

function events(calls: Call[]): string[] {
  return lifecycleCalls(calls).map((call) => lifecycleEvent(call));
}

/** `event` del cuerpo de un POST del ciclo de vida ("" si no se puede leer). */
function lifecycleEvent(call: Call): string {
  try {
    return String((JSON.parse(call.body) as { event?: string }).event ?? "");
  } catch {
    return "";
  }
}

/** `decision_id` del cuerpo de un POST del ciclo de vida ("" si no se puede leer). */
function lifecycleDecisionId(call: Call): string {
  try {
    return String(
      (JSON.parse(call.body) as { decision_id?: string }).decision_id ?? "",
    );
  } catch {
    return "";
  }
}

/** Abre el drill desde «Repasar hoy» de Flashcards y devuelve el ámbito de página. */
async function openDrillFromQueue(page: Page): Promise<Page> {
  await page.goto("/#/diccionario");
  // V3.85.0: la cola de repaso dejó de ser una lista de filas con un botón por
  // ítem (que vivía en la pestaña PERSONAL) y pasó a ser una ÚNICA acción
  // («Review now (N)») en la sub-pestaña Estudiar de Flashcards. La spec mide el
  // drill, así que entra por donde ahora vive la acción; el ámbito que devuelve
  // es la página (el drill se localiza por su propio contenido).
  // V3.80.1: los modos del diccionario son pestañas ARIA reales (`role="tab"`).
  await page
    .getByRole("tab", { name: "Flashcards", exact: true })
    .first()
    .click();
  const start = page.getByRole("button", { name: /review now|repasar ahora/i });
  await expect(start).toBeVisible({ timeout: 15_000 });
  await start.click();
  // El peldaño está CARGADO cuando la cue se ve: es el instante declarado en el
  // que el cliente puede declarar `started`.
  await expect(page.getByText("río")).toBeVisible({ timeout: 15_000 });
  return page;
}

test("desktop: el drill devuelve el decision_id y declara started/abandoned", async ({
  page,
}) => {
  test.skip((page.viewportSize()?.width ?? 0) < 1024, "Solo desktop");

  const calls = await mockApi(page, { decisionId: "d-recall" });
  const section = await openDrillFromQueue(page);

  // 1) El GET del peldaño declara el servicio CON el id que dio la cola.
  const recall = calls.find((call) =>
    call.url.startsWith("/api/vocabulary/drill/recall?"),
  );
  expect(recall).toBeDefined();
  expect(recall!.url).toContain("decision_id=d-recall");

  // 2) `started` se declara DESPUÉS de cargar el peldaño (orden exigido por la
  // FSM: `computed → started` sería una transición inválida).
  await expect
    .poll(() => events(calls).includes("started"), { timeout: 10_000 })
    .toBe(true);
  const started = lifecycleCalls(calls).find(
    (call) => lifecycleEvent(call) === "started",
  )!;
  expect(started.method).toBe("POST");
  expect(lifecycleDecisionId(started)).toBe("d-recall");
  expect(JSON.parse(started.body).target_id).toBe("river");
  expect(calls.indexOf(started)).toBeGreaterThan(calls.indexOf(recall!));
  // TODOS los eventos viajan con el id de la decisión servida (incluido el
  // `abandoned` prematuro del doble montaje de StrictMode).
  for (const call of lifecycleCalls(calls)) {
    expect(call.method).toBe("POST");
    expect(lifecycleDecisionId(call)).toBe("d-recall");
  }

  // 3) El intento devuelve el id en el CUERPO del POST.
  await section.getByRole("textbox").first().fill("river");
  await section
    .getByRole("button", { name: /check|comprobar/i })
    .first()
    .click();
  const attempt = calls.find((call) =>
    call.url.startsWith("/api/vocabulary/drill/recall-attempt"),
  );
  expect(attempt).toBeDefined();
  expect(attempt!.method).toBe("POST");
  expect(JSON.parse(attempt!.body).decision_id).toBe("d-recall");

  // 4) Salir del diccionario (navegación SPA) desmonta el drill → el ÚLTIMO
  // evento es el abandono. El cliente lo declara igual: la terminalidad la
  // decide la FSM del servidor (si la decisión ya está medida, lo rechaza).
  await page.evaluate(() => {
    window.location.hash = "#/progreso";
  });
  await expect
    .poll(() => events(calls).at(-1) ?? "", { timeout: 10_000 })
    .toBe("abandoned");
  expect(calls.indexOf(lifecycleCalls(calls).at(-1)!)).toBeGreaterThan(
    calls.indexOf(attempt!),
  );
});

test("desktop: sin decision_id (ítem sin provenance) no se declara nada", async ({
  page,
}) => {
  test.skip((page.viewportSize()?.width ?? 0) < 1024, "Solo desktop");

  const calls = await mockApi(page, { decisionId: null });
  const section = await openDrillFromQueue(page);

  // El peldaño se cargó (la cue se ve — lo garantiza `openDrillFromQueue`) y aun
  // así el GET no declara decisión ni el ciclo de vida emite nada.
  await expect(section.getByText("río")).toBeVisible();
  const recall = calls.find((call) =>
    call.url.startsWith("/api/vocabulary/drill/recall?"),
  );
  expect(recall).toBeDefined();
  expect(recall!.url).not.toContain("decision_id");
  expect(lifecycleCalls(calls)).toEqual([]);

  // Y al desmontar tampoco: sin decisión no hay abandono que declarar.
  await page.evaluate(() => {
    window.location.hash = "#/progreso";
  });
  await expect(page.getByText("río")).toHaveCount(0);
  expect(lifecycleCalls(calls)).toEqual([]);
});
