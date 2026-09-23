# Release notes — English Tutor v3.81.1

**Fecha:** 2026-09-23 · **Tipo:** release **DE PRODUCTO** (patch) ·
**Versión de app:** `3.81.0 → 3.81.1`

**SIN migración de BD, SIN endpoints nuevos, SIN cambios de contrato y SIN tocar
ni una línea de la aplicación.** Lo único que cambia en el árbol es **un fichero
de pruebas**: `frontend/tests/visual/profileDialog.spec.ts`. `GENERATOR_VERSION`,
`DECISION_POLICY_VERSION` (`CURRICULUM_VERSION` sigue `1.3.1`),
`LISTENING_BANK_VERSION` y las evaluaciones **no se tocan**.

**Por qué existe esta release.** Porque el **CI del commit del tag `v3.81.0`
salió rojo**, y una release publicada con un job rojo no es una release
publicada: es una promesa con una deuda. Se arregla, y se publica un parche en vez
de mover el tag, porque **un tag publicado no se recrea**
(`docs/audit/KIT-VALIDACION-GATES.md`).

---

## 1. El hallazgo: 11 de 12 jobs verdes, y el rojo era el barrido visual

```bash
git rev-parse 'v3.81.0^{commit}'      # 6724d8be7d563348e6626810beeb3cf0da7f5812
gh run list --commit 6724d8be7d563348e6626810beeb3cf0da7f5812
gh run view 35847281531 --json jobs   # 12 jobs
```

| Job | Estado |
|---|---|
| `Release consistency` | success |
| `Backend (ruff + pytest)` | success |
| `Frontend (tsc + vitest + build)` | success |
| `Launcher (ruff + pytest)` | success |
| `Launcher (Windows, ruff + pytest)` | success |
| `Content validation` | success |
| `Validation gate (checks automáticos)` | success |
| `Beta V3.0 gate` | success |
| `Dependency audit (pip-audit + npm audit)` | success |
| `Product origin (Windows, informativo)` | success |
| `Product origin (UI served over HTTPS)` | success |
| **`Playwright E2E (visual)`** | **failure** |

`6 failed · 28 skipped · 50 passed`, y **los 6** eran las dos pruebas de
`frontend/tests/visual/profileDialog.spec.ts` en los **tres breakpoints**:

```
[desktop] › profileDialog.spec.ts:32:1 › el diálogo de perfil no se sale por arriba en un viewport bajo
[tablet]  › (el mismo)
[mobile]  › (el mismo)
[desktop] › profileDialog.spec.ts:58:1 › el cuerpo del diálogo scrollea y la cabecera no se va con el scroll
[tablet]  › (el mismo)
[mobile]  › (el mismo)
```

Y el error, idéntico en los seis:

```
Error: locator.click: Test timeout of 30000ms exceeded.
  - waiting for getByRole('button', { name: 'Edit profile' })
    at openProfileDialog (profileDialog.spec.ts:28:60)
```

---

## 2. La causa: un rótulo viejo en el spec, no un fallo del producto

`V3.81.0` renombró el concepto entero de **«perfil» a «usuario»** —es la release
que convierte la gestión de perfiles en gestión de usuarios— y con él dos cadenas
que el spec de `V3.79.0` daba por fijas:

```bash
git diff -U0 v3.80.0..v3.81.0 -- frontend/src/utils/i18n.ts
# -  "user.editProfile": { en: "Edit profile", es: "Editar perfil" },
# +  "user.editProfile": { en: "Edit user",    es: "Editar usuario" },
# -  "profile.editTitle": { en: "Edit profile", es: "Editar perfil" },
# +  "profile.editTitle": { en: "Edit user",    es: "Editar usuario" },
```

El spec buscaba el rótulo **viejo** en cuatro sitios: el botón del menú y el
`name` del diálogo. El menú se abría, el botón existía y el diálogo se pintaba —
**la app estaba bien**—, pero `getByRole("button", { name: "Edit profile" })` no
encontraba nada, así que Playwright esperaba los 30 s de su timeout y fallaba.

**Es un spec desactualizado, y hay que decir por qué importa igual.** El spec no
es un adorno: es el candado que fija que el diálogo **no se sale por arriba** en
un viewport bajo, que es el fallo que el alumno reportó en V3.79.0. Un candado que
no corre **no protege nada**, y llevar dos releases sin correr equivale a haberlo
perdido.

---

## 3. El arreglo: un rótulo en un solo sitio

El spec gana una constante con el rótulo **actual** —usada en las cuatro
búsquedas— y, al lado, el motivo escrito, para que el próximo renombrado se
arregle en **un** sitio y el spec siga contando por qué:

