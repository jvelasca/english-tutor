# Release notes — English Tutor v3.75.8

**Fecha:** 2026-09-20 · **Tipo:** release **DE PRODUCTO** (patch) ·
**Versión de app:** `3.75.7 → 3.75.8`

**SIN migración de BD, SIN bump de `GENERATOR_VERSION` ni
`DECISION_POLICY_VERSION`, SIN tocar el currículum (`CURRICULUM_VERSION` sigue
`1.3.1`), SIN tocar las evaluaciones (`assessments.json`), SIN tocar
`LISTENING_BANK_VERSION` y SIN endpoints nuevos:** todo el diff de producto es
**frontend**. No añade ni retira un gate y no adelanta la validación física
(**G1–G7 siguen `pending`**).

---

## 1. Qué es esta release

Es una release de **presentación y de identidad**. No cambia el motor, ni el
banco, ni el currículum, ni una sola ruta de la API. Cambia **cómo se ve el
diccionario de consulta** y **cómo se sabe qué compilación está corriendo**.

Nace de cuatro peticiones del gerente sobre la app **en uso**:

1. que la parte visual del diccionario sea **más atractiva**, como la de los
   diccionarios de las apps de referencia;
2. que el **espacio para escribir la palabra** sea más grande y más claro,
   **especialmente en el móvil**;
3. que **cada sentido de la consulta tenga su color**, para que se vea de un
   vistazo si se busca inglés → español o español → inglés;
4. y, al cerrar la sesión, que la **Ayuda** declare junto al autor la **versión de
   compilación** que está corriendo.

---

## 2. El diccionario: el buscador pasa a ser la vista

Antes, la pantalla de consulta tenía un campo de **40 px** (`h-10 text-sm`) con el
botón al lado, compitiendo por la atención con el `h1`, con las pestañas de la
pantalla y con un conmutador de sentido que vivía **encima** del campo, en una
pastilla gris, sin relación visual con él.

Ahora el campo vive dentro de una **tarjeta-buscador**:

- **Marco de 2 px** con la barra superior y el anillo de foco **del color del
  sentido activo**.
- **48 px de alto en móvil y 56 px en escritorio/tablet**, con `text-base` y
  `text-lg` respectivamente. Medido en 390×844, 768×1024 y 1280×800, no estimado.
- El **conmutador EN→ES / ES→EN entra dentro del buscador**, en dos pastillas a
  ancho completo: dentro no compite con las pestañas de la pantalla y se lee como
  lo que es —una propiedad de la consulta—.
- **Sin consulta todavía, cuatro ejemplos por sentido** (`travel/book/water/family`
  en EN→ES, `casa/viaje/comida/tiempo` en ES→EN) que rellenan el campo y buscan al
  pulsarlos, y un **botón de borrado** (`X`) dentro del campo que solo existe
  cuando hay texto: nada de botones muertos en reposo.

El precio, declarado: **la tarjeta ocupa más** (132 px en escritorio y 172 px en
móvil, contando conmutador y fila de búsqueda) y en móvil el campo y el botón se
apilan, así que el botón no está a la altura del campo. A cambio, el objetivo
táctil del campo sube por encima de los 44 px que pide el estándar justo donde el
gerente lo pedía.

---

## 3. Un color por sentido (y por qué no sigue al acento del perfil)

| Sentido | Tinta (tema oscuro) | Tinta (tema claro) | Color |
| --- | --- | --- | --- |
| Inglés → Español | `#93c5fd` | `#1e40af` | **azul** |
| Español → Inglés | `#f0abfc` | `#86198f` | **fucsia** |

El relleno y el borde **se derivan de la tinta** (`color-mix()` al 15 % y al
35 %), igual que la rampa de niveles de V3.75.4: un consumidor nuevo no exige
tocar un hex.

La pareja es **complementaria** (el máximo contraste entre los dos sentidos) y
**no pisa los colores de estado** —verde dominada, ámbar en curso, rojo débil—,
que ya significan otra cosa en toda la app.

**A diferencia de la rampa de niveles, no sigue el acento del perfil y no se
ofrece en Ajustes.** La razón está escrita en el propio CSS y merece repetirse
aquí: si el color del sentido cambiara con el acento, dos acentos afines podrían
dejar el azul y el fucsia **casi iguales** y la señal se perdería. Esto es una
**leyenda del diccionario** (azul ↔ fucsia), y una leyenda que se puede cambiar
deja de ser una leyenda. El precio es una asimetría declarada: hay colores de la
app que siguen al perfil y este no.

### Cuál manda: activo vs. resultado

- El **buscador** se tiñe del sentido **activo** (barra, marco, pastilla
  seleccionada, anillo de foco).
