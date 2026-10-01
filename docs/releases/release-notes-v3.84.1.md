# Release notes — English Tutor v3.84.1

**Fecha:** 2026-09-25 · **Tipo:** release **DE ROBUSTEZ** (patch) · **Versión de app:**
`3.84.0 → 3.84.1`

**Con backend y frontend, SIN migración de BD y SIN endpoints nuevos.** El único cambio de
backend es el `detail` de un `400` que ya existía (`DECK_NAME_TAKEN`). **SIN cambio de
contrato de API y SIN bump** de `GENERATOR_VERSION` / `DECISION_POLICY_VERSION`
(`CURRICULUM_VERSION` sigue `1.3.1`) / `LISTENING_BANK_VERSION` ni de las evaluaciones. **No
se añade ni se retira gate** —siguen los **ocho**, todos en `pending`— y
`docs/audit/validation-evidence.json` **sigue sin existir**.

**En una frase.** El alta del diccionario deja de decir «error» cuando en realidad **el
aprendizaje sí se guardó** y solo falló la tarjeta del mazo: se declara el estado **parcial**
y se puede **reintentar solo la tarjeta**. Y crear un mazo con un nombre que ya existe se dice
como tal, sin esconder el selector.

---

## 1. El defecto, y por qué no es cosmético

V3.84.0 hizo que añadir desde el diccionario pudiera archivar además la palabra en un **mazo
manual**. Eso son **dos escrituras**:

```228:245:frontend/src/features/vocabulary/DictionaryLookup.tsx
      await addVocabularyItem(userId, practiceTerm, { translation });
      if (selectedDeck) {
        ...
        await createFlashcard(userId, deckId, { front: practiceTerm, back: translation });
        setSavedDeck({ id: deckId, name: deckName });
      }
      setAddStatus("ok");
    } catch {
      setAddStatus("error");
    }
```

Las dos compartían un `catch`, así que un fallo de `createFlashcard` se pintaba **igual** que
un fallo de `addVocabularyItem`: «No se pudo añadir la palabra». Pero el estado real era otro:

```
PALABRA
 ├── léxico              OK
 ├── FSRS                OK
 ├── Mi diccionario      OK
 └── mazo manual         ERROR
```

No es corrupción —la palabra no se pierde—, pero la UI **miente sobre lo que sí ocurrió**. Es
la variante de producto de **H5** (`add_item` no atómico), que sigue abierto para su propio
flujo.

## 2. La política elegida: opción A, no B

Había dos caminos:

- **A) Mantener las dos escrituras y declarar el estado parcial** con reintento de la tarjeta.
- **B) Un endpoint transaccional** «alta de léxico + tarjeta de mazo».

Se implementa **A**: es quirúrgica, no cambia el contrato de API y no toca la BD. **B sigue
siendo arquitectónicamente más fuerte** y queda declarada como deuda en
`docs/audit/PARKED.md §V3.84.1`; antes de abordarla hay que comprobar que la persistencia
SQLite del proyecto permite una transacción conjunta razonable.

## 3. Lo que cambia, en concreto

### 3.1 Estado parcial con reintento (`DictionaryLookup.tsx`)

- `addStatus` pasa a `"idle" | "ok" | "partial" | "error"`.
- **El alta del léxico** (`addVocabularyItem`) tiene su propio `try/catch`: si falla, no se
  escribió nada y el error simple es correcto.
- **La tarjeta del mazo** se aísla en `saveDeckCard(target)`, que devuelve si entró de verdad y
  nunca lanza.
- Si falla, la tarjeta pendiente queda en `pendingDeck` y el panel declara el estado
  **parcial** con el nombre del mazo, ofreciendo **reintentar solo la tarjeta**
  (`handleRetryDeckCard`), **sin repetir** el alta del léxico. El CTA «Estudiar en Flashcards»
  sigue disponible porque el aprendizaje sí se completó.
- `pendingDeck` se limpia en `runLookup`, `closeAddPanel`, `changeDirection` y `clearQuery`.

```
                ┌─ addVocabularyItem() → OK
AÑADIR ─────────┤
                └─ createFlashcard()
                        ├── OK    → éxito completo (aprendizaje + mazo)
                        └── ERROR → estado PARCIAL
                                      ↓
                              «ya está en aprendizaje,
                               pero no se pudo guardar en el mazo»
                                      ↓
                              [Reintentar]  [Estudiar]
```

### 3.2 Mazo duplicado se dice como tal

- `create_flashcard_deck` responde **`400 DECK_NAME_TAKEN`** en vez de «No se pudo crear el
  mazo». Con el nombre ya validado y el usuario tomado de la sesión, el único desenlace posible
  ahí es la colisión `UNIQUE (user_id, name)`.
- El frontend separa `deckCreateError` (`"duplicate" | "generic"`) de `deckError` (fallo de
  **carga** de mazos). Antes compartían estado y un nombre duplicado **ocultaba el selector**
  entero con el mensaje de «no se pudieron cargar tus mazos».

### 3.3 i18n

Claves nuevas (**en** + **es**): `dictionary.lookup.addPartial` · `addPartialHint` ·
`addPartialRetry` · `addDeckDuplicate` · `addDeckCreateError`. `check_i18n_coverage.py
--strict` verde.

---

## 4. Pruebas

### 4.1 Unitarias (`DictionaryLookup.test.tsx`)

