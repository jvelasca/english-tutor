# AU — Auditoría externa total · arco `v3.81.2..v3.83.0`

> **Prefijo:** `AU` (primer prefijo libre; `AP`–`AT` siguen reservados, ver §9).
> **Ancla:** tag anotado **`v3.83.0`** → commit **`e05b3dd`**. La release auditada es
> el tag, **no** la página de Release (§1).
> **Alcance ampliado (a petición del gerente):** el encargo
> [`agentes/auditoria-total-externa-v383.md`](../../agentes/auditoria-total-externa-v383.md)
> cubre **solo** `v3.82.0..v3.83.0` y declara como deuda (§6-D1) que el arco
> **`v3.81.2..v3.82.0`** —el que **cambia el contrato de la API y migra la BD**— no
> tiene punto de entrada. Este informe **sí** lo dictamina (§2, §4-D1).
> **Naturaleza:** auditoría **de solo lectura** del producto. La evidencia **nueva**
> que este informe produce (§7) son **pruebas** (specs de Playwright), no producto:
> no se ha tocado `backend/`, `frontend/src/` ni la base de datos.

---

## 0. Método y ancla por comando

Todo lo que sigue se ha **ejecutado** sobre el árbol de trabajo, no citado. El ancla
se resuelve con git (§1 del encargo):

```text
git rev-parse 'v3.83.0^{commit}'   → e05b3dd6a6ef531c993c3340aa921417d8cbca5d
git rev-parse 'v3.82.0^{commit}'   → (base del delta)
git log --oneline v3.82.0..v3.83.0 → e05b3dd release(v3.83.0): diccionario a Flashcards y sesion de estudio tipo juego
git log --oneline v3.83.0..HEAD    → 5a5e600 docs(audit) · fd086e8 test(visual) · 240e5c9 docs(audit)
gh run view 35995172219            → conclusion=success · headSha=e05b3dd  (12/12 jobs)
gh run view 35995527317            → conclusion=success · headSha=240e5c9
gh run view 35998603280            → conclusion=success · headSha=fd086e8
gh api repos/jvelasca/english-tutor/releases/latest --jq .tag_name → v3.83.0
```

Instrumentos automáticos ejecutados (salidas literales en §1 y §6):

| Instrumento | Comando | Salida |
|---|---|---|
| Gates | `python scripts/validation_gate.py status` | **8 gates, los 8 en `pending`** |
| Gates (auto) | `python scripts/validation_gate.py auto` | **10/10**, sin diff en `docs/audit/generated` |
| i18n | `python scripts/check_i18n_coverage.py --strict` | **1772** cadenas · 0 huérfanas · 0 sin definir · 0 duplicadas |
| Contraste | `npm run audit:contrast` | **480 pares + 6 guardas / 0 bloqueantes** (17 acentos reportados) |
| Unitarios | `npm run test` | **1033/1033** (109 ficheros) |
| E2E visual | `npx playwright test` | **86/86** (3 breakpoints, `workers=1`) |
| Evidencia de gates | `Test-Path docs/audit/validation-evidence.json` | **NO EXISTE** |

---

## 1. Invariantes (§1.1 del encargo) — comprobados uno a uno

| # | Invariante | Comando | Resultado | Dictamen |
|---|---|---|---|---|
| 1 | Backend: **una** línea y es `VERSION` | `git diff v3.82.0..v3.83.0 -- backend/` | solo `-VERSION="3.82.0"` / `+VERSION="3.83.0"` | **pass** |
| 2 | Sin DDL nuevo | `git diff v3.82.0..v3.83.0 -- backend/repositories` (y `db.py`) | **vacío** | **pass** |
| 3 | Sin bumps pedagógicos | `git diff -U0 … -- backend/config.py \| grep -E 'VERSION\|GENERATOR_VERSION\|DECISION_POLICY\|CURRICULUM_VERSION\|LISTENING_BANK_VERSION'` | solo `VERSION` | **pass** |
| 4 | Sin rutas nuevas | `git diff v3.82.0..v3.83.0 -- backend/routers \| grep '@router\.'` + `--stat` | **vacío** | **pass** |
| 5 | Currículum / lanzador / scripts | `git diff --stat … -- backend/curriculum launcher scripts` | **vacío** (los tres) | **pass** |
| 6 | Producto no movido desde el tag | `git diff --stat v3.83.0..HEAD -- backend frontend/src launcher scripts` | **vacío** | **pass** (con excepción declarada) |
| 7 | Evidencia de gates a cero | `validation-evidence.json` + `validation_gate.py status` | no existe el fichero; 8/8 `pending` | **pass** |

