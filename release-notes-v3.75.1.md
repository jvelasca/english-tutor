# Release notes — English Tutor v3.75.1

**Fecha:** 2026-09-19 · **Tipo:** release de **PARCHE + CONTENIDO** · **Versión de
app:** `3.75.0 → 3.75.1`

**SIN migración de BD, SIN bump de `GENERATOR_VERSION` ni
`DECISION_POLICY_VERSION`, SIN tocar el banco y SIN tocar las evaluaciones
(`assessments.json`), pero SÍ toca el currículum (`CURRICULUM_VERSION` 1.3.0 →
1.3.1).** Ninguna capacidad pedagógica nueva y ninguna ruta de producto nueva:
cierra el **único P0** que quedaba abierto del motor pedagógico —el sesgo
posicional de los 368 checks del currículum— y añade el instrumento determinista
que lo hace reproducible.

> **Esto cambia el contenido que ve el alumno, no el contrato de la API.** Los
> 368 checks son los mismos (mismo `id`, mismo enunciado, misma opción correcta,
> mismos distractores); lo que cambia es **en qué posición** aparece la correcta.
> Ninguna app necesita adaptarse.

---

## Qué es esta release

La auditoría pedagógica de V3.70 midió, en su eje de adecuación CEFR
(`docs/audit/AA-PED-CONTENIDO-CEFR.md` §3), que **329 de los 368 checks del
currículum (89,4 %) tenían la respuesta correcta en la posición 0**. La
consecuencia no es estética: un alumno que marcase **siempre la primera opción**
acertaba casi **9 de cada 10** checks sin leer el enunciado, y las señales que el
motor extrae de esos aciertos —`student skill state`, mastery, el Planner—
heredaban ese ruido.

V3.70 lo elevó a **P0**, lo aparcó asignado a la fase de contenido y dejó escrito
el criterio de cierre (un reparto determinista con invariante **≤ 35 % por
posición**) y el candado: el test que fijaba la cifra **fallaría** al corregirla,
obligando a re-auditar el eje. Esta release ejecuta ese cierre.

**Fuera de alcance (declarado).** El **P2 de forma/longitud** —la correcta es
también la opción más larga en el 39,1 % de los checks y en el 50 % del
placement— **no se toca**: reposicionar no cambia longitudes, y ese es el
hallazgo `#7` de `AA`. Y **`assessments.json` (exámenes y placement) no se
toca**: es otro instrumento, con su propia medición, y sigue con la correcta en
la posición 0 en el 63,6 % de sus 22 ítems. §8 lo desarrolla.

---

## 1. El problema, con su alcance exacto

Medición con el instrumento que ya existía (`python -m scripts.audit_dossier
mc-bias`), antes de tocar nada:

| Grupo | n | Posición 0 | Posición 1 | Posición 2 |
|---|---|---|---|---|
| **checks del currículum** | **368** | **89,4 %** | 10,1 % | 0,5 % |
| corpus de listening | 490 | 25,5 % | 24,7 % | 24,9 % |

El corpus de listening **no tiene el defecto** y no se toca. Por niveles, el
reparto era aún más extremo de lo que sugiere el agregado:

| Nivel | Checks | Reparto de la correcta (antes) |
|---|---|---|
| A1 | 105 | `0:67 · 1:36 · 2:2` |
| A2 | 55 | `0:55` — **todo en la posición 0** |
| B1 | 53 | `0:52 · 1:1` |
| B2 | 35 | `0:35` — **todo en la posición 0** |
| C1 | 63 | `0:63` — **todo en la posición 0** |
| C2 | 57 | `0:57` — **todo en la posición 0** |

Cuatro de los seis niveles no tenían **ni un solo** check con la correcta fuera
de la posición 0. A1 era el único con variedad apreciable.

---

## 2. La regla: reposicionar, no rotar

La regla es determinista y se declara entera:

> Dentro de cada grupo de checks con el **mismo número de opciones `k`**,
> ordenados por `id` ascendente, el check que ocupa la posición `j` del grupo
> lleva la correcta a la posición **`j % k`**.

Dos decisiones importan más de lo que parece:

**(A) Se agrupa por `k`, no se agrega todo junto.** Una posición solo existe
dentro de su número de opciones: «posición 3» no significa nada en un ítem de 3
opciones. Agregar los 368 en un único reparto escondería que el 4.º distractor
(los 10 checks de 4 opciones) nunca fuese la correcta — que es exactamente el
defecto que se está corrigiendo, un nivel más abajo. El invariante se mide, por
tanto, **por grupo**.