- La **tarjeta del resultado** se tiñe del sentido **de su propia consulta**
  (`entry.direction`) y lleva una **marca de dirección** («English → Spanish»)
  junto a la palabra: conmutar el buscador **después** de buscar **no** repinta el
  resultado, así que el resultado no puede mentir sobre en qué sentido se pidió.
- Dentro de la ficha, el color se concentra en el **equivalente** —el bloque con
  más tinta y `text-lg font-semibold`, porque es la respuesta— y en la pestaña del
  ejemplo. El resto queda en neutro para que el color **informe** en vez de
  decorar.

---

## 4. Un solo `h1` en `/diccionario` (defecto encontrado de paso)

La vista de consulta traía cabecera propia (`h1` + subtítulo) y la pantalla la
suya: había **dos `h1`** en la misma página, el título repetido y el relleno de
página aplicado **dos veces**. `DictionaryLookup` recibe ahora `showHeader`
(**defecto `true`**, que es lo que necesitan las superficies que la montan suelta)
y `DictionaryScreen` lo apaga.

---

## 5. La Ayuda declara la versión de la compilación

Nuevo `frontend/src/utils/buildInfo.ts`: la versión se lee del `package.json` **en
tiempo de compilación** y viaja dentro del bundle —**solo el campo `version`**; el
resto del fichero (dependencias, scripts) no entra, porque Vite convierte el JSON
en exports con nombre y el árbol de módulos se poda—.

La razón no es cosmética. Hasta ahora, la única versión visible en la app era la
del **backend** (`GET /api/health` → `components/SystemStatus.tsx`), que es
exactamente la que **no responde** cuando el alumno pregunta «¿qué versión
tengo?». La Ayuda es una pantalla **sin red**: su versión no puede depender de la
API. `scripts/check_release_consistency.py` mantiene ese número igual al de
`backend/config.py::VERSION` y al resto de orígenes, así que la versión de la
compilación y la que declara el backend no pueden divergir en una release
publicada.

Además, la tarjeta de **«Vocabulary y diccionario»** de la Ayuda decía «tu
diccionario personal» y no mencionaba el diccionario de **consulta** ni su
conmutador de sentido: se le añade una frase («…y tú eliges el sentido
(inglés → español o español → inglés): cada sentido tiene su color»). No se toca
ninguna otra tarjeta porque ninguna otra describe algo que haya cambiado.

**Lo que la Ayuda no dice, y es a propósito:** muestra la **versión**, no la fecha
ni el `hash` del build, así que **dos compilaciones de la misma versión se
declaran igual**.

---

## 6. Medido, no mirado

### Contraste (guarda permanente, `--strict`)

El par de direcciones entra en `frontend/scripts/contrast_audit.mjs`: tinta de
cada sentido sobre su **relleno compuesto**, en los **2 temas** × **2 fondos**
(`--color-bg`, `--color-surface`), con el **porcentaje de mezcla leído del CSS**
en vez de supuesto.

| Tema | Dirección | Fondo | Razón | Mínimo | Estado |
| --- | --- | --- | ---: | ---: | --- |
| dark | EN→ES | `--color-bg` / `--color-surface` | 7.83 / 6.51 | 4.5 | OK |
| dark | ES→EN | `--color-bg` / `--color-surface` | 8.02 / 6.69 | 4.5 | OK |
| light | EN→ES | `--color-bg` / `--color-surface` | 6.37 / 6.75 | 4.5 | OK |
| light | ES→EN | `--color-bg` / `--color-surface` | 5.99 / 6.35 | 4.5 | OK |

Sobre el relleno compuesto **el peor caso medido es 5.76:1** (ES→EN en tema claro
sobre `--color-surface-2`, que es la superficie de la Card del buscador),
con holgura frente al 4.5:1 exigido. Total: **480 pares + 6 guardas, 0
bloqueantes**.

Dos guardas nuevas, y la que importa es la segunda:

- `direccion-completa` — las dos tintas declaradas en los dos temas.
- `direccion-clases-y-derivados` — relleno al 15 %, borde, las clases
  `.dir-en-es`/`.dir-es-en` y los modificadores `.dir-chip` / `.dir-ink` /
  `.dir-line` / `.dir-wash` / `.dir-bar`, más el marco `.dir-field`.

**Por qué esa guarda es la que importa:** `directionClass()` devuelve el **nombre**
de una clase CSS. El unitario comprueba el nombre, no que exista una regla con ese
nombre. Si alguien renombrara `.dir-en-es` en el CSS, el buscador se quedaría **sin
color** y ninguna otra prueba se enteraría: la guarda del script lo caza.

### Layout (spec temporal, borrado)

- Campo de **48 px** en móvil (390×844) y **56 px** en tablet (768×1024) y
  escritorio (1280×800).
