# AK · Inferibilidad de los distractores — V3.75.1

> **Release auditada:** V3.75.1 · **commit:** `7962d57de719ee8e4c62b0f3017c517b04714408`
> **Tag:** `v3.75.1` (anotado) · **rama:** `main`
> **Fecha de la auditoría:** 2026-09-19
> **Eje:** AK · ¿la opción correcta se puede identificar sin comprender?
> **Instrumento:** `backend/scripts/audit_dossier.py::distractor-signals` (solo
> lectura) + las funciones puras del mismo módulo, ejecutadas con el intérprete
> del proyecto (`backend/.venv`).
> **Regla dura respetada:** no se ha modificado ningún fichero salvo este
> dossier. En particular **no se ha ejecutado el subcomando CLI**, porque
> reescribe `docs/audit/generated/distractor-signals.{md,json}`; las cifras se
> reprodujeron importando las funciones puras, que no escriben nada.

## Alcance

**Entra:**

- Las **tres señales declaradas** del instrumento (`prompt_keyword_echo`,
  `shape_outlier`, `quantity_literal`): recuento por banco, definición exacta
  `[D]` y límites.
- La **muestra determinista** que el propio artefacto incluye (5 ítems por banco,
  semilla `7`): lectura cualitativa con ids.
- **Patrones adicionales** medidos de forma declarada y reproducible sobre el
  universo completo (904 MC), fuera del instrumento, como candidatos a señal.

**No entra (declarado, para no solapar):**

- **Longitud de la correcta** → eje `AH` (`AA` #7: 39,1 % checks · 50,0 %
  placement). Aquí solo se mide en qué **dirección** dispara `shape_outlier`,
  citando la cifra de `AH`, sin re-derivarla.
- **Posición de la correcta** → eje `AI`; **número de opciones `k`** → eje `AJ`;
  **gradiente por nivel** → eje `AL`.
- **Plausibilidad semántica** real de un distractor: **no es medible** sin
  hablantes nativos / juicio experto (§AK-5). No se finge con una métrica.
- **Corrección de contenido.** Cero correcciones; los hallazgos de este eje son
  de **medición** y de **forma**, y su cierre se propone, no se implementa.

## Método

1. **Solo lectura.** Instrumento leído `[A]` en este commit y ejecutado sin
   escribir en `docs/audit/generated/` `[R]`.
2. **Población = universo.** Los recuentos se calculan sobre los **904 MC**
   completos (`mc_banks()`), no sobre una muestra. La muestra determinista del
   artefacto (n≤5 por banco, semilla fija) se usa solo para lo **cualitativo**:
   no estima tasas.
3. **Regla de evidencia `[D]`/`[A]`/`[R]`** en toda afirmación.
4. **Anti-solapamiento.** Se parte de las cifras del briefing y se citan; no se
   re-derivan las de otros ejes.
5. **Medición ad-hoc declarada.** Los patrones adicionales (§AK-4) se definen por
   escrito y se reproducen con el script del §Regenerar. Se marcan como
   **recomendación para la fase de cierre**, nunca como modificación del
   instrumento.

## Evidencia

### Baseline y trazabilidad

| Concepto | Valor | Procedencia |
|---|---|---|
| Commit | `7962d57de719ee8e4c62b0f3017c517b04714408` | `git rev-parse HEAD` `[R]` |
| Tag anotado | `v3.75.1` → mismo commit (`obj 2cd0e6d`, `deref 7962d57`) | `git rev-list -n 1 v3.75.1` `[R]` |
| Rama | `main` (`HEAD -> main, tag: v3.75.1`) | `git log -1` `[R]` |
| `CURRICULUM_VERSION` | `1.3.1` | `services/curriculum.py:205` `[A]` |
| `ASSESSMENT_VERSION` | `1.0.0` | `services/curriculum.py:210` `[A]` |
| Bancos MC | checks 368 · corpus 490 · exámenes 22 · placement 24 = **904** | `item-form.md` + `mc_banks()` `[R]` |

