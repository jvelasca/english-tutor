# Listening Curriculum (V2.8)

Este documento fija la **progresión pedagógica de listening** por nivel CEFR y
cómo se audita en el Curriculum Quality Dashboard.

> Objetivo V2.8: pasar de "listening cableado por referencia al banco" a un
> **currículo de escucha estructurado** — cada unidad integra listening y cada
> nivel entrena subskills concretos, no actividades genéricas.

## 1. Progresión por nivel

| Nivel | Foco pedagógico | Subskills canónicos (`LISTENING_FOCUS_BY_LEVEL`) |
|---|---|---|
| A1 | Reconocimiento de palabras y sonidos | `word_recognition`, `sound_recognition` |
| A2 | Información (idea general y detalle) | `gist`, `detail`, `word_recognition` |
| B1 | Habla natural (ritmo y frases) | `connected_speech`, `phrase_recognition`, `fast_speech` |
| B2 | Inferencia (actitud e intención) | `inference`, `speaker_intention`, `attitude` |
| C1 | Matiz (tono e implicatura) | `inference`, `attitude`, `speaker_intention` |
| C2 | Pragmática (actitud e implicatura avanzada) | `inference`, `attitude`, `speaker_intention` |

La fuente de verdad del foco está en `services/curriculum.py`:
`LISTENING_FOCUS_BY_LEVEL`.

## 2. Evidencia por unidad

Una unidad cumple el **listening curricular** cuando:

1. **Sección `listening` poblada** — al menos un objetivo con `skills` que
   incluyan `listening`, checks de listening y/o `listening_items` referenciando
   el banco (`listening_corpus.json`).
2. **Fase `listen` del Unit Learning Loop** — misma evidencia que alimenta la
   sección (ver `docs/UNIT_ARCHITECTURE.md`).
3. **Subskills alineados** — el objetivo declara al menos un subskill del foco
   de su nivel.

## 3. Métrica de alineación (V2.8)

`listening_curriculum()` en `services/curriculum_coverage.py` calcula, por
nivel:

- `listening_objectives`: objetivos con evidencia real de escucha.
- `aligned_objectives`: objetivos que declaran ≥1 subskill del foco del nivel.
- `alignment_pct`: porcentaje de alineación (meta **100%**).

El bloque `listening_curriculum` del Curriculum Quality Dashboard agrega estos
datos sobre los 6 niveles con curso (A1..C2).

Complementa la dimensión **`listening` del dashboard** (cobertura por unidad:
¿hay listening en cada unidad?) con **qué tipo de listening** entrena cada
nivel.

## 4. Cierre A1 (V2.8)

Tras V2.7, el único hueco de listening por unidad estaba en **A1** (5 unidades
sin escucha + Final sin retrieve/transfer). V2.8 añadió:

- **5 objetivos de listening** (`a1-m03`, `m05`, `m06`, `m08`, `m09`) con loop
  completo y foco A1 (`word_recognition`, `sound_recognition`).
- **retrieve/transfer** en la unidad Final (`a1-m10-u01`).

Resultado: **listening por unidad 100%** y **fase `listen` del loop 100%** en
todos los niveles.

## 5. Forma canónica de un objetivo de listening

```json
{
  "id": "a1-m03-u01-l01-o03",
  "can_do": "I can understand simple descriptions of family.",
  "title": "Listening: la familia",
  "skills": ["listening", "vocabulary"],
  "subskills": ["word_recognition", "sound_recognition"],
  "listening_items": ["c002", "c050", "c053", "c008"],
  "activities": [
    { "type": "listening", "phase": "practice", "..." : "..." },
    { "type": "recall", "phase": "retrieve", "..." : "..." },
    { "type": "dialogue", "phase": "transfer", "..." : "..." },
    { "type": "recall", "phase": "review", "..." : "..." },
    { "type": "listening", "phase": "assess", "..." : "..." }
  ],
  "checks": [
    { "skill": "listening", "prompt": "Listen: ...", "..." : "..." }
  ]
}
```

## 6. Regenerar

```powershell
cd backend
.venv\Scripts\python.exe -m scripts.curriculum_coverage --quality
```

Tests: `backend/tests/test_curriculum_quality.py` (`test_listening_curriculum_*`).
