# Release notes — English Tutor v3.91.0

**Fecha:** 2026-09-29 · **Tipo:** release **DE PRODUCTO** (minor) · **Versión de app:**
`3.90.0 → 3.91.0`

**Con backend y frontend, CON migración de BD aditiva e idempotente** (columna plegada
`translation_fold` + tabla virtual FTS5 de contenido externo + tres disparadores + guarda de
reconstrucción), **SIN endpoints nuevos** y **SIN cambio de contrato incompatible** (el contrato de
acepción crece con campos **aditivos**), **CON bump de `GENERATOR_VERSION`** (`1.6.0 → 1.7.0`), que
invalida la caché de forma **perezosa** (como en V3.88). `DECISION_POLICY_VERSION`
(`CURRICULUM_VERSION` sigue `1.3.1`) y `LISTENING_BANK_VERSION` **no cambian**. **No se añade ni se
retira gate** —siguen los **ocho**, todos en `pending`— y `docs/audit/validation-evidence.json`
**sigue sin existir**.

**En una frase.** El diccionario deja de ser una lista de traducciones y pasa a ser un **motor de
sentidos**: cada acepción es **contenido de pantalla** (equivalente, categoría, ámbito, ejemplo,
contexto, lema y procedencia) con **su propio audio**, la inversa **ES→EN** deja de **barrer la
tabla entera en Python** y el **léxico base se prepara una sola vez** con un lote de operador sobre
el vocabulario que la app **declara**.

---

## 1. Lo que se verificó antes de tocar nada

| Comprobación | Estado en `main` antes de V3.91 |
|---|---|
| Buscadoc ES→EN | **Escaneo O(N)** en Python: `list_entries()` volcaba la tabla y el matcher filtraba |
| Coste medido del barrido | **268 ms por consulta** a tamaño de diccionario completo (192 ms de SQL + 76 ms de bucle sobre 64.258 filas), `docs/DISENO-V388-DICCIONARIO-OFFLINE.md` §2.3 |
| `senses_json` | Se **persistía** desde V3.44 con dos campos (`{pos, gloss}`) y **no se pintaba** en ninguna pantalla |
| FTS5 | **No existía** índice alguno sobre la caché |
| Léxico offline | Estudio **medido** en V3.88 (`docs/DISENO-V388-DICCIONARIO-OFFLINE.md`), **sin implementar** |

De ahí el recorte: **no** un diccionario nuevo, sino (1) quitar el O(N) con índice y consultas
dirigidas, (2) hacer que el sentido sea la unidad de pantalla y (3) resolver el léxico base con el
**modelo local** sobre lo que la app ya declara.

## 2. El O(N) de la inversa: medido y retirado

**Tres piezas, las tres aditivas e idempotentes** en `backend/repositories/db.py`
(`_migrate_dictionary_fts`):

1. **Columna plegada** `dictionary_entries.translation_fold`, rellenada en la migración para lo ya
   cacheado con la **MISMA** función con la que la pliega `save_entry` y con la que compara el
   matcher puro (`services.dictionary_reverse.fold`). Si el índice y el matcher no plegaran igual,
   el índice **escondería** candidatos que el matcher **sí** acepta. La columna existe también sin
   FTS5, porque es la que usa el repliegue `LIKE`.
2. **Tabla virtual FTS5 de contenido EXTERNO** (`content='dictionary_entries'`,
   `content_rowid='rowid'`, `tokenize="unicode61 remove_diacritics 0"`): el índice **no duplica** el
   texto —los valores salen de la tabla real al leer— y `remove_diacritics 0` mantiene la **`ñ` como
   letra distinta** (`año` ≠ `ano`), que es la regla del matcher.
3. **Tres disparadores** (inserción, actualización y borrado): la sincronización la garantiza **la
   BD**, no el código de una consulta concreta. `save_entry` hace `INSERT ... ON CONFLICT DO UPDATE`,
   así que también pasa por aquí.

Más una **guarda**: si el índice y la tabla no cuadran (`count(*)` distinto) se **reconstruye**
(`'rebuild'`) y se registra. El caso real es la instalación que **estrena el índice con caché ya
dentro**; así el backfill no es un paso aparte que alguien pueda olvidar.

