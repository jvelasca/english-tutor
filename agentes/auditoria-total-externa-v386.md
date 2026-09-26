# Auditoría EXTERNA del producto — punto de entrada anclado a `v3.86.0`

> **Qué es este archivo.** El prompt **autocontenido** para que un auditor externo (que **solo ve
> el repositorio público** de GitHub) audite **la release `v3.86.0`**: una **minor** que por
> primera vez en este arco **migra la base de datos** —de forma aditiva e idempotente— y que
> **absorbe íntegro el delta de `v3.85.1`**, una versión que **nunca llegó a etiquetarse**. La
> revisión es **de solo lectura**: no se cambia código, datos, configuración ni etiquetas
> publicadas.
>
> **Por qué esta auditoría y por qué AHORA.** Porque este arco **cambia el modelo de datos** por
> primera vez en cinco releases, y lo hace en el punto donde el proyecto es más frágil: una
> **columna heredada que sigue viva** (`flashcard_cards.deck_id`) convive con una **tabla puente
> nueva** (`flashcard_deck_cards`) y **las dos dicen a qué mazo pertenece una ficha**. Todo lo
> demás de la release —significados múltiples, recordatorio en la cara B, salto del diccionario a
> la sesión— es visible y por eso es lo que se audita a sí mismo. Lo que hay que intentar tumbar
> es **(a)** si la migración es de verdad **idempotente** y su backfill **no se puede perder**,
> **(b)** si las dos verdades sobre la pertenencia **pueden divergir** y **cuál gana** en la cola,
> en el listado y al borrar un mazo, **(c)** si el contrato nuevo (`meanings`) **deja intacto** al
> cliente viejo, y **(d)** si el tag dice la verdad sobre **una** release cuando en realidad
> contiene **dos**.
>
> **Aviso de encuadre (léelo antes de puntuar).** El patrón de este proyecto es que las releases
> «sin migración» invitan a una auditoría blanda. Esta **sí migra**, y aun así tiene una trampa
> simétrica: como todo es **aditivo**, `check_release_consistency` pasa, el CI pasa y la BD vieja
> **se abre sin migrar nada**, así que la tentación es firmar «sin riesgo». No lo hagas. En una
> migración aditiva el riesgo **no** está en la columna que se añade: está en **(1) el backfill que
> se ejecuta una sola vez** y que, si no se ejecuta, deja a las fichas sin mazo **en silencio y
> para siempre** (la tabla ya existirá y el guard lo impedirá), y **(2) las dos fuentes de verdad**
> que la migración aditiva **deja conviviendo a propósito**. El bug clásico aquí no es «falla la
> migración»: es «la migración funcionó y aun así una ficha quedó en un mazo que el alumno había
> quitado».
>
> **Continuidad con los puntos de entrada vecinos — los cinco siguen vivos.**
> `agentes/auditoria-total-externa-v382.md` cubre el eslabón `v3.81.2..v3.82.0` (**contrato +
> migración**) y **sigue esperando su informe `AV`** —es la mayor deuda de auditoría de la serie—;
> `agentes/auditoria-cierre-global-v383.md` cubre el cierre de la serie V3.83.x y espera su informe
> **`AW`**; `agentes/auditoria-total-externa-v384.md` cubre `v3.83.1..v3.84.0` y espera su informe
> **`AX`**; `agentes/auditoria-total-externa-v385.md` cubre `v3.84.0..v3.85.0` y espera su informe
> **`AY`**. Este documento **no repite** ninguna de sus preguntas: las **hereda** y pregunta por el
> delta `v3.85.0..v3.86.0`.
>
> **Informe esperado:** `docs/audit/AZ-AUDITORIA-TOTAL-V386.md`. Prefijo **`AZ`** porque **es el
> primer prefijo libre** (ver la nota de prefijos en §8). El siguiente ya exigiría una convención
> nueva, y **eso es parte de lo que hay que dictaminar**: la cola de encargos abiertos no deja de
> crecer (§6-D6).
>
> **Estado del punto de entrada:** entregado 2026-09-26 en un **commit documental POSTERIOR al
> tag**, porque **un tag publicado no se recrea** (regla de `docs/audit/KIT-VALIDACION-GATES.md`).
> El ancla es `v3.86.0` y el producto **no se mueve** para entregar esto.

---

## 0. Cómo arrancar (auditor con contexto nuevo)

Orden de lectura recomendado, de marco a evidencia:

1. `docs/RELEVO.md` — **cabecera**, y en particular las **dos notas** (`V3.86.0` y `V3.85.1`), en
   ese orden. La de `V3.85.1` lleva la **errata**: esa versión **no existe como tag**.
2. `release-notes-v3.86.0.md` — las notas **de la release**. Su **§8 «Honestidad»** declara
   **nueve** límites, y su punto **(ix)** es la confesión central de este encargo: la fusión de
   `v3.85.1`. Su §2 es la afirmación de producto que hay que intentar tumbar.
3. `release-notes-v3.85.1.md` — el documento **del delta absorbido**. Léelo **con su errata en
   cabecera**: no describe un tag, describe **un tercio de este tag**. Sirve para saber **qué parte
   de `v3.86.0` no es de `v3.86.0`**.
4. `docs/audit/AY-AUDITORIA-TOTAL-V385.md` — el informe de la auditoría **anterior**. Su **§9** es
   el addendum de disposición: los hallazgos `P0`/`P1` del arco `v3.84.0..v3.85.0` se declaran
   corregidos en el delta que este tag absorbe. **Es la primera vez que un informe previo se puede
   verificar contra el tag que auditas** (§2-B7 del encargo `AY`... comprueba que sigue en pie).
5. `backend/repositories/db.py` — **el núcleo de esta release**: la migración. Busca
   `flashcard_deck_cards` y `deck_cards_existed`. Es el fichero que decide si el backfill se
   ejecuta **una vez** o **nunca**.
6. `backend/repositories/flashcards.py` — donde vive la **pertenencia múltiple**: alta, borrado de
   pertenencia, dedupe de la cola y `delete_deck`.
7. `backend/services/dictionary_content.py` (`GENERATOR_VERSION`), `backend/domain/vocabulary.py`
   (`build` de `meanings`) y `backend/services/dictionary_reverse.py`
   (`match_pack_translation`) — **el contrato nuevo de significados**.
8. `frontend/src/features/vocabulary/DictionaryLookup.tsx` — **el alta** deja de estar suprimida
   por `usage.tracked`, entra el **selector de significado** (con el nombre propio **nunca**
   preseleccionado), el **panel multi-mazo** y la **cara B a mano**.
9. `frontend/src/features/vocabulary/FlashcardsScreen.tsx` — la pestaña **Fichas** (varios mazos,
   recordatorio editable y borrable) y el **guardia de cola obsoleta** (`queue.deck.id !== deck`,
   línea ~529).
10. `frontend/src/utils/studyFocus.ts` **y** `frontend/src/features/vocabulary/DictionaryScreen.tsx`
    (línea ~81) — el **recado de un solo uso** del diccionario a la sesión. Es el mecanismo más
    frágil del frontend de esta release (ver §2-F1).
11. `backend/tests/test_multi_deck_v386.py` (nuevo, **8 casos**) y las specs visuales que esta
    release **reescribió** (`flashcardsSmoke`, `dictionarySmoke`, `vocabularyRoutesReview`,
    `reviewSession`). Son las guardias; §2-G1 pide el experimento de reversión, no la opinión.
12. `docs/audit/PARKED.md` — **§V3.86.0** y **§V3.85.1** (con su errata): lo cerrado, lo que sigue
    abierto y la deuda heredada.
13. `CHANGELOG.md` (las entradas `3.86.0` y `3.85.1`) y `docs/audit/TEMPLATE.md` (formato del
    informe).

**Punto de partida git:**

```bash
git clone https://github.com/jvelasca/english-tutor
cd english-tutor
git fetch --tags
git log --oneline -5 main
git tag --list 'v3.85.1'      # DEBE estar vacío, y eso es parte del encargo (§2-A3)
```

---