```20:36:frontend/tests/visual/profileDialog.spec.ts
 * V3.81: el rótulo pasa de «Edit profile» a «Edit user» (la gestión de perfiles
 * se convierte en gestión de usuarios). Se busca por el nombre **actual**, y si
 * vuelve a cambiar, este spec es el que lo dice.
 */
const EDIT_LABEL = "Edit user";

/** Abre el diálogo de edición del perfil de la sesión. */
async function openProfileDialog(page: Page) {
  await page.goto("/");
  await ensureProfile(page);
  // El disparador del menú se localiza por su contrato accesible (`aria-haspopup`)
  // y no por su texto: su nombre accesible es el del perfil, que cambia.
  await page.locator('button[aria-haspopup="menu"]').click();
  await page.getByRole("button", { name: EDIT_LABEL }).click();
  await expect(page.getByRole("dialog", { name: EDIT_LABEL })).toBeVisible();
}
```

**Y el candado muerde**, que es lo que se le pide a un candado: con el rótulo
viejo, esos mismos seis casos **fallan** por timeout. La demostración la dio el
propio CI, que es una forma incómoda y perfectamente válida de comprobarlo.

---

## 4. Por qué se escapó (que es lo que hay que arreglar de verdad)

La verificación local de `V3.81.0` lanzó **solo los dos specs nuevos** —
`dictionarySmoke` y `flashcardsSmoke`— y dio **6/6** en los tres breakpoints.
**Nunca se lanzó la suite visual completa**, y el spec afectado vivía en ella.

Las notas de `V3.81.0` dicen literalmente eso:

> Playwright `dictionarySmoke` + `flashcardsSmoke` | **6/6** en los 3 breakpoints

Es una frase **cierta y a la vez insuficiente**: declara lo que se corrió y no
dice nada de lo que no se corrió. El hueco no es de honestidad, es de **método**:
el barrido visual completo es la autoridad del CI, y en local ya estaba declarado
con flakiness (§`V3.81.0` · honestidad (v)), así que la tentación de correr solo
lo nuevo es exactamente la que hay que resistir.

**La lección, escrita para la próxima vez:** un renombrado de **i18n** toca
selectores por texto en pruebas de toda la casa. Cuando cambia una cadena que
alguien busca, el barrido entero se lanza, no solo los specs nuevos.

---

## 5. Verificación

| Comprobación | Resultado |
|---|---|
| `npx playwright test tests/visual/profileDialog.spec.ts` | **6 passed** (2 pruebas × 3 breakpoints) |
| `ruff check` | limpio (no hay cambios de Python) |
| `pytest -q` | **3085/3085** |
| `tsc --noEmit` | limpio |
| `vitest run` | **1028/1028** (109 ficheros) |
| `npm run build` | correcto (`package.json` en `3.81.1`) |
| i18n `--strict` | **1733** cadenas, 0 huérfanas / 0 usadas sin definir / 0 duplicadas |
| `check_release_consistency.py` | OK en los **6 orígenes** (`3.81.1`) |
| `validation_gate.py auto` | **10/10** |
| CI del commit del tag | **se resuelve por comando** (§1); el rojo que abrió esta release queda verde |

**La prueba visual se hizo contra un backend real sobre una COPIA de la BD**
(`backend/data/tutor.db` → temporal), como en V3.81.0: el `globalSetup` del
barrido visual crea y borra un perfil de prueba, así que no se apunta a la BD en
uso.

---

## 6. Honestidad

1. **Esto no arregla el producto, arregla una prueba.** Si alguien esperaba que
   `v3.81.0` tuviera un fallo funcional en el diálogo de edición, no lo tiene: el
   fallo era del test. Se declara explícitamente para que nadie lea «parche» como
   «había algo roto en la app».
2. **El renombrado de i18n no se revierte.** `"Edit user"` / `"Editar usuario"` es
   el nombre decidido en V3.81.0; lo que estaba mal era la prueba.
3. **No se corrigieron las notas de `v3.81.0`.** Son parte del árbol publicado del
   tag `v3.81.0` y no se reescriben: la frase de la evidencia visual sigue ahí,
   cierta y parcial, y esta release es la que explica el resto.
4. **El árbol de certificación no se mueve.** `G1–G7` siguen `pending` y la base
   sigue siendo `v3.81.0`: el árbol de `v3.81.1` solo se diferencia en un fichero
   de pruebas, así que no hay nada que re-anclar.
5. **El barrido visual completo sigue sin ser fiable en local.** En la máquina de
   desarrollo la tanda entera en paralelo da fallos que **pasan en aislamiento**
   (comprobado: `smoke.spec.ts` y `keyboard.spec.ts` → `9 passed` sueltos, y eran
   parte de los fallos de la tanda). La autoridad del barrido completo es el CI, y
   por eso la verificación de esta release se apoya en CI más los specs concretos,
   no en «la tanda local salió verde».
