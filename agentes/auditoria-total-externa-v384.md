# Auditoría EXTERNA del producto — punto de entrada anclado a `v3.84.0`

> **Qué es este archivo.** El prompt **autocontenido** para que un auditor externo
> (que **solo ve el repositorio público** de GitHub) audite **la release Responsive
> global, mazos estándar y ruta de aprendizaje**: la release que arregla el **recorte
> silencioso** de botones en pantallas estrechas, permite **elegir/crear el mazo
> manual** al añadir una palabra desde el diccionario, y multiplica el vocabulario
> estándar de **3 packs de 25 palabras a 15 packs de 40–60**. La revisión es **de solo
> lectura**: no se cambia código, datos, configuración ni etiquetas publicadas.
>
> **Por qué esta auditoría y por qué AHORA.** Por dos motivos, y ninguno es «compila».
> **(1) Es la primera release del proyecto cuyo defecto reportado no era de pintura sino
> de *clase***: el botón se recortaba porque vivía en un contenedor `overflow-hidden`
> sin envoltura, y ese mismo patrón estaba en **ocho** sitios más. Lo que hay que
> dictaminar no es si el botón se ve, es **si se arregló la clase o solo el síntoma**.
> **(2) Introduce contenido de autoría** (~650 entradas léxicas nuevas) y **una política
> de duplicación declarada** (una palabra añadida a un mazo manual queda en el léxico
> **y** como tarjeta). Las dos cosas son fáciles de vender como «más y mejor» sin que
> nadie mire si el modelo de datos sostiene lo que la UI promete.
>
> **Aviso de encuadre (léelo antes de puntuar).** Esta release **no** cambia el contrato
> de la API, **no** migra la BD y **no** añade endpoints: eso invita a una auditoría
> blanda porque «no hay nada que romper». No la hagas. **48 ficheros, +2995/−210**, de
> los cuales **11 son de producto** (`frontend/src`) y **15 son contenido**
> (`backend/curriculum/vocab_packs/*.json`). El riesgo no está en el runtime, está en
> **(a)** tres afirmaciones de UI que la nota de release hace sobre el modelo de tarjetas
> y **(b)** la calidad de un contenido que ningún test puede validar salvo por su forma.
>
> **Continuidad con los puntos de entrada vecinos — los tres siguen vivos.**
> `agentes/auditoria-total-externa-v382.md` cubre el eslabón `v3.81.2..v3.82.0`
> (contrato + migración) y **sigue esperando su informe `AV`** —es la mayor deuda de
> auditoría de la serie—. `agentes/auditoria-total-externa-v383.md` cubre
> `v3.82.0..v3.83.0` y produjo el informe **`AU`**. Y
> `agentes/auditoria-cierre-global-v383.md` cubre el **cierre de la serie V3.83.x** y
> espera su informe **`AW`**. Este documento **no repite** ninguna de sus preguntas: las
> **hereda** y solo pregunta por el delta `v3.83.1..v3.84.0`.
>
> **Informe esperado:** `docs/audit/AX-AUDITORIA-TOTAL-V384.md`. Prefijo **`AX`**
> porque **es el primer prefijo libre**: `AA`–`AF` los ocupan los dossiers de V3.70,
> `AG`–`AM` la pausa pedagógica y psicometría, `AN` el arco de `v3.75.1`, `AO` la
> política psicométrica de V4.0, y **`AP` (`v3.75.7`), `AQ` (`v3.77.1`), `AR`
> (`v3.80.0`), `AS` (`v3.81.1`), `AT` (`v3.81.2`), `AU` (`v3.83.0`, dictaminado),
> `AV` (`v3.82.0`, pendiente) y `AW` (cierre V3.83.x, pendiente) siguen reservados**.
> Ver la nota de prefijos en §8.
>
> **Estado del punto de entrada:** entregado 2026-09-25 en un **commit documental
> POSTERIOR al tag `v3.84.0`**, porque **un tag publicado no se recrea** (regla de
> `docs/audit/KIT-VALIDACION-GATES.md`). El ancla sigue siendo `v3.84.0` y el producto
> **no se mueve** para entregar esto; el invariante que lo demuestra está declarado y se
> comprueba por comando (§1.1, invariante 8).

