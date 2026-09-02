# Beta V3.0 — Feature freeze

> Tras **V2.7 → V2.12** el motor pedagógico está cerrado. **V3.0 congela
> funcionalidad nueva** y abre la fase de *contenido + calibración + UX +
> pruebas reales* (auditoría post-V2.6).

Fecha de freeze: **2026-09-02**. Versión: `3.0.0`.

Gate automatizado: `python scripts/check_beta_v3.py` (también en CI).

---

## 1. Qué está congelado (no features nuevas)

| Área | Estado al freeze | Doc |
|---|---|---|
| Curriculum Depth (V2.7) | ✅ A1–C2 con Unit Architecture | `docs/UNIT_ARCHITECTURE.md` |
| Listening Curriculum (V2.8) | ✅ foco CEFR + 100% por unidad | `docs/LISTENING_CURRICULUM.md` |
| Speaking Mission (V2.9) | ✅ Attempt → Drill → Retry → Improvement | `docs/SPEAKING_MISSION.md` |
| Assessment 2.0 (V2.10) | ✅ formative→retention + mastery gate | `docs/ASSESSMENT_2.md` |
| FSRS-lite (V2.11) | ✅ cola due auditable | `docs/FSRS.md` |
| Evidence Graph (V2.12) | ✅ can-do → limiting factor → because[] | `docs/EVIDENCE_GRAPH.md` |
| Beta 1.0 infra/UX (V2.0) | ✅ 5 gates 10/10 | `docs/BETA_GATES.md` |

**Regla de freeze:** no se abren hitos `V2.x`/`V3.1+` de producto hasta cerrar
las cuatro vías de abajo. Solo se admiten:

- bugs / regresiones
- contenido curricular (autoría JSON, audio, escenarios)
- calibración de umbrales ya existentes (sin cambiar el modelo)
- pulido UX y a11y
- evidencias de pruebas reales en dispositivos

---

## 2. Dashboard al freeze (Curriculum Quality)

| Dimensión | Score |
|---|---|
| **Overall** | **95,7** |
| Depth (media) | 84,2 |
| Listening / Speaking / Interaction | 100 |
| Assessment / Review | 100 |
| Unit Learning Loop (media) | 100 |
| Coverage (matriz nivel×sección) | 85,7 |

Pre-A1 sigue sin curso (hueco conocido, no bloquea el freeze).

---

## 3. Gates pedagógicos V3 (G6–G9)

Complementan los G1–G5 de `BETA_GATES.md`.

### G6 — Curriculum Depth (10/10)

| Criterio | Evidencia |
|---|---|
| Unit Architecture documentada | `docs/UNIT_ARCHITECTURE.md` |
| Depth media ≥ 80 | dashboard `depth.score` |
| Loop 100% en niveles con curso | `learning_loop.mean_loop_pct` |
| Review/Assessment por unidad 100% | dimensiones `review`/`assessment` |

### G7 — Listening + Speaking performance (10/10)

| Criterio | Evidencia |
|---|---|
| Listening focus CEFR alineado 100% | `listening_curriculum.overall` |
| Speaking Mission API + UI | `speaking_mission.py`, `SpeakingMission` |
| Retry + improvement visible | `docs/SPEAKING_MISSION.md` |

### G8 — Assessment + Retention (10/10)

| Criterio | Evidencia |
|---|---|
| Escalera Assessment 2.0 | `assessment_v2.py` |
| Mastery gate 5 evidencias | `mastery_evidence_gate` |
| FSRS-lite due/review | `fsrs.py` + `/api/academy/fsrs/*` |

### G9 — Explainable Adaptive (10/10)

| Criterio | Evidencia |
|---|---|
| Evidence Graph por can-do | `evidence_graph.py` |
| `because[]` en next-best | `NextBestActivityOut.because` |
| Limiting factor expuesto | UI Profile + NextBestCard |

**Score V3 pedagógico: 10/10** (verificado por `check_beta_v3.py`).

---

## 4. Fase post-freeze (trabajo permitido)

### 4.1 Contenido

- [ ] Autoría fina de prompts/checks por unidad (sin inflar objetivos)
- [ ] Completar Pre-A1 si se decide como producto (opcional)
- [ ] Audio humano faltante / QA de clips rechazados
- [ ] Escenarios speaking: revisar prompts C1/C2

### 4.2 Calibración

- [ ] Umbrales Assessment 2.0 (`PASS_THRESHOLDS`) con alumnos reales
- [ ] `REQUEST_RETENTION` / intervalos FSRS con datos de uso
- [ ] Readiness CEFR (`cefr_matrix`) vs sensación de nivel
- [ ] Speaking weak threshold / mission drills

### 4.3 UX

- [ ] Home: “Where am I / How am I doing / What is weak / What should I do / Why”
- [ ] Vaciar estados vacíos restantes; i18n de strings nuevas V2.9–V2.12
- [ ] Revisar carga cognitiva de Assessment ladder + FSRS + Evidence Graph

### 4.4 Pruebas reales

Completar `docs/DEVICE_MATRIX.md` (hoy todo ⬜):

- [ ] PC Windows Chrome/Edge
- [ ] Android Chrome (HTTPS + mic)
- [ ] iPhone Safari (HTTPS + mic)
- [ ] Listening + Speaking end-to-end en LAN
- [ ] Recuperación de permiso de micrófono

Protocolo: sección «Cómo probar» de la matriz de dispositivos.

---

## 5. Cómo verificar el freeze

```powershell
# Backend
cd backend
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\ruff.exe check .

# Quality + Beta V3 gate
.venv\Scripts\python.exe -m scripts.curriculum_coverage --quality
cd ..
python scripts/check_beta_v3.py
python scripts/check_release_consistency.py

# Frontend
cd frontend
npx tsc --noEmit
npm test
```

CI: jobs existentes + `beta-v3-gate` (`check_beta_v3.py`).

---

## Veredicto

**V3.0 Beta freeze declarado.** La arquitectura y el stack pedagógico V2.7–V2.12
quedan cerrados. El trabajo siguiente es perfeccionar el motor ya construido
(contenido, calibración, UX, dispositivos), no abrir otro motor.