- Conmutador con **dos colores computados distintos** al conmutar (el test exigía
  que fueran distintos, no un valor concreto; EN→ES computa `rgb(30, 64, 175)` en
  tema claro).
- **Cero desbordamiento horizontal** en los tres breakpoints
  (`scrollWidth - innerWidth <= 0`).
- El botón de borrado **no existe** en reposo.

---

## 7. Verificación

| Instrumento | Resultado |
| --- | --- |
| `tsc --noEmit` | limpio |
| `vitest run` | **819/819** (95 ficheros) |
| `npm run build` | correcto; el bundle publica `3.75.8` |
| i18n `--strict` | **1515 claves / 0 huérfanas / 0 usadas sin definir** |
| contraste `--strict` | **480 pares + 6 guardas / 0 bloqueantes** (17 pares de acento reportados, no bloqueantes) |
| `check_release_consistency` | OK en los **6 orígenes** (`3.75.8`) |
| `validation_gate.py auto` | **10/10** |
| `pytest` (backend) | **2909 passed** / 0 skipped (sin cambios de producto en backend, pero la suite se ejecuta sobre el árbol de release) |
| `ruff` (backend) | limpio |

**Instrumento nuevo:** `frontend/src/features/help/HelpScreen.test.tsx` — la Ayuda
pasa a tener test propio (no lo tenía) y fija que la versión de la compilación se
ve junto al autor y que la tarjeta de vocabulario explica el sentido de la
consulta.

---

## 8. Honestidad

1. **El color no añade información, evita una confusión.** El sentido ya lo decía
   el rótulo («English → Spanish») y el color solo lo adelanta. Quien no distinga
   azul de fucsia sigue teniendo el rótulo; lo que no hay es una señal redundante
   **no cromática** más allá de él (ni forma, ni icono distinto por sentido).
2. **La pareja de direcciones no es configurable, a propósito.** Ofrecerla como
   preferencia de apariencia la convertiría en algo que puede dejar de coincidir
   entre lo que el alumno cree y lo que la app dice. El precio es la asimetría con
   la rampa de niveles, que sí sigue el acento.
3. **Dos compilaciones de la misma versión se declaran igual.** La Ayuda muestra
   la versión, no la fecha ni el `hash` del build, así que no distingue un `dist`
   recompilado del original.
4. **El diccionario se queda sin spec visual permanente.** La medición se hizo con
   un spec temporal que se borró al cerrar la revisión: el contraste **sí** está
   cubierto por guarda permanente y la clase aplicada por unitario, pero **cómo se
   ve** la pantalla no tiene prueba automática.
5. **Los ejemplos son fijos:** cuatro palabras por sentido, escritas a mano en
   `utils/dictionaryDirection.ts`. Generarlas del léxico del alumno o del banco
   sería material de otra iteración.
6. **El `dist` no se versiona** (`.gitignore`): para ver la UI nueva hay que
   recompilar y reiniciar el backend.
7. **El P0 de identidad sigue entero** y esta release no lo toca: no añade ni una
   ruta ni un endpoint.
8. **Los 7 gates siguen en `pending`.** No cambia un gate ni se adelanta validación
   física alguna.

---

## 9. Archivos del diff de producto

- `frontend/src/styles/legacy.css` — tokens `--dir-*-fg` (2 temas) y clases
  `.dir-en-es`, `.dir-es-en`, `.dir-chip`, `.dir-ink`, `.dir-line`, `.dir-wash`,
  `.dir-bar`, `.dir-field`.
- `frontend/src/utils/dictionaryDirection.ts` *(nuevo)* — `directionClass`,
  `DIRECTION_OPTIONS`, `directionLabelKey`, `DIRECTION_EXAMPLES`.
- `frontend/src/utils/buildInfo.ts` *(nuevo)* — `APP_VERSION`.
- `frontend/src/features/vocabulary/DictionaryLookup.tsx` — buscador grande,
  conmutador dentro, estado vacío, borrado, color por sentido y `showHeader`.
- `frontend/src/features/vocabulary/DictionaryScreen.tsx` — `showHeader={false}`.
- `frontend/src/features/help/HelpScreen.tsx` — versión de compilación junto al
  autor.
- `frontend/src/utils/i18n.ts` — `help.buildVersion` y la frase nueva del
  diccionario de consulta en `help.vocabulary.body`.
- `frontend/scripts/contrast_audit.mjs` — medición del par de direcciones y dos
  guardas.
- Tests: `dictionaryDirection.test.ts` *(nuevo)*, `HelpScreen.test.tsx` *(nuevo)*,
  `DictionaryLookup.test.tsx` (casos nuevos de chips, color y estado vacío).