**FTS5 es opcional y se declara.** `fts5_available()` **no es una dependencia nueva** —FTS5 viene
compilada dentro de SQLite—, crea y destruye una tabla de sonda dentro de un `SAVEPOINT`, se paga
**una vez por proceso** y es **la misma sonda** que decide si la migración crea el índice: así no
puede existir un estado en el que una diga que sí y la otra no. Sin FTS5, la consulta **degrada** a
un `LIKE` por token sobre la columna plegada.

## 3. Consultas dirigidas (y `list_entries()` deja de ser camino de producción)

| Consulta | Sustituye a | Qué hace |
|---|---|---|
| `find_by_translation(term)` | barrido de la inversa ES→EN | Candidatos por **frase FTS5** (secuencia contigua = la condición de palabra completa del matcher), ordenados por `bm25` y acotados a **200** filas |
| `find_by_words(words)` | barrido de recall y de disponibilidad por palabra | Lookup **por PK** en lotes de **400**, solo las palabras que se conocen por nombre |
| `distractor_pool(word)` | barrido del MCQ de reconocimiento | Diana + candidatos **reproduciendo el orden por franjas** del helper puro: primero el mismo `pos`, después el resto, cada franja alfabética |

`list_entries()` **se conserva con su semántica intacta** y ya **no la usa ningún camino de
producción**: es la referencia con la que los tests comprueban que lo dirigido devuelve
**exactamente** lo mismo, y lo que un instrumento (informe de caché) puede querer volcar.

**Garantía declarada:** la consulta dirigida devuelve un **superconjunto** de las filas que el
matcher puede aceptar, **nunca un subconjunto**. Un candidato de más no cambia el resultado (el
matcher puro sigue puntuando); uno de menos **sí**, y por eso las dos vías (frase FTS5 y `LIKE` por
token) son deliberadamente **anchas**. Y el término se tokeniza en
`services.dictionary_reverse.phrase_tokens` (letras y dígitos, ya plegado) para **ambas** vías, así
que no pueden acabar buscando cosas distintas ni recibir un comodín escrito por el alumno: **el
término es TEXTO, nunca sintaxis**.

## 4. El contrato de acepción: de dos campos a nueve

Un sentido deja de ser una **etiqueta interna del scoring** y pasa a ser **la unidad que la ficha
pinta**:

```text
{term, pos, gloss, domain, proper_noun, example, context, lemma, source}
```

- `term` — equivalente en el **otro** idioma de esa acepción (español en EN→ES, inglés en ES→EN).
- `example` — **UNA** frase de uso en inglés de **ESA** acepción: es lo que suena el altavoz.
- `context` — etiqueta corta del contexto de uso («money and finance»).
- `lemma` — forma base declarada, aceptada **solo** si el motor puro de morfología la reconoce.
- `source` — procedencia: `model` (contenido del modelo) o `lexicon` (lexicón offline).

**Los dos prompts** (EN→ES y ES→EN) piden **una acepción por significado, en el MISMO orden que
`meanings`**, y `GENERATOR_VERSION` sube a **`1.7.0`**: la caché de 1.6.0 se regenera **una sola vez
al primer lookup** (invalidación perezosa, sin migración de datos ni de esquema, como en V3.88).
`pos`/`gloss` siguen siendo la identidad frente a los sentidos viejos, así que **el scoring NO
cambia de forma**.

**Lo que NO se hace con la caché vieja.** `_decode_senses` conserva **solo las claves que la fila
declara** —con el tipo normalizado y `bool` **estricto** en `proper_noun`— e **ignora las
desconocidas**. Una fila anterior al contrato se sirve **tal cual**, sin rellenar campos que nadie
declaró: rellenarlos aquí inventaría contenido, y la política del proyecto es que la caché obsoleta
se **regenera**, no se disfraza. El contrato vive en **un solo sitio** (`SENSE_KEYS` en
`services/dictionary_content.py`) y el repositorio lo **importa** en vez de reescribirlo.

## 5. La ficha: acepciones numeradas con ejemplo y audio propio

Nuevo componente `SenseList` en `frontend/src/features/vocabulary/DictionaryLookup.tsx`:

- acepciones **numeradas**, con insignia de `pos`, ámbito, **marca de nombre propio**, glosa,
  etiqueta de contexto, **forma base verificada** y **procedencia** (`model`/`lexicon`);
- **un botón de audio por acepción que suena el EJEMPLO, no la glosa**: la acepción se aprende
  oyéndola en contexto, no leyendo una etiqueta;