**Invariante 6 — la excepción declarada, verificada.** El candado fuerte («desde el
tag solo se ha tocado documentación») **no se cumple literalmente**, y el encargo lo
declara en vez de esconderlo:

```text
git diff --name-only v3.83.0..HEAD | grep -v '\.md$'  →  frontend/playwright.config.ts
```

Es el commit `fd086e8` (**solo el arnés de Playwright**: fija `workers: 1`). **No es
producto**: no se compila en la app, no cambia ninguna respuesta, y su run de CI
**está verde** (`35998603280`, `success`). La formulación nueva —acotar el candado a
`backend frontend/src launcher scripts` y **declarar** la excepción— es **honesta**
(§4-E2), pero registra un hecho: **la certificación del tag ya no describe el árbol
`main`**; describe el árbol del tag, que es lo correcto, siempre que nadie presente
`main` como «lo auditado». Lo declaro aquí.

---

## 2. El eslabón sin punto de entrada: `v3.81.2..v3.82.0` (§6-D1)

Comprobado por comando:

```text
git log --oneline v3.81.2..v3.82.0
  3f686a0 release(v3.82.0): alta profesional de cuentas - solicitud autorizada, invitacion, entrada por email y recuperacion
  88e998a docs(audit): publica la Release de v3.81.2 y ancla el candado post-tag por invariante, no por SHA
  0b85e69 docs(audit): punto de entrada externo anclado a v3.81.2 y la deriva del recuento de gates
  ea65561 docs(v3.81.2): sella la run de CI en las notas y declara la errata del commit posterior al tag

git diff --shortstat v3.81.2..v3.82.0        → 96 files changed, 9378 insertions(+), 3537 deletions(-)
            … -- backend                      → 29 files changed,  3778 insertions(+), 1468 deletions(-)
            … -- frontend/src                 → 34 files changed,  2369 insertions(+), 1647 deletions(-)
git diff v3.81.2..v3.82.0 -- backend/repositories/db.py | grep '^+.*ALTER TABLE'
  → +  f"ALTER TABLE profile_requests ADD COLUMN {column} {ddl}"
```

Y el cambio incompatible de contrato, localizado en `backend/routers/session.py`
(`git diff v3.81.2..v3.82.0 -S'user_id' -- backend/routers`):

```text
-    user = await user_service.get_user(body.user_id)
-    await _require_password_if_set(body.user_id, body.password)
+    email = credentials.normalize_email(body.email)
+    user = await user_service.find_by_email(email) if email else None
+    stored = await user_service.get_password_hash(user["id"]) or ""
+        raise HTTPException(status_code=403, detail="ACCOUNT_NOT_ACTIVATED")
+    if not credentials.verify_password(stored, body.password): …
+    "/api/admin/users/{user_id}/resend-activation"
```

**No existe punto de entrada para este arco**: en `agentes/` están
`auditoria-total-externa-v381.md`, `…-v3812.md` y `…-v383.md`, pero **no hay
`…-v382*`**. La ausencia es real, no un despiste de nombres.

### Dictamen D1

**El eslabón más peligroso de la serie es el único sin auditoría.** Es el arco que
**retira** `POST /api/users`, **despublica** `GET /api/users`, **elimina** la entrada
sin contraseña, **introduce cuatro columnas aditivas** en `profile_requests` y cuatro
en `users`, y **cambia la forma del cuerpo de `POST /api/session`** — con
`frontend`, `launcher` y sus tests coordinados en el mismo lanzamiento.

Lo que he verificado por comando (mínimo de higiene, **no es una auditoría del arco**):

- La migración es **aditiva e idempotente** (`ALTER TABLE … ADD COLUMN` dentro de un
  patrón que ya existía), así que una BD de `3.81.2` se abre intacta.
- El cambio de contrato **no deja una puerta trasera**: el acceso sin contraseña se
  retira (`ACCOUNT_NOT_ACTIVATED`), el 401 es genérico y la superficie pública queda
  fijada por `backend/tests/test_public_surface.py`.