---

## 0. Cómo arrancar (auditor con contexto nuevo)

Orden de lectura recomendado, de marco a evidencia:

1. `docs/RELEVO.md` — **cabecera**, y en particular la **nota `V3.84.0`**.
2. `release-notes-v3.84.0.md` — las notas **de la release que se audita**. Su **§8
   «Honestidad»** declara **seis** límites, y cada uno es una pregunta encubierta.
3. `frontend/src/features/vocabulary/DictionaryLookup.tsx` — **el núcleo de la
   release**: el cluster que se recortaba y el panel de alta que ahora elige mazo.
4. `frontend/tests/visual/layoutHelper.ts` y `responsiveOverflow.spec.ts` — **la guardia
   nueva**. Es el artefacto que decide si el defecto puede volver.
5. `frontend/src/features/vocabulary/wordDrill.tsx`, `frontend/src/app/Header.tsx`,
   `StudySession.tsx`, `FlashcardsScreen.tsx`, `DictionaryScreen.tsx`,
   `AddVocabSection.tsx`, `PersonalDictionary.tsx` — **el resto de la clase**.
6. `backend/curriculum/vocab_packs/` — **los 15 packs**, y
   `backend/tests/test_vocab_packs_content.py` — **lo único que los valida**.
7. `backend/repositories/collections.py` (`ensure_theme_packs_seeded`) — **el sembrado
   idempotente por `slug`**, que es lo que hace innecesaria la migración.
8. `frontend/src/features/vocabulary/FlashcardsScreen.tsx` (filtro de la ruta) y
   `frontend/src/api/normalize.ts` — el consumo de `collection_id`.
9. `frontend/src/utils/i18n.ts` — las cadenas nuevas (selector/creación de mazo y
   filtros), en `en` y `es`.
10. `docs/audit/KIT-VALIDACION-GATES.md` — **el desfase de ancla declarado** (§6-D1):
    la planilla de campo sigue apuntando a `v3.83.1` y esta release publica producto.
11. `CHANGELOG.md` (la entrada `3.84.0`) y `docs/audit/TEMPLATE.md` (formato del informe).

**Punto de partida git:**

```bash
git clone https://github.com/jvelasca/english-tutor
cd english-tutor
git fetch --tags
git log --oneline -5 main
```

---

## 0.1 El rango tiene DOS commits, y uno NO es el release

A diferencia del punto de entrada de `v3.83.0` —cuyo rango era un solo commit—, aquí el
rango **arrastra un commit documental heredado** del cierre de la serie anterior:

```bash
git log --oneline v3.83.1..v3.84.0
# 9296c1f release(v3.84.0): responsive global, mazos estandar y ruta de aprendizaje ...
# b9baa8d docs(audit): entrega el cierre global de la serie V3.83.x (sintesis interna, encargo externo AW y re-congelacion del ancla en v3.83.1)
```

`b9baa8d` es **documental puro** (4 ficheros `.md`, +914/−1): entrega el entregable de
cierre de la serie V3.83.x que había quedado **sin trackear**, incluido el encargo `AW`
y la re-congelación del ancla. **No toca producto.** Se declara aquí y en §6-D2 porque
**quien audite «el diff del tag» verá 48 ficheros y esperará 44**: los otros cuatro son
este documento heredado, y ninguno está en `frontend/src`, `backend/` ni `launcher/`.

---

## 1. Punto de entrada verificado (contra GitHub, no contra un árbol local)

```bash
git ls-remote --tags origin 'refs/tags/v3.84.0*'   # debe existir el tag y su ^{}
git rev-list -n 1 v3.84.0                           # el commit al que apunta (el de release)
git cat-file -t v3.84.0                             # 'tag' (anotado, no ligero)
git log -1 --format=%s v3.84.0                      # 'release(v3.84.0): ...'
python scripts/check_release_consistency.py         # OK en los 6 orígenes
```