## 0.1 El arco tiene UNA release etiquetada, un delta absorbido y un commit heredado

A diferencia de los puntos de entrada anteriores —cuyo rango contenía una o dos releases, cada una
con **su propio tag**—, aquí el rango contiene **una sola release etiquetada** y **dos deltas de
producto**:

```bash
git log --oneline v3.85.0..v3.86.0
# 929c684 release(v3.86.0): diccionario polisemico, ficha en varios mazos y recordatorio ...
# 6098d88 docs(audit): punto de entrada externo del arco v3.84.0..v3.85.0 (prefijo AY, ...)
```

Y el detalle que **este encargo quiere que dictamines**: de los **dos** commits del rango, **uno**
(`6098d88`) es **documental puro** —el punto de entrada `AY`—, así que el commit de release es
**uno solo** (`929c684`). Como el delta de `v3.85.1` **nunca se commiteó por separado**, ese único
commit de release contiene:

| Delta | Qué es | De dónde sale |
|---|---|---|
| `v3.85.1` (**absorbido**) | sesión de repaso que no se atasca, panel APRENDER con su CTA, accesibilidad y sello del contraste | `release-notes-v3.85.1.md` + `docs/audit/AY-AUDITORIA-TOTAL-V385.md §9` |
| `v3.86.0` (**el tag**) | diccionario polisémico, ficha en varios mazos, recordatorio, alta desbloqueada, salto al diccionario | `release-notes-v3.86.0.md` |

**La consecuencia de auditoría, dicha sin adornos:** **no existe un subrango** que aísle el patch de
la minor. El precedente `AY` declaraba con orgullo que «los **subrangos son limpios** y así se
declaran, porque es lo que permite auditar cada release sin desenredarla de la otra» (§0.1 de
`agentes/auditoria-total-externa-v385.md`). **Aquí eso no se puede cumplir**: el `git log` te dará
un solo commit y el `git diff` un solo diff. El delta de `v3.85.1` solo se puede **reconstruir
leyendo su documento de notas** y cruzando las líneas que cita contra el diff del tag. Es
exactamente la pérdida que §6-D1 pone a dictamen, y **es deliberada**: la alternativa era
**reconstruir a mano** un commit intermedio de ~15 ficheros con cambios intercalados a nivel de
*hunk*, y **verificarlo entero** (vitest + pytest + Playwright) para que el tag fuese auditable,
con el riesgo de publicar un tag intermedio **roto**. Se eligió **declarar** en vez de fingir.

Los **subrangos que sí existen** y son limpios:

```bash
git log --oneline v3.83.1..v3.85.0     # las releases anteriores, para situarte (no es tu alcance)
git log --oneline v3.86.0..main         # SOLO el commit documental de este encargo
```

`6098d88` es **documental puro** (`agentes/auditoria-total-externa-v385.md` y la noticia del encargo
en el relevo y el PARKED): **no toca producto** y por eso **no** es parte del cuerpo de la release,
pero **sí** aparece en el rango `v3.85.0..v3.86.0` de `git diff`. Quien audite «el diff del tag»
verá el diff acumulado de **63 ficheros** (`git diff --name-only v3.85.0..v3.86.0 | wc -l`); el
commit de release es **`929c684`**, y **62** de esos 63 ficheros son suyos: el que sobra es
documentación. Declararlo es parte del encargo, no una excusa.

**Por qué una sola release y no dos.** Porque `v3.85.1` **no se publicó** (§6-D1) y porque las dos
superficies se solapan (`features/vocabulary`): separarlas habría exigido inventar un estado
intermedio verificado. Si prefieres acotar el informe, **audita el delta de `v3.86.0` estricto**
—reconstruido desde `release-notes-v3.86.0.md`— y **declara que no auditaste el absorbido**; el
encargo se declaró para el tag completo.

---

## 1. Punto de entrada verificado (contra GitHub, no contra un árbol local)

```bash
git ls-remote --tags origin 'refs/tags/v3.86.0*'
# 1053ef5...  refs/tags/v3.86.0        <- el objeto tag ANOTADO
# 929c684...  refs/tags/v3.86.0^{}     <- el commit de release (el que hay que auditar)
git ls-remote --tags origin 'refs/tags/v3.85.1*'
# (sin salida: la versión NUNCA se etiquetó — §6-D1)
git rev-list -n 1 v3.86.0                            # 929c684: el commit de release
git cat-file -t v3.86.0                              # debe ser 'tag' (anotado)
git log -1 --format=%s v3.86.0                       # 'release(v3.86.0): ...'
git log --oneline v3.85.0..v3.86.0                   # 2 commits: 1 release + 1 documental
python scripts/check_release_consistency.py          # OK en los 6 orígenes
```

> *Nota para quien audite desde PowerShell:* `v3.86.0^{commit}` **se rompe** en PowerShell (el `^`
> se interpreta como escape y llega a lanzar un `-EncodedCommand` a `powershell`: reproducido
> durante la entrega de este documento). Usa `git rev-list -n 1 v3.86.0`, que es equivalente y
> funciona en cualquier shell. Este punto de entrada lo usa así a propósito.

### 1.1 Invariantes — los que se pueden cumplir, y solo esos

1. **El ancla es un tag anotado que apunta a su commit de release.** Si `git cat-file -t` devuelve
   `commit`, el punto de entrada está roto: el tag sería ligero y no llevaría su mensaje de release.
2. **El rango contiene un solo commit de release y un commit documental heredado.** Verificable con
   `git log --oneline v3.85.0..v3.86.0` (2 líneas) y con `git show --stat 6098d88` (solo
   `agentes/` y documentación; **cero** ficheros de `frontend/src`, `backend/` y `launcher/`).
3. **`v3.85.1` no existe como tag, en local ni en remoto, y eso está declarado en cuatro sitios.**
   Verificable:

```bash
git rev-parse --verify v3.85.1        # fatal: unknown revision
git ls-remote --tags origin 'refs/tags/v3.85.1*'   # (sin salida)
git grep -n "v3.85.1" v3.86.0 -- release-notes-v3.85.1.md | head -5
git grep -n "no existe como tag\|NUNCA se etiqueto\|nunca se etiquetó" v3.86.0 -- \
  release-notes-v3.86.0.md CHANGELOG.md PLAN.md docs/RELEVO.md docs/audit/PARKED.md
```

4. **La migración es aditiva e idempotente.** Nada se destruye y ejecutarla dos veces no cambia
   nada. Verificable (§2-B1 pide el experimento, no la lectura):

```bash
git diff --name-only v3.85.0..v3.86.0 -- backend/repositories/db.py     # 1 fichero
git grep -nE "DROP TABLE|DROP COLUMN|DELETE FROM flashcard|ALTER TABLE .* DROP" v3.86.0 -- backend
# (sin salida: no hay una sola operación destructiva)
```

5. **Los tres cambios de esquema son columnas nuevas con `NOT NULL DEFAULT`.** Verificable: en
   `db.py` aparecen `meanings_json` (en **las dos** cachés), `mnemonic` (en `flashcard_cards`) y la
   tabla puente `flashcard_deck_cards` con `PRIMARY KEY (card_id, deck_id)`.
6. **`flashcard_cards.deck_id` SIGUE EXISTIENDO.** Es la deuda estructural que la release declara
   (§6-D3). No busques una migración destructiva: **no la hay, a propósito**.

```bash
git grep -n "deck_id INTEGER NOT NULL" v3.86.0 -- backend/repositories/db.py
# flashcard_cards sigue con su columna; la tabla puente NO la sustituye en el esquema
```

7. **El contrato viejo sigue en pie.** `DictionaryEntryOut` conserva su forma y los endpoints
   legacy siguen respondiendo. Verificable con el `git diff` de `backend/schemas/vocabulary.py`: los
   cambios son **añadidos** (`DictionaryMeaningOut`, el campo `meanings`), no renombrados.
8. **La versión es consistente en los 6 orígenes.** `check_release_consistency.py` en `v3.86.0`
   informa `3.86.0` en los seis.