- un campo ausente **no se pinta**: nunca se rellena a ojo;
- van **después** del selector de significados —elegir sigue siendo la acción principal— y **antes**
  de la definición, porque **no dependen** del contenido del modelo.

Cadenas nuevas en `frontend/src/utils/i18n.ts` (es/en): `dictionary.lookup.senses`, `senseHint`,
`senseNumber`, `senseExample`, `senseContext`, `senseLemma`, `senseSourceModel`, `senseSourceLexicon`,
con `--strict` en verde.

## 6. El léxico offline, fase 2: un lote de operador, sin licencias de terceros

**Dos piezas nuevas:**

- `backend/services/dictionary_batch.py` — lógica **pura** (`normalize_word`, `parse_word_list`,
  `clean_term`, `map_pos`, `plan_batch`, `run_batch`, `estimate_seconds`, `format_duration`). Aquí
  **no se abre SQLite ni se importa el cliente del modelo**: la E/S se **inyecta**, que es lo que
  permite probar la reanudación, el tope de tiempo y el recuento de fallos **sin modelo ni BD**.
- `backend/scripts/dictionary_lexicon_batch.py` — el script de operador: `--dry-run`, `--limit`,
  `--max-seconds`, `--json`, `--words-file`, `--progress-every`, `--model`; salidas **0** (lote
  terminado, aunque alguna palabra falle), **2** (error de configuración o de BD) y **3** (se intentó
  y NO se preparó nada: modelo caído o BD de solo lectura, que es lo que un operador o un CI deben
  notar).

**No es el precalentado de V3.88.0** (`domain/dictionary_warmup.py`): ese prepara el léxico de **UN**
usuario, pasa por **la puerta de la consulta** (con sus cuotas, su single-flight y su negative cache)
y tiene un tope de 60 palabras. Ese camino es correcto para «mis palabras» y **no sirve** para
preparar el currículum entero: con la cuota de **10 palabras nuevas por usuario y minuto**, una
pasada de **1.041** palabras exigiría **al menos 1 h 45 min de reloj** aunque el modelo fuera
instantáneo, además de 1.041 consultas disparadas a mano. Un lote de **mantenimiento** tiene que poder
**saltarse las cuotas**, y eso es exactamente lo que hace el script: llama al **mismo** generador
(`dictionary_content.generate_content`) y persiste por el **mismo** repositorio (`save_entry`).

**La reanudación no necesita fichero de estado: la caché ES el estado.** `dictionary_repo.fresh_entry_words`
devuelve exactamente las palabras que la caché ya sirve frescas, con **el mismo criterio** que
`domain.vocabulary._content_is_fresh` (versión de generación vigente **y** definición no vacía). Así
que relanzar el script vuelve a planificar y **salta sola** lo hecho, interrumpir (Ctrl-C, corte de
luz, tope de tiempo) **no deja nada a medias** —cada palabra se persiste entera de una vez— y un
fichero de marcas sería una **segunda fuente de verdad** que puede desincronizarse de la BD.

**Best-effort por palabra.** Una palabra que falla (modelo caído, respuesta inválida, timeout) se
**cuenta con su motivo** (`empty`, `RuntimeError`, `persist:<error>`, `not_persisted`) y **el lote
sigue**: es mantenimiento, y una palabra mala no puede tumbar 2 horas de trabajo. El tope de tiempo se
comprueba **antes** de cada palabra, así que se para **en un límite de palabra** y no a mitad de
generación.

**Universo y coste, medidos `[M]`** (`--dry-run` en este equipo):

| Magnitud | Valor |
|---|---|
| Entradas crudas de la lista | **1.268** |
| Descartes (no son palabra/locución) | **10** |
| Duplicados | **217** |
| **Pendientes** | **1.041** |
| Ritmo medido (`llama3.1:8b`, contrato 1.7.0) | **8,7 s/palabra** (3 palabras en 26 s de lote, BD temporal) |
| Coste de la pasada completa | **≈ 2 h 31 min** de CPU, **una sola vez** |

**Verificado de punta a punta:** las tres palabras del lote de prueba quedaron en
`dictionary_entries` con `generator_version = "1.7.0"`, el contrato de **nueve campos** y sus **tres
filas en el índice FTS5** —alimentado por el **repositorio**, no por el script: `save_entry` es el
mismo camino.