El helper `routeFetch` gana **respuestas de error** (`{ ok: false, status, json }`),
estáticas o **por llamada** (para fallar la primera y acertar la segunda). Dos casos nuevos:

- fallo de la tarjeta → **estado parcial** → reintento con éxito, comprobando que el alta del
  léxico ocurre **una sola vez**;
- nombre de mazo duplicado → mensaje claro y **selector visible**.

### 4.2 E2E (`dictionaryFlashcardsBridge.spec.ts`)

Los mocks dejan de servir un fixture fijo de cola: **la cola de cada mazo se construye con lo
que entró de verdad** (el léxico para el mazo automático, las tarjetas creadas para los
manuales). Se cubren los **cuatro desenlaces**:

| Caso | Qué fija |
|---|---|
| Crear mazo en el panel → añadir → estudiar ese mazo | la tarjeta aparece y la sesión declara el mazo nuevo |
| Mazo existente → añadir → estudiar | la sesión declara ESE mazo, no el automático |
| Solo aprendizaje | **una** escritura: sin POST de tarjeta, y el mazo automático sirve la palabra |
| Fallo de la tarjeta | estado parcial declarado + reintento que **no** repite el alta |

### 4.3 Backend (`test_flashcards_v378.py`)

Test nuevo `test_duplicate_deck_name_is_declared_as_such`: repetir el nombre da `400` con
`detail == "DECK_NAME_TAKEN"`, el mazo original sigue existiendo y no se crea uno segundo.

---

## 5. Documentación

- `ensure_theme_packs_seeded` (`backend/repositories/collections.py`) documenta que el seed es
  **append-only por `slug`**: editar un `*.json` **no** propaga a las filas ya sembradas, así
  que un pack publicado es **inmutable en la práctica** mientras no exista un proceso de
  actualización de catálogo propio.
- `docs/audit/PARKED.md §V3.84.1`: lo cerrado, la opción B aparcada, `delete_deck` no
  transaccional, **H1 sigue vivo** como deuda aceptada `P2`, la política de packs y los gates.

---

## 6. Verificación

| Comprobación | Resultado |
|---|---|
| `npx tsc --noEmit` | limpio |
| `npm run test` (vitest) | **1038/1038** (109 ficheros) |
| `python -m ruff check .` (backend) | limpio |
| `python -m ruff check .` (lanzador) | limpio |
| `python -m pytest -q` | **3141/3141** |
| `python scripts/check_i18n_coverage.py --strict` | **1785** cadenas, 0 huérfanas / 0 sin definir / 0 duplicadas |
| `node scripts/contrast_audit.mjs --strict` | **480 pares + 6 guardas / 0 bloqueantes** |
| `npm run build` | OK |
| `python scripts/validation_gate.py auto --require-dist` | **10/10** (8 gates) |
| `npx playwright test` (barrido **completo**) | **96 passed · 0 failed · 30 skipped** |
| `python scripts/check_release_consistency.py` | OK en los **6 orígenes** (`3.84.1`) |

> Nota de honestidad sobre `ruff`: un `python -m ruff check .` **desde la raíz** señala
> **1 hallazgo preexistente** ajeno a esta release —`DTZ005` en
> `scripts/purge_virtual_testers.py:198`, un script que esta release **no toca**—. `backend/`
> y `launcher/`, que son los árboles que la release sí modifica, quedan **limpios**.

---

## 7. Honestidad

1. **El ítem sigue duplicándose.** La palabra queda en el léxico («Mi diccionario»/PERSONAL)
   **y** como tarjeta manual del mazo. No es un bug: es el precio de que los dos modelos de
   tarjeta no se compartan. Consolidarlo sigue **aparcado**.
2. **La opción B no se implementa.** No hay endpoint transaccional; el estado parcial se
   **declara** y se **reintenta**, no se evita.
3. **`delete_deck` sigue sin ser transaccional** (borra las cartas FSRS una a una y después el
   mazo). Es deuda preexistente del módulo.
4. **H1 sigue vivo en el código** (`_collection_writable` devuelve `True` para un pack global)
   y **no se endurece aquí**: es la deuda aceptada `P2` en `AU §12` y arreglarla es un cambio de
   backend ajeno a este patch.
5. **Los packs sembrados no se actualizan.** Corregir una traducción de un pack ya publicado
   exige un proceso de actualización que **no existe** y que esta release solo documenta.
6. **Los 8 gates humanos siguen `pending`** y `validation-evidence.json` **no existe**; el
   ancla de certificación sigue en `v3.83.1`.

---

## Para auditar esta release

- **Ancla:** el tag **`v3.84.1`**.
- **Alcance:** `frontend/src/features/vocabulary/DictionaryLookup.tsx`,
  `frontend/src/utils/i18n.ts`, `frontend/src/features/vocabulary/DictionaryLookup.test.tsx`,
  `frontend/tests/visual/dictionaryFlashcardsBridge.spec.ts`,
  `backend/routers/vocabulary.py` (un solo `detail`),
  `backend/tests/test_flashcards_v378.py`,
  `backend/repositories/collections.py` (solo docstring), documentación y bump de versión.
- **Lo que NO toca:** esquema de BD, contrato de API, `GENERATOR_VERSION`,
  `DECISION_POLICY_VERSION`, `CURRICULUM_VERSION`, `LISTENING_BANK_VERSION`, evaluaciones y el
  número o la definición de los gates.
- **Punto de entrada al detalle:** `docs/audit/PARKED.md §V3.84.1` y `docs/RELEVO.md`.
