# AH · Sesgo de longitud de la opción correcta (V3.75.1 · pausa pedagógica)

> **Eje AH** de la auditoría psicométrica del banco. **Solo medición, cero
> correcciones.** Mide si la longitud de la opción correcta permite acertar sin
> comprender, y si esa señal se refuerza con la posición.
> Baseline congelado **V3.75.1** (`7962d57`, tag `v3.75.1`).
> Regla de evidencia `[D]` declarado · `[A]` leído en este commit · `[R]` ejecutado.

## Alcance

- **Se audita:** la longitud relativa de la opción correcta en los cuatro bancos
  MC (`checks_curriculum` 368 · `corpus_listening` 490 · `exams` 22 ·
  `placement` 24) y su interacción con la posición de la correcta. `[D]`
  `backend/scripts/audit_dossier.py:1310-1461`.
- **No se audita:** el contenido ni la calidad editorial de cada ítem; el número
  de opciones como deuda (eje `AJ`); la posición como sesgo propio (eje `AI`, P0
  ya cerrado); la inferibilidad por eco léxico/gramática/forma (eje `AK`); la
  adecuación CEFR (eje `AL`). Aquí solo se **cita** `assessments.json` cuando la
  longitud compone con la posición.
- **Cifra de partida (no se re-deriva como hallazgo nuevo):** correcta = opción
  más larga única en **39,1 %** de los checks y **50,0 %** del placement. `[D]`
  `docs/audit/AA-PED-CONTENIDO-CEFR.md:168` (hallazgo #7, P2) y
  `docs/audit/AE-PED-INSTRUMENTOS.md:50-51,106`.

## Método

1. **Instrumento** `[D]`: `item-form` y `cefr-adequacy` de
   `backend/scripts/audit_dossier.py`. La unidad de medida es
   `_length_profile(options, correct_index)` (`:1359-1397`), que declara:
   - `correct_is_longest`: la correcta es la **más larga única** del ítem;
   - `correct_is_longest_or_tied`: la correcta es la más larga **o empata al
     máximo**;
   - `length_ratio_to_distractors`: `len(correcta) / media(len(distractores))`;
   - `shape_outlier`: desviación ≥ 50 % de la mediana de distractores y la mayor
     del ítem.
   La fuente única de ítems es `mc_banks()` (`:1400-1461`), de modo que
   `item-form`, `distractor-signals` y `mc-bias` miden exactamente el mismo
   conjunto. `[A]`/`[R]`
2. **Muestreo:** no aleatorio. Se lee el **censo** de los 904 ítems MC y, para la
   parte cualitativa, una **muestra determinista** (primeros 3 ids ordenados por
   nivel con `correct_is_longest=True`; 18 ítems, semilla = orden lexicográfico
   de `id`). Se declara por ser reproducible, no representativa. `[R]`
3. **Criterio de referencia:** azar uniforme. En `k` opciones, la probabilidad de
   que la correcta sea (una de) la más larga bajo longitudes i.i.d. continuas es
   `1/k` ⇒ **33,3 %** en `k=3` y **25,0 %** en `k=4`. Para el agregado de checks
   se pondera por el reparto real de `k` (358 de 3 y 10 de 4):
   `(358·⅓ + 10·¼)/368 = 121,8/368 = 33,1 %`. `[R]`
4. **Sin re-medir otros ejes:** la posición se cita de `mc-position-bias.json` y
   `item-form`; no se re-deriva el P0 posicional.

## Evidencia

### 1. Tasa de correcta = opción más larga, por banco, nivel y grupo de `k`

Fuente `[A]`: `docs/audit/generated/item-form.json` / `.md` (líneas 35-56 del
`.md`) y `docs/audit/generated/cefr-adequacy.json` (`mc`, líneas 283-323).

| Grupo | N | k | más larga única | o empatada | ratio correcta/distractores |
|---|---|---|---|---|---|
| checks del currículum (todos) | 368 | 3:358 · 4:10 | 144 (39,1 %) | 219 (59,5 %) | 1,162 |
| checks A1 | 105 | 3:95 · 4:10 | 27 (25,7 %) | 52 (49,5 %) | 1,057 |
| checks A2 | 55 | 3 | 20 (36,4 %) | 32 (58,2 %) | 1,173 |
| checks B1 | 53 | 3 | 27 (50,9 %) | 34 (64,2 %) | 1,225 |
| checks B2 | 35 | 3 | 15 (42,9 %) | 23 (65,7 %) | 1,216 |
| checks C1 | 63 | 3 | 23 (36,5 %) | 37 (58,7 %) | 1,147 |
| checks C2 | 57 | 3 | 32 (56,1 %) | 41 (71,9 %) | 1,268 |
| corpus listening (todos) | 490 | 4 | 195 (39,8 %) | 266 (54,3 %) | 1,249 |
| corpus A1 | 200 | 4 | 59 (29,5 %) | 90 (45,0 %) | 1,186 |
| corpus A2 | 200 | 4 | 79 (39,5 %) | 112 (56,0 %) | 1,252 |
| corpus B1 | 25 | 4 | 15 (60,0 %) | 19 (76,0 %) | 1,360 |
| corpus B2 | 25 | 4 | 10 (40,0 %) | 13 (52,0 %) | 1,227 |
| corpus C1 | 20 | 4 | 16 (80,0 %) | 16 (80,0 %) | 1,482 |
| corpus C2 | 20 | 4 | 16 (80,0 %) | 16 (80,0 %) | 1,503 |
| exámenes finales (todos) | 22 | 3 | 8 (36,4 %) | 15 (68,2 %) | 1,221 |
| examen a1 | 10 | 3 | 2 (20,0 %) | 6 (60,0 %) | 1,111 |
| examen b1 | 12 | 3 | 6 (50,0 %) | 9 (75,0 %) | 1,312 |
| placement | 24 | 3 | 12 (50,0 %) | 18 (75,0 %) | 1,225 |

**Por grupo de `k`** (checks del currículum): `k=3`: 141/358 = **39,4 %** (o
empatada 212, 59,2 %; ratio 1,161); `k=4`: 3/10 = **30,0 %** (o empatada 7,
70,0 %; ratio 1,179). Los 10 ítems `k=4` son todos de A1. `[R]`

### 2. Ratio de longitud correcta / media de distractores (dónde aprieta el atajo)

Ordenado por ratio (`item-form.json` + `cefr-adequacy.json`):

| Grupo | ratio | lectura |
|---|---|---|
| corpus C2 | **1,503** | el atajo más fuerte: la correcta mide ~50 % más que la media de distractores |
| corpus C1 | **1,482** | 80 % de correctas más largas |
| corpus B1 | 1,360 | 60 % más largas (n=25, ruidoso) |
| examen b1 | 1,312 | 50 % más largas |
| corpus A2 | 1,252 | 39,5 % más largas |
| corpus A1 | 1,186 | 29,5 % (el corpus donde menos aprieta) |
| checks C2 | **1,268** | el más fuerte de los checks |
| checks B1 | 1,225 | 50,9 % |
| placement | 1,225 | 50,0 % (compone con posición 1, ver §3) |
| checks B2 | 1,216 | 42,9 % |
| checks A2 | 1,173 | 36,4 % |
| checks C1 | 1,147 | 36,5 % |
| checks A1 | **1,057** | prácticamente sin señal de longitud |

### 3. Interacción longitud × posición (tabla cruzada construida en este eje)

El artefacto `item-form` **no** cruza longitud con posición; el eje AH lo
construye de forma reproducible. **Método exacto:** se importa `mc_banks()` y
`_length_profile()` del propio instrumento y se agrupa por `profile["index"]`,
contando `correct_is_longest` por posición. No se reimplementa ninguna
heurística: se reutiliza la función declarada (`:1359-1397`). Comando en
§Regenerar. `[R]`

**Checks del currículum (todos)** — % de ítems en los que la correcta es la más
larga única, por posición:

| Grupo | pos 0 | pos 1 | pos 2 | pos 3 |
|---|---|---|---|---|
| checks (todos) | **44,7 %** (55/123) | 36,9 % (45/122) | 36,4 % (44/121) | 0,0 % (0/2) |
| checks A1 | 31,4 % (11/35) | 22,9 % (8/35) | 24,2 % (8/33) | 0,0 % (0/2) |
| checks A2 | **50,0 %** (9/18) | 27,8 % (5/18) | 31,6 % (6/19) | — |
| checks B1 | 44,4 % (8/18) | **61,1 %** (11/18) | 47,1 % (8/17) | — |
| checks B2 | 41,7 % (5/12) | 45,5 % (5/11) | 41,7 % (5/12) | — |
| checks C1 | 42,9 % (9/21) | 23,8 % (5/21) | 42,9 % (9/21) | — |
| checks C2 | **68,4 %** (13/19) | 57,9 % (11/19) | 42,1 % (8/19) | — |
| corpus (todos) | 39,2 % (49/125) | 40,5 % (49/121) | 38,5 % (47/122) | 41,0 % (50/122) |
| exámenes | 35,7 % (5/14) | 37,5 % (3/8) | muerta (0/0) | — |
| placement | **66,7 %** (4/6) | 47,1 % (8/17) | 0,0 % (0/1) | — |

Lectura `[R]`:
- **En el agregado de checks la señal NO es independiente de la posición:** pos 0
  = 44,7 % frente a ~36,5 % en pos 1-2 (+8,2 pp). La posición está balanceada por
  la regla `j % k`, así que ese exceso es cola de autoría, no de reparto.
- **La dirección depende del nivel:** en A1/A2/C2 el máximo está en pos 0; en B1
  el máximo está en pos 1 (61,1 %); C1 no tiene dirección clara. No hay un patrón
  único «longitud ⇒ primera».
- **En corpus la posición no importa:** 38,5-41,0 % plano en las cuatro
  posiciones. El sesgo de longitud del corpus es ortogonal a la posición.
- **Placement compone con `AI`:** de 24 ítems, 12 son «correcta = más larga» y
  17 tienen la correcta en la posición 1; **8/24 (33,3 %) son simultáneamente
  «más larga» y «posición 1»**. La coincidencia de los dos atajos es lo que
  eleva el vector de explotación (ver §4).

### 4. Base aleatoria y margen sobre el azar

| Grupo | N observado | azar esperado `n/k` | observado | margen (pp) | ratio obs/azar |
|---|---|---|---|---|---|
| checks (todos, k mixto 3/4) | 144 | 121,8 (33,1 %) | 39,1 % | **+6,0** | 1,18 |
| — checks `k=3` | 141 | 119,3 (33,3 %) | 39,4 % | +6,1 | 1,18 |
| — checks `k=4` | 3 | 2,5 (25,0 %) | 30,0 % | +5,0 | 1,20 |
| corpus listening (k=4) | 195 | 122,5 (25,0 %) | 39,8 % | **+14,8** | 1,59 |
| exámenes (k=3) | 8 | 7,3 (33,3 %) | 36,4 % | +3,1 | 1,09 |
| placement (k=3) | 12 | 8,0 (33,3 %) | 50,0 % | **+16,7** | 1,50 |

Para «más larga o empatada» el azar también es `1/k`, y el margen se dispara
(checks 59,5 % vs 33,1 % = +26,4 pp; corpus 54,3 % vs 25,0 % = +29,3 pp;
placement 75,0 % vs 33,3 % = +41,7 pp). Pero ese número **no** es la tasa de
acierto de la estrategia: si hay empate a máximo, elegir «la más larga» acierta
solo con probabilidad `1/n_empate`.

**Valor real de la estrategia** «elegir siempre la opción más larga, desempatar
al azar», calculado ítem a ítem como `E[1/n_longest · 1{correcta es máxima}]`
`[R]`:

| Banco | Estrategia longitud | Azar 1/k | Margen |
|---|---|---|---|
| checks_curriculum | **48,05 %** | 33,1 % | +14,9 pp |
| corpus_listening | **46,48 %** | 25,0 % | +21,5 pp |
| exams | 50,76 % | 33,3 % | +17,4 pp |
| placement | **61,11 %** | 33,3 % | +27,8 pp |

Nota de honestidad `[R]`: `AE-PED-INSTRUMENTOS.md:106` afirma que «un alumno que
siempre elija la opción más larga acierta tres cuartas partes» del placement.
Ese 75 % es la tasa **«más larga o empatada»**, no la de la estrategia: con
desempate al azar el valor medido es **61,1 %**. Sigue siendo un atajo muy
potente (+27,8 pp sobre el azar), pero la cifra correcta es 61,1 %.

### 5. Muestra determinista (cualitativa)

Muestra: primeros 3 `id` por nivel con `correct_is_longest=True` (18 ítems).
**Medido** = cifras; **interpretado** = la lectura del ítem.

| id | nivel | longitud (correcta : distractores) | lectura |
|---|---|---|---|
| `a1-m01-u01-l01-o01-c01` | A1 | `country` 7 : `name` 4 · `city` 4 | «Which word means 'país'?». La correcta es la única traducción válida; es la más larga por 3 caracteres. Un no-comprendedor acierta por longitud. **Atajo explotable** (medido: ratio 1,75). |
| `a1-m01-u01-l01-o02-c03` | A1 | `Where` 5 : `What` 4 · `Who` 3 | «Which question word for a place?». La correcta es la más larga por 1 carácter, pero la pregunta exige sentido. Longitud **incidental**. |
| `a1-m01-u01-l01-o02-c04` | A1 | `your` 4 : `my` 2 · `his` 3 | «Which word means 'tu'?». Correcta más larga; longitud **explotable** para quien no sepa el posesivo. |
| `a2-m01-u01-l01-o02-c01` | A2 | 21 : 19 · 20 | «Choose the correct sentence (Present Perfect)». Diferencias de 1-2 caracteres; la corrección es gramatical. Longitud **no explotable**. |
| `a2-m02-u01-l01-o01-c04` | A2 | `cheaper` 7 : `bigger` 6 · `more` 4 | «más barato». La correcta más larga coincide con el superlativo correcto; el distractor compite por longitud. **Atajo débil**. |
| `a2-m02-u01-l01-o02-c01` | A2 | 40 : 30 · 35 | Frase superlativa correcta; la correcta es la más informativa y la más larga. Frontera difusa. |
| `b1-m01-u01-l02-o04-c01` | B1 | `I see your point, but` 21 : `You are wrong` 13 · `No way` 6 | «Which phrase politely introduces a disagreement?». La opción más larga **es** la única pragmáticamente correcta: la longitud correlaciona con la cortesía/paráfrasis. **Atajo explotable**. |
| `b1-m01-u01-l02-o03-c01` | B1 | `In my opinion` 13 : 10 · 10 | «Which phrase introduces a personal opinion?». Correcta más larga; longitud **explotable** (frase hecha frente a fragmentos). |
| `b2-m01-u01-l01-o02-c02` | B2 | 42 : 39 · 41 | Frase correcta de `owing to`; diferencias mínimas. Longitud **no explotable**. |
| `c1-m01-u01-l01-o03-c02` | C1 | 29 : 28 · 14 | «Never have I seen such dedication…». La correcta parafrasea con precisión («How unusual...»); el distractor corto es el señuelo literal. **Semi-explotable**: la correcta es también la más informativa. |
| `c1-m02-u01-l01-o01-c02` | C1 | 29 : 21 · 16 | «He cut corners...». La correcta es la glosa más completa; longitud = información. |
| `c2-m01-u01-l01-o01-c02` | C2 | 29 : 18 · 13 | «A rhetorical question is asked...». La correcta (`for effect, not for an answer`) es la más específica y la más larga. **Semi-explotable**. |
| `c2-m01-u01-l01-o01-c03` | C2 | `understatement` 14 : `hyperbole` 9 · `repetition` 10 | Léxico; la correcta es el término más largo. Longitud **explotable** para quien no domine los términos. |

Patrón cualitativo `[R]` (interpretado, no medido como señal):
- **A1 y B1:** varios ítems donde la correcta es la opción «más elaborada»
  (traducción única, frase hecha, cortesía). El atajo de longitud es **real y
  explotable** ítem a ítem.
- **A2/B2 (gramática de frase):** el diferencial de longitud es de 1-3 caracteres
  y la corrección es sintáctica; el atajo **no es fiable**.
- **C1/C2 (paráfrasis/glosa):** la correcta es sistemáticamente la más
  informativa, y por eso más larga. Es a la vez **la opción más informativa y un
  atajo**: la frontera entre «más clara» y «más larga» es difusa por diseño.

## Hallazgos

| # | Severidad | Hallazgo | Evidencia | Recomendación (propuesta, no implementada) | Estado |
|---|---|---|---|---|---|
| AH-1 | **P2** | **Checks del currículum:** la correcta es la más larga única en 144/368 = **39,1 %** frente al 33,1 % esperado por azar (+6,0 pp); la estrategia «elegir la más larga» rinde **48,1 %**. Señal real pero moderada; no hay atajo dominante. | `item-form.json`; §Evidencia 1 y 4 `[R]` | Normalizar longitudes al regenerar contenido (V4.x). No es urgente por sí solo. | abierto |
| AH-2 | **P1** | **Corpus de listening:** 195/490 = **39,8 %** frente al 25,0 % del azar (**+14,8 pp**, ratio 1,59); estrategia longitud **46,5 %**. En C1 y C2 la correcta es la más larga en **16/20 = 80,0 %** (ratio 1,48-1,50). Es el atajo más fuerte medido. | `item-form.json`; §Evidencia 1, 2 y 4 `[R]` | Reequilibrar longitudes del corpus C1/C2 al reautorar; prioridad alta dentro de la deuda de forma. | abierto |
| AH-3 | **P1** | **Placement:** 12/24 = **50,0 %** de correctas más largas, 18/24 = 75,0 % «más larga o empatada»; estrategia longitud **61,1 %** frente al 33,3 % del azar (+27,8 pp). **8/24 son «más larga» y «posición 1» a la vez** (`AI` mide 17/24 en posición 1). El nivel se puede inflar sin comprender. | `item-form.json`; `mc-position-bias.json`; §Evidencia 3 y 4 `[R]` | Corregir junto con el sesgo posicional de placement (`AI`), no por separado. | abierto |
| AH-4 | **P2** | **Gradiente de nivel no monótono en checks:** C2 **56,1 %** (ratio 1,268) y B1 **50,9 %** (ratio 1,225) son los peores; A1 es el único **por debajo del azar** (25,7 % vs 33,3 %). El sesgo no es «de todo el banco»: se concentra en niveles medios-altos. | `item-form.json`; §Evidencia 1 y 3 `[R]` | Aplicar la normalización con prioridad C2/B1. | abierto |
| AH-5 | **P3** | **La longitud no es independiente de la posición:** en checks, pos 0 = 44,7 % vs ~36,5 % en pos 1-2; la dirección cambia por nivel (A1/A2/C2 → pos 0; B1 → pos 1). En corpus es plana (38,5-41,0 %). Dato metodológico: «longitud» y «primera» no son ortogonales en el currículum. | §Evidencia 3 `[R]` | No tratar longitud y posición como deudas separadas en la corrección. | abierto |
| AH-6 | **P2** | **Exámenes finales:** 8/22 = 36,4 % (solo +3,1 pp sobre el azar), pero 15/22 = 68,2 % «más larga o empatada» y estrategia longitud **50,8 %** (frente a 33,3 %). Efecto moderado, agravado por la posición 2 muerta que ya mide `AI`. | `item-form.json`; §Evidencia 1 y 4 `[R]` | Coordinar con `AI` y `AJ`. | abierto |

**Honestidad (regla del briefing):** un ítem con la correcta más larga **no** es
por sí solo un ítem malo; en la muestra, varios son simplemente la opción más
informativa o la única paráfrasis correcta. Lo medido es la **tasa** (39,1 %
checks, 39,8 % corpus, 50,0 % placement) y su **valor predictivo** sobre el azar
(+6,0 / +14,8 / +16,7 pp; estrategia 48,1 / 46,5 / 61,1 %). La parte cualitativa
es interpretación declarada, no medición.

## Veredicto

**No aprobado en el invariante de neutralidad de longitud; aprobado con matices
en el resto.** Hay una señal de longitud medible por encima del azar en los
cuatro bancos, **fuerte** en el corpus C1/C2 (80 %) y en placement (estrategia
61,1 %), y **moderada** en los checks (39,1 % vs 33,1 %). No hay posición muerta
de longitud ni atajo determinista del 100 %, y en varios ítems la correcta larga
es sencillamente la más informativa. La deuda es de **forma y autoría**, no un
defecto ítem a ítem; se cierra con la corrección de contenido de V4.x, no con un
candado que fije el defecto.

## Regenerar / Verificar

Procedencia de las cifras y comandos desde `backend` (PowerShell 5.1; sin `&&`):

```powershell
# 1. Artefactos de origen (item-form y cefr-adequacy). NO se re-ejecutan para
#    no escribir en docs/audit/generated/ (regla dura de este eje); se leen:
#    docs/audit/generated/item-form.{md,json}
#    docs/audit/generated/cefr-adequacy.json   (bloque "mc")
#    Si en el futuro se regeneran, este es el comando declarado:
.\.venv\Scripts\python.exe -m scripts.audit_dossier item-form
.\.venv\Scripts\python.exe -m scripts.audit_dossier cefr-adequacy

# 2. Tabla cruzada longitud x posición y valor de la estrategia "más larga"
#    (reutiliza mc_banks() y _length_profile() del propio instrumento; solo lectura).
@'
import json
from collections import defaultdict
import sys
sys.path.insert(0, ".")
from scripts.audit_dossier import mc_banks, _length_profile

banks = mc_banks()
def cross(rows):
    out = defaultdict(lambda: {"n":0,"longest":0})
    for r in rows:
        p = _length_profile(r["options"], r["correct_index"])
        if p is None: continue
        d = out[p["index"]]; d["n"] += 1
        d["longest"] += 1 if p["correct_is_longest"] else 0
    return {str(k): {"n":v["n"],"longest":v["longest"],
            "pct": round(100*v["longest"]/v["n"],1) if v["n"] else 0}
            for k,v in sorted(out.items())}
print(json.dumps({
  "checks": cross(banks["checks_curriculum"]),
  "checks_k3": cross([r for r in banks["checks_curriculum"] if len(r["options"])==3]),
  "checks_k4": cross([r for r in banks["checks_curriculum"] if len(r["options"])==4]),
  "corpus": cross(banks["corpus_listening"]),
  "exams": cross(banks["exams"]),
  "placement": cross(banks["placement"]),
  **{lv: cross([r for r in banks["checks_curriculum"] if r["level"]==lv])
     for lv in ["A1","A2","B1","B2","C1","C2"]}}, ensure_ascii=False, indent=1))

# 3. Valor de la estrategia "elegir siempre la más larga, desempatar al azar"
def strategy(rows):
    tot=0.0; n=0
    for r in rows:
        opts=r.get("options") or []; idx=r.get("correct_index")
        if not isinstance(idx,int) or not 0<=idx<len(opts): continue
        lens=[len(str(o)) for o in opts]; m=max(lens); n+=1
        if lens[idx]==m: tot += 1.0/lens.count(m)
    return round(100.0*tot/n,2), n
for name in ("checks_curriculum","corpus_listening","exams","placement"):
    print(name, strategy(banks[name]))

# 4. Muestra determinista (primeros 3 id por nivel con correcta más larga única)
for lv in ["A1","A2","B1","B2","C1","C2"]:
    rows=[r for r in banks["checks_curriculum"] if r["level"]==lv
          and _length_profile(r["options"], r["correct_index"])["correct_is_longest"]]
    for r in sorted(rows, key=lambda r: r["id"])[:3]:
        print(lv, r["id"], r["correct_index"],
              [len(str(o)) for o in r["options"]], "::", str(r["prompt"])[:80])
'@ | .\.venv\Scripts\python.exe -X utf8 -
```

## Tests que respaldan

`[A]` `backend/tests/test_psy_item_form_v3751.py` (contrato del instrumento, no
las cifras del defecto):

- `test_mc_banks_son_los_cuatro_bancos_declarados` / `TAMANO_BANCOS`: fija
  368/490/22/24, la misma base que mide este eje.
- `test_length_profile_marca_la_mas_larga_unica_y_los_empates` y
  `test_length_profile_rechaza_lo_que_no_es_un_mc_valido`: contrato de la unidad
  de medida usada en todas las tablas.
- `test_shape_outlier_solo_dispara_con_la_desviacion_mayor`: valida la señal
  `shape_outlier` citada por `AK`.
- `test_item_form_posiciones_y_k_suman_y_las_muertas_lo_son` y
  `test_item_form_marca_el_reparto_por_grupo_no_solo_el_agregado`: coherencia de
  los totales que se citan.
- `test_el_instrumento_no_escribe_en_data_ni_en_curriculum`: garantiza que estas
  mediciones son de solo lectura.