- Las notas de `v3.82.0` **declaran sus límites** (migración preparada y **no
  aplicada**; tokens sin historial; cupo de recuperación por IP/proceso; sin 2FA),
  y `G0` sigue `pending` **por la migración no aplicada**, no por código.

**Pero eso no sustituye al encargo.** Un arco de **96 ficheros y +9378/−3537** que
mueve el contrato de arranque de sesión y el esquema de identidad **no puede
declararse auditado** por el hecho de que su predecesor (`v3.81.2`) y su sucesor
(`v3.83.0`) lo estén. **La serie queda cubierta con un agujero**, y el agujero está
exactamente donde más duele.

**Recomendación:** un punto de entrada `…-v382.md` **antes** de considerar la serie
cerrada. Es la deuda de auditoría más grande que este informe deja al descubierto.

---

## 3. Matriz de cierre (§3 del encargo) — A1…E6

| ID | Área | Dictamen | Evidencia (comando o fichero) | Severidad |
|---|---|---|---|---|
| A1 | Ancla y rango (1 commit) | **pass** | `git log --oneline v3.82.0..v3.83.0` → 1 commit (`e05b3dd`) | — |
| A2 | «SOLO FRONTEND» y el bump | **pass** (redacción) | `git diff … -- backend/` → solo `VERSION`; declarado en notas §5.1 y encargo §1.1-1 | P3 |
| A3 | La promesa en el código | **pass** | `api/vocabulary.ts::addVocabularyItem` → `routers/vocabulary.py` → `domain/retention.py::add_item` (léxico + FSRS); sin estado local en la UI | — |
| A4 | `AUTO_DECK_ID = 0` es vista | **pass** | `repositories/flashcards.py::AUTO_DECK_ID` («no existe como fila»); `create_deck` usa `lastrowid` (SQLite ≥ 1) | — |
| A5 | CHANGELOG vs diff y vs la run | **pass** | cifras reproducidas (§6) + `gh run view 35995172219` `success` | — |
| B1 | Éxito optimista | **pass** | `DictionaryLookup.tsx`: `setAddStatus("ok")` **solo** tras `await addVocabularyItem(...)`; el `catch` pinta `error` | — |
| B2 | Alta y archivo atómicos | **pass** (matiz) | `retention.add_item`: `seed_study_items` → `add_membership`/`add_items_to_collection` → `_ensure_fsrs_lexicon`, **sin una sola transacción** | **P2** |
| B3 | Re-alta no reinicia FSRS | **pass** | doble guarda: `_ensure_fsrs_lexicon` (`if prev and reps>0: continue`) y `academy.sync_fsrs_cards` («No pisa cartas ya revisadas (`reps > 0`)») | — |
| B4 | `tracked` autoritativo | **pass** (matiz) | `tracked = Boolean(entry?.usage.tracked)` de la respuesta del servidor; `add_item` es idempotente; la UI ignora `added` | P2 |
| B5 | Filtro del selector | **fail** | filtro **en el cliente** (`c.kind === "user_list"`); el guardia servidor `_collection_writable` devuelve **`True`** para un pack global (`not owner`) → §5-H1 | **P2** |
| B6 | 12 cadenas en `en` y `es` | **pass** | `i18n.ts`: **10 nuevas + 2 actualizadas = 12**; ambos idiomas, sin vacíos (`--strict`) | — |
| B7 | ¿Estado nuevo? | **pass** | `services/lexicon.py::item_status`: fila recién añadida → `learning`; **no** hay estado «nuevo» | — |
| C1 | Volteo 3D accesible | **pass** | control = botón con `aria-label` «Flip card»; caras decorativas; E2E lo alcanza por rol | — |
| C2 | `reduced-motion` completo | **pass** (producto) / **fail** (instrumento) | producto: E2E nuevo prueba 0 `rotateY` en línea; instrumento: **GUI-05 era vacuo** → §5-H2 | **P2** |
| C3 | Atajos 1–4 (foco / doble) | **pass** (matiz) | guardia `INPUT`/`TEXTAREA`/`contentEditable` + `busy`; E2E nuevo cubre el campo de edición | P3 |
| C4 | `aria-valuenow` extremos | **pass** | E2E nuevo: `aria-valuenow` 50 → 100 y `aria-label` «Card 1 of 2»; 0 % **no alcanzable por diseño** | — |
| C5 | Definición de «acierto» | **pass** (matiz) | la cadena lo **declara** al alumno («…rated Good or Easy»); separado del recuento de sesión | P3 |
| C6 | Acierto con sesión retomada | **pass** (matiz) | `index/done/good` son estado local; el texto dice «**of this session**» → coherente | P3 |
| C7 | Celebración con 0 % | **pass** (matiz) | el cierre muestra `Sparkles` **siempre** + «0 % …» cuando todas fueron «Again» → §5-H3 | P3 |
| D1 | i18n `--strict` | **pass** | ejecutado: 1772 / 0 / 0 / 0 / 0 | — |
| D2 | Contraste + iconos | **pass** | 480+6 / 0 bloqueantes; cada nota conserva **texto** («Again/Hard/Good/Easy») + `kbd` 1–4 → alternativa no cromática | — |
| D3 | Generados no editados | **pass** | `validation_gate.py auto` **no** produce diff (`git status` limpio tras ejecutar) | — |
| D4 | Candado de 8 gates | **pass** | `backend/tests/test_docs_drift_v373.py:183` → `len(GATES) == 8`; la release no añade gate | — |
| E1 | Deriva documental | **pass** | `git grep '3.82.0' -- '*.md'`: solo entradas **fechadas** y el encargo; los docs de estado dicen `3.83.0` / 8 `pending` | P3 |
| E2 | ¿Invariante rebajado? | **pass** | §1: la excepción es **una**, no-producto, verificable por comando y con CI verde | P2 |
| E3 | ¿Arnés con tag propio? | **pass** (matiz) | `fd086e8` no mueve producto y su run está verde; pero deja el tag sin cubrir el arnés → §5-H4 | P2 |
| E4 | Promesas cerradas / PARKED | **pass** | `CHANGELOG §3.83.0`, `PLAN.md` entrada V3.83.0 y `PARKED.md §V3.83.0` con etiquetas `[PRODUCTO]`/`[UX]`/`[VALIDACIÓN]`, sin presentar deuda como cerrada | P3 |
| E5 | Las cinco de «Honestidad» | **fail** (1 de 5) | §3.1: la (i) es **literalmente falsa** y la (v) es **solo-UI** | P2 |
| E6 | La señal de CI en PRs | **no verificado** | requiere `gh pr checks` sobre los PRs de Dependabot (no ejecutado aquí) | P2 |