> *Nota para quien audite desde PowerShell:* `v3.84.0^{commit}` **se rompe** en PowerShell
> (el `^` se interpreta como escape). Usa `git rev-list -n 1 v3.84.0`, que es equivalente
> y funciona en cualquier shell. Este punto de entrada lo usa así a propósito.

### 1.1 Invariantes — los que se pueden cumplir, y solo esos

1. **El ancla es un tag anotado que apunta al commit de release.** Si `git cat-file -t`
   devuelve `commit`, el punto de entrada está roto: el tag sería ligero y no llevaría
   mensaje de release.
2. **Fuera de `curriculum/` y `tests/`, el único cambio en `backend/` es la línea de
   `VERSION`.** Verificable:

```bash
git diff --stat v3.83.1..v3.84.0 -- backend/config.py
# backend/config.py | 2 +-   (VERSION = "3.83.1" -> "3.84.0")
git diff --name-only v3.83.1..v3.84.0 -- backend | grep -v 'curriculum/\|tests/'
# solo: backend/config.py
```

3. **No hay endpoints nuevos ni cambio de contrato.** El diff de `backend/routers/`,
   `backend/domain/` y `backend/repositories/` debe estar **vacío**:

```bash
git diff --name-only v3.83.1..v3.84.0 -- backend/routers backend/domain backend/repositories
# (sin salida)
```

4. **No hay migración de BD.** El diff de `backend/db.py` y de cualquier `ALTER TABLE`
   debe estar **vacío**; los packs se siembran por `slug` en
   `repositories/collections.py::ensure_theme_packs_seeded`, que es idempotente.
5. **Los 15 packs cumplen forma, `slug` único, 40–60 ítems y unicidad de palabras.**
   Verificable con el test **y** por comando (§1.3). *Nota:* el test valida **forma**, no
   calidad léxica ni traducción correcta (ver §2-D).
6. **Nada de `launcher/` ni de la superficie de red se toca:**

```bash
git diff --name-only v3.83.1..v3.84.0 -- launcher scripts .github
# (sin salida)
```

7. **Los ocho gates siguen `pending` y `validation-evidence.json` no existe.** Esta
   release **no** registra evidencia ni mueve el número de gates.
8. **El producto no se mueve para entregar este documento.** El commit de entrega es
   **posterior** al tag y **solo añade `.md`**; el commit al que apunta `v3.84.0`
   (`git rev-list -n 1 v3.84.0`) no cambia.

### 1.2 Lista cerrada — los commits del rango `v3.83.1..v3.84.0`

| Commit | Tipo | Contenido |
|---|---|---|
| `9296c1f` | release | La release `v3.84.0` (producto + contenido + versión + docs) |
| `b9baa8d` | docs heredado | El cierre de la serie V3.83.x que quedó sin trackear (§0.1) |

Ninguno más. Si `git log --oneline v3.83.1..v3.84.0` devuelve más líneas, algo se coló.

### 1.3 Estado de publicación (verificado por comando, no fijado a mano)

```bash
git diff --stat v3.83.1..v3.84.0 | tail -1
# 48 files changed, 2995 insertions(+), 210 deletions(-)

git diff --stat v3.83.1..v3.84.0 -- frontend/src        # producto:  11 ficheros, +542/-131
git diff --stat v3.83.1..v3.84.0 -- frontend/tests      # pruebas:    4 ficheros, +264/-57
git diff --stat v3.83.1..v3.84.0 -- backend/curriculum  # contenido: 15 ficheros, +763/-5
git diff --stat v3.83.1..v3.84.0 -- backend/tests       # pruebas:    1 fichero,  +107
git diff --stat v3.83.1..v3.84.0 -- backend/config.py frontend/package.json frontend/package-lock.json
# versión: 3 ficheros, +4/-4
# (el resto —14 ficheros— es documentación: README, CHANGELOG, PLAN, RELEVO, PARKED,
#  KIT/VALIDATION, los informes generados y release-notes-v3.84.0.md)
```

**Contenido, contado por comando (no por la nota):**

