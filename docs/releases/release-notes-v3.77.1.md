# Release notes — English Tutor v3.77.1

**Fecha:** 2026-09-21 · **Tipo:** release **DE PRODUCTO** (patch) ·
**Versión de app:** `3.77.0 → 3.77.1`

**SIN migración de BD, SIN bump de `GENERATOR_VERSION` ni
`DECISION_POLICY_VERSION`, SIN tocar el currículum (`CURRICULUM_VERSION` sigue
`1.3.1`), SIN tocar las evaluaciones y SIN tocar `LISTENING_BANK_VERSION`.** No
añade ni retira un gate: **G1–G7 siguen `pending`** y el árbol que se certifica
sigue siendo el de `v3.75.8`.

---

## 1. Qué arregla

**Un fallo REAL de la V3.77.0 publicada, y llegó al tag.** El diccionario personal
podía morir **entero** —no una tarjeta, **la pantalla**— si
`GET /api/vocabulary/collections` no traía el campo `collections`.

`AddVocabSection` guardaba la respuesta **sin comprobar la forma**:

```tsx
const data = await listVocabCollections(userId);
setPacks(data.collections);        // ← si el campo no viene, queda `undefined`
```

…y la lista de temas hacía `packs.filter(...)` **al pintar**. Un fallo al pintar no
rompe «la lista de packs»: rompe el **árbol de React entero**, y con él todo lo que
el alumno tenía delante en esa pantalla.

**El arreglo va donde se guarda**, no donde se pinta:

```tsx
setPacks(Array.isArray(data?.collections) ? data.collections : []);
```

y la misma defensa se extiende a los avisos de alta (`out.added?.[0] ?? word`,
`out.count ?? 0`), que habrían fallado igual con una respuesta incompleta.

## 2. Cómo se encontró — que es la parte que hay que contar

El job **`Playwright E2E (visual)`** pasó de verde a **2 fallos** con la V3.77.0.
Los dos, en `drillProvenance.spec.ts`, que abre el drill **desde la cola de repaso
del diccionario** y dejó de encontrar el ítem.

No era el drill: era que **la pantalla ya no existía** cuando el test miraba. El
harness mockea `/api/**` con respuestas **vacías**, así que sirvió de **sonda de
contrato** sin proponérselo.

La release se había publicado **quince minutos antes**.

## 3. Se arregla la causa, no el síntoma

Había dos atajos y los dos se descartaron:

| Atajo | Por qué no |
| --- | --- |
| Añadir los endpoints nuevos al `mockApi` de la spec | Es lo que pone el CI en verde **sin arreglar nada**. El mock se queda **vacío a propósito**: es lo que lo hace útil |
| Aflojar el localizador del test | Tapa el síntoma en el único sitio donde el defecto **no** está |

El mismo camino que recorre el mock vacío lo recorre un **servidor que cambie el
contrato**. Lo que cambia es que **el componente no confía en la forma**.

## 4. Candado nuevo, y comprobado que muerde

`frontend/src/features/vocabulary/AddVocabSection.test.tsx` fija tres casos:

1. respuesta **sin `collections`** → la sección sigue en pie y ofrece sus tres
   caminos;
2. **packs servidos** → se pintan y activarlos manda la inscripción;
3. respuesta **sin `added`** → el aviso cae al término tecleado en vez de reventar.

**Con el código anterior, el caso 1 falla.** No es una suposición: se revirtió la
línea, se corrió y se comprobó.

## 5. Verificación

| Instrumento | Resultado |
| --- | --- |
| `vitest run` | **875/875** (101 ficheros) |
| `tsc --noEmit` | limpio |
| `npm run build` | correcto (`package.json` en `3.77.1`) |
| `Playwright` · `drillProvenance.spec.ts` | verde en las **tres** configuraciones (desktop/tablet/mobile) |
| i18n `--strict` | **0 huérfanas / 0 usadas sin definir** |
| `check_release_consistency` | OK en los **6 orígenes** (`3.77.1`) |
| `validation_gate.py auto` | **10/10** |

## 6. Honestidad

1. **El fallo llegó al tag publicado.** Lo encontró la sonda del harness, **no una
   prueba del producto**, y eso es un dato sobre la cobertura: ninguna unidad se
   había pedido qué pasa con un contrato incompleto.
2. **En el producto con el backend de verdad el campo siempre viaja**, así que el
   defecto no se habría visto en uso normal. Lo que se arregla es que un contrato
   incompleto **no pueda tumbar la pantalla**.
3. **El dinero de esta release es la pantalla, no el dato.** El alumno no perdía
   vocabulario: perdía la vista mientras estaba delante de ella.
4. **La fragilidad del arnés visual bajo carga en Windows** (`PARKED.md` §V3.75.2)
   **sigue aparcada, y no es lo que falló aquí.** En local, la tanda completa de
   esta máquina volvió a dar fallos en specs que esta release **no toca** (13
   fallos, con `analysis`, `smoke`, `grammar`… entre ellos), mientras que
   `drillProvenance` **pasa aislado**. La autoridad es el CI, que es donde el
   defecto se destapó.
5. **La V3.77.0 no se reescribe.** El tag está publicado y se queda como está; la
   corrección viaja en su propia etiqueta, que es lo que permite auditar qué se
   publicó, cuándo y con qué defecto.
6. **Nada de la V3.77.0 cambia de significado.** Retención léxica, perfiles con
   autorización del webmaster, doble candado y borrado en dos pasos siguen
   exactamente como se publicaron; esta release solo añade que la pantalla
   **aguante** una respuesta incompleta.