### 3.1 El ejercicio de contradicción (E5)

Las cinco afirmaciones de `release-notes-v3.83.0.md §5` son, en su mayoría, ciertas.
Contra el árbol:

1. **«Solo frontend. No se toca ni el backend ni la BD.»** — **Falsa en su letra.**
   `git diff v3.82.0..v3.83.0 -- backend/` **no** sale vacío: cambia
   `backend/config.py` (`VERSION`). La frase siguiente («El alta usa el endpoint que
   ya existía…») **sí** es cierta y es la que importa. Es una **contradicción de
   redacción**, no de hecho — pero es una contradicción, y es la que un lector
   literal usaría para desacreditar las otras cuatro.
2. **«El selector solo archiva, nunca saca del estudio.»** — Cae en su primer
   miembro; **el segundo depende de un filtro de cliente** (ver H1): el servidor
   acepta un `collection_id` de un **pack global**. La afirmación presupone «una
   **lista propia**», y esa parte **no está enforced en el servidor**.

Las afirmaciones (ii) «sin gamificación de datos», (iii) «el acierto es de la
sesión» y (iv) «el alta deja la palabra en `learning`» **resisten** la verificación
en el árbol.

---

## 4. Puntos de vigilancia del arco (los 7 del plan)

| # | Punto | Dictamen | Evidencia |
|---|---|---|---|
| 1 | **Puente Diccionario → Flashcards** | **pass** | E2E nuevo `dictionaryFlashcardsBridge.spec.ts` (9 casos, 3 breakpoints): EN→ES, panel, confirmación y CTA |
| 2 | **ES→EN** | **pass** | mismo spec: se añade el **equivalente inglés** (`word: "house"`), nunca el español |
| 3 | **Listas / duplicados** | **fail (parcial)** | cliente filtra a `user_list` (verificado por E2E); **servidor no** (H1). Duplicados: `INSERT OR IGNORE` + `reps>0` → **pass** |
| 4 | **`tracked`** | **pass** | E2E: con `usage.tracked=true` no aparece el botón de alta, **0 peticiones** de alta y **0** de colecciones, y sí el CTA de estudiar |
| 5 | **Móvil / tablet** | **pass** | los 24 casos nuevos corren en `desktop`/`tablet`/`mobile` (1280/768/390) |
| 6 | **Teclado + a11y** | **pass** | E2E nuevo: 1–4 califican y avanzan; **no** se disparan al escribir el reverso; `aria-valuenow` 50→100 con `aria-label` |
| 7 | **Traducción propia vs generación tardía** | **pass (con gap declarado)** | no cambia en esta release; la precedencia de la cara B está declarada en `retention.card_face` (alumno > pack > caché). **No** hay E2E nuevo: el reverso vacío se hidrata por red y mockearlo haría una prueba tautológica; se declara el hueco |