9. **Las guardias muerden.** Ni los 8 casos de `test_multi_deck_v386.py` ni el caso «una cola del
   mazo anterior que llega tarde no se come el arranque del mazo pedido» (`FlashcardsScreen.test.tsx`
   **unidad**, ~551) deben pasar por vacío: revertir el comportamiento tiene que **romperlos**
   (§2-G1 pide el experimento, no la opinión). **Ojo con las specs que esta release REESCRIBIÓ**:
   una spec cambiada para que pase es la forma clásica de convertir un rojo en verde sin arreglar
   nada.
10. **El CI certifica lo que dice certificar.** El run del commit de release está publicado y en
    `success` (§1.3). Pero **este proyecto tiene declarado que el CI no certifica estados
    intermedios de un mismo push** (invariante 9 del informe `AT`), y **aquí hubo UN solo push con
    DOS deltas**: la fusión hace que el run certifique `v3.85.1` y `v3.86.0` **juntos y ninguno por
    separado**. Está declarado en §6-D5 y **es una de las cosas que hay que dictaminar**, no un
    detalle de color.

### 1.2 Lista cerrada — los commits del arco

| Commit | Tipo | Qué es |
|---|---|---|
| `6098d88` | documental | Punto de entrada `AY` del arco anterior + noticia del encargo en el relevo y el PARKED. **Heredado**: entregado tras los tags `v3.84.1`/`v3.85.0`, cae dentro del rango |
| `929c684` | **release** | **`v3.86.0`** — diccionario polisémico, ficha en varios mazos y recordatorio. **Absorbe íntegro el delta de `v3.85.1`**, que nunca se etiquetó |

| Tag | Apunta a | ¿Anotado? |
|---|---|---|
| `v3.85.0` | `b1b502f` | sí (el ancla anterior) |
| `v3.86.0` | `929c684` | sí (el ancla de este encargo) |
| `v3.85.1` | **no existe** | — |

### 1.3 Estado de publicación (verificado por comando, no fijado a mano)

| Comprobación | Resultado |
|---|---|
| `git ls-remote --tags origin 'refs/tags/v3.86.0*'` | `v3.86.0` presente, **anotado** (`^{}` → `929c684`) |
| `git ls-remote --tags origin 'refs/tags/v3.85.1*'` | **sin salida** (no existe) |
| `git cat-file -t v3.86.0` | `tag` |
| CI en `929c684` (`v3.86.0`) | `success` — run `36256446832`, **12/12 jobs en verde** (`Backend`, `Frontend`, `Playwright E2E`, `Launcher` ×2, `Launcher Windows`, `Release consistency`, `Validation gate`, `Beta V3.0 gate`, `Content validation`, `Dependency audit`, `Product origin` ×2) |
| `main` vs `origin/main` | al día en el momento de entregar este documento (solo por delante el commit documental de este encargo) |
| Última versión declarada en `README.md` | `v3.86.0` |
| `docs/audit/validation-evidence.json` | **sigue sin existir** (§6-D2) |

### 1.4 Verificación que la release declara

| Comprobación | `v3.86.0` (minor, con migración) |
|---|---|
| `npx tsc --noEmit` | limpio |
| `npm run test` (vitest) | **1055/1055** (109 ficheros) |
| `python -m pytest -q` (backend) | **3157/3157** |
| `python -m pytest -q` (lanzador) | **269/269** |
| `python -m ruff check .` (en `backend/`, como el CI) | limpio |
| `python -m ruff check .` (en la **raíz**) | **1 hallazgo preexistente y ajeno** (§6-D7) |
| `check_i18n_coverage.py --strict` | **1797** cadenas · 0 huérfanas · 0 sin definir · 0 duplicadas · 0 vacías · 80 prefijos dinámicos |
| `contrast_audit.mjs --strict` | **480** pares medidos · **6** guardas OK · **0** fallos *enforced* · **17** fallos **reportados** que no bloquean (§6-D8) |
| `validation_gate.py auto --require-dist` | **10/10** checks (8 gates, todos `pending` por diseño) |
| `scripts.check_beta_v3` | OK (freeze pedagógico V2.7–V2.12) |
| `scripts.content_validation` | OK |
| `python -m scripts.transfer_validation` | OK (con avisos `advisory` preexistentes) |
| `npx playwright test` (barrido completo, 26 ficheros) | **116 passed · 0 failed · 34 skipped** (150 en total) |
| `check_release_consistency.py` | OK en los 6 orígenes |

> **Dos avisos sobre esta tabla, para que no la copies sin mirarla.**
> (a) El **34 skipped** de Playwright y el **8 gates `pending`** son los dos sitios donde un número
> verde puede esconder cobertura. Están en §2-G5 y §6-D2.
> (b) El **`ruff` limpio** es **del alcance del proyecto** (`backend/` y `lanzador/`), no de la
> raíz: el CI nunca ve el hallazgo de la raíz porque linta por `working-directory`. Está declarado
> en §6-D7 y la redacción «limpio en el alcance del proyecto» es lo que hay que dictaminar.

---

## 2. Preguntas falsables por área

Cada pregunta se responde con **un comando, un experimento o una lectura**, y cada veredicto debe
llevar su evidencia pegada en el informe. Las preguntas marcadas **[NÚCLEO]** son las que deciden
el dictamen.

### A. El ancla, el arco y la promesa

- **A1.** ¿El tag es anotado y apunta a su commit de release? ¿Y el mensaje del tag describe **su**
  release sin vender como propio lo que viene del delta absorbido?
- **A2.** El rango `v3.85.0..v3.86.0` contiene **dos** commits: uno documental heredado (`6098d88`)
  y uno de release. ¿Está declarado, y es aceptable, o el punto de entrada debería haber anclado en
  `v3.85.1` (que no existe) para que el diff fuese «de la release»?
- **A3. [NÚCLEO]** **`v3.85.1` nunca se etiquetó y no se recrea.** Es la decisión central de este
  encargo (§6-D1). Dictamina **la política**, no el hecho: la regla de la casa («un tag publicado no
  se recrea») **no aplica** aquí, porque **nunca hubo tag**. La pregunta real es: ¿era correcto
  **absorber** (`release-notes-v3.86.0.md` §8-ix, errata en cabecera de las notas de `v3.85.1`) o
  debió **reconstruirse** un commit verificado de `v3.85.1` y etiquetarlo **antes** de publicar
  `v3.86.0`? Compara con la pérdida concreta: **el delta del patch ya no es auditable por
  separado**, y el informe `AY` —que pedía correcciones **en `v3.85.1`**— no se puede verificar
  contra el tag que nombra. Mide el coste de la alternativa (los ~15 ficheros intercalados) y di si
  el intercambio fue razonable **o** si la casa se ha quedado sin la propiedad que `AY` §0.1
  consideraba valiosa («subrangos limpios»).
- **A4.** Este documento se entrega en un commit **posterior** al tag. ¿Es verificable el desfase
  (`git log --oneline v3.86.0..main`) y el rango del tag queda intacto y sin reescritura?
- **A5.** ¿`docs/audit/PARKED.md §V3.86.0` cubre **toda** la deuda que las notas declaran, y
  `§V3.85.1` conserva su errata? Busca un «cerrado» que no lo esté: es el defecto clásico de este
  proyecto.
- **A6.** El informe `AY` (`docs/audit/AY-AUDITORIA-TOTAL-V385.md`) declara su **§9** como addendum
  de disposición de sus `P0`/`P1`, «con el comando que la demuestra», y se compromete a que esos
  hallazgos se corrigen **en el delta absorbido**. **Verifícalo contra `929c684`**: los comandos del
  §9 ¿se cumplen hoy? Es la primera vez en este arco que un informe previo se puede **cerrar por
  comando** dentro del tag siguiente.

### B. La migración — el núcleo estructural (nuevo en este arco)

