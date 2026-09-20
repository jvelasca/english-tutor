/**
 * LISTENING · repetición con STOP y lectura corta (V3.75.5/V3.75.6).
 *
 * Fija el contrato de UI de tres cosas que se pidieron con la app en uso y que
 * ninguna suite cubría en pantalla real:
 *
 * 1. **Una ruta con contenido de opción múltiple no muestra tarjeta de dictado.**
 *    Los ítems `c071`/`c084` estaban etiquetados `dictation`/`shadowing` aunque
 *    eran preguntas con opciones, y la RUTA B1 acababa mostrando «Send dictation».
 *    Aquí se navega a la ruta con un ítem B1 servido por mock y se comprueba que
 *    las opciones están y la tarjeta de producción **no**. Que el backend sirva
 *    de verdad una pregunta receptiva para B1 lo fija `test_listening_corpus.py`
 *    (`test_corpus_production_items_do_not_carry_multiple_choice_options`): aquí
 *    se mide la UI, no el banco.
 * 2. **El «...» permite elegir qué se lee al repetir** (`replay_scope`): el ítem
 *    completo (defecto), el ítem más las opciones o solo la pregunta con la
 *    respuesta correcta; y la elección se persiste.
 * 3. **Tras responder, el altavoz ofrece A/B y —mientras suena— un STOP** que
 *    corta la lectura larga; el STOP desaparece cuando ya no hay nada que parar.
 * 4. **Ningún desplegable tapa su propio texto** (V3.75.7) y el icono promete lo
 *    que hay dentro: **(i)** cuando el panel solo explica (`#listening-route-notes`),
 *    **(...)** cuando además trae opciones (`#listening-audio-settings`, con las
 *    voces y la lectura al repetir). El botón de la esquina flota sobre la tarjeta
 *    y el panel nace justo debajo, así que antes su primera línea salía tapada.
 *    Aquí se mide la geometría real: ni un nodo de texto del panel puede solaparse
 *    con el botón, en los tres breakpoints.
 *
 * El TTS se deja **pendiente a propósito** (nunca responde): es la forma
 * determinista de observar el estado «sonando», y de paso deja constancia del
 * texto exacto que el alumno habría oído.
 */
import { expect, test, type Locator } from "@playwright/test";

import { ensureProfile } from "./gateHelper";

function lv(level: string, mastered: number, total: number) {
  return {
    level,
    mastered,
    total,
    base_total: total,
    extras: 0,
    completed: mastered >= total,
    state: "functional",
    retention: null,
    gate: null,
  };
}

/** Ítem B1 con pregunta y opciones: lo que el backend sirve ahora para c071. */
const B1_QUESTION = {
  id: "c071",
  level: "B1",
  skill: "numbers",
  difficulty: 3,
  difficulty_vector: { speed: 3 },
  script: "I'll pick you up at a quarter past eight.",
  question: "Which time did you hear?",
  options: ["8:45", "7:45", "9:15", "8:15"],
  audio_id: "",
  duration: 5,
  speaker_id: "speaker_001",
  accent: "British RP",
  speech_rate: 143,
  transcript: "I'll pick you up at a quarter past eight.",
  clean_transcript: "I'll pick you up at a quarter past eight.",
  noise_level: 0,
  repetition_policy: "twice",
  topic: "daily_routine",
  context: "message",
  audio_ready: false,
  audio_type: "tts",
  realized_difficulty: 3,
  realization: {},
  variants: [],
  default_variant: "normal",
};

async function installMocks(page: import("@playwright/test").Page) {
  await page.route("**/api/listening/stats*", (route) =>
    route.fulfill({
      json: {
        attempts: 210,
        correct: 155,
        accuracy: 74,
        level: "B1",
        completed: false,
        levels: [
          lv("A1", 200, 200),
          lv("A2", 200, 200),
          lv("B1", 3, 25),
          lv("B2", 0, 25),
          lv("C1", 0, 20),
          lv("C2", 0, 20),
        ],
      },
    }),
  );  await page.route("**/api/listening/items*", (route) =>
    route.fulfill({ json: { level: "B1", items: [] } }),
  );
  await page.route("**/api/listening/question*", (route) =>
    route.fulfill({ json: B1_QUESTION }),
  );
  await page.route("**/api/listening/answer*", (route) =>
    route.fulfill({
      json: {
        question_id: "c071",
        correct: true,
        correct_index: 3,
        level: "B1",
        skill: "numbers",
        difficulty: 3,
        realized_difficulty: 3,
      },
    }),
  );
  await page.route("**/api/listening/diagnostic*", (route) =>
    route.fulfill({
      json: {
        subskills: [],
        weak: [],
        recommendation: "",
        first_pass_accuracy: null,
        automaticity: null,
        by_difficulty: [],
        by_topic: [],
        trend: {
          recent_accuracy: null,
          prior_accuracy: null,
          delta: null,
          direction: "n/a",
        },
        recurrence: {
          questions_seen: 0,
          retried: 0,
          recovered: 0,
          retry_rate: null,
          recovery_rate: null,
        },
        retention: {
          total_questions: 0,
          immediate_accuracy: null,
          delayed_accuracy: null,
          retention_rate: null,
          by_bucket: [],
        },
        bank_version: "7.0.0",
        realization: { attempts: 0, verified: 0, gap: 0 },
        resilience: { dimensions: [], main_weakness: null, recommendation: "" },
      },
    }),
  );
  // Dos voces instaladas: es lo que hace aparecer A y B.
  await page.route("**/api/voices*", (route) =>
    route.fulfill({
      json: {
        voices: [
          { id: "en_US-lessac-medium", name: "American English · Lessac" },
          { id: "en_GB-alan-medium", name: "British English · Alan" },
        ],
        downloadable: [],
        default: "en_US-lessac-medium",
        selected: "en_US-lessac-medium",
        defaults: { en: "en_US-lessac-medium" },
      },
    }),
  );
  await page.route("**/api/settings*", (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({ json: { settings: {} } });
    }
    return route.fulfill({ json: { settings: {} } });
  });
}

