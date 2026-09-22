/**
 * Candado de FUENTE del diálogo (V3.79.0).
 *
 * El fallo del alumno —«al editar un perfil, el cuadro de selección de icono se
 * sale de pantalla por arriba»— tenía DOS capas, y conviene no confundirlas:
 *
 * 1. **La causa raíz** era de contención, no de CSS: el diálogo se abría desde
 *    el menú de usuario, dentro de un `<header>` con `backdrop-filter`, y esa
 *    propiedad crea bloque contenedor para `position: fixed`. El `inset: 0` del
 *    backdrop medía la franja del header, no el viewport. Eso se arregla con un
 *    portal a `document.body`, y su candado vive en
 *    `src/components/ProfileDialog.test.tsx` («se monta fuera del header»).
 * 2. **El CSS** era frágil por su cuenta: centraba con `align-items` y medía en
 *    `vh`. Este test fija esas invariantes, que protegen a los otros tres
 *    diálogos que comparten clases y sí se montan fuera del header.
 *
 * No comprueba píxeles: comprueba que la decisión sigue escrita. En el Chrome de
 * escritorio `vh == dvh`, así que un test de navegador no puede provocar el
 * recorte del móvil; lo que sí puede es fijar la cota (ver
 * `tests/visual/profileDialog.spec.ts`) y la invariante de aquí.
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const LEGACY = readFileSync(join(__dirname, "legacy.css"), "utf8");

/** Bloque de declaraciones de una regla concreta (el primer `{...}` tras el selector). */
function rule(selector: string): string {
  const start = LEGACY.indexOf(selector);
  expect(start, `no existe la regla ${selector}`).toBeGreaterThan(-1);
  const open = LEGACY.indexOf("{", start);
  const close = LEGACY.indexOf("}", open);
  // Se quitan los comentarios: si no, una regla que EXPLICA por qué no usa una
  // propiedad prohibida la «contendría» y el candado daría un falso positivo.
  return LEGACY.slice(open + 1, close).replace(/\/\*[\s\S]*?\*\//g, "");
}

const backdrop = rule(".dialog-backdrop {");
const dialog = rule(".dialog {");

describe("dialogo · no puede recortarse por arriba", () => {
  it("el backdrop desplaza, para que el borde superior sea alcanzable", () => {
    // Sin scroll en el backdrop, un diálogo más alto que el viewport deja su
    // cabecera —y su asa de cerrar— fuera del alcance del alumno.
    expect(backdrop).toMatch(/overflow-y:\s*auto/);
  });

  it("NO centra con align-items: es lo que empujaba el borde fuera de la pantalla", () => {
    // Con `align-items: center`, un hijo más alto que el contenedor se desborda
    // por los DOS lados y la mitad superior queda inalcanzable.
    expect(backdrop).not.toMatch(/align-items:\s*center/);
    // El centrado lo da `margin: auto`, que sí respeta el área desplazable.
    expect(dialog).toMatch(/margin:\s*auto/);
  });

  it("mide con dvh, no con vh: en movil `vh` ignora la barra del navegador", () => {
    // `90vh` medía el viewport con la barra OCULTA, así que podía ser más alto
    // que el área visible. Se exige la unidad dinámica, con su respaldo.
    expect(dialog).toMatch(/max-height:\s*calc\(100dvh/);
    expect(dialog).not.toMatch(/max-height:\s*90vh/);
  });

  it("cabecera y pie no se encogen: el cuerpo es el que cede", () => {
    // El scroll vive en el cuerpo, así que al desplazar no se va la cabecera.
    expect(rule(".dialog-header {")).toMatch(/flex-shrink:\s*0/);
    expect(rule(".dialog-footer {")).toMatch(/flex-shrink:\s*0/);
    const body = rule(".dialog-body {");
    expect(body).toMatch(/overflow-y:\s*auto/);
    // Sin `min-height: 0` un hijo flex no puede encogerse por debajo de su
    // contenido y el desbordamiento vuelve a salir por arriba.
    expect(body).toMatch(/min-height:\s*0/);
  });
});
