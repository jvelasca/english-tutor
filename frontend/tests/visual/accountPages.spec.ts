import { test, expect, type Page } from "@playwright/test";
import path from "node:path";

/**
 * Smoke visual permanente del ALTA PROFESIONAL (V3.82): las tres páginas que
 * llegan por un enlace de correo —activar, restablecer y verificar— y las tres
 * pantallas de la puerta de entrada —entrar, pedir acceso y recuperar—.
 *
 * Por qué existe: V3.82 cambia la primera impresión del producto entero. La
 * puerta deja de ser «elige un usuario de la lista» y pasa a ser email +
 * contraseña, y las páginas de cuenta se pintan **fuera del armazón de la app**,
 * sin cabecera ni navegación y con un pie que avisa de que el correo puede no
 * estar configurado. Nada de eso estaba cubierto por una sonda visual, y es
 * justo el tipo de pantalla que se rompe sin que nadie mire: no hay usuario
 * dentro de la app que la use a diario.
 *
 * Es **determinista y no necesita backend**: las tres páginas de cuenta solo
 * hablan con su endpoint (`activate`, `reset-password`, `verify`) y la puerta con
 * `/api/session`. Todo se responde desde el navegador. Los mocks van anclados al
 * **origen** (`/^https?:\/\/[^/]+\/api\//`) por la razón que ya está escrita en
 * `dictionarySmoke.spec.ts`: un glob como `**​/api/settings*` casa también con el
 * módulo de la app `/src/api/settings.ts` y, al servirle JSON, la app **no
 * arranca**.
 */

const USER = {
  id: "u-visual-tester",
  name: "Visual Tester",
  avatar_color: "",
  avatar_emoji: "",
  email: "visual@tester.local",
  email_verified: true,
  has_password: true,
  must_change_password: false,
  is_test: false,
};

const PASSWORD = "caballo-bateria-grapa";

/**
 * Todo `/api/**` con una forma válida y vacía, y **después** el endpoint que
 * decide cada pantalla.
 *
 * El orden importa: en Playwright gana la **última** ruta registrada, así que la
 * general va primero y la específica después.
 */
async function installAccountMocks(
  page: Page,
  handlers: Record<string, (method: string) => { status?: number; json?: unknown }>,
) {
  await page.route(/^https?:\/\/[^/]+\/api\//, (route) => {
    const { pathname } = new URL(route.request().url());
    const method = route.request().method();
    const handler = handlers[pathname];
    if (handler) {
      const { status, json } = handler(method);
      return route.fulfill({ status: status ?? 200, json: json ?? {} });
    }
    return route.fulfill({ json: method === "GET" ? {} : { ok: true } });
  });
}

/** La app **sin** sesión: `GET /api/session` no encuentra cookie y se pinta la puerta. */
async function installNoSession(page: Page) {
  await page.route("**/api/session", (route) =>
    route.fulfill({ status: 401, json: { detail: "SESSION_REQUIRED" } }),
  );
}