- **B1. [NÚCLEO]** **Idempotencia y backfill que se ejecuta UNA vez.** El `init_db` crea la tabla
  puente y hace el backfill **solo si la tabla no existía** (`deck_cards_existed`, `db.py:~2036`).
  Experimentos obligatorios, **sobre una copia** de una BD con datos:
  1. Arranca dos veces: ¿el segundo arranque cambia **una sola fila**? (`SELECT COUNT(*) FROM
     flashcard_deck_cards` antes y después).
  2. **Fuerza el caso que el guard no cubre:** crea la tabla a mano **vacía**, deja
     `flashcard_cards` con fichas y arranca. `deck_cards_existed` será `True` → **el backfill NO se
     ejecuta** → las fichas se quedan **sin ninguna pertenencia**. ¿Es alcanzable en la realidad
     (un `CREATE` que se commitea y un `INSERT` que no, un cierre a mitad de migración, un
     `KeyboardInterrupt`, un `SIGKILL`)? Si `CREATE` + `INSERT` **no** van en la misma transacción,
     el agujero es real y **silencioso**: la tabla existe y nadie vuelve a rellenarla. Dictamina con
     el código delante: ¿la migración es atómica?
  3. ¿Qué pasa si `flashcard_cards` está **vacía** y luego se importa un backup anterior? ¿El
     backfill se ejecuta, o el guard ya lo impidió para siempre?
- **B2.** El backfill copia **`SELECT id, deck_id, created_at FROM flashcard_cards`**. La tabla
  puente declara `deck_id INTEGER NOT NULL` y una `FOREIGN KEY` a `flashcard_decks`. `deck_id` en
  `flashcard_cards` es `NOT NULL`, así que no habrá NULLs — **compruébalo tú**—; pero la FK **no se
  aplica si `PRAGMA foreign_keys` está apagado** (SQLite por defecto). ¿Está encendido? Si no lo
  está, la FK es **decorativa** y lo único que impide una pertenencia a un mazo borrado es el código
  de `delete_deck`. Búscalo: `git grep -n "foreign_keys" v3.86.0 -- backend`.
- **B3. [NÚCLEO]** **`delete_deck` conserva las fichas compartidas y «lo dice».** Preguntas
  encadenadas, cada una con su experimento:
  - Una ficha en **dos** mazos, se borra **uno**: ¿la ficha sigue viva y sigue en el otro? ¿Qué
    dice la UI al alumno?
  - Una ficha en **un solo** mazo, se borra **ese** mazo: ¿se borra la ficha, o **sobrevive sin
    ninguna pertenencia**? Si sobrevive, **la UI de la pestaña Fichas no la puede alcanzar** (lista
    por mazo) y queda un **zombi de datos** que nadie ve y nadie limpia. Búscalo en la BD después
    del borrado: `SELECT * FROM flashcard_cards WHERE id NOT IN (SELECT card_id FROM
    flashcard_deck_cards)`.
  - ¿Y `flashcard_cards.deck_id` (la columna heredada) **qué valor tiene** tras borrar el mazo? Si
    sigue apuntando al mazo muerto, tienes una tercera fuente de verdad rota.
- **B4.** **Dedupe de la cola.** Una ficha en dos mazos, se estudian **los dos** en la misma sesión:
  ¿aparece **una** vez o **dos**? La release dice que deduplica. Reproduce con una ficha en 2 mazos
  y ambos seleccionados. Y la variante que importa: **¿la dedupe es por `card_id` o por
  `(card_id, deck_id)`?** Si es lo segundo, la misma ficha se estudia dos veces y el scheduler FSRS
  recibe dos calificaciones de la misma carta en la misma sesión — eso **corrompe el estado de
  repaso**, no solo la UI. Reproduce con el mazo automático **y** un mazo manual conteniendo la
  misma ficha.
- **B5. [NÚCLEO]** **Las dos fuentes de verdad de la pertenencia.** `flashcard_cards.deck_id` sigue
  existiendo **y** existe `flashcard_deck_cards`. Es la deuda estructural declarada (§6-D3). El
  encargo no pregunta si es bonito: pregunta **si pueden divergir y quién gana**.
  1. Enumera **todas** las lecturas de `flashcard_cards.deck_id` en el producto (`git grep -n
     "deck_id" v3.86.0 -- backend/repositories/flashcards.py backend/domain/flashcards.py`) y di,
     para cada una, si es **autoritativa** o **heredada y no usada**.
  2. Encuentra un camino que **escriba** una pertenencia **sin** actualizar `deck_id` (o al revés).
     El candidato natural: quitar la ficha del mazo que era su `deck_id` **original** y dejarla en
     otro. ¿`deck_id` se actualiza? Si no, ¿qué lee el que lea `deck_id`?
  3. `test_init_db_is_idempotent_and_backfills_only_once` cubre la migración, y
     `test_delete_deck_keeps_shared_cards_and_says_so` el borrado. **Ninguno de los dos nombres
     promete cubrir la divergencia**: escribe tú el experimento que la busca y di si la encuentras.
- **B6.** **Las dos cachés y sus filas viejas.** `meanings_json` se añade **a las dos** cachés
  (`dictionary_entries` y `dictionary_reverse_entries`) con `NOT NULL DEFAULT ''`. Una fila
  cacheada antes de `v3.86.0` queda con `''` y con `generator_version` viejo. Responde:
  - ¿Qué devuelve la API para `meanings_json = ''`? ¿`[]`, `null`, o una lista con un solo
    significado sintético? Y **¿el frontend aguanta las tres?** Prueba con una fila forzada a `''`
    y con `generator_version` de `1.4.0`.
  - **¿La invalidación es perezosa de verdad?** `GENERATOR_VERSION = "1.5.0"`: localiza la
    comprobación (`backend/domain/vocabulary.py:~2001`) y demuestra que una fila de `1.4.0` **se
    regenera al leerla**. Y la pregunta que muerde: si la regeneración **falla** (sin modelo, sin
    red, excepción del generador), ¿la ruta devuelve la fila **vieja** (honesto) o un **error**
    (rompe una palabra que funcionaba)? Busca el `try/except` de esa ruta.
  - ¿Hay **dos** rutas de lectura (directa e inversa) y **una** sola comprobación? Si la inversa no
    comprueba `generator_version`, la mitad de la caché queda envenenada en silencio.

### C. El contrato: `meanings` y el nombre propio

- **C1. [NÚCLEO]** **El nombre propio nunca se preselecciona.** Es una afirmación de producto
  (`release-notes-v3.86.0.md`) y una regla de corrección: marcar «London» como traducción de
  «Londres» para una tarjeta de vocabulario es un error pedagógico. Verifica **los dos lados**:
  - **Backend:** el `prompt` (`dictionary_content.py:~155`) pide `"proper_noun": true ONLY if that
    meaning is a proper noun`. ¿Los repos lo **normalizan** (`proper_noun: bool(...)`,
    `dictionary.py:~105`) o un `null`/`"false"`/`0` del generador se cuela como **verdadero**?
    Prueba a meter `"proper_noun": "false"` (string) y mira qué sale por la API.
  - **Frontend:** el selector **no** debe preseleccionar un nombre propio. Encuentra la lógica y
    **el caso límite que importa**: una palabra cuyos significados **son todos** nombres propios.
    ¿Qué se preselecciona? ¿El alumno puede **seguir adelante** (añadir la ficha) o queda
    **atrapado** con un selector que no ofrece nada y un botón que no se habilita? Ese es el modo de
    fallo: la regla correcta convertida en un **callejón sin salida**.
- **C2.** **Compatibilidad hacia atrás del contrato.** `DictionaryEntryOut` gana `meanings`. Un
  cliente de `v3.85.0` (o de la misma app antes de recargar la caché del navegador) envía y lee el
  contrato viejo:
  - ¿Sigue existiendo el campo **`translation`** en la respuesta y con el **mismo significado**
    (ahora derivado de `meanings[0]`)? Demuéstralo con el esquema y con una petición real.
  - ¿El **serializador** del frontend (`frontend/src/api/normalize.ts`) tolera `meanings` ausente,
    `null` y lista vacía **sin** romper la pantalla del diccionario? Es el mismo tipo de defecto que
    `AY` encontró en otro sitio: el backend añade un campo y el normalizador asume su forma.
  - Los **endpoints legacy** que la release conserva envueltos: ¿su **forma de respuesta** es
    idéntica a la de `v3.85.0`? Diffla el esquema entre los dos tags y **pega el diff**. Si añadiste
    campos al envoltorio legacy, un cliente viejo sigue funcionando, pero un test que compare
    diccionarios exactos **no** — y eso es una decisión, no un accidente.
