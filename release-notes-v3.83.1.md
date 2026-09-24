# Release notes — English Tutor v3.83.1

**Fecha:** 2026-09-24 · **Tipo:** release **DE INSTRUMENTO Y HONESTIDAD** (patch) ·
**Versión de app:** `3.83.0 → 3.83.1`

**SIN producto nuevo y SIN tocar la aplicación.** `frontend/src` y `launcher/` quedan
**intactos**; lo único que cambia en `backend/` es la línea de `VERSION` (bookkeeping,
no lógica). **SIN migración de BD, SIN endpoints nuevos, SIN cambio de contrato de
API y SIN bump** de `GENERATOR_VERSION` / `DECISION_POLICY_VERSION`
(`CURRICULUM_VERSION` sigue `1.3.1`) / `LISTENING_BANK_VERSION` ni de las
evaluaciones. **No se añade ni se retira gate** —siguen los **ocho**, todos en
`pending`— y `docs/audit/validation-evidence.json` **sigue sin existir**.

**Por qué existe esta release.** Porque **la versión que se estaba auditando no
existía**: hasta este lanzamiento la última etiqueta del repositorio era `v3.83.0`,
así que el arreglo del gate `reduced-motion` (H2) y las pruebas visuales nuevas vivían
en `main` **sin etiqueta**, y la deuda de honestidad de `release-notes-v3.83.0.md §5.1`
seguía abierta. El propio informe
[`docs/audit/AU-AUDITORIA-TOTAL-V383.md`](docs/audit/AU-AUDITORIA-TOTAL-V383.md) pedía
un **`v3.83.1` quirúrgico de instrumento y honestidad**; esto es ese parche, publicado.

---

## 1. El hallazgo que lo motiva: `v3.83.1` no existía

Comprobado por comando contra el remoto `jvelasca/english-tutor`:

```bash
gh api repos/jvelasca/english-tutor/git/ref/tags/v3.83.1        # → 404
gh api repos/jvelasca/english-tutor/releases/tags/v3.83.1       # → 404
gh api repos/jvelasca/english-tutor/compare/v3.83.0...v3.83.1   # → 404
gh api "repos/jvelasca/english-tutor/tags?per_page=5" --jq '.[].name'
#   v3.83.0 · v3.82.0 · v3.81.2 · v3.81.1 · v3.81.0
```

No era **latencia de propagación**: **no había ningún objeto que exponer**. Tampoco
existía en local (ni ref, ni commit, ni stash, ni rama). Una auditoría que empieza por
el diff exacto del tag no podía empezar, y eso es lo que esta release arregla: **crea
el ancla**.

---

## 2. H2 — el gate `reduced-motion` que emulaba en vacío (lo que más justifica el parche)

`GUI-05` se declaró cerrado en `V3.73.1` con esta línea:

```ts
// frontend/tests/visual/reducedMotionAndZoom.spec.ts (antes)
test.use({ reducedMotion: "reduce" });
```

**`reducedMotion` no es una opción válida de `test.use` en Playwright 1.62**: no
existe como propiedad de `TestOptions` y **se ignora en silencio**. El gate pasaba
**sin emular nada**, así que la evidencia de un gate declarado desde `V3.73.1` era
**vacua** —y la release `V3.83.0` se apoyaba en él—. La corrección (commit `54a32fd`)
emula de verdad y añade una **guarda de mordida** para que no pueda volver a pasar por
vacío:

```ts
// frontend/tests/visual/reducedMotionAndZoom.spec.ts (ahora)
await page.emulateMedia({ reducedMotion: "reduce" });
// …
// Guarda de mordida: sin la emulación activa el test sería vacuo.
await expect
  .poll(() =>
    page.evaluate(() =>
      window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    ),
  )
  .toBe(true);
```

Con la guarda, si alguien vuelve a una emulación que no muerde, **el test falla en
lugar de pasar en verde sin probar nada**.

---

## 3. E5/i — la letra de las notas de `v3.83.0`

`release-notes-v3.83.0.md §5.1` afirmaba:

> **Solo frontend.** No se toca ni el backend ni la BD.

Y el commit de release (`e05b3dd`) **sí** tocaba `backend/config.py` (el bump de
`VERSION`). La contradicción es literal, no de matiz. Se corrige a:

> **Solo frontend, sin lógica de backend** (el único cambio fuera de la UI es el bump
> de `VERSION` en `backend/config.py`) **y sin tocar la BD.**