**(B) Se mueve la correcta; no se rota el array.** La auditoría llamó al arreglo
«rotación determinista», y la primera implementación fue literalmente una
rotación cíclica. **Es peor y se descartó al verificarla.** Una rotación
preserva el orden *cíclico*, pero al extraer la correcta para comparar el
contenido el orden *lineal* de los distractores cambia: el distractor que
precedía a la correcta pasa a seguirla. Eso rompe, por ejemplo, opciones
autoriadas en orden natural (`["8:15", "8:30", "8:45"]` deja de estar en orden).
El **movimiento** —extraer la correcta y reinsertarla en su destino— deja a los
distractores **en su orden relativo original**, así que el único cambio es la
posición de un elemento: el mínimo posible, y el que respeta el trabajo de
autoría.

La operación es **idempotente**: si la correcta ya está en su destino, la
reinserción devuelve la misma lista. Aplicarla dos veces no mueve nada.

---

## 3. El instrumento: `scripts/rebalance_mc_positions.py`

Es un instrumento de **contenido**, no una ruta de producto (no lo importa
ningún servicio), con dos modos:

```powershell
# Informa y NO escribe. Sale 1 si algún check no cumple la regla o si el
# reparto supera el 35 %.
python -m scripts.rebalance_mc_positions --check

# Aplica el reposicionamiento a los JSON de nivel.
python -m scripts.rebalance_mc_positions --write
```

Por qué es un candado y no un script de un solo uso: **`--check` es
re-ejecutable**. El contenido del currículum se va a reautorar en V4.0.x, y ese
es el momento en que el sesgo reaparece si nadie lo impide. `--check` sale **1**
en cuanto una revisión de contenido vuelva a concentrar la correcta, sin
necesidad de recordar qué se hizo aquí.

---

## 4. La cirugía: qué se toca y qué no

La reescritura **no** es un `json.dump` del fichero entero. Reescribir el nivel
completo arrastraría reformateo —el `dumps` expande las listas cortas que hoy van
en línea (`"accepted_answers": ["went"]`) y se come líneas en blanco— y dejaría un
diff irrevisable en el que los 368 cambios reales quedarían enterrados.

En su lugar, la reescritura es **por líneas**: se localiza el bloque de cada check
y se sustituyen **solo** los textos de las líneas de `options` (misma
indentación, misma coma) y el valor de `correct_index`. Todo lo demás se copia
literal. Antes de escribir, cada fichero pasa **tres invariantes**:

1. **Forma canónica** — con la correcta puesta en primer lugar, la lista de
   opciones es idéntica antes y después: misma opción correcta y mismos
   distractores **en el mismo orden relativo**.
2. **Nº de líneas intacto** — un recuento distinto delata una línea en blanco
   introducida o una pérdida de formato.
3. **JSON válido** tras la reescritura.

Y el JSON se valida **entero** después: si el fichero no parsea, el script falla
en alto en lugar de dejar contenido corrupto.

**Resultado del diff:** **614 inserciones / 614 borrados** en los 6 niveles, y
**cero** líneas en blanco añadidas. Son puros intercambios de línea.

---

## 5. El test: de declarar el sesgo a fijar el invariante

V3.70 dejó un test que **fijaba la cifra** precisamente para que fallase al
corregirla:

```python
# antes
assert positions[0] == 329
assert positions[0] / total >= 0.80
```

Ese contrato ya se cumplió (falló, y por eso se re-auditó el eje). Lo que se
reescribe es su contenido, no su espíritu:
`test_mc_position_bias_of_curriculum_checks_is_declared` pasa a
`test_mc_position_of_curriculum_checks_is_balanced` y ahora **fija el
invariante**:

- el reparto se mide **por grupo de `k`**;
- ninguna posición supera el **35 %** de su grupo;
- **ninguna posición queda muerta**: `set(counts) == set(range(k))`, es decir, la
  correcta debe ejercer **todas** las posiciones disponibles — que es lo que
  impide volver a esconder el 4.º distractor;
- y se conserva el invariante que ya existía para el corpus de listening
  (≤ 35 % por posición en sus 490 ítems).

El candado ahora muerde **en las dos direcciones**: también falla si una
reautoría futura vuelve a concentrar la correcta en una posición.

---

## 6. Medición antes y después

`python -m scripts.audit_dossier mc-bias`, después de aplicar el cambio:

| Grupo | n | Posición 0 | Posición 1 | Posición 2 | Posición 3 |
|---|---|---|---|---|---|
| **checks del currículum** | **368** | **33,4 %** | **33,2 %** | **32,9 %** | **0,5 %** |

Por grupo, que es donde vive el invariante:

| Grupo | n | Reparto de la correcta (después) |
|---|---|---|
| `k = 3` | 358 | `0:120 (33,5 %) · 1:119 (33,2 %) · 2:119 (33,2 %)` |
| `k = 4` | 10 | `0:3 (30 %) · 1:3 (30 %) · 2:2 (20 %) · 3:2 (20 %)` |