**Verificación positiva:** los recuentos declarados se reprodujeron **exactos**
con las funciones puras (sin escribir el artefacto): checks `{shape_outlier: 59,
prompt_keyword_echo: 22}`, corpus `{shape_outlier: 103, prompt_keyword_echo: 2}`,
exámenes `{shape_outlier: 6, prompt_keyword_echo: 3}`, placement `{shape_outlier:
4, prompt_keyword_echo: 2, quantity_literal: 1}`. Coinciden con
`docs/audit/generated/distractor-signals.json`. `[R]`

---

### AK-1 · Las tres señales declaradas: definición exacta, recuento y límites

Definiciones declaradas en `DISTRACTOR_SIGNALS`
(`backend/scripts/audit_dossier.py:1318-1331`):

```startLine:1318:1331:backend/scripts/audit_dossier.py
DISTRACTOR_SIGNALS: dict[str, str] = {
    "prompt_keyword_echo": (
        "El enunciado comparte una palabra de contenido con la opción correcta "
        "y con ninguna otra: la correcta se puede emparejar sin comprender."
    ),
    "shape_outlier": (
        "La opción correcta es el outlier de longitud: se desvía de la mediana "
        "de los distractores en >= 50 % y esa desviación es la mayor del ítem."
    ),
    "quantity_literal": (
        "El enunciado pide una cantidad o un momento (how many, what time, "
        "when...) y solo la opción correcta contiene una cifra, un número "
        "escrito o un día de la semana."
    ),
}
```

**Recuento por banco** (reproducido, `[R]`; idéntico al artefacto):

| Banco | N | con señal | `prompt_keyword_echo` | `shape_outlier` | `quantity_literal` |
|---|---|---|---|---|---|
| checks_curriculum | 368 | 79 | 22 (6,0 %) | 59 (16,0 %) | 0 (0,0 %) |
| corpus_listening | 490 | 104 | 2 (0,4 %) | 103 (21,0 %) | 0 (0,0 %) |
| exams | 22 | 7 | 3 (13,6 %) | 6 (27,3 %) | 0 (0,0 %) |
| placement | 24 | 6 | 2 (8,3 %) | 4 (16,7 %) | 1 (4,2 %) |

`prompt_keyword_echo` — implementación en `_prompt_keyword_echo`
(`:1630-1644`) `[A]`:

- Usa `_content_words`, que descarta palabras de **≤2 letras** y las de
  `STOPWORDS` (`:348-357`).
- **No lematiza**: `eat`/`eats`, `check`/`checks` no emparejan.
- Dispara **solo si la correcta es la única** opción que comparte una palabra de
  contenido con el enunciado. Es, por definición, un **eco exclusivo**.

`shape_outlier` — implementación en `_length_profile` (`:1392-1396`) `[A]`:
desviación `|len(correcta) − mediana(distractores)| ≥ 0,5 × mediana` y **mayor
que la de cualquier distractor**. Es **agnóstica a la dirección**: la correcta
puede ser la más larga o la más corta.

`quantity_literal` — prompt regex en `:1335-1338` y número/día en `:1342-1349`
`[A]`; la señal exige que **el enunciado case el regex** y que **solo la
correcta** contenga número/día.

---

### AK-2 · Muestra determinista: lectura cualitativa con ids

La muestra (`distractor_signals`, `:1692-1693`, semilla `7`, hasta 5 por banco
**solo entre los marcados**) no estima tasas; ilustra. `[A]`

**Eco léxico exclusivo — la correcta se empareja sin comprender:**

- `a1-m05-u01-l01-o03-c01`: *"…Maria eats an apple… What does Maria eat?"* →
  correcta `2:An apple`. El eco `apple` es exclusivo: se acierta sin entender.
- `a1-m06-u01-l01-o03-c02`: `jacket` en enunciado y en la correcta `1:A jacket`.
- `c1-m01-u01-l01-o03-c02`: `dedication` en el audio y en la correcta
  `1:How unusual the dedication is`.
- `a1f-08` (examen A1): `breakfast` en el enunciado y en la correcta
  `1:Has breakfast`.