/** Clases del `<svg>` del disparador (lucide marca cada icono con la suya). */
async function iconClasses(trigger: Locator): Promise<string> {
  return (await trigger.locator("svg").first().getAttribute("class")) ?? "";
}

/**
 * Trozos de texto **dentro** del panel que caen bajo el botón.
 *
 * El panel puede apoyarse en la esquina del botón —eso es diseño—, pero ni una
 * letra: cualquier nodo con caja que intersecte el rectángulo del disparador se
 * devuelve aquí, y el test exige lista vacía. Se miden ambos rects en el mismo
 * estado de scroll para que las coordenadas sean comparables.
 */
async function textUnderTrigger(
  trigger: Locator,
  panel: Locator,
): Promise<string[]> {
  const box = await trigger.boundingBox();
  if (!box) throw new Error("el disparador no tiene caja");
  const covered: string[] = [];
  const nodes = panel.locator("p, span, li, label, button, input, h2, h3, h4");
  const total = await nodes.count();
  for (let i = 0; i < total; i += 1) {
    const node = nodes.nth(i);
    const rect = await node.boundingBox();
    if (!rect) continue;
    const overlaps =
      rect.x < box.x + box.width &&
      box.x < rect.x + rect.width &&
      rect.y < box.y + box.height &&
      box.y < rect.y + rect.height;
    if (overlaps) {
      const tag = await node.evaluate((el) => el.tagName.toLowerCase());
      const text = (await node.innerText()).replace(/\s+/g, " ").slice(0, 40);
      covered.push(`${tag}|${text}`);
    }
  }
  return covered;
}

test("desplegables: el icono promete lo que hay dentro y el panel no se tapa a sí mismo", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  await ensureProfile(page);
  await installMocks(page);
  await page.goto("/#/aprender/listening");

  await expect(page.getByText("Mastered 3 of 25").first()).toBeVisible({
    timeout: 15_000,
  });
  await page
    .getByRole("button", { name: "Level B1 history" })
    .last()
    .click();

  // --- (i): el panel de notas de la ruta solo explica, no configura nada. -----
  const notesTrigger = page.locator(
    'button[aria-controls="listening-route-notes"]',
  );
  await expect(notesTrigger).toBeVisible({ timeout: 15_000 });
  expect(await iconClasses(notesTrigger)).toContain("lucide-info");

  await notesTrigger.click();
  const notesPanel = page.locator("#listening-route-notes");
  await expect(notesPanel).toBeVisible();
  await notesPanel.scrollIntoViewIfNeeded();

  const coveredNotes = await textUnderTrigger(notesTrigger, notesPanel);
  await page.screenshot({
    path: `tests/visual/screenshots/${testInfo.project.name}/listening-disclosure-info.png`,
  });

  // --- (...): el «...» de la tarjeta de audio sí trae opciones. ---------------
  const audioTrigger = page.locator(
    'button[aria-controls="listening-audio-settings"]',
  );
  await expect(audioTrigger).toBeVisible();
  expect(await iconClasses(audioTrigger)).toMatch(/ellipsis|more-horizontal/);

  await audioTrigger.click();
  const audioPanel = page.locator("#listening-audio-settings");
  await expect(audioPanel).toBeVisible();
  // «Opciones» de verdad: las composiciones de la lectura al repetir.
  await expect(
    audioPanel.getByRole("radiogroup", { name: "When repeating, read" }),
  ).toBeVisible({ timeout: 15_000 });
  await audioPanel.scrollIntoViewIfNeeded();

  const coveredAudio = await textUnderTrigger(audioTrigger, audioPanel);
  await page.screenshot({
    path: `tests/visual/screenshots/${testInfo.project.name}/listening-disclosure-options.png`,
  });

  // eslint-disable-next-line no-console
  console.log(
    `[${testInfo.project.name}] ` +
      JSON.stringify({ coveredNotes, coveredAudio }, null, 0),
  );
  expect(coveredNotes).toEqual([]);
  expect(coveredAudio).toEqual([]);
});