- **C3.** **Prioridad de los pares curados.** `match_pack_translation` (`dictionary_reverse.py:~149`)
  da prioridad a los pares de los packs sobre lo generado. Dos preguntas con trampa:
  - ¿La prioridad es **total** o **por turno**? Si dos packs curados dan inglés **distinto** para el
    mismo término español (`tornillo` → `screw` / `bolt`), ¿qué sale? ¿Y es **determinista**
    (orden estable) o depende del orden de iteración de un `set`/`dict`?
  - `v3.86.0` **cambia la prioridad** respecto a `v3.85.0`. ¿El cambio está declarado en las notas
    como cambio **de producto** (una palabra puede **cambiar de traducción** sin que el alumno haga
    nada) o solo como mejora técnica? Si `lima` pasa a «lime» por la caché nueva, **una ficha
    existente puede quedar con un anverso que ya no coincide con el diccionario**: ¿está declarado?
- **C4.** **El tope de significados.** `dictionary_content.py:~107` declara un tope «más alto que el
  de `senses`». ¿Cuál es, **exactamente**, y qué pasa al superarlo: se recortan (¿por qué orden?) o
  se aceptan todos? Un recorte silencioso del significado correcto es peor que no tener
  significados múltiples.

### D. El alta desbloqueada

- **D1. [NÚCLEO]** **Se retira la supresión por `usage.tracked`.** Es un cambio de comportamiento
  visible y **la eliminación de una defensa**. Antes de celebrarlo, haz lo que el proyecto exige:
  **averigua contra qué protegía**. `git log -S "tracked" -- backend/routers/vocabulary.py` y el
  mensaje del commit que la introdujo. Si la guardia existía para evitar **duplicar** algo o
  **reintroducir** un estado que el alumno ya tenía, la pregunta es si la release lo reabre **y con
  qué lo sustituye**. Un candado que se quita sin sustituto es sospechoso aunque la UI quede más
  cómoda; un candado que se quita **porque su razón murió** debe demostrar que murió.
- **D2.** **La cara B a mano.** Sin traducción, el alumno **escribe** la cara B. Preguntas:
  - ¿Se **valida** algo? ¿Un `back` vacío o de un espacio se guarda? Una ficha con el reverso vacío
    es una tarjeta **rota** que el alumno descubrirá en mitad de una sesión. Búscalo: crea la ficha
    con `back: ""` por API y estudia.
  - ¿El **sentido** de la traducción (ES→EN vs EN→ES) se respeta al escribir a mano? Es decir: ¿el
    texto manual cae en la cara que le toca según la dirección del drill, o siempre en la misma?
- **D3.** **Panel multi-mazo: doble clic.** Con `PRIMARY KEY (card_id, deck_id)` e `INSERT OR
  IGNORE`
  el duplicado *parece* imposible, pero el encargo pregunta por la **UI**: dos `click` rápidos sin
  `await` sobre «Guardar», o sobre dos casillas distintas. ¿Se crean **dos fichas** (una por mazo,
  cuando debe ser **una** ficha en **dos** mazos), o dos peticiones crean dos fichas por la carrera
  entre el `POST` y el `PUT de pertenencias`? Es el defecto que `AY` encontró en el reintento de la
  tarjeta (B2 de aquel encargo): **compruébalo que sigue cerrado**.
- **D4.** **El CTA de estudio con el mazo elegido.** El alumno firma su alta y pulsa estudiar: ¿llega
  a la sesión del mazo **elegido** o del **automático**? Y con un mazo **vacío o sin pendientes**:
  ¿aterriza en ese mazo con su mensaje de vacío, o se queda en el panel **sin decir por qué**?
  (Encadena con F2.)
- **D5.** **No reabrir `v3.84.1`.** Aquel patch introdujo el estado parcial y el reintento solo de
  la tarjeta. Esta release **reescribe** el alta entera. Verifica la **no regresión** ejecutando el
  caso de `dictionaryFlashcardsBridge.spec.ts` sobre el código nuevo y **provocando el fallo** del
  `POST` de la tarjeta: ¿sigue declarando el estado parcial y ofreciendo el reintento?

### E. Ficha en varios mazos y recordatorio

- **E1. [NÚCLEO]** **Contrato ficha-primero.** `GET/POST/PATCH/DELETE /api/vocabulary/cards` + los
  `/decks/{id}/cards` **envueltos**. Lo que hay que dictaminar:
  - ¿La API **nueva** es la fuente de verdad y los envoltorios **delegan** en ella, o hay **dos
    implementaciones** que pueden dar resultados distintos? Compáralo: si el envoltorio tiene su
    propia consulta, es una duplicación y la pregunta es cuál de las dos tiene el dedupe.
  - `/api/vocabulary/cards` con `deck_ids` **vacío**: el `PATCH` declara que «si llega `deck_ids`, el
    conjunto no puede quedar vacío». ¿Qué código y qué mensaje devuelve? **Pruébalo**: es el borde
    entre «quitar de un mazo» (permitido) y «quitar de todos» (¿borra la ficha? ¿400?).
  - ¿El listado nuevo (`FlashcardCardsOut`) soporta **paginación o tope**? Un usuario con 5 000
    fichas: ¿la pestaña Fichas pide 5 000 de golpe? Si no hay tope, dilo (es deuda, no defecto).
- **E2.** **El recordatorio no rompe la sesión.** `mnemonic` se muestra en el reverso de
  `StudySession`. El encargo pide **probar la afirmación de que no altera la máquina de estudio**:
  `git diff v3.85.0..v3.86.0 -- frontend/src/features/vocabulary/StudySession.tsx` y di si el cambio
  es **render-only**. Si toca el estado (el orden de las caras, el contador, la calificación), la
  afirmación es falsa. Y el caso límite: una ficha con `mnemonic` vacío **no** debe dejar un hueco
  visible.
- **E3.** **Etiquetas de varios mazos.** Una ficha en 3 mazos: ¿3 etiquetas? ¿Puede quitarse una
  pertenencia **sin** borrar la ficha desde la UI (no solo por API)? Y la pregunta que muerde:
  **quitar la última pertenencia desde la UI** — ¿se bloquea, se avisa, o la ficha desaparece
  (dejando un zombi como en B3)?
- **E4. [NÚCLEO]** **El guardia de cola obsoleta, y su hueco complementario.** El efecto de
  arranque automático (`FlashcardsScreen.tsx:~528`) es:

```javascript
if (!autoStart || loading || !queue || queue.deck.id !== deck) return;
onAutoStarted();
```

  - Reproduce **la carrera que el comentario describe** (llegar del diccionario con un mazo manual
    mientras la primera carga era la del mazo automático) y comprueba que **antes** del guardia se
    arrancaba la sesión equivocada y **después** no. Si no lo puedes reproducir, el guardia es
    defensa sin defecto (dilo). **El candado que ya existe es de unidad**, no visual:
    `FlashcardsScreen.test.tsx:551`, «una cola del mazo anterior que llega tarde no se come el
    arranque del mazo pedido (V3.86.0)». **Aplícale el experimento de G1**: revierte el guardia y
    demuestra que ese caso **falla**. Un guardia sin candado que muerda es una intención.
  - **Y ahora el hueco:** si el mazo pedido **nunca** llega a coincidir, la función **no consume**
    `autoStart` (`onAutoStarted()` solo se llama en el camino que pasa el guardia). `autoStart` es
    estado y `deck` es la **selección actual** (cambia cuando el alumno elige otro mazo en la UI).
    Por tanto: ¿puede el alumno, **después** del encargo fallido, seleccionar **otro** mazo a mano y
    ver arrancar una sesión **que no pidió**? Diseña el experimento (deja el encargo apuntando a un
    mazo que no existe o sin cola, y luego selecciona un mazo con tarjetas) y **di si es alcanzable**.
    Si lo es, el guardia cerró la carrera y abrió una **sorpresa**.
  - ¿Y si el alumno navega **fuera** del diccionario con el encargo sin consumir? ¿`autoStart` muere
    con el desmontaje o sobrevive y dispara en la próxima visita?