- `pl-13` (placement): `market` en el audio y en `0:To the market`.
- En exámenes, los tres ítems con eco **exclusivo** son `a1f-08`, `b1f-06` y
  `b1f-10`; `a1f-07` y `b1f-09` **contienen** eco en la correcta pero el
  instrumento **no** los marca, porque un distractor también lo contiene (es el
  subconteo de AK-02).

**`shape_outlier` — la correcta es la más larga:**

- `a2-m02-u01-l01-o03-c03`: `'más caro'` → `0:more expensive` frente a
  `cheaper`/`bigger`. Además la correcta es la única opción de dos palabras.
- `b1-m03-u01-l01-o17-c02`: `1:What happened next?` única interrogativa; las
  otras dos son cierres (`I see.`, `That's it.`).
- `c020`, `c097`, `c152`, `c388` (corpus): la correcta es la más larga con
  holgura (`c388`: `1:The minutes sent to everyone` = 29 car. frente a
  `A day off`/`A new schedule`/`A shorter meeting`).
- `a1f-03`: `There ___ two bedrooms` → `1:are`; aquí `shape_outlier` **coincide
  con el constructo** (concordancia plural), no es un atajo independiente.
- `b1f-07`, `b1f-08`, `pl-12`: la correcta repite el contenido del enunciado con
  más palabras.

**Señal doble (eco + forma) — el caso más inferible:**

- `b1f-06`: `In my opinion` es a la vez eco (`opinion` en el enunciado) y la
  opción más larga.
- `pl-04`: eco (`eight`) **y** `quantity_literal`; es el único ítem del banco
  con las dos señales de cantidad/eco simultáneas.
- `pl-18`: `1:I see your point, but I'd argue that...` es la más larga **y** la
  única de registro adecuado; los distractores son de caricatura
  (`Nah, that's dumb.`, `You're totally wrong.`). Es el mejor ejemplo de que
  **forma y registro** coinciden, y de que la "absurdidad" no es medible (§AK-5).

**Lo que la muestra NO permite concluir:** con 5 ítems por banco y solo entre los
marcados, la muestra no da una tasa ni prueba que el resto del banco esté limpio;
solo confirma que las señales, cuando disparan, describen atajos reales.

---

### AK-3 · Patrones adicionales medidos (ad-hoc declarado)

Candidatos que el instrumento **no** captura, medidos sobre los 904 MC con el
script del §Regenerar. Se declaran como **medición externa al instrumento**.

| # | Patrón candidato | Definición operativa | Resultado `[R]` | Veredicto |
|---|---|---|---|---|
| C1 | opciones que repiten una palabra del enunciado | palabra de contenido (`len>2`, no stopword) del enunciado ∩ opción | correcta con eco: **80/904 (8,9 %)** vs 29 declarados; eco ambiguo (también un distractor): 51; **solo un distractor**: 21 | **AK-02**: el instrumento mide el eco **exclusivo**, no la presencia |
| C2 | categoría distinta (número vs texto) | opciones con ≥1 número/día y ≥1 sin él | **32 ítems** (checks 7 · corpus 23 · exams 1 · placement 1) | sin atajo sistemático: en 69/87 enunciados de cantidad **todas** las opciones son numéricas |
| C3 | opciones con la misma raíz | prefijo común ≥4 de la 1.ª palabra de contenido | **118/368** checks (32,1 %) · 117/490 corpus (23,9 %) | **ruido**: lo dominan la morfología paralela y los ítems de orden; se descarta como señal |
| C4 | distractores sinónimos entre sí | Jaccard de palabras de contenido ≥0,5 entre dos distractores | **85/368** checks (23,1 %) · 20 corpus · 5 exams · 7 placement | **no es sinonimia**: el proxy se dispara con permutaciones y variantes de hora, no con significado |
| C5 | distractores permutación de la correcta | multiconjunto de palabras de contenido de la correcta = el de un distractor | **59 ítems** (checks 56 = 15,2 % · placement 2 · exams 1 · corpus 0) | **por diseño**: son ítems de orden de palabras; la correcta es la gramatical |
| C6 | incompatibilidad gramatical con el hueco | — | 9 ítems con hueco `___` (8 checks + `a1f-03`) | **no medible sin POS/hablante**: la compatibilidad **es** el constructo del ítem; medirla sería circular |
| C7 | distractores absurdos o cómicos | — | solo cualitativo (`pl-18`) | **no medible**: se declara, no se finge |