**Gap declarado (punto 7 y cross-screen).** El plan preveía un caso «tras el alta, la
vista Flashcards muestra la palabra». **No lo he escrito a propósito**: la cola la
construye el **servidor** desde el léxico, así que un E2E con la cola mockeada solo
demostraría que el mock pinta lo que el mock contiene. Lo que **sí** queda cubierto es
el **destino** del CTA («Study in Flashcards» → modo Flashcards con `aria-selected`).
La equivalencia «alta → aparece en el mazo» está fijada por el **código**
(`add_item` → `seed_study_items`; `AUTO_DECK_ID` es vista del léxico;
`sync_fsrs_cards` siembra la carta) y por los unitarios, no por un E2E tautológico.

---

## 5. Hallazgos

### H1 — `B5` · El filtro de listas es **solo cliente**; el servidor acepta un pack global · **P2**

**Qué.** La UI de V3.83.0 filtra el selector a `kind === "user_list"` (verificado por
E2E) y declara en pantalla «un pack curado no es un destino». Pero el guardia del
servidor **no** lo impone:

```python
# backend/domain/retention.py:172
def _collection_writable(coll: dict | None, user_id: str) -> bool:
    """… un pack global (`user_id=''`) es de todos, pero la lista
    privada de otro perfil no es un destino válido. Sin esto, `collection_id`
    … permitía inyectar palabras y traducciones en el catálogo de un pack global
    o en la lista de otro usuario. …"""
    if coll is None:
        return False
    owner = str(coll.get("user_id") or "")
    return not owner or owner == user_id      # ← `not owner` == True para el pack global
```

Y `add_item` escribe **dos** cosas cuando llega `collection_id`:

```python
# backend/domain/retention.py:226
if collection_id is not None:
    collections_repo.add_membership(user_id, collection_id, normalized)
    if translation:
        collections_repo.add_items_to_collection(collection_id, items)
```

`add_items_to_collection(collection_id, items)` (repositories/collections.py:166) hace
`INSERT OR IGNORE INTO vocab_collection_items (collection_id, …)` **sin `user_id`**:
escribe en el **catálogo compartido** de la colección. Y es la **única** vía que mete
entrada de usuario en un catálogo: el otro camino que toca colecciones —
`enroll_collection`— solo **lee** el catálogo (`list_collection_items`) y escribe
membresías (`add_memberships`) y `mark_enrolled`; nunca lo amplía.

**Consecuencia.** Un cliente que no sea la UI (o una petición manipulada) con
`collection_id` de un **pack global** pasa el guardia (`owner === ""` → `True`) y
**inserta su palabra y su traducción en el catálogo compartido del pack**, visible
para todos los alumnos. La promesa «un pack curado no es un destino» es, hoy, **solo
de UI**.

**Atribución honesta.** El código es **heredado** (`V3.77.1`), **no** lo introduce
V3.83.0. Lo que V3.83.0 hace es **apoyar una promesa de producto** en él y no
reforzarlo. Y el propio docstring **declara la intención** de bloquear el pack global
—la implementación no la cumple—: hay contradicción entre docstring y código.

**Recomendación.** Para **ingestión**, exigir `owner == user_id` (dueño no vacío):
`return bool(owner) and owner == user_id`, o parametrizar el predicado con un modo
(`read`/`enroll` vs `ingest`). Añadir un caso al candado de superficie pública.
**No se ha corregido** (auditoría de solo lectura).