### F. El salto incrustado al diccionario (el recado de un solo uso)

- **F1. [NÚCLEO]** **El recado se consume dentro de un inicializador de `useState`, y la app corre
  bajo `StrictMode`.** `DictionaryScreen.tsx:~81` hace
  `useState<StudyFocus>(() => { const pending = takePendingStudyFocus(); ... })`, y
  `takePendingStudyFocus()` **muta** el módulo (pone `pending = null`) — es un efecto secundario
  dentro de un inicializador. `frontend/src/main.tsx` monta la app bajo **`StrictMode`**, y en
  desarrollo React **invoca el inicializador dos veces**: la primera llamada **consume** el recado y
  la segunda recibe `null`. **Diseña el experimento**: monta `DictionaryScreen` bajo `StrictMode`
  (el proyecto ya lo hace en `frontend/src/features/account/AccountPages.test.tsx`, y su comentario
  explica que **es como corre la app de verdad en desarrollo**), llama antes a
  `setPendingStudyFocus(7)` y comprueba **si el salto sobrevive**. Si no sobrevive, la función
  **solo funciona en producción** y ningún test la cubre en el modo en que se desarrolla — un
  defecto que únicamente un test con `StrictMode` puede ver. Si sobrevive, explica **por qué**
  (¿React descarta el primer resultado pero no el efecto?), porque entonces la pregunta pasa a ser
  si el mecanismo es **correcto por accidente**.
- **F2.** **El mazo se conserva, y el caso vacío no debe mentir.** El recado lleva `deckId`.
  Compruébalo con un mazo **con** pendientes (arranca la sesión de ese mazo) y con un mazo **sin**
  pendientes o **vacío** (¿aterriza en ese mazo con su mensaje, o cae en «Estudiar» del automático
  sin decir nada?). Y con `setPendingStudyFocus()` **sin** argumento (`deckId = null`): ¿qué
  significa «estudiar sin mazo» y a dónde lleva?
- **F3.** `allowFlashcardsJump` solo lo activa `VocabularyRoutesPractice.tsx:44`. Es decir: **desde
  el diccionario de la ruta de práctica** se puede saltar; desde **los otros** hostings del
  diccionario (`QuizRoutePage` con otras configuraciones), ¿no? Enumera **todos** los puntos de
  montaje de `DictionaryLookup`/`DictionaryScreen` y di en cuáles **no** hay salto. Si la capacidad
  existe en uno y no en otros, ¿está declarado como decisión o es una asimetría heredada?

### G. Instrumento: candados, i18n, contraste y el CI como alcance

- **G1. [NÚCLEO]** **Los candados que esta release escribió —y los que reescribió.** Dos trabajos
  distintos:
  - **Los nuevos:** los **8** casos de `backend/tests/test_multi_deck_v386.py` y el caso de la cola
    obsoleta. Por **cada** uno: **revierte** la línea que protege en un clon de trabajo y demuestra
    que **falla**. Un test que pasa con el comportamiento viejo es un comentario caro.
  - **Los reescritos:** esta release **modifica** `flashcardsSmoke.spec.ts` (16 líneas),
    `dictionarySmoke.spec.ts`, `vocabularyRoutesReview.spec.ts` (144) y `reviewSession.spec.ts`
    (326). Una spec que se cambia para que pase es **exactamente** el mecanismo por el que un rojo
    se convierte en verde. Por **cada** spec tocada, di si cambió porque **el comportamiento cambió
    legítimamente** o porque **estaba en el camino**. Y un caso concreto que el diff delata: en
    `flashcardsSmoke.spec.ts` esta release **AÑADIÓ** un mock para `GET /api/vocabulary/cards`
    (~179) **sin quitar** el del envoltorio legacy (`/api/vocabulary/decks/{id}/cards`, ~182), con
    un comentario que declara que el legacy «sigue existiendo en el contrato (deprecado)». Pregunta:
    si la pestaña Fichas migró a la API nueva, **¿el mock viejo sigue cubriendo una llamada que ya no
    se hace** (cobertura muerta) **o sigue tapando que la vista llama a las dos** (contrato doble
    vivo)? Distinguirlo no es cosmético: decide si el envoltorio legacy tiene todavía un consumidor
    de producto.
- **G2.** `check_i18n_coverage.py --strict`: **1797** cadenas, **0** huérfanas, **0** sin definir,
  **0** duplicadas, **0** vacías, **80** prefijos dinámicos (el encargo `AY` declaraba 81 → 80).
  ¿Alguna cadena **retirada** seguía usándose de forma **dinámica** (construida por concatenación) y
  por eso no aparece como huérfana? Ese descenso de **un** prefijo dinámico es una cifra que merece
  una comprobación, no un encogimiento de hombros.
- **G3.** **Contraste: 0 bloqueantes, 17 reportados.** El informe (`contrast-report.json`) declara
  **480** pares medidos, **6** guardas en verde, **0** fallos *enforced* y **17** fallos
  **reportados** bajo el epígrafe «**Acento como relleno y como borde (reportado; decisión para
  V4.0.x)**» (`contrast-report.md:~231`). Localízalos y dictamina: ¿es una **decisión medida** (los
  pares de acento-relleno no son texto, y por eso AA no aplica) o un **defecto aplazado** que la
  palabra «reportado» blanquea? Y la pregunta de alcance: los rótulos **nuevos** de esta release
  (selector de significado, etiquetas multi-mazo, recordatorio), ¿**reutilizan** pares ya medidos o
  introducen combinaciones que **no** están en los 480?
- **G4.** **El `ruff` limpio y su alcance real.** Desde la **raíz**, `python -m ruff check .` reporta
  **1** hallazgo preexistente y ajeno (`scripts/purge_virtual_testers.py:198`, `DTZ005`) que el
  **CI nunca ve**, porque el job linta con `working-directory: backend` (y otro con `launcher`).
  Dictamina: una release que publica «`ruff` limpio en el **alcance del proyecto**» mientras la raíz
  tiene un hallazgo **¿informa o maquilla?** La respuesta depende de si el hallazgo es real (ábrelo)
  y de si la redacción lo declara (§6-D7).
- **G5.** **Los números verdes, reproduciéndolos.** Reproduce `1055/1055` (vitest, 109 ficheros),
  `3157/3157` (pytest backend), `269/269` (lanzador), `116 passed · 0 failed · 34 skipped`
  (Playwright) y `10/10` (validation gate). Y responde las dos que importan:
  - **¿Qué son los 34 skipped** de Playwright, y **alguno cubre una superficie que esta release
    tocó** (flashcards, diccionario, rutas)? Un `skip` que tapa la superficie de la release es
    cobertura falsa.
  - Los **8 gates** de validación siguen `pending` **por diseño** (§6-D2). Si los 8 están
    `pending`, ¿qué certifica el `10/10`? Nómbralo con precisión: son **checks automáticos**, no
    gates humanos, y la tabla debe decirlo así.

---

## 3. Matriz de cierre (la rellena el auditor)

| # | Área | Veredicto | Evidencia (comando + salida) |
|---|---|---|---|
| A | Ancla, arco y promesa | | |
| B | Migración: idempotencia, backfill y dos verdades **[NÚCLEO]** | | |
| C | Contrato `meanings` y nombre propio **[NÚCLEO]** | | |
| D | Alta desbloqueada: la defensa que se retira **[NÚCLEO]** | | |
| E | Varios mazos, recordatorio y cola obsoleta **[NÚCLEO]** | | |
| F | Recado de un solo uso bajo `StrictMode` **[NÚCLEO]** | | |
| G | Candados (nuevos y reescritos), i18n, contraste y alcance del CI | | |
| D1 | `v3.85.1` absorbida, no etiquetada (§6-D1) | | |
| D2 | Deriva del ancla de certificación, ya con 4 releases (§6-D2) | | |
| D3 | `flashcard_cards.deck_id` viva como segunda verdad (§6-D3) | | |
| D4 | El recordatorio no llega al mazo automático (§6-D4) | | |
| D5 | Un solo push certifica dos deltas (§6-D5) | | |
| D6 | Cola de auditoría atrasada, quinto encargo abierto (§6-D6) | | |
| D7 | El `ruff` de la raíz que el CI no ve (§6-D7) | | |
| D8 | 17 pares de contraste reportados y no bloqueantes (§6-D8) | | |

