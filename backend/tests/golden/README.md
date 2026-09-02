# Datasets dorados de auditoría (V3.0, post-freeze)

Fixtures JSON versionados que fijan la **calibración auditada** del contenido y
del motor pedagógico. Complementan los tests unitarios del motor: mientras los
tests prueban invariantes generales, estos fixtures congelan decisiones de
auditoría (bandas por nivel, muestras revisadas, casos de frontera de umbrales y
comportamiento esperado de perfiles sintéticos).

## Layout

```
tests/golden/
  loader.py                 helpers para leer fixtures y resolver ids reales
  listening/
    level_bands.json        bandas de calibración por nivel (A1→C2)
    samples.json            muestras representativas revisadas cualitativamente
  assessment/
    thresholds.json         semántica en frontera de PASS_THRESHOLDS / mastery gate
  evidence_graph/
    profiles.json           perfiles sintéticos → limiting factor esperado
  fsrs/
    sequences.json          historias de review → propiedades del scheduling
  speaking/
    mission_probes.json     criterios débiles, drills, mejora, determinismo
```

## Convención

- Un golden **no se edita** como consecuencia de un cambio de código cualquiera:
  si un test golden falla, hay una **regresión de calibración** que debe
  re-auditarse (dossier en `docs/audit/` y, si procede, entrada en
  `CHANGELOG.md`). Solo entonces se actualiza el fixture.
- Cada fixture lleva el id de auditoría (`audit: "B-2026-09-02"`) para trazar qué
  dossier lo fijó.
- Los ids de ítems (`c001`…) se resuelven contra el contenido real en tiempo de
  test: si un ítem auditado desaparece o cambia de nivel, falla.

## Tests que consumen los golden

- `test_golden_listening.py` — bandas por nivel + muestras revisadas.
- `test_golden_assessment.py` — umbrales y mastery gate.
- `test_golden_evidence_graph.py` — limiting factor (incl. caso 88/91/85/63/58).
- `test_golden_fsrs.py` — propiedades del scheduler.
- `test_golden_speaking.py` — misión, frontera 0.6, determinismo del scoring.

## Regenerar las métricas de los dossieres

```powershell
cd backend
.venv\Scripts\python.exe -m scripts.audit_dossier corpus-stats
.venv\Scripts\python.exe -m scripts.audit_dossier curriculum-stats
.venv\Scripts\python.exe -m scripts.audit_dossier speaking-stats
```

Salidas en `docs/audit/generated/`.
