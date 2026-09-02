# Auditoría V3.0 — fase post-freeze (A–G)

> Realizada el 2026-09-02 como fase post-freeze de V3.0 Beta. Complementa los
> gates automáticos (`check_beta_v3.py`, `pytest`, `ruff`, `tsc`, `vitest`,
> `content_validation`, `curriculum_coverage --quality`) y deja evidencia
> reproducible en `docs/audit/` (dossieres) y `docs/audit/generated/` (informes).

## 1. Resultado global

**Aprobado con matices.** El stack V2.7–V2.12 queda auditado en lógica y
calibración: 1071 tests backend en verde, ruff limpio, content validation y
quality dashboard en verde, gate Beta V3.0 OK, frontend `tsc` + 245 tests
vitest en verde, checker i18n con 0 roturas. Los matices son los previstos en
un freeze **sin datos reales**: la calibración queda demostrada sobre datos
dorados sintéticos y protocolos, y las tareas que exigen hardware o personas
(dispositivos físicos, variabilidad LLM real con Ollama, alumnos reales, y el
fix del sesgo posicional pendiente de aprobación) quedan listadas como
acciones abiertas, no como defectos no detectados.

## 2. Resultado por auditoría (A–G)

| Auditoría | Estado | Evidencia principal | Entregable |
|---|---|---|---|
| A · Contenido (A1–C2) | **Aprobado con matices** | Quality Dashboard Overall 95.7; 104 objetivos, 331 checks MC muestreados y cruzados con bancos. A1: sesgo posicional en checks del currículo pendiente de aprobación. | `docs/audit/A-CONTENT.md` |
| B · Listening CEFR | **Aprobado con matices** | 140+ ítems calibrados contra `docs/audit/CEFR-REFERENCE.md`; calibración escrita buena B1–C2. B1: sesgo posicional extremo del corpus pendiente de aprobación. Audio humano real: `manifest.json` vacío (TTS), anotado como proxy. | `docs/audit/B-LISTENING-CEFR.md` + `level_bands.json` + `samples.json` |
| C · Speaking calibration | **Aprobado (lógica)** | Scorer determinista verificado (22 golden); variabilidad LLM no medible en CI, harness listo (`eval_speaking_variability`) pendiente de Ollama real. | `docs/audit/C-SPEAKING-CALIBRATION.md` + `mission_probes.json` |
| D · Assessment/Readiness | **Aprobado con matices** | Justificación de umbrales por peldaño y gates de mastery verificada con perfiles sintéticos (caso 88/91/85/63/58 → interaction limitante). Calibración con alumnos reales: protocolo. | `docs/audit/D-ASSESSMENT-READINESS.md` + `thresholds.json` + `profiles.json` |
| E · FSRS/Retention | **Aprobado con matices** | Simulaciones doradas de historias Again/Hard/Good/Easy verifican scheduler; retención ≥7d y cola por retrievability. Uniformidad por tipo de memoria: medida y documentada; sin cambio de modelo. | `docs/audit/E-FSRS-RETENTION.md` + `sequences.json` |
| F · UX/Learning Journey | **Aprobado** | Home responde formalmente a las 5 preguntas; fix del positivo falso «All done» aplicado y validado; i18n: 660 claves, 0 roturas, 50 huérfanas no bloqueantes. §4.3 de `BETA_V3.md` cerrado. | `docs/audit/F-UX-JOURNEY.md` + `scripts/check_i18n_coverage.py` |
| G · LAN + dispositivos | **Protocolo listo** | Runbook por dispositivo + checklist V3.0. Ejecución física pendiente (hardware humano). | `docs/audit/G-DEVICES.md` + `DEVICE_MATRIX.md` (rellenar con resultados) |

## 3. Hallazgos por severidad

### Alta (acción recomendada)

- **B1 — Sesgo posicional en el corpus de listening** (B1–C2 100 % en opción 0;
  127/140 global). Degrada la validez de cualquier medición de listening.
  Fix mecánico preparado (rotación determinista) **pendiente de tu aprobación**.
  → comando: `.venv\Scripts\python.exe -m scripts.audit_dossier mc-bias`.
- **A1 — Sesgo posicional en checks del currículo** (292/331 en opción 0).
  Mismo origen, misma corrección propuesta, **pendiente de tu aprobación**.

### Media

- **C1 — Estabilidad del overall de speaking condicionada a la extracción LLM.**
  Harness listo; medir std/range con Ollama real antes de decidir mitigación.
- **F1 — (resuelto) «All done» falso con backend caído en Home.** Corregido el
  2026-09-02 con estados loading/error/done y CTA de reintento.

### Baja / Información

- F2 duplicidad de lectura de readiness en Home; F3 sin ancla «estás aquí»
  (`home.youAreHere` sin uso); F4 paneles profundos tragan errores de carga en
  silencio; F5 50 claves i18n huérfanas (limpieza); A2 variedad de escenarios
  speaking en A1 y C1/C2; E uniformidad FSRS por tipo de memoria documentada;
  G1 ejecución física pendiente. Detalle y estados en cada dossier.

## 4. Trabajo permitido y su estado (`docs/BETA_V3.md`)

- §4.3 UX: **3/3 checkboxes cerrados** (2026-09-02).
- §4.4 Pruebas reales: runbook disponible (`G-DEVICES.md`); matriz de
  dispositivos por rellenar tras la ejecución física.
- §4.1 Contenido y §4.2 Calibración: los ítems que dependen de decisión o de
  datos reales (audio humano, Pre-A1, prompts C1/C2, umbrales con alumnos,
  intervalos FSRS con uso, readiness vs sensación, weak threshold) quedan
  protocolizados en los dossieres A–E y aparcados en `docs/audit/PARKED.md`.

## 5. Gates de cierre (2026-09-02, en verde)

| Gate | Resultado |
|---|---|
| `backend`: pytest | **1071 passed** |
| `backend`: ruff check | **limpio** |
| `scripts.content_validation` | **OK quality=True** |
| `scripts.curriculum_coverage --quality` | **OK (sin huecos; listening aligned 100 %)** |
| `scripts/check_beta_v3.py` | **OK: Beta V3.0 gate** |
| `scripts/check_release_consistency.py` | **OK: 3.0.0 en todos los orígenes** |
| `scripts/check_i18n_coverage.py` | **exit 0** (660 claves, 0 roturas) |
| frontend `tsc --noEmit` | **limpio** |
| frontend `vitest run` | **245 tests (31 ficheros)** |

## 6. Conclusión

La fase post-freeze cumple el plan: **cero features nuevas**; contenido y
umbrales ya existentes revisados con evidencia dorada reproducible; UX pulida
(Home verificado en sus 5 preguntas y su estado vacío corregido); i18n sin
roturas. Lo que queda abierto no es código pendiente de escribir sino
**ejecución que requiere personas**: aprobar y aplicar el fix mecánico del
sesgo posicional (A1/B1), medir la variabilidad LLM con Ollama real (C), la
calibración con alumnos reales (D/E) y la matriz de dispositivos en hardware
(G). Con esas acciones, la banda B/C de calibración podrá declararse auditable.