Peor posición: **33,5 %**, por debajo del límite del 35 %. Y el cambio por nivel
es el que se buscaba: A2, B2, C1 y C2 **dejan de estar al 100 % en la posición
0**.

Los artefactos `docs/audit/generated/mc-position-bias.{md,json}` y
`cefr-adequacy.{md,json}` se regeneran con los instrumentos que ya existían, que
son de solo lectura.

---

## 7. `CURRICULUM_VERSION` 1.3.0 → 1.3.1

La constante está declarada así en `services/curriculum.py`:

> **Versión del esquema/contenido del currículum y las evaluaciones.
> Independiente de la versión de la aplicación: identifica QUÉ contenido se
> evaluó.**

El contenido servido cambia, así que se sube. Antes de hacerlo se verificó el
alcance real: `curriculum_version` se **sella** en cada fila de evidencia y en
cada snapshot de perfil, pero **nunca se compara** en ninguna parte del código
—no dispara invalidación, ni recálculo, ni descarte de estado—. Subirla es
**provenance pura**: deja escrito con qué revisión de contenido se produjo cada
acierto, y no afecta al estado de ningún alumno.

---

## 8. Honestidad

(i) **El P2 de forma/longitud NO se cierra, y es deliberado.** La opción correcta
sigue siendo la más larga en el **39,1 %** de los checks del currículum y en el
**50 %** del placement. Reposicionar la correcta **no cambia ninguna longitud**:
son ejes distintos y ese sigue abierto (`#7` de `AA`).

(ii) **Exámenes y placement (`assessments.json`) no se tocan.** Sus 22 ítems
siguen con la correcta en la posición 0 en el **63,6 %** y el placement concentra
la correcta en la posición 1 en **17 de 24**. Son otro instrumento, con su propio
`ASSESSMENT_VERSION` y su propia medición; arreglarlos aquí habría mezclado dos
hallazgos.

(iii) **Esto elimina el atajo, no mejora los ítems.** Los distractores son los
mismos y el enunciado es el mismo. Un alumno que no entienda el enunciado sigue
teniendo la pista de la longitud (§i) y el conocimiento previo sigue siendo lo
único que resuelve el ítem **bien**. Lo que desaparece es acertar **sin leer**.

(iv) **La asignación es estable por revisión de contenido, no por ítem.**
Insertar o borrar un check desplaza la posición de los checks posteriores de su
mismo `k`, porque `j` es la posición dentro del grupo ordenado por `id`.
`--check` es exactamente el candado que detecta cualquier desviación resultante.

(v) **Que solo 10 de 368 checks tengan 4 opciones es una irregularidad de autoría
que este cambio no arregla.** El reposicionamiento hace que esas 10 ejerciten
sus 4 posiciones (2 de ellas en la 4.ª), pero la falta de uniformidad de forma
—número de opciones, longitud, tipo de distractor— es el P2 de forma, y sigue
abierto.

(vi) **Los 7 gates siguen en `pending`** y la identidad sellada en el kit sigue
siendo la del pre-vuelo (`3.73.6` → `13cc30b`), que es historia y no se
reescribe.

(vii) **No hay cambio de comportamiento del motor.** No se toca el argmax del
Planner, ni un umbral, ni una fórmula de mastery. La única vía por la que esto
puede mover una métrica es la legítima: los aciertos del alumno dejan de estar
correlacionados con la posición, así que las señales que el motor deriva son
menos ruidosas, no distintas.

---

## 9. Verificación

- **Backend:** `python -m pytest tests/ -q` → **2882 passed**. El recuento es
  **idéntico** al de V3.75.0: el test del eje se **reformuló en sitio**, no se
  añadió ni se retiró ninguno.
- **Frontend:** `npm test` → **721 passed** (87 ficheros), sin cambios.
- **Launcher:** `python -m pytest tests/ -q` → **142 passed**, sin cambios.
- **`ruff`** limpio sobre los ficheros tocados.
- **`check_release_consistency`** OK en los **6 orígenes** (`3.75.1`).
- **Instrumento idempotente:** `rebalance_mc_positions --check` sale **0**
  después de aplicar `--write`, y salía **1** antes (246 checks fuera de la
  regla, peor posición 90,8 %).
- **`validation_gate.py auto`**: **10/10** (no cambia).

---

## 10. Notas de actualización

**No hay nada que hacer.** No hay migración de BD, no hay variable de entorno
nueva, no hay ajuste de configuración y no hay dato que borrar. La siguiente vez
que la app sirva un check, servirá el mismo con la correcta en otra posición.

Si eres operador del repositorio y vas a **reautorar contenido**, el candado es:

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.rebalance_mc_positions --check   # debe salir 0
.\.venv\Scripts\python.exe -m scripts.audit_dossier mc-bias            # re-mide el reparto
```