Una línea, y desaparece la contradicción. **No se reescribe el resto** de las notas de
`v3.83.0`: el párrafo decía la verdad sobre el alcance del producto y lo sigue diciendo.

---

## 4. H1 — deuda **aceptada**, no resuelta

El informe `AU` (§5-H1) dictaminó que
[`backend/domain/retention.py`](backend/domain/retention.py) devuelve `True` para un
pack global:

```python
# backend/domain/retention.py:185
return not owner or owner == user_id      # `not owner` == True para el pack global
```

Es decir: la promesa «un pack curado no es un destino» es, hoy, **solo de cliente**. Un
cliente que no sea la UI podría insertar una palabra en el catálogo de un pack global.

**`v3.83.1` NO lo endurece, y lo declara.** Motivos:

1. **Es heredado** (`V3.77.1`): no lo introduce la serie de releases que se está
   auditando.
2. **No es alcanzable desde la UI**: el selector de `V3.83.0` filtra a
   `kind === "user_list"` y está fijado por E2E.
3. **Rompería la premisa «solo frontend»** de este patch: `frontend/src` dejaría de
   estar intacto en el diff y abriría una revisión de `retention.py` con sus tests.

Queda **aparcado como deuda `P2`** en
[`docs/audit/AU-AUDITORIA-TOTAL-V383.md §12`](docs/audit/AU-AUDITORIA-TOTAL-V383.md),
con su recomendación viva (`return bool(owner) and owner == user_id` para la ingestión).
**No se cierra por omisión:** mientras siga en el código, sigue declarada.

---

## 5. Verificación

| Comprobación | Resultado |
|---|---|
| `python scripts/check_release_consistency.py` | **OK en los 6 orígenes** (`3.83.1`) |
| `python scripts/check_i18n_coverage.py --strict` | sin cambios (no hay cadenas nuevas) |
| `python scripts/validation_gate.py auto` | **10/10** (informe regenerado con `3.83.1`) |
| `npx playwright test tests/visual/reducedMotionAndZoom.spec.ts` | verde (el gate ya muerde) |
| `npx playwright test` (specs nuevos) | `dictionaryFlashcardsBridge` · `studySessionKeyboard` · `studySessionVisual` verdes |
| `git diff --stat v3.83.0..HEAD -- backend frontend/src launcher scripts` | solo `backend/config.py` (la línea `VERSION`) |
| `validation_gate.py status` | **8 gates, los 8 en `pending`** |
| `Test-Path docs/audit/validation-evidence.json` | **NO EXISTE** |

---

## 6. Honestidad

1. **No arregla el producto: etiqueta el árbol y cierra la letra.** Si alguien esperaba
   un cambio funcional, no lo hay: el único cambio en `backend/` es `VERSION`.
2. **El diff `v3.83.0...v3.83.1` es más grande que este parche.** Incluye **los 8
   commits que ya estaban en `main`** (6 `docs(audit)` + 2 `test(visual)`), no solo el
   commit de release. Eso es lo que se etiqueta, y es lo que hay que leer al auditar;
   declararlo aquí evita que sorprenda.
3. **H1 sigue vivo en el código.** Esta release lo **sitúa** fuera de un patch de
   instrumento; **no** lo rebaja ni lo cierra.
4. **El árbol de certificación no se mueve.** `G1–G8` siguen `pending` y la base
   certificada sigue siendo la de `v3.75.8`: este patch no añade ni retira gate.
5. **El CI no dispara en tags.** La run que **certifica** el commit del tag es la del
   **push a `main`**, porque `.github/workflows/ci.yml` escucha `push: branches: [main]`
   y `pull_request`. Quien audite «el CI del tag» audita el CI del commit al que apunta.

---

## Para auditar esta release

- **Ancla:** el tag anotado **`v3.83.1`**. Contiene `main` en el momento de publicar:
  `dfe9898` (los 8 commits ya en `main`) **más** el commit de release de este parche.
- **Punto de entrada:** el archivo `agentes/auditoria-total-externa-v383.md` cubre el
  arco `v3.82.0..v3.83.0`; el informe **`AU`** ya dictaminó ese arco. `v3.83.1` es el
  parche de instrumento y honestidad que ese informe pedía.
- **La revisión es de solo lectura:** un tag publicado no se recrea.
- **Alcance fino que sí toca este parche:** (a) el gate `reduced-motion` (H2, ya
  corregido en `main`), (b) la letra de `release-notes-v3.83.0.md §5.1` (E5/i) y
  (c) la declaración de deuda de H1. **Nada de producto.**
