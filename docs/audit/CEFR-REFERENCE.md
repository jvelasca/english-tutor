# Tabla de referencia CEFR para auditoría de contenido (v0.1)

> Referencia **interna provisional** usada por las auditorías A y B. Pendiente de
> calibración con alumnos reales (`docs/BETA_V3.md` §4.2). NO es un documento
> normativo CEFR; es la operacionalización del proyecto para poder auditar
> contenido de forma consistente. Los rangos se alinean con el descriptor del
> marco ("slow, clearly articulated speech" → C2 "with ease virtually everything")
> y con rangos prácticos de materiales EFL, pero **la fuente de verdad para
> marcar desviaciones es esta tabla**, no una intuición por nivel.

## Escala de dificultad del vector

Cada ítem declara `difficulty_vector` (8 dimensiones, 1..6). Significado:

| Valor | Etiqueta | Uso |
|---|---|---|
| 1–2 | Bajo | Automatizable, sin esfuerzo de procesamiento |
| 3–4 | Medio | Exige atención consciente, una sola relectura mental |
| 5–6 | Alto | Carga de procesamiento propia del nivel; solo C1/C2 deberían usar 5–6 de forma sostenida |

## Bandas de referencia por nivel

| Nivel | Velocidad operativa (wpm) | Longitud de turno (palabras) | `difficulty_vector` típico | Léxico/registro | Connected speech | Operación cognitiva esperada |
|---|---|---|---|---|---|---|
| A1 | 80–115 | 3–10 | 1–2 | palabras de alta frecuencia, frases fijas, registro neutro | 0% (aislado y claro) | literal: reconocer palabras/números y detalles explícitos |
| A2 | 110–135 | 6–15 | 2–3 | frecuencia alta-media, rutinas cotidianas | 0–20% (solo contracciones suaves) | literal + gist: idea principal y detalle directo; inferencia mínima |
| B1 | 130–160 | 8–20 | 2–4 | frecuencia media, registro informal/formal simple | 20–60% (reducciones reales: *gonna*, *whaddaya*) | detalle + intención sencilla: predicción y secuencia |
| B2 | 150–185 | 10–30 | 3–5 | registro amplio, matices de actitud, discurso con marcadores | 40–70% | inferencia, actitud del hablante, intención no literal explícita |
| C1 | 165–195 | 15–40 | 4–5 | registro académico/profesional, coloquialismos, ironía suave, hedging | 60–85% | matiz, tono, implicatura; actitud ante un argumento |
| C2 | 175–200+ | 18–50 | 4–6 | registro completo, ironía, sarcasmo, referencia cultural, juego retórico | 80–100% | pragmática: intención indirecta, rechazo velado, ironía, implicatura sin marca literal |

## Criterios de comprobación por ítem

### Dificultad (¿corresponde al CEFR?)
- El escalar derivado (`difficulty_from_vector`) debe caer dentro de la banda del nivel.
- Un ítem **A1/A2** no debe exigir léxico fuera de la frecuencia básica ni sintaxis subordinada compleja.
- Un ítem **C1/C2** debe exigir más que vocabulario raro: la respuesta correcta debe depender de comprensión de actitud/intención, no de una sola palabra difícil.

### Velocidad (¿es adecuada?)
- `speech_rate` (wpm) dentro de la banda operativa del nivel (columna 2).
- La progresión entre niveles debe ser **monótona no decreciente en el rango alto** (el ítem más rápido de B2 no debe ser más rápido que el más rápido de C1/C2 cuando el objetivo es velocidad).
- Un ítem marcado `fast_speech` debe acercarse al techo de la banda de su nivel.

### Léxico
- Dentro del registro esperado del nivel (columna 5). Un ítem C1/C2 con registro exclusivamente informal "charla" sin exigencia de matiz se considera mal etiquetado.

### Sintaxis
- Complejidad sintáctica (subordinación, incrustación, inversión, elipsis) coherente con el nivel; C1/C2 deben incluir estructuras que obliguen a parsear relaciones no adyacentes.

### Distractors (¿razonables?)
- Al menos un distractor debe ser **plausible** (misma categoría semántica o recuperable del audio) para que el ítem discrimine.
- Distractors absurdos o imposibles en el nivel → calidad baja aunque el ítem "funcione".
- El distractor correcto no debe ser el más largo ni el único con palabra del audio.

### Inference (¿realmente evalúa inferencia?)
- Un ítem etiquetado `inference` no debe resolverse con una palabra del audio (eso es `detail`).
- Debe requerir combinar dos claves no adyacentes o derivar una relación causa→efecto no dicha.

### Connected speech (¿existe realmente?)
- `connected_speech: true` debe corresponderse con reducciones/linking en la transcripción (`gonna`, `whaddaya`, `dunno`, elisión de /t/…), no solo con contracciones suaves.

### Pragmatics (C1/C2)
- Un ítem C1/C2 de pragmática debe requerir interpretar intención sin marca literal: rechazo velado ("that's one way of looking at it…"), ironía, hedged disagreement, sobre- o sub-declaración, implicatura.
- La pregunta debe poder **fallarse** incluso habiendo entendido todas las palabras (si no, es B2 avanzado, no C1/C2).

## Qué NO audita esta tabla

- Calidad acústica real del audio (ver `services/audio_library` QA + manifest).
- Discriminación empírica con alumnos (fase de observación, `docs/audit/PARKED.md`).

## Regenerar / Verificar

Las métricas por nivel del corpus se reproducen con:

```powershell
cd backend
.venv\Scripts\python.exe -m scripts.audit_dossier corpus-stats
```