**Recuento de `quantity_literal` (C2/C6 relacionado):** hay **87 enunciados de
cantidad/momento** en el banco (checks 13 · corpus 73 · placement 1) y **69**
ofrecen **≥2 opciones numéricas**; solo **1 ítem** (`pl-04`) ofrece exactamente
una (la correcta) y dispara la señal. Es decir: el `0,0 %` de tres bancos **no
significa "sin atajo de cantidad"**, significa que la heurística casi no puede
dispararse. `[R]`

---

### AK-4 · Señales: qué solapa y qué no

- **`shape_outlier` solapa con `AH`.** Dispara 172 veces (59+103+6+4); en
  **167/172 (97,1 %)** la correcta es **la más larga única** (la cifra de `AH`
  #7 es 39,1 % checks · 50,0 % placement; se cita, no se re-deriva). Solo **5**
  ítems tienen la correcta **más corta** que la mediana de sus distractores:
  `a1-m04-u01-l01-o02-c01` (`on` vs `under`/`behind`),
  `c1-m03-u01-l01-o03-c02` (`Hedging`),
  `c2-m02-u01-l01-o03-c03` (`plus`),
  `c2-m02-u01-l02-o01-c03` (`Irony`),
  `c123` (`Irony`). Esos 5 son lo único que `shape_outlier` aporta sobre la
  señal de longitud de `AH`.
- **Las tres señales son casi disjuntas.** Solo **6 ítems** disparan ≥2 señales:
  `a1-m07-u01-l01-o01-c03`, `a2-m03-u01-l01-o03-c01`, `c268`, `b1f-06`,
  `b1f-10` (eco+forma) y `pl-04` (eco+cantidad). El total «con señal» es por
  tanto la unión casi exacta de las tres. `[R]`
- **`prompt_keyword_echo` no ve el eco por raíz.** Un stemmer trivial
  (prefijo ≥4, palabras de ≥5 letras) añadiría **9 ítems** (4 checks, 3 corpus, 2
  exámenes) donde la correcta comparte raíz con el enunciado sin palabra exacta.
  Es un **límite declarado**, no una corrección. `[R]`

---

### AK-5 · Honestidad: lo que esta medición NO demuestra

1. **La plausibilidad semántica de un distractor no es medible aquí.** Requiere
   hablantes nativos o juicio experto. Ninguna de las cifras de este dossier
   dice si un distractor es *creíble*: dice si comparte forma, palabra o
   categoría con la correcta. Un distractor con eco puede ser perfectamente
   plausible; uno sin eco, absurdo.
2. **Sinonimia: no medida.** El proxy de solapamiento léxico (C4) **no** es
   sinonimia: se dispara con permutaciones (`I is…`/`I are…`) y variantes de hora
   (`At nine`/`At nine twenty`). No existe en el repo un lexicón semántico con el
   que medirla.
3. **Incompatibilidad gramatical: no medida.** El banco no tiene POS-tagger;
   además, en los 9 ítems con hueco la compatibilidad **es** el constructo
   (concordancia, orden), de modo que usarla como "atajo" sería circular.
4. **Absurdidad/cómico: no medida.** `pl-18` es el caso cualitativo; convertirlo
   en métrica exigiría juicio, no una heurística.
5. **Presencia de eco ≠ inferibilidad.** Que la correcta contenga una palabra del
   enunciado (80 ítems) no la hace elegible sin comprender: si **otro** distractor
   también la contiene (51 casos), emparejar solo reduce a dos y hay que
   entender. Por eso el hallazgo AK-02 es un **límite de la métrica**, no una
   tasa de ítems rotos.
6. **La muestra determinista no estima.** n≤5 por banco, solo entre marcados.

## Hallazgos

| # | Severidad | Hallazgo | Evidencia | Recomendación (cierre) | Estado |
|---|---|---|---|---|---|
| **AK-01** | **P2** | `quantity_literal` es prácticamente inerte: dispara **1/904** (solo `pl-04`). Hay **87 enunciados de cantidad/momento** y **69** con ≥2 opciones numéricas. El `regex` de prompt omite `"how often"` (`c379`) y `_NUMBER_OR_DAY_RE` no ve plurales (`Wednesdays`, `c077`) ni ordinales (`first`, `c488`). El `0,0 %` de checks/corpus/exámenes es un **falso negativo**, no una ausencia de atajo | `:1335-1338`, `:1342-1349`, `:1647-1661` `[A]`; recuento y sondas §Regenerar `[R]`; caso `c379` | Ampliar el léxico del prompt (`how often`, `how early`, `what day`) y el número/día (plurales, ordinales, `once`/`twice`); **no** implementar aquí, proponer como subcomando/sonda en cierre | abierto |
| **AK-02** | **P2** | `prompt_keyword_echo` mide **eco exclusivo** (29/904), no presencia: la correcta contiene una palabra del enunciado en **80/904 (8,9 %)**; **51** de esos casos se suprimen porque un distractor también la contiene, y en **21** el eco está **solo** en un distractor. La cifra declarada es un **suelo**, no la tasa del atajo | `:1630-1644` `[A]`; recuento §Regenerar `[R]` | Declarar el subconjunto "eco presente/no exclusivo" como medición aparte; hoy no existe | abierto |
| **AK-03** | **P3** | `shape_outlier` **no es una señal independiente**: en **167/172 (97,1 %)** coincide con "correcta = más larga única" del eje `AH`, y es unidireccional (167 larga · 5 corta). Aporta información solo en los 5 casos de correcta **más corta** | `:1392-1396` `[A]`; recuento §Regenerar `[R]`; cifra `AH` citada | Documentar el solape `AK↔AH` en la síntesis `AM`; los 5 casos cortos son el único delta | abierto |
| **AK-04** | **P3** | El solapamiento léxico **no** mide sinonimia: Jaccard ≥0,5 en **85/368** checks está dominado por **59 ítems de permutación** (checks 56 = 15,2 %) y variantes de hora; `same_root` (118/368) lo domina la morfología paralela. Ninguno es defecto: son ítems de orden/forma por diseño | §AK-3 `[R]`; ejemplos `a1-m01-u01-l01-o01-c03`, `c205`, `pl-16` | No convertir estos proxies en señal; si se quiere medir sinonimia, hacerlo con juicio experto (fase de cierre) | abierto |

**Totales: 0 P0 · 0 P1 · 2 P2 · 2 P3.** No se ha encontrado ningún patrón nuevo
que permita acertar sin comprender **de forma sistemática** más allá de lo que
`AH` (longitud) y las dos señales de eco/forma ya declaran. El valor de AK es
acotar **cuánto subestiman** esas señales y **qué no** se está midiendo.

## Veredicto

**Aprobado con matices (de medición).** Las tres señales declaradas son
deterministas, reproducibles y su recuento se verifica exacto; la muestra cierra
la parte cualitativa con casos reales de eco (`a1-m05-…`, `pl-13`) y de forma
(`c388`, `pl-18`). El banco **no** muestra un atajo de categoría (número/texto),
sinonimia ni absurdidad medibles con las herramientas actuales.

Los dos matices P2 no son defectos de contenido, sino **puntos ciegos del
instrumento**: `quantity_literal` casi no puede dispararse (1/904 pese a 87
enunciados de cantidad) y `prompt_keyword_echo` reporta solo el eco exclusivo
(subestima la presencia en ~2,8×). Ambos pueden llevar a la síntesis a leer un
`0 %`/`6 %` como "sin problema" cuando no lo es. Se declaran para la fase de
cierre; **no** se corrige el instrumento en esta pausa.

## Regenerar / Verificar

```powershell
cd backend

# --- 0) Baseline ---
git rev-parse HEAD
git rev-list -n 1 v3.75.1
git log -1 --format="%H %d" v3.75.1
rg -n "CURRICULUM_VERSION|ASSESSMENT_VERSION" services\curriculum.py
```

**Recuento declarado + patrones adicionales sin reescribir
`docs/audit/generated/`** (importa las funciones puras; no llama a
`_write_generated`). Pegar tal cual en PowerShell 5.1:

```powershell
$code = @'
import json
from collections import Counter
from scripts.audit_dossier import (
    mc_banks, _content_words, _length_profile, _NUMBER_OR_DAY_RE,
    _QUANTITY_PROMPT_RE, _signals_for,
)

B = mc_banks()
def cw(t): return set(_content_words(t))
def cl(t): return sorted(_content_words(t))

out = {}
for bank, rows in B.items():
    echo_raw = echo_amb = echo_distractor = 0
    perm = so_short = mixed = qp = qp_single_correct = 0
    for r in rows:
        opts = r["options"]; idx = r["correct_index"]; prompt = r.get("prompt") or ""
        if not isinstance(idx, int) or not (0 <= idx < len(opts)):
            continue
        p = cw(prompt); ow = [cw(o) for o in opts]; base = cl(opts[idx])
        if len(base) >= 2 and any(cl(opts[j]) == base for j in range(len(opts)) if j != idx):
            perm += 1
        if ow[idx] & p:
            echo_raw += 1
            if any(ow[j] & p for j in range(len(opts)) if j != idx):
                echo_amb += 1
        elif any(ow[j] & p for j in range(len(opts)) if j != idx):
            echo_distractor += 1
        prof = _length_profile(opts, idx)
        if prof and prof["shape_outlier"] and prof["correct_len"] < prof["distractor_mean_len"]:
            so_short += 1
        mask = [bool(_NUMBER_OR_DAY_RE.search(str(o))) for o in opts]
        if any(mask) and not all(mask):
            mixed += 1
        if _QUANTITY_PROMPT_RE.search(str(prompt)):
            qp += 1
            if sum(mask) == 1 and mask[idx]:
                qp_single_correct += 1
    out[bank] = {
        "n": len(rows),
        "declared_signals": dict(Counter(s for r in rows for s in _signals_for(r))),
        "echo_raw_correct_option": echo_raw,
        "echo_raw_ambiguous_distractor_also": echo_amb,
        "echo_distractor_only": echo_distractor,
        "permutation_distractor": perm,
        "shape_outlier_short_correct": so_short,
        "numeric_mix": mixed,
        "quantity_prompts": qp,
        "quantity_single_numeric_correct": qp_single_correct,
    }
print(json.dumps(out, ensure_ascii=False, indent=1))

print("how_often_matches_quantity_re:", bool(_QUANTITY_PROMPT_RE.search("How often does the man go to the gym?")))
print("Wednesdays_matches_number_re:", bool(_NUMBER_OR_DAY_RE.search("Closed on Wednesdays")))
print("first_matches_number_re:", bool(_NUMBER_OR_DAY_RE.search("On the first of next month")))
'@
$code | .\.venv\Scripts\python.exe -
```

**No ejecutar `python -m scripts.audit_dossier distractor-signals`** dentro de
esta auditoría: regeneraría `docs/audit/generated/distractor-signals.{md,json}`,
que es un fichero protegido por la regla dura. El script de arriba produce las
mismas cifras.

## Tests que respaldan

| Fichero | Protege | Relación con AK |
|---|---|---|
| `backend/tests/test_psy_item_form_v3751.py` | Forma de los ítems (k, posición, longitud) y estabilidad del instrumento de V3.75.1 | Fija la base sobre la que AK mide el eco/forma; no cubre `distractor_signals` |
| `docs/audit/generated/distractor-signals.{md,json}` | Definición declarada de las tres señales + muestra determinista | Fuente citable de AK-1 y AK-2 |
| `docs/audit/generated/item-form.{md,json}` | Longitud y `k` por banco | Origen de la cifra de `AH` que AK-3 cita (no re-deriva) |

**Hueco de test declarado:** no existe ninguna prueba que fije que
`quantity_literal` se dispare (o no) sobre los enunciados de cantidad del banco,
ni que mida el eco presente-no-exclusivo. Es exactamente la clase de candado que
AK-01/AK-02 pedirían para la fase de cierre, sin implementarlo aquí.