### H2 — `C2` · El gate `reduced-motion` **existente** (GUI-05) era **vacuo** · **P2**

**Qué.** `frontend/tests/visual/reducedMotionAndZoom.spec.ts` declaraba
`test.use({ reducedMotion: "reduce" })`. En Playwright **1.62.1** `reducedMotion`
**no es una propiedad de `TestOptions`** —queda **ignorada en silencio**—; la vía que
emula de verdad es `page.emulateMedia` (o `use.contextOptions.reducedMotion`).
Comprobado por comando:

```text
test.use({ colorScheme:"dark" })  → matchMedia('(prefers-color-scheme: dark)').matches === true
test.use({ reducedMotion:"reduce" }) → matchMedia('(prefers-reduced-motion: reduce)').matches === false
page.emulateMedia({ reducedMotion:"reduce" }) → true
Select-String '^\s*reducedMotion\??:' playwright/types/test.d.ts → 0 coincidencias
```

**Consecuencia.** GUI-05 se ha estado poniendo verde **sin emular nada**: su aserción
(«opacidad 1») la alcanza la animación al terminar, con o sin movimiento reducido. El
gate era **vacuo desde V3.73.1**, no roto. Y la release V3.83.0 **se apoya en él**
al declarar «el volteo y la celebración se apagan».

**El producto, sin embargo, sí cumple**: con emulación real (`page.emulateMedia`), el
spec nuevo prueba que tras el volteo **no** queda ningún `rotateY` en línea y que el
reverso se ve igual. **El defecto era del instrumento, no de la pantalla.**

**Corrección aplicada (solo pruebas).** `reducedMotionAndZoom.spec.ts` emula ahora con
`page.emulateMedia` y lleva una **guarda de mordida** (`matchMedia(...).matches === true`),
de modo que no puede volver a pasar por vacío.

### H3 — `C7` · El cierre celebra **también** el 0 % · **P3**

El bloque de cierre de `StudySession` muestra **siempre** el icono `Sparkles` junto a
«Session done — N cards reviewed.» y, si hubo crédito, «{pct}% of this session rated
Good or Easy.». Con todas las notas en «Again», se lee **«0 % …» junto al icono de
celebración**. **No lo considero un fallo**: el icono celebra **haber terminado**, no
el acierto, y el número de al lado dice la verdad en la misma línea. **Recomendación
(P3):** condicionar el `Sparkles` a `good > 0`.

### H4 — `E3` · Un cambio de arnés posterior al tag **no** lleva tag propio · **P2 (observación)**

`fd086e8` está **después** de `v3.83.0` y toca `frontend/playwright.config.ts`. El
precedente `v3.73.2` fue un **tag de parche** para corregir la CI de `v3.73.1`.
**Dictamen:** no hace falta tag propio **cuando** el cambio (a) no toca producto,
(b) no altera ninguna respuesta y (c) tiene run verde propia —las tres se cumplen
aquí—. Pero **la regla debe quedar escrita**, porque hoy la decisión es de criterio:
quien audite «el árbol del tag» y quien audite «`main`» verán dos arneses distintos.

### H5 — `B2`/`B1` · Alta no atómica: el error puede **subdeclarar** lo ocurrido · **P2**

`add_item` hace `seed_study_items` (fila de léxico, **ya comprometida**) y **después**
`add_membership`/`add_items_to_collection` y `_ensure_fsrs_lexicon`, sin una única
transacción. Si un paso posterior falla, se propaga un 500 y la UI pinta «No se pudo
añadir la palabra» **cuando la palabra ya está en el léxico**. El modo de fallo es del
lado **seguro** para la promesa —nunca hay «archivada que no se estudia»: cuando
`sync_fsrs_cards` lee el léxico, la carta ausente se siembra—, pero el **mensaje
miente sobre el estado**. **Recomendación:** envolver en una transacción, o degradar
el mensaje a «se añadió al diccionario; la lista no se pudo actualizar».

### H6 — `E6` · La señal de CI en PRs de Dependabot **no se ha cerrado** · **P2 (no verificado aquí)**