test("las páginas del correo: activar, restablecer y verificar", async ({
  page,
}, testInfo) => {
  const project = testInfo.project.name;
  const shot = (name: string) =>
    path.join("tests", "visual", "screenshots", project, `${name}.png`);

  await installAccountMocks(page, {
    "/api/account/activate": () => ({
      status: 400,
      json: { detail: "ACTIVATION_TOKEN_INVALID" },
    }),
    "/api/account/reset-password": () => ({
      status: 400,
      json: { detail: "RESET_TOKEN_EXPIRED" },
    }),
    "/api/account/verify": () => ({ json: USER }),
  });
  await installNoSession(page);

  // --- Activar: el formulario y el fallo del token -------------------------
  await page.goto("/#/cuenta/activar?token=tok-visual-123");
  await expect(
    page.getByRole("heading", { name: "Choose your password" }),
  ).toBeVisible({ timeout: 15_000 });
  // El pie no es decoración: en este equipo puede no haber correo, y decirlo es
  // lo que evita esperar un mensaje que nunca va a llegar.
  await expect(page.getByText("the webmaster can hand it to you")).toBeVisible();
  await expect(page.getByRole("button", { name: "Activate my account" })).toBeDisabled();
  await page.screenshot({ path: shot("account-activate"), fullPage: true });

  await page.getByLabel("New password", { exact: true }).fill(PASSWORD);
  await page.getByLabel("Repeat the password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Activate my account" }).click();
  // Un token gastado se dice con `role="alert"`: interrumpe, que es lo que debe
  // hacer un fallo. Un «activando…» no.
  await expect(page.getByRole("alert")).toHaveText(
    "That invitation is not valid. It may have been used already.",
  );
  await page.screenshot({ path: shot("account-activate-error"), fullPage: true });

  // --- Activar sin token: el enlace llegó mutilado --------------------------
  await page.goto("/#/cuenta/activar");
  await expect(page.getByRole("alert")).toHaveText(
    "The link has no invitation. Open the link from the email exactly as it arrived.",
  );

  // --- Restablecer: el mismo formulario, otro token, y la caducidad --------
  await page.goto("/#/cuenta/restablecer?token=tok-visual-456");
  await expect(
    page.getByRole("heading", { name: "Choose a new password" }),
  ).toBeVisible();
  await page.getByLabel("New password", { exact: true }).fill(PASSWORD);
  await page.getByLabel("Repeat the password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Save password" }).click();
  await expect(page.getByRole("alert")).toHaveText(
    "That link has expired. Ask for a new one.",
  );
  await page.screenshot({ path: shot("account-reset-error"), fullPage: true });

  // --- Verificar: el enlace que existía en el correo desde V3.81 y no llevaba
  // a ninguna parte (la ruta no existía) ------------------------------------
  await page.goto("/#/cuenta/verificar?token=tok-visual-789");
  await expect(
    page.getByRole("heading", { name: "Confirm your email" }),
  ).toBeVisible();
  // El aviso de éxito es un `status`, no una alarma: no debe interrumpir.
  await expect(page.getByRole("status")).toHaveText(
    "Your email is confirmed. Thank you.",
  );
  await expect(page.getByRole("button", { name: "Go to the app" })).toBeVisible();
  await page.screenshot({ path: shot("account-verify"), fullPage: true });
});

test("la puerta: entrar, pedir acceso y recuperar la contraseña", async ({
  page,
}, testInfo) => {
  const project = testInfo.project.name;
  const shot = (name: string) =>
    path.join("tests", "visual", "screenshots", project, `${name}.png`);

  await installAccountMocks(page, {});
  await installNoSession(page);

  // --- Entrar: email + contraseña, sin selector de nombres -----------------
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible({
    timeout: 15_000,
  });
  // V3.82: la puerta ya no enumera quién tiene cuenta, así que no hay lista.
  await expect(page.getByLabel("Email", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Password", { exact: true })).toBeVisible();
  // El botón solo se activa con los dos campos: no se manda una petición que el
  // servidor va a rechazar.
  await expect(page.getByRole("button", { name: "Sign in" })).toBeDisabled();
  await page.screenshot({ path: shot("gate-signin"), fullPage: true });

  // --- Pedir acceso: nombre, email y avatar (lo que hace falta para invitar) -
  await page.getByRole("button", { name: "Ask for access" }).click();
  await expect(page.getByRole("heading", { name: "Ask for access" })).toBeVisible();
  await expect(page.getByLabel("Name or nickname", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Email", { exact: true })).toBeVisible();
  await expect(page.getByText("Avatar", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Use a photo" })).toBeVisible();
  // La promesa del flujo, escrita en la propia pantalla antes de pedir nada.
  await expect(
    page.getByText("Fill this in and the webmaster will authorise it"),
  ).toBeVisible();
  await page.screenshot({ path: shot("gate-request"), fullPage: true });

  await page.getByRole("button", { name: "Back to sign in" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();

  // --- Recuperar: el formulario real, no un texto informativo ---------------
  await page.getByRole("button", { name: "I forgot my password" }).click();
  await expect(
    page.getByRole("heading", { name: "Recover your password" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Send link" })).toBeVisible();
  // No promete que el correo exista: promete que, si existe, el enlace va.
  await expect(
    page.getByText("we will send you a link to choose a new password"),
  ).toBeVisible();
  await page.screenshot({ path: shot("gate-forgot"), fullPage: true });
});