---

## 4. Reglas duras para el auditor

1. **Solo lectura.** No se modifica, etiqueta ni empuja nada del repositorio público. Los
   experimentos de reversión (G1), de migración (B1, B3) y de `StrictMode` (F1) se hacen en un
   **clon de trabajo** y se documentan; el resultado que vale es la salida del comando, no la
   magnitud del cambio.
2. **Los tags no se recrean.** Si encuentras que el tag dice algo falso, **no se arregla el tag**:
   se declara en el informe y se corrige hacia delante. Aquí hay un caso especial: `v3.85.1`
   **nunca se etiquetó**, así que la regla **no la protege** — y esa asimetría es justo lo de
   §6-D1.
3. **Ningún veredicto sin comando.** «Parece que», «debería», «en principio» no son veredictos. Si
   no pudiste comprobarlo, escribe **«no verificado»** y di por qué.
4. **Distingue no-verificado de falso.** Un informe que declara lo que no miró vale más que uno que
   opina sobre todo.
5. **Cuidado con PowerShell** (§1): el `^` rompe las expresiones de git y llega a lanzar un
   `-EncodedCommand` a `powershell`. Usa `git rev-list -n 1 <tag>`.
6. **Trabaja sobre una COPIA de la base de datos.** B1, B2, B3 y B6 destruyen o falsean datos por
   diseño. `backend/data/` está fuera del control de versiones y un `git clean` **no** lo protege:
   copia el fichero antes de tocar nada y dilo en el informe.
7. **No puntúes la migración aditiva como virtud.** El encargo no premia que «no rompa»: premia que
   dictamine si el **backfill se puede perder**, si las **dos verdades divergen** y si el
   **contrato viejo sigue vivo de verdad**.

---

## 5. Honestidad esperada del informe

Un informe aceptable para este proyecto:

- **Declara el entorno** (SO, versiones de node/python, si el barrido de Playwright se corrió
  completo o por ficheros, si la BD de prueba era **copia** o la de trabajo) y **el rango real** que
  auditó —incluido si decidió **no** auditar el delta absorbido de `v3.85.1` (§0.1).
- **Separa los dos deltas dentro del mismo tag** cuando el veredicto difiera: es perfectamente
  posible que el delta absorbido esté bien y el nativo no, o al revés. La ausencia de subrango
  **no** dispensa de separar el veredicto.
- **Nombra los modos de fallo encontrados con su reproducción** (pasos, resultado esperado,
  resultado obtenido) y **dice cuáles son silenciosos** (el backfill perdido, el zombi sin mazo, la
  divergencia de `deck_id`): un fallo silencioso vale más en el informe que tres ruidosos.
- **Dice qué NO miró** (rendimiento del `meanings` con caché fría, seguridad de sesión,
  accesibilidad completa, calidad pedagógica de los significados generados) sin fingir cobertura.
- **No inventa una nota global** si la casa no la pide; y si la pide, que sea la consecuencia de la
  matriz, no un resumen del ánimo.

---

## 6. Discrepancias declaradas a propósito (para que las dictamine)

Se declaran aquí, y no en las notas de release, porque **se descubrieron o se decidieron al margen
de la publicación**. Es el mecanismo que este proyecto usa para no reescribir la historia: la
discrepancia se **declara** y se dictamina.

- **D1. `v3.85.1` nunca se etiquetó, y su delta va dentro de `v3.86.0`.** El trabajo de `v3.85.1`
  (sesión de repaso que no se atasca, panel APRENDER con su CTA, accesibilidad, sello del contraste)
  se redactó y se verificó, pero **quedó en el árbol de trabajo sin commitear**: el `HEAD` público
  seguía en `v3.85.0` y `git rev-parse v3.85.1` **falla**. **No se recrea** (no hay tag que
  preservar, pero crear uno hoy con un estado reconstruido sería publicar algo que **nunca se
  verificó como unidad**). Se eligió **absorber**: el tag `v3.86.0` contiene los dos deltas y el
  rango `v3.85.0..v3.86.0` tiene **un solo commit de release**. Está declarado en cinco sitios:
  errata en cabecera de `release-notes-v3.85.1.md`, §8-ix de `release-notes-v3.86.0.md`, nota en la
  entrada `[3.85.1]` de `CHANGELOG.md`, errata en el bullet de `PLAN.md`, nota en `docs/RELEVO.md`
  y errata en `docs/audit/PARKED.md §V3.85.1`; además, `docs/audit/AY-AUDITORIA-TOTAL-V385.md` lleva
  una nota de cabecera para que sus referencias a `v3.85.1` se lean como «el delta absorbido por
  `v3.86.0`». **La pérdida, dicha sin adornos:** el informe `AY` declara sus `P0`/`P1` corregidos
  **en `v3.85.1`**, y **ese tag no existe**: la corrección **sí está** (dentro de `v3.86.0`) pero
  **no es auditable por separado**, y la propiedad que `AY` §0.1 valoraba («subrangos limpios») se
  ha perdido en este eslabón. **Pregunta:** ¿fue la decisión correcta, o debió reconstruirse el
  commit intermedio y etiquetarlo **antes** de publicar `v3.86.0`?

- **D2. La deriva del ancla de certificación ha crecido a CUATRO releases.**
  `docs/audit/KIT-VALIDACION-GATES.md` sigue re-congelado en **`v3.83.1`** (re-congelación del
  2026-09-24, `4ee32e5`) y `docs/audit/VALIDATION-RELEASE-V373.md` también; desde entonces se han
  publicado `v3.84.0`, `v3.84.1`, `v3.85.0` y `v3.86.0`. `docs/audit/validation-evidence.json`
  **sigue sin existir** y los **ocho** gates siguen `pending` **por diseño** (acción humana). Ya era
  la pregunta `§6-D1` del encargo `AX` y `§6-D1` del encargo `AY`; **esta release no la cierra**.
  Dictamina si la deriva es tolerable o si debe **re-congelarse el ancla** antes de seguir
  publicando — y ten en cuenta que **esta** release es la primera del arco que **migra la BD**:
  certificar un árbol de `v3.83.1` mientras se publican migraciones es la peor versión de esa deuda.

- **D3. `flashcard_cards.deck_id` sigue viva y es una segunda fuente de verdad.**
  Es una decisión **declarada** (migración aditiva y no destructiva) y una deuda estructural: la
  pertenencia de una ficha vive **en la tabla puente** y **en la columna heredada**, y las dos
  pueden divergir. **Pregunta:** ¿es aceptable convivir con las dos durante N releases, o debería
  haberse hecho la parte destructiva (migrar y **quitar** la columna, o convertirla en un espejo
  escrito **siempre** por el mismo punto) en la **misma** release aditiva? Nótese que la ventana de
  convivencia es donde vive el bug silencioso de §2-B5.

- **D4. El recordatorio no llega al mazo automático.** La ficha del mazo automático (una vista del
  léxico) **no** puede llevar mnemónico. Está declarado en la honestidad de las notas. Es un límite
  de producto con una consecuencia concreta: el alumno que estudia desde el mazo automático —el
  camino por defecto— **no ve nunca** el recordatorio. Dictamina si el límite es aceptable o si la
  función nace ya a medio camino.