```bash
python - <<'PY'
import json, subprocess, pathlib
def count(rev):
    files = subprocess.run(['git','ls-tree','-r','--name-only',rev,'backend/curriculum/vocab_packs'],
                           capture_output=True, text=True).stdout.split()
    files = [f for f in files if f.endswith('.json')]
    per = {}
    for f in files:
        blob = subprocess.run(['git','show',f'{rev}:{f}'], capture_output=True,
                              text=True, encoding='utf-8').stdout
        per[pathlib.Path(f).name] = len(json.loads(blob).get('items', []))
    return len(files), sum(per.values()), per
print('v3.83.1', count('v3.83.1')[0:2])   # 3 packs,  75 items
print('v3.84.0', count('v3.84.0')[0:2])   # 15 packs, 725 items
PY
```

**i18n, leído de los informes generados de ambos tags:** `defined` pasa de **1772** a
**1780** (+8 neto), con **0 huérfanas / 0 usadas sin definir / 0 duplicadas**.

### 1.4 Verificación que la release declara

`tsc --noEmit` limpio · `vitest run` **1036/1036** (109 ficheros) · `ruff` limpio ·
`pytest` **3140/3140** · i18n `--strict` **1780** cadenas · contraste **480 pares + 6
guardas / 0 bloqueantes** · `validation_gate.py auto --require-dist` **10/10** ·
**barrido Playwright COMPLETO: 90 passed · 0 failed · 30 skipped** · `check_release_consistency`
OK en los 6 orígenes. **No lo aceptes por la nota:** cada cifra es reproducible desde el
árbol del tag (§4).

---

## 2. Preguntas falsables por área

Cada pregunta se responde **con el código o con un comando**, no con la nota de release.

### A. El ancla, el rango y la promesa

- **A1.** ¿`v3.84.0` es un tag **anotado** que apunta a `9296c1f`, y `9296c1f` es el
  único commit de release del rango? ¿Se sostiene el invariante 8 (el commit de entrega
  solo añade `.md`)?
- **A2.** ¿El diff **no** toca contrato, esquema ni `launcher/` (invariantes 3, 4 y 6)?
  Si algo se coló, ¿está declarado?
- **A3.** La release se declara **«con backend y frontend»**, pero el backend que cambia
  **no es lógica**: es `VERSION` y **datos** (`curriculum/`). ¿Es esa una descripción
  honesta, o «con backend» sugiere un cambio que no existe?
- **A4.** ¿La entrada `3.84.0` de `CHANGELOG.md`, la nota `V3.84.0` de `docs/RELEVO.md`,
  `docs/audit/PARKED.md §V3.84.0` y `release-notes-v3.84.0.md` dicen **lo mismo**? Señala
  cualquier divergencia de cifras (packs, ítems, tests, cadenas).

### B. La clase del defecto responsive (el núcleo)

- **B1.** El botón se recortaba por `overflow-hidden` + cluster sin `flex-wrap`. ¿Se
  arreglaron **todos** los sitios de esa clase, o queda alguno con el mismo patrón?
  Recorre `frontend/src` buscando clusters `flex` **sin** `flex-wrap` dentro de
  contenedores con `overflow-hidden` y dictamina si la lista de la release está completa.
- **B2.** ¿`expectInsideClippingAncestor` **muerde**? Es decir: si se revierte el arreglo
  del botón, ¿el test **falla**? Si no muerde, la guardia es decorativa y esta es la
  pregunta más importante del documento.
- **B3.** ¿`expectNoHorizontalOverflow` detecta **scroll horizontal real** (el de
  `wordDrill`) y **no** el recorte silencioso? Es decir: ¿son dos defectos distintos y
  hacen falta las **dos** comprobaciones? Si una basta para los dos, la otra es ruido.
- **B4.** El spec nuevo cubre 320 px en un `describe` propio que **se salta en dos de los
  tres proyectos**. ¿Se está midiendo 320 px de verdad, o el `skip` deja el ancho sin
  cobertura en la práctica?
- **B5.** ¿La guardia usa `viewport` real o depende de datos mockeados? Si depende de
  mocks, **¿qué clase de desborde no puede ver nunca?**

