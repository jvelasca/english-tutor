# v3.95.0 — El diccionario deja de mentir

Release de **PRODUCTO (minor)** sobre `v3.94.10`. **CON backend y CON
frontend**, **CON migración aditiva** (tablas `dictionary_curated` y
`dictionary_lexicon`) y **CON endpoints nuevos** de administración del
diccionario.

Endpoints nuevos (administración, con `X-Admin-Pin` y origen local):

- `GET /api/admin/dictionary/curated` — lista las correcciones a mano.
- `PUT /api/admin/dictionary/curated` — fija/sobrescribe una corrección.
- `DELETE /api/admin/dictionary/curated/{direction}/{word}` — la retira.
- `GET /api/admin/dictionary/lexicon/sources` — fuentes de léxico externo y su
  licencia (atribución).

**`GENERATOR_VERSION` sube `1.7.0 → 1.8.0`.** Es la palanca que invalida la
caché anterior del diccionario: al primer lookup, cada fila deja de ser fresca
y se regenera **bajo el guardarraíl**. `DECISION_POLICY_VERSION`
(`CURRICULUM_VERSION` sigue `1.3.1`) y `LISTENING_BANK_VERSION` **no cambian**.
**No se añade ni se retira gate** —siguen los **ocho**, todos `pending`— y
`docs/audit/validation-evidence.json` **sigue sin existir**.

## Qué cierra

1. **El guardarraíl (calidad).** Un equivalente ES→EN que el modelo no pueda
   **retrotraducir** a la palabra original se descarta
   (`ContentUnavailableError`) en lugar de cachearse. Es lo que impide guardar
   «broca» → «rock»: el modelo retrotraduce «rock» a «roca», no a «broca», y
   la fila no se escribe. Si no hay contenido verificable, se degrada de forma
   honesta a `definition_source="none"`.
2. **Las autoridades, por orden.** Corrección manual del webmaster
   (`dictionary_curated`, manda sobre todo) → glosario curado ES→EN
   (`curriculum/lexicon/es_en_glossary.json`) → pares curados de los packs →
   inversa instantánea sobre la caché → léxico externo opcional
   (`dictionary_lexicon`) → generación con guardarraíl. El desempate de la capa
   curada respeta `priority` (`broca` → `drill bit` antes que `drill`).
3. **Cobertura determinista.** El glosario curado nace con el vocabulario de
   herramienta, casa y oficio que el diccionario fallaba. La consulta ES→EN se
   responde sin tocar el modelo cuando hay autoridad.
4. **Corrección desde la propia ficha.** El webmaster corrige el término que
   está viendo en el diccionario (componente `DictionaryCuration`), con el
   mismo PIN de administración que la biblioteca de audio. La corrección manda
   sobre glosario, packs y caché para **todos** los usuarios.
5. **Herramientas de operador.** `scripts/dictionary_validate_cache.py` valida
   la caché contra el conocimiento curado: por defecto solo informa; `--apply`
   purga **solo la dirección inversa** (determinista) y la directa exige
   `--include-direct` porque es **asesora** (marca sinónimos legítimos como
   `armchair → butaca`). El lote y el warmup cubren ya las dos direcciones
   (`--direction es-en`). `scripts/import_freedict.py` importa un léxico
   bilingüe externo y **exige `--accept-license`**.

## Qué no cierra

- El frontend **sigue sin pintar** `new_sense_exposure`.
- No hay FSRS por acepción (sigue el reparto por palabra).
- Los **ocho gates humanos siguen `pending`**.
- El léxico externo **nace vacío**: solo se rellena aceptando su licencia.
- La dirección EN→ES del validador es **ASESORA**, no determinista.
- El tag anotado `v3.95.0` espera a que la CI de esta PR esté verde.

## Verificación local

- `pytest` del diccionario (reverse, curación, léxico, lote, sentidos) y suites
  relacionadas, **157/157**.
- `vitest` del diccionario y de i18n, **211/211**.
- `tsc --noEmit` limpio · `npm run build` correcto.
- `check_i18n_coverage.py --strict` en verde (0 huérfanas, 0 sin definir, 0
  duplicadas).
- `check_release_consistency.py` OK en los **6 orígenes** (`3.95.0`).

## Verificación del operador (BD de producto)

- Purga aplicada: **6 filas envenenadas borradas** (`broca → rock`,
  `sierra → mountain range`, `serrucho → jigsaw`, `fresadora → grinder`,
  `lima → capital`, `alicates → alicates`).
- Consultas ya correctas: `broca → drill bit`, `sierra → circular saw`,
  `serrucho → handsaw`.