- **D5. Un solo push certifica DOS deltas.** Este proyecto tiene declarado (invariante 9 del informe
  `AT`) que **el CI solo certifica el tip del push** y no estados intermedios; por eso las releases
  anteriores se publicaron en **pushes separados**, cada una con su run. Aquí, al absorber `v3.85.1`
  en `v3.86.0`, **hubo un solo push** (`929c684` + el tag): el run `36256446832` certifica los dos
  deltas **juntos**, y **ninguno por separado**. El candado por invariante que la casa usa
  («un run verde por release») **no se puede aplicar**. Dictamina: ¿es una consecuencia aceptable de
  la fusión o refuerza que la fusión fue la decisión equivocada (§6-D1)?

- **D6. La cola de auditoría sigue atrasada y este encargo es el QUINTO abierto.** Pendientes de
  informe: **`AV`** (`v3.82.0` — el eslabón que **cambió el contrato de `POST /api/session`** y
  **migró la BD**), **`AW`** (cierre de la serie V3.83.x), **`AX`** (`v3.84.0`) y **`AY`**
  (`v3.84.0..v3.85.0`). `AZ` llega **antes** que el único que toca contrato, y **antes** que el
  informe que este encargo cita como prueba (`AY` §9). No es un defecto de producto: es una **deuda
  de proceso**, y se declara para que el informe pueda dictaminar **el orden**.

- **D7. El `ruff` de la raíz que el CI nunca ve.** `python -m ruff check .` desde la **raíz** reporta
  **1** hallazgo preexistente y ajeno (`scripts/purge_virtual_testers.py:198`, `DTZ005`), idéntico al
  que ya existía en el árbol de `v3.85.0`. El CI **no lo ve** porque sus jobs de lint corren con
  `working-directory: backend` y `launcher`. Las notas dicen «`ruff` limpio en el **alcance del
  proyecto**». Dictamina si esa redacción **declara el subconjunto** o lo maquilla, y si el CI debería
  lintar la raíz.

- **D8. El contraste publica 17 pares que no cumplen AA y no bloquean.**
  `docs/audit/generated/contrast-report.json` declara **480** pares medidos, **6** guardas en verde,
  **0** fallos *enforced* y **17** fallos **reportados** bajo el epígrafe «**Acento como relleno y
  como borde (reportado; decisión para V4.0.x)**» (`contrast-report.md:~231`). La decisión —separar
  el acento-**relleno** del acento-**texto**— está justificada en un comentario del CI y aplazada a
  V4.0.x. Dictamina si es una **decisión medida** o un **defecto aplazado** con nombre prudente, y si
  los rótulos nuevos de esta release caen dentro o fuera de los 480 pares.

---

## 7. Alcance

**`v3.86.0` — el delta nativo (diccionario polisémico + fichas en varios mazos + recordatorio).**

- **Migración:** `backend/repositories/db.py` — `meanings_json` en **las dos** cachés
  (`dictionary_entries`, `dictionary_reverse_entries`), `mnemonic` en `flashcard_cards`, tabla puente
  `flashcard_deck_cards` con `PRIMARY KEY (card_id, deck_id)` + índice, y el backfill con guard
  `deck_cards_existed`.
- **Significados:** `backend/services/dictionary_content.py` (**prompt** + `GENERATOR_VERSION`
  `1.4.0` → **`1.5.0`**), `backend/services/dictionary_reverse.py` (`match_pack_translation`),
  `backend/domain/vocabulary.py` (construcción de `meanings` y comprobación de versión),
  `backend/repositories/dictionary.py` (normalización con `proper_noun`),
  `backend/schemas/vocabulary.py` (`DictionaryMeaningOut`, `meanings` en `DictionaryEntryOut`).
- **Fichas y mazos:** `backend/repositories/flashcards.py`, `backend/repositories/collections.py`
  (`delete_deck` conservando compartidas), `backend/domain/flashcards.py`, `backend/domain/retention.py`,
  `backend/routers/vocabulary.py` (**`/api/vocabulary/cards`** GET/POST/PATCH/DELETE + pertenencias +
  **envoltorios legacy**).
- **Frontend:** `features/vocabulary/DictionaryLookup.tsx` (selector de significado, panel multi-mazo,
  cara B a mano, retirada de la supresión por `usage.tracked`), `FlashcardsScreen.tsx` (pestaña
  Fichas, recordatorio editable y borrable, guardia de cola obsoleta),
  `StudySession.tsx` (recordatorio en el reverso), `features/routes/QuizRoutePage.tsx` +
  `features/vocabulary/VocabularyRoutesPractice.tsx` (`allowFlashcardsJump`),
  `utils/studyFocus.ts` (**nuevo**), `DictionaryScreen.tsx` (consumo del recado),
  `api/{client,vocabulary,normalize}.ts`, `types/api.ts`, `utils/i18n.ts`.
- **Pruebas:** `backend/tests/test_multi_deck_v386.py` (**nuevo**, 8 casos) y la actualización de
  `test_dictionary_content_v330`, `test_dictionary_reverse_v339`, `test_flashcards_v378`,
  `test_senses_v344`, `test_situational_cue_v338`; en el frontend, `DictionaryLookup.test.tsx`,
  `DictionaryScreen.test.tsx`, `FlashcardsScreen.test.tsx`, `StudySession.test.tsx`,
  `ReviewToday.test.tsx`, `wordDrill.test.tsx` y las specs visuales `flashcardsSmoke`,
  `dictionarySmoke`, `dictionaryFlashcardsBridge`, `vocabularyRoutesReview`, `reviewSession`.

**Delta absorbido de `v3.85.1`** (declarado en `release-notes-v3.85.1.md`; **no** auditable por
separado): `features/vocabulary/ReviewToday.tsx` y `wordDrill.tsx`, `scripts/contrast_audit.mjs` y
sus pruebas/specs.

**Absorbido también, y declarado:** `docs/audit/AY-AUDITORIA-TOTAL-V385.md` (el informe `AY`, que
era su deliverable y **seguía sin commitear**), `release-notes-v3.85.1.md` y una línea de higiene en
`.gitignore` (`.ruff_cache/`).

**Lo que NO toca:** `DECISION_POLICY_VERSION`, `CURRICULUM_VERSION` (sigue `1.3.1`),
`LISTENING_BANK_VERSION`, las evaluaciones, el número o la definición de los gates, y la
**consolidación léxico ↔ ficha manual** (sigue aparcada).

**No hay operación destructiva de BD**: la migración es **aditiva e idempotente** y una BD anterior
se abre sin migrar nada.

**Punto de entrada al detalle:** `docs/audit/PARKED.md §V3.86.0` y `§V3.85.1` (con errata),
`docs/RELEVO.md`, `release-notes-v3.86.0.md` y `release-notes-v3.85.1.md` (con errata).

---

## 8. Nota de prefijos y cierre

Los prefijos `AP`, `AQ`, `AR`, `AS`, `AT`, `AU` (`v3.83.0`, dictaminado), `AV` (`v3.82.0`,
**pendiente**), `AW` (cierre V3.83.x, **pendiente**), `AX` (`v3.84.0`, **pendiente**) y `AY`
(`v3.84.0..v3.85.0`, **pendiente**) están **reservados** por encargos anteriores. **`AZ` es el
primer prefijo libre** y es el que corresponde a este informe.

Y una consecuencia que el propio `AY` dejó anunciada: «el siguiente sería `AZ`, y a partir de ahí
habría que decidir una convención nueva». **Ese momento es ahora.** Con `AZ` se agota el alfabeto de
dos letras que la casa venía usando (`AA`…`AZ`), la cola de encargos abiertos **ha crecido a cinco**
(§6-D6) y la convención actual —un prefijo por encargo, reservado a mano— **ya no escala**. El
informe `AZ` **debe dictaminar la convención**: no basta con que sea correcto; tiene que decir **cómo
se nombra el siguiente**.

**Cierre.** Este documento es un **encargo**, no un informe. No declara que nada esté bien: declara
**qué hay que intentar tumbar** y con qué instrumento. Si una afirmación de las notas de release no
se puede verificar, el informe debe decirlo; si se puede y es falsa, el informe debe decirlo **con la
salida del comando delante**. Y si el instrumento no permite verificar algo —porque el subrango no
existe (§0.1)— el informe debe decir **exactamente qué se perdió al no existir**.