## 7. El léxico offline, fase 3: aparcado por una decisión que no es técnica

Empaquetar **FreeDict `eng-spa` 2025.11.23** (64.258 entradas crudas → 35.935 simples, **24,52 MiB**
con FTS5, búsquedas a **0,034 ms**) daría cobertura **fuera** del currículum. **No se hace en esta
release**, y no por falta de código: la fuente es **CC BY-SA 3.0**, es decir **atribución y
*ShareAlike* de la obra derivada**.

- **No es deuda técnica.** El código está listo: `clean_term`/`map_pos` de `dictionary_batch` son la
  **puerta de ingesta** prevista para un dataset léxico externo.
- **Es un gate del gerente.** Empaquetarla **cambia la naturaleza del producto** (deja de haber solo
  contenido propio) y ninguna decisión técnica puede aceptar una obligación legal en su nombre.
- **Las tres condiciones para desbloquearlo** (juntas): (i) aceptación **escrita** de CC BY-SA 3.0 con
  *ShareAlike* sobre la obra derivada; (ii) pantalla de créditos + texto de licencia y su traducción;
  (iii) asumir que la dirección **ES→EN** seguiría pagando el modelo (el `spa-eng` de FreeDict tiene
  **4.502** entradas y está marcado `too small`), o un plan aparte para ella.

Queda documentado en `docs/audit/PARKED.md §Licencia del lexicón offline`, junto al instrumento que
mide el antes/después (`scripts/dictionary_cache_report.py`).

## 8. Verificación

| Puerta | Resultado |
|---|---|
| `ruff check .` (backend y lanzador) | limpio |
| `pytest` backend | **3368 passed** (incluye `test_dictionary_fts_v391.py`, `test_dictionary_senses_v391.py` y `test_dictionary_batch_v391.py`, 92 tests nuevos) |
| `vitest run` | **1097 passed** (111 ficheros) |
| `tsc --noEmit` | limpio |
| `npm run build` | correcto |
| `check_i18n_coverage.py --strict` | **1864** cadenas · 0 huérfanas · 0 sin definir · 0 duplicadas · 0 vacías |
| `contrast_audit.mjs --strict` | 480 pares + 6 guardas · **0 bloqueantes** · `audit: V3.91.0-contraste-wcag` |
| Playwright (rutas tocadas: **Diccionario**) | `dictionarySmoke`, `dictionaryFlashcardsBridge` y `responsiveOverflow` en los **3 breakpoints** · **31 passed**, 2 skipped |
| `validation_gate.py auto --require-dist` | **10/10** (8 gates) |
| `check_release_consistency` | OK en los **6 orígenes** (`3.91.0`) |

**Orden de la verificación y su evidencia:** el primer `pytest` completo de este árbol cayó **en un
solo test** —`test_validation_gate_v373.py::test_las_comprobaciones_de_auto_no_fallan_en_este_arbol`—
porque las versiones ya estaban bumpeadas a `3.91.0` y todavía **no** existían el encabezado de este
CHANGELOG ni la entrada de `PLAN.md`: era la propia puerta de consistencia señalando trabajo a medias.
Se completaron los documentos y la suite se re-ejecutó en verde. **No se oculta el primer rojo: es la
prueba de que la puerta funciona.**

Tests añadidos o ampliados: `backend/tests/test_dictionary_fts_v391.py` (nuevo: índice, disparadores,
reconstrucción, degradación sin FTS5, acuerdo con `list_entries()`, tokenización sin inyección),
`backend/tests/test_dictionary_senses_v391.py` (nuevo: contrato de nueve campos, compatibilidad con
filas viejas, persistencia), `backend/tests/test_dictionary_batch_v391.py` (nuevo: higiene de la lista,
mapeo de POS, planificación, tope de tiempo, recuento de fallos, acuerdo de frescura con el dominio),
`frontend/src/features/vocabulary/DictionaryLookup.test.tsx` (acepciones ricas, caché heredada sin
marcadores falsos, sección oculta cuando está vacía).

## 9. Honestidad: lo que NO trae

- **No se empaqueta ningún dataset de terceros.** El «léxico offline» de esta release es el **batch
  local** sobre el vocabulario que la app **declara** (1.041 palabras) y **no** cubre palabras fuera
  de él. FreeDict sigue **aparcado**.