### C. Diccionario → mazo manual (el cambio de producto)

- **C1.** La duplicación es **declarada**: la palabra entra en el léxico (y por tanto en
  «Mi diccionario») **y** como tarjeta manual. ¿Es coherente con el modelo de datos
  (`AUTO_DECK_ID = 0` como vista del léxico vs `flashcard_cards` como filas)? ¿Hay algún
  camino en que las dos copias se **desincronicen** y la UI diga algo falso?
- **C2.** ¿Qué pasa si la creación del mazo **tiene éxito** y la de la tarjeta **falla**
  (o al revés)? ¿Queda un estado intermedio que la UI no declara? Es la misma clase de
  hallazgo que **H5** (`add_item` no atómico) que sigue abierto.
- **C3.** El éxito declara **las dos cosas** y «Estudiar en Flashcards» abre **ese** mazo
  (`onOpenFlashcards(deckId)` → `StudyFocus.deckId` → `focusDeckId`). ¿El mazo que se abre
  es **realmente** el elegido, o hay un caso (mazo creado en línea, mazo borrado entre
  medias, `focusNonce` repetido) en que abre otro?
- **C4.** Al **retirar** el archivado en listas desde el diccionario, ¿queda alguna
  referencia muerta (clave i18n huérfana, prop sin uso, test que ya no prueba nada)? El
  barrido Playwright cazó una (`dictionaryFlashcardsBridge`); ¿había más?
- **C5.** ¿El nuevo panel respeta **accesibilidad** (etiqueta del `select`, `aria` del
  input de creación en línea, foco) y **es** i18n en `en` **y** `es`, sin literales
  sueltos?

### D. El contenido de los packs (lo que ningún test valida)

- **D1.** ¿Los 12 packs nuevos tienen `slug` único **entre** ellos y **frente** a los 3
  antiguos? ¿El `title`/`title_es` se corresponde con el `slug` (lo que el test
  `test_vocab_packs_content.py` comprueba) o hay un pack cuyo título y contenido no
  cuadran?
- **D2.** ¿Qué pasa con **palabras repetidas entre packs** (p. ej. una palabra en `home` y
  otra vez en `city`)? El test garantiza unicidad **intra-pack**; ¿el sembrado crea dos
  colecciones con la misma palabra, y eso es un problema o una decisión?
- **D3.** El test **quitó** una comprobación de «traducción != palabra» por falsos
  positivos con préstamos (`hotel`, `bonus`). ¿Quedan entradas donde `translation` sea
  idéntica a `word` y sean **error** en vez de préstamo? Cuéntalas y dictamina.
- **D4.** ¿El sembrado es **idempotente** en el caso real (arrancar dos veces, con los
  packs ya insertados a medias)? ¿Qué pasa si un pack **encoge** o cambia un ítem entre
  versiones: se actualiza, se duplica o se ignora? **Esa política no está declarada en la
  nota** y es la deuda más silenciosa de esta release.
- **D5.** Calidad léxica: muestrea 3 packs al azar y dictamina si las 40–60 entradas son
  realmente del tema, con `pos` correcto y traducción aceptable. El proyecto **declara**
  que esto no está validado; lo que se pide es **cuantificar** el hueco, no negarlo.

### E. La ruta genérica y el instrumento

- **E1.** El filtro Todas / por pack / por lista reutiliza `collection_id` de la cola
  FSRS. ¿El filtro se aplica **en el servidor** (cola) o filtra en cliente? ¿Los contadores
  («N pendientes») se recalculan con el filtro o mienten?
- **E2.** ¿El filtro por **lista** expone `kind === "user_list"` y **no** los packs
  curados, coherente con la frontera que fijó `v3.83.0`?
- **E3.** **La deriva de ancla (D1 de §6).** `KIT-VALIDACION-GATES.md` y
  `VALIDATION-RELEASE-V373.md` declaran que el árbol a certificar es `v3.83.1`, pero
  `v3.84.0` **publica producto** (UI + contenido). ¿Es sostenible certificar sobre
  `v3.83.1`, o esta release **obliga** a una nueva re-congelación? Dictamínalo.