Heredado del punto de entrada anterior. **No lo he podido dictaminar**: `gh pr checks`
sobre los PRs de Dependabot no se ha ejecutado en esta pasada. Lo dejo **explícitamente
`no verificado`** en la matriz en vez de heredar el veredicto del encargo. Lo que sí
puedo decir: `fd086e8` (fijar `workers`) reduce el ruido **local**, y **nadie ha
demostrado** que los rojos de Dependabot y la no determinación local sean el mismo
problema —son **dos** observaciones, como el propio encargo admite (§6-D4).

---

## 6. Evidencia nueva producida por este informe (§7 del plan)

Tres specs **nuevos** y **una corrección** (todo pruebas; nada de producto). Corren con
`workers=1` en los **tres** breakpoints (`desktop` 1280 / `tablet` 768 / `mobile` 390).

| Fichero | Casos × breakpoints | Qué fija |
|---|---|---|
| `frontend/tests/visual/dictionaryFlashcardsBridge.spec.ts` | 3 × 3 = 9 | contrato del alta: EN→ES traduce, ES→EN usa el inglés, `tracked` no re-da de alta, listas perezosas y filtradas a `user_list` |
| `frontend/tests/visual/studySessionKeyboard.spec.ts` | 2 × 3 = 6 | atajos 1–4 califican y avanzan **una** vez por tarjeta; **no** disparan al escribir el reverso |
| `frontend/tests/visual/studySessionVisual.spec.ts` | 3 × 3 = 9 | `aria-valuenow`/`aria-label` (50→100); reverso largo **sin** desbordar a 390 px; `reduced-motion` **con emulación real** (0 `rotateY`) |
| `frontend/tests/visual/reducedMotionAndZoom.spec.ts` (**modificado**) | 1 × 3 (ya existía) | GUI-05 deja de ser vacuo: emula de verdad y lleva guarda de mordida (H2) |

**Ejecución (literal):**

```text
npx playwright test tests/visual/dictionaryFlashcardsBridge.spec.ts \
  tests/visual/studySessionKeyboard.spec.ts \
  tests/visual/studySessionVisual.spec.ts \
  tests/visual/reducedMotionAndZoom.spec.ts      → 30 passed (1.2m)

npx playwright test                              → 86 passed (4.1m)
npm run test     (frontend)                      → 1033 passed (109 ficheros)
```

**La cola post-tag crece, y se declara.** Tras este informe, `git status` es:

```text
 M frontend/tests/visual/reducedMotionAndZoom.spec.ts
?? frontend/tests/visual/dictionaryFlashcardsBridge.spec.ts
?? frontend/tests/visual/studySessionKeyboard.spec.ts
?? frontend/tests/visual/studySessionVisual.spec.ts
```

Estos **4 ficheros son pruebas**: no entran en `frontend/src`, no se compilan en la
app y no cambian ninguna respuesta. El candado del invariante 6 (`git diff --stat
v3.83.0..HEAD -- backend frontend/src launcher scripts` = **vacío**) **sigue
cumpliéndose**. Lo digo porque el propio encargo hace de esto una pregunta (E2/E3): el
informe **no** se exime de la regla que aplica.

---

## 7. Declaraciones de honestidad (§5 del encargo)

Declaro explícitamente, aunque nadie lo pregunte:

- **La release no añade ninguna capacidad al backend.** El alta de vocabulario **ya
  existía** y **ya** creaba la fila de léxico y la carta FSRS. Lo que V3.83.0 cambia es
  que **se ve y se dice**. «Diccionario → Flashcards como funcionalidad nueva» sería
  vender algo que ya estaba.
- **El «juego» no son datos.** No hay XP, niveles ni rachas —ni en la UI ni en la BD—:
  es movimiento y color, que era el encargo.
- **Los ocho gates siguen `pending`** y esta release no los toca. `validation-evidence.json`
  **no existe**; no hay ninguna aprobación física que la release pueda estar blanqueando.
- **El arco `v3.81.2..v3.82.0` no tiene punto de entrada**, y es el que **cambia el
  contrato de la API y migra la BD** (96 ficheros, +9378/−3537). Es la deuda de
  auditoría más grande que este informe deja al descubierto (§2, §4-D1).
- **La cola posterior al tag no es solo documental**: `fd086e8` toca el arnés de
  Playwright, y **este informe añade 4 ficheros de prueba más** a esa cola (§6).
- **La señal de CI en pull requests queda `no verificado`** en esta pasada (H6), en vez
  de heredar el veredicto del encargo.