test("RUTA B1: opción múltiple, lectura al repetir y STOP", async ({
  page,
}, testInfo) => {
  // Lo que realmente se pide al TTS. La ruta nunca responde a propósito: es la
  // forma determinista de observar el estado «sonando» —y con él el STOP— además
  // de dejar constancia del texto compuesto que el alumno oiría.
  const spoken: string[] = [];
  await page.route("**/api/tts", (route) => {
    const body = route.request().postDataJSON() as { text?: string };
    if (body?.text) spoken.push(body.text);
    return new Promise(() => {});
  });

  await page.goto("/");
  await ensureProfile(page);
  await installMocks(page);
  await page.goto("/#/aprender/listening");

  await expect(page.getByText("Mastered 3 of 25").first()).toBeVisible({
    timeout: 15_000,
  });

  // 1) Seleccionar la RUTA B1.
  await page
    .getByRole("button", { name: "Level B1 history" })
    .last()
    .click();

  const optionCorrect = page.getByRole("button", { name: /8:15/ }).first();
  await expect(optionCorrect).toBeVisible({ timeout: 15_000 });
  // La tarjeta de dictado NO está en ninguna ruta.
  expect(
    await page.getByRole("button", { name: /send dictation/i }).count(),
  ).toBe(0);
  expect(await page.getByText(/send dictation/i).count()).toBe(0);

  // 2) El «...» configura la lectura al repetir: tres composiciones, la primera
  //    por defecto (texto del ítem + pregunta + respuesta correcta).
  await page.getByRole("button", { name: "Audio settings" }).first().click();
  const scopeGroup = page.getByRole("radiogroup", {
    name: "When repeating, read",
  });
  await expect(scopeGroup).toBeVisible({ timeout: 15_000 });
  const scopeRadios = scopeGroup.getByRole("radio");
  await expect(scopeRadios).toHaveCount(3);
  await expect(scopeRadios.nth(0)).toHaveAttribute("aria-checked", "true");
  const scopeBox = await scopeGroup.boundingBox();
  const overflowScope = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));

  // Elegir la lectura más larga (ítem + opciones) se guarda en el perfil.
  await scopeRadios.nth(1).click();
  await expect(scopeRadios.nth(1)).toHaveAttribute("aria-checked", "true");
  await expect(scopeRadios.nth(0)).toHaveAttribute("aria-checked", "false");
  await page.screenshot({
    path: `tests/visual/screenshots/${testInfo.project.name}/listening-replay-scope.png`,
  });

  // 3) Responder y repetir: A, B y STOP. Con la lectura larga elegida, lo que se
  //    pide al TTS es texto del ítem + pregunta + opciones + clave.
  await optionCorrect.click();
  const replayA = page.getByRole("button", { name: /accent A/i }).first();
  await expect(replayA).toBeVisible({ timeout: 15_000 });
  await replayA.click();

  const stop = page.getByRole("button", { name: "Stop the reading" }).first();
  await expect(stop).toBeVisible({ timeout: 15_000 });
  const stopBox = await stop.boundingBox();

  await expect.poll(() => spoken.length, { timeout: 15_000 }).toBeGreaterThan(0);
  expect(spoken[0]).toContain(B1_QUESTION.script);
  expect(spoken[0]).toContain("A: 8:45. B: 7:45. C: 9:15. D: 8:15");
  expect(spoken[0]).toContain("D: 8:15.");

  await stop.click();
  await expect(stop).toBeHidden({ timeout: 15_000 });

  // eslint-disable-next-line no-console
  console.log(
    `[${testInfo.project.name}] ` +
      JSON.stringify(
        {
          scopeGroupW: Math.round(scopeBox?.width ?? -1),
          stop: {
            w: Math.round(stopBox?.width ?? -1),
            h: Math.round(stopBox?.height ?? -1),
            x: Math.round(stopBox?.x ?? -1),
          },
          overflowScope,
        },
        null,
        0,
      ),
  );

  expect(overflowScope.scroll).toBeLessThanOrEqual(overflowScope.client);
  expect(stopBox?.width ?? 0).toBeGreaterThanOrEqual(30);
  expect((stopBox?.x ?? 0) + (stopBox?.width ?? 0)).toBeLessThanOrEqual(
    overflowScope.client,
  );

  await page.screenshot({
    path: `tests/visual/screenshots/${testInfo.project.name}/listening-replay-stop.png`,
    fullPage: true,
  });
});