- **E4.** ¿Se respetó la **lección de V3.81.1** (un renombrado de i18n obliga a lanzar el
  barrido visual **completo**)? El retirar el panel de listas **es** un renombrado de
  facto: ¿la nota declara que se corrió el barrido entero? ¿Los **30 skipped** son los
  declarados solo-desktop, o hay skips nuevos que esconden cobertura perdida?

---

## 3. Matriz de cierre (la rellena el auditor)

| # | Comprobación | Esperado | Resultado | Evidencia |
|---|---|---|---|---|
| 1 | `git cat-file -t v3.84.0` | `tag` | | |
| 2 | `git log --oneline v3.83.1..v3.84.0` | 2 líneas (§1.2) | | |
| 3 | Invariante 2 (`backend/` fuera de currículum/tests) | solo `config.py` | | |
| 4 | Invariante 3 (sin routers/domain/repositories) | diff vacío | | |
| 5 | Invariante 4 (sin migración) | diff vacío | | |
| 6 | Invariante 5 (15 packs, 40–60, únicos) | test verde | | |
| 7 | Invariante 6 (`launcher/`, `scripts/`, `.github/`) | diff vacío | | |
| 8 | Invariante 7 (8 gates `pending`, sin evidencia) | sin `validation-evidence.json` | | |
| 9 | Invariante 8 (entrega solo `.md`) | `rev-list -n 1 v3.84.0` intacto | | |
| 10 | B1 (clase completa) | sin sitios pendientes | | |
| 11 | B2 (`expectInsideClippingAncestor` muerde) | falla al revertir | | |
| 12 | B4 (320 px se mide de verdad) | medido, no saltado | | |
| 13 | C2 (estado intermedio mazo/tarjeta) | dictamen | | |
| 14 | C3 (el foco abre el mazo correcto) | dictamen | | |
| 15 | D1 (slug/título coherentes) | dictamen | | |
| 16 | D3 (traducción == palabra) | recuento | | |
| 17 | D4 (política de evolución del pack) | declarada o hueco | | |
| 18 | D5 (muestreo de calidad léxica) | 3 packs | | |
| 19 | E1 (filtro en servidor y contadores) | dictamen | | |
| 20 | E3 (deriva de ancla) | dictamen | | |
| 21 | E4 (barrido completo y `skipped`) | dictamen | | |
| 22 | §1.4 reproducible | 1036 / 3140 / 1780 | | |

---

## 4. Reglas duras para el auditor

1. **Todo veredicto con comando.** Si una afirmación no se puede reproducir con un
   comando o una lectura de código citada por fichero y línea, no es un veredicto.
2. **No puntúes por la nota de release.** `release-notes-v3.84.0.md` es **parte a
   auditar**: sus cifras y su §8 «Honestidad» son afirmaciones, no evidencia.
3. **Distingue «no lo hace» de «lo declara».** Esta release **declara** duplicación,
   autoría acotada y 320 px nuevo. Lo que se dictamina es si la declaración es **correcta
   y suficiente**, no si el producto es perfecto.
4. **La guardia se prueba revirtiendo.** Un test de layout que no falla al reintroducir
   el defecto **no es** una guardia (es la lección de H2/`reducedMotion` en `v3.83.1`:
   un gate que pasaba **sin emular nada**). Si no puedes revertir, dilo y baja el
   veredicto.
5. **No reabras lo ya dictaminado.** `AU` juzgó `v3.82.0..v3.83.0`; `AV` y `AW` están
   pendientes sobre otros arcos. Este documento solo cubre `v3.83.1..v3.84.0`.
6. **Contenido: mide, no opines.** «Las traducciones podrían ser mejores» no es
   dictamen; «de 725 entradas, N tienen `translation == word` y son préstamos, M son
   errores» sí.

---

## 5. Honestidad esperada del informe

El informe `AX` debe declarar **al menos**:

- Qué **no** pudo verificar y por qué (si el tag no está publicado, dilo y **no**
  improvises sobre un árbol local).