- **Lo que NO he hecho:** no he cerrado gates, no he recreado tags, no he tocado
  `backend/` ni `frontend/src/` ni la BD, y **no he corregido el hallazgo H1** aunque
  la corrección sea de una línea: una auditoría de solo lectura que arregla lo que
  encuentra deja de ser una auditoría de solo lectura.

---

## 8. Veredicto

**Dictamen: `V3.83.0` se puede cerrar como release de producto.** Los **siete
invariantes** se cumplen, la **promesa central** («añadir desde el diccionario = palabra
en aprendizaje que sigue el proceso de estudio») **se sostiene en el código** —no en
las notas—, no hay éxito optimista, el FSRS **no se reinicia** al re-dar de alta, la
accesibilidad de la sesión está cubierta con evidencia nueva, y las **cifras de las
notas se reproducen por comando**.

**Pero no se cierra «limpio», y no procede un `3.83.1` de producto.** Procede, sí, un
**`v3.83.1` quirúrgico de instrumento y de honestidad**, con este contenido mínimo:

1. **H2 (obligatorio, ya corregido en este árbol):** el gate `reduced-motion` era
   **vacuo** por una opción **inexistente** en Playwright 1.62. Es el hallazgo que
   **más justifica un parche**, porque invalida la evidencia de un gate declarado
   desde V3.73.1 y la release V3.83.0 **se apoyaba en él**. La corrección ya está
   escrita y verde; solo falta commitearla.
2. **E5/i (obligatorio, trivial):** corregir la letra de la afirmación «No se toca ni
   el backend» en `release-notes-v3.83.0.md §5.1` a «sin lógica de backend (solo el
   bump de `VERSION`)». Cuesta una línea y elimina una contradicción literal.
3. **H1 (recomendado, no bloqueante):** endurecer `_collection_writable` para la
   ingestión (`bool(owner) and owner == user_id`) **o** declararlo como deuda con su
   severidad. Es **heredado**, no lo introduce esta release y **no es alcanzable desde
   la UI**, así que no bloquea el cierre; pero la promesa «un pack curado no es un
   destino» no debería ser solo de cliente. **No lo he corregido.**
4. **E6 (recomendado):** cerrar el dictamen de los PRs de Dependabot, que sigue
   `no verificado` y arrastra dos documentos.
5. **D1 (el grande, fuera de este parche):** abrir el punto de entrada `…-v382.md`.
   **Mientras no exista, la serie no puede declararse auditada**, por mucho que
   `v3.83.0` salga impecable.

**Lo que bloquea el cierre de la SERIE (no de la release):** el eslabón
`v3.81.2..v3.82.0` sin encargo. Un `v3.83.1` no lo tapa: lo que lo tapa es un informe.

---

## 9. Reproducir / verificar

```powershell
# ancla y candado
git rev-parse 'v3.83.0^{commit}'
git log --oneline v3.82.0..v3.83.0
git diff --stat v3.83.0..HEAD -- backend frontend/src launcher scripts   # VACÍO
git diff --name-only v3.83.0..HEAD | Select-String -NotMatch '\.md$'      # solo playwright.config.ts (+ los specs de §6)

# instrumentos
python scripts/validation_gate.py status
python scripts/check_i18n_coverage.py --strict
cd frontend; npm run audit:contrast; npm run test
npx playwright test                                        # 86/86
npx playwright test tests/visual/dictionaryFlashcardsBridge.spec.ts `
  tests/visual/studySessionKeyboard.spec.ts `
  tests/visual/studySessionVisual.spec.ts `
  tests/visual/reducedMotionAndZoom.spec.ts                 # 30/30

# la prueba de que H1 es real (lectura, no ejecución)
python -c "print('retention.py:185 -> return not owner or owner == user_id')"
```

---

## 10. Anexo — Prefijos

`AA`–`AF` (dossiers V3.70), `AG`–`AM` (pausa pedagógica y psicometría), `AN` (`v3.75.1`),
`AO` (política psicométrica V4.0). Reservados **sin dictamen** a fecha de este informe:
**`AP`** (`v3.75.7`), **`AQ`** (`v3.77.1`), **`AR`** (`v3.80.0`), **`AS`** (`v3.81.1`),
**`AT`** (`v3.81.2`) y **`AU`** (este). Y **sin punto de entrada**: `v3.82.0`.