- **Sin FTS5, el peor caso sigue siendo un barrido.** El repliegue `LIKE` **recorre** la tabla: la
  degradación es **real** y se declara, no desaparece.
- **`source: "lexicon"` es una procedencia que hoy no produce ningún camino de producción.** El batch
  escribe `source: "model"`; la UI pinta la etiqueta cuando el valor es `lexicon` **o** `model`, así
  que la etiqueta de lexicón está lista pero **no se emite** todavía.
- **La generación de acepciones está orientada por prompt, NO garantizada por el modelo.** Los
  prompts **piden** una acepción por significado, en orden; que el modelo lo cumpla no está
  garantizado por construcción.
- **El bump a `1.7.0` invalida toda la caché.** La primera consulta de cada palabra vuelve a pagar el
  modelo **hasta que el operador corra el lote**; eso es exactamente lo que hace útil la fase 2.
- **Se toca `GENERATOR_VERSION` pero no el scoring semántico de forma:** `pos`/`gloss` siguen siendo
  la identidad frente a los sentidos viejos.
- **Los ocho gates humanos siguen `pending`** y `docs/audit/validation-evidence.json` sigue sin
  existir.

## 10. Archivos tocados (resumen)

- **Backend:** `repositories/db.py` (`translation_fold`, FTS5, disparadores, guarda, `fts5_available`),
  `repositories/dictionary.py` (`fresh_entry_words`, `find_by_translation`, `find_by_words`,
  `distractor_pool`, `_decode_senses`/`_encode_senses` con `SENSE_KEYS`),
  `services/dictionary_content.py` (`GENERATOR_VERSION = "1.7.0"`, `SENSE_KEYS`, prompts de acepción),
  `services/dictionary_reverse.py` (`phrase_tokens`, `phrase_query`), `domain/vocabulary.py` y
  `domain/review.py` (consultas dirigidas), `schemas/vocabulary.py`, `services/dictionary_batch.py`
  (nuevo), `scripts/dictionary_lexicon_batch.py` (nuevo).
- **Frontend:** `features/vocabulary/DictionaryLookup.tsx` (`SenseList`), `api/normalize.ts`
  (`normalizeDictionarySense`), `types/api.ts`, `utils/i18n.ts`.
- **Tests:** `backend/tests/test_dictionary_fts_v391.py` (nuevo),
  `backend/tests/test_dictionary_senses_v391.py` (nuevo),
  `backend/tests/test_dictionary_batch_v391.py` (nuevo),
  `frontend/src/features/vocabulary/DictionaryLookup.test.tsx`, más los ficheros de contrato que fijan
  `GENERATOR_VERSION`.
- **Versión y docs:** `backend/config.py`, `frontend/package.json`, `frontend/package-lock.json`,
  `README.md`, `CHANGELOG.md`, `PLAN.md`, `docs/RELEVO.md`, `docs/audit/PARKED.md`.

## Para auditar esta release

1. `python -m scripts.dictionary_lexicon_batch --dry-run` desde `backend/` y comprobar que el universo
   es **1.268 → 10 descartes → 217 duplicados → 1.041 pendientes**.
2. Correr el lote con `--limit 3 --json` sobre una BD **temporal** (`--db <ruta>`) y comprobar que las
   tres palabras quedan con `generator_version = "1.7.0"`, el contrato de nueve campos y sus filas en
   `dictionary_entries_fts`.
3. Relanzar el mismo lote sin `--limit`: debe decir **`Ya frescas: 3`** y **no** volver a llamar al
   modelo (reanudación sin fichero de estado).
4. Buscar una palabra **ES→EN** en CONSULTAR y comprobar que la respuesta es correcta y rápida con la
   caché ya poblada; con `EXPLAIN QUERY PLAN` debe verse la tabla virtual FTS5 y **no** un barrido.
5. Comprobar que la ficha pinta las **acepciones numeradas** con su `pos`, ámbito, ejemplo, etiqueta de
   contexto y **altavoz por acepción** que suena **el ejemplo**, no la glosa.
6. Consultar una palabra **cacheada antes** del bump (fila de 1.6.0): la ficha **no** debe inventar
   campos que la fila no declaró, y la fila debe regenerarse en la siguiente consulta.
7. Forzar la ausencia de FTS5 (build de SQLite sin FTS5) y comprobar que la inversa **sigue
   respondiendo** por el repliegue `LIKE` y que el arranque **registra la degradación** en el log.