- Si **`expectInsideClippingAncestor` muerde** o no, con el resultado de haberlo probado.
- Su dictamen sobre **la clase B1** (cerrada o parcial) y, si es parcial, **qué sitios**
  faltan.
- Su dictamen sobre **D4** (evolución de un pack ya sembrado), que la release **no**
  declara y que es el hueco más silencioso.
- Su dictamen sobre **E3** (deriva de ancla: ¿certificar sobre `v3.83.1` o re-congelar
  en `v3.84.0`?).
- Veredicto explícito: **apta / apta con reservas / no apta**, con la lista de bloqueantes
  separada de la de deuda aceptada.

---

## 6. Discrepancias declaradas a propósito (para que las dictamine)

- **D1 · La deriva de ancla.** `docs/audit/KIT-VALIDACION-GATES.md` y
  `docs/audit/VALIDATION-RELEASE-V373.md` declaran que el árbol a certificar es
  **`v3.83.1`**; esta release publica **producto** (UI + contenido). El proyecto tiene
  precedente de re-congelar cuando se mueve el producto (`v3.81.0` → `v3.83.1`). **Esta
  release NO re-congela**, y eso se declara como posible deuda: ¿debe moverse el ancla a
  `v3.84.0` antes de arrancar la campaña, o el contenido/UI de `v3.84.0` no invalida las
  condiciones de campo? **Dictamen del auditor.**
- **D2 · El rango arrastra un commit documental.** `b9baa8d` (§0.1) es el cierre de la
  serie V3.83.x entregado **dentro** del rango. No toca producto, pero explica el
  desfase 48 vs 44 ficheros.
- **D3 · La duplicación es deliberada.** Añadir a un mazo manual deja el ítem en el
  léxico **y** como tarjeta. Es el precio de no compartir el modelo de tarjetas; la UI lo
  declara. Lo que se pide es si el **estado intermedio** (C2) está cubierto.
- **D4 · El contenido no está validado por calidad.** El test valida **forma**. La nota lo
  declara. Se pide **cuantificar**, no negar.
- **D5 · 320 px es un ancho nuevo.** El plan avisaba de que podía revelar más defectos
  de los enumerados. La nota dice que se cerraron los que aparecieron. ¿Queda alguno?
- **D6 · La nota afirma «~650 entradas nuevas».** El comando de §1.3 lo confirma:
  **725 − 75 = 650**. Se declara para que no haya que fiarse de la nota.

---

## 7. Alcance

**Dentro:** el delta `v3.83.1..v3.84.0` —el responsive y su guardia, el alta en mazo
manual y su cableado de foco, los 15 packs y su sembrado, el filtro de la ruta genérica,
i18n, y las afirmaciones de `release-notes-v3.84.0.md`, `CHANGELOG.md` (entrada `3.84.0`),
`docs/RELEVO.md` (nota `V3.84.0`) y `docs/audit/PARKED.md §V3.84.0`—.

**Fuera:** todo lo anterior a `v3.83.1` (heredado: `AU` dictaminó `v3.83.0`; `AV` y `AW`
siguen pendientes sobre `v3.82.0` y el cierre V3.83.x), la ejecución de los ocho gates
(campaña física, no auditoría de escritorio) y la deuda ya aparcada **H1** (`P2`,
`_collection_writable` devuelve `True` para un pack global), **H5** (`add_item` no
atómico) y **H3** (`Sparkles` celebra el 0 %), que se **heredan** sin reabrirse.

---

## 8. Nota de prefijos y cierre

Los prefijos `AP`, `AQ`, `AR`, `AS`, `AT`, `AU`, `AV` y `AW` están **reservados** por
puntos de entrada previos (con informe recibido los tres primeros son históricos; `AU` ya
se dictaminó). **`AX` es el primer prefijo libre** y es el que corresponde a este informe.

**Una frase para el auditor, y es la que decide esta release:** aquí no hay que preguntar
si el botón se ve. Hay que preguntar si, **revertido el arreglo, el test falla** —porque
si no falla, esta release no ha arreglado una **clase** de defecto: ha movido un botón de
sitio y ha escrito un documento que dice que hay una guardia.
