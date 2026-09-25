import { expect, type Locator, type Page } from "@playwright/test";

/**
 * Guardas de layout compartidas por la suite visual (V3.84.0).
 *
 * El hueco que cierran: hasta ahora solo tres specs comprobaban desborde
 * horizontal, y cada uno con su copia de la misma expresión. El defecto real
 * (el botón «Practicar esta palabra» del diccionario, recortado por el
 * `overflow-hidden` de su tarjeta) vivía justo en el punto ciego: la vista se
 * **fotografiaba** pero nadie medía si sus acciones cabían.
 */

/** Tolerancia de 1px por redondeo subpíxel del navegador. */
const TOLERANCE = 1;

/**
 * Afirma que la página no tiene scroll horizontal.
 *
 * `documentElement.scrollWidth` frente a `window.innerWidth`: si un elemento
 * desborda su contenedor pero el contenedor **recorta** (`overflow-hidden`), el
 * scroll ancho NO crece —por eso existe además `expectInsideClippingAncestor`—;
 * esto cubre el caso de un elemento que empuja la página entera.
 */
export async function expectNoHorizontalOverflow(
  page: Page,
  label = "",
): Promise<void> {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(
    overflow,
    `desborde horizontal${label ? ` en ${label}` : ""}: ${overflow}px`,
  ).toBeLessThanOrEqual(TOLERANCE);
}

/**
 * Afirma que `inner` cabe dentro del ancestro que lo recorta.
 *
 * Es la guarda del defecto confirmado: un `flex` sin `flex-wrap` dentro de un
 * `Card` con `overflow-hidden` no genera scroll (el recorte es visual), así que
 * la única forma de detectarlo es comparar rectángulos. Se compara el borde
 * derecho/inferior del elemento con el del ancestro recortador.
 *
 * Lanza si no se encuentra el ancestro: una guarda que no mide nada es peor que
 * ninguna, porque da por bueno lo que no ha comprobado.
 */
export async function expectInsideClippingAncestor(
  inner: Locator,
  label: string,
): Promise<void> {
  const innerBox = await inner.boundingBox();
  expect(innerBox, `${label}: el elemento no está visible`).not.toBeNull();

  const clipBox = await inner.evaluate((node) => {
    let parent: HTMLElement | null = node.parentElement;
    while (parent) {
      const overflowX = getComputedStyle(parent).overflowX;
      if (overflowX === "hidden" || overflowX === "clip") {
        const rect = parent.getBoundingClientRect();
        return { right: rect.right, bottom: rect.bottom };
      }
      parent = parent.parentElement;
    }
    return null;
  });

  expect(
    clipBox,
    `${label}: no se encontró un ancestro que recorte`,
  ).not.toBeNull();
  expect(
    innerBox!.x + innerBox!.width,
    `${label}: el elemento se sale del contenedor que lo recorta`,
  ).toBeLessThanOrEqual(clipBox!.right + TOLERANCE);
  expect(
    innerBox!.y + innerBox!.height,
    `${label}: el elemento se sale (abajo) del contenedor que lo recorta`,
  ).toBeLessThanOrEqual(clipBox!.bottom + TOLERANCE);
}
