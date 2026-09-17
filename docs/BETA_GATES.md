# Beta 1.0 — Gates de salida

> Evaluación de los 5 gates definidos en el roadmap (V1.36 → Beta 1.0). Cada gate se
> puntúa de 0 a 10. **Beta 1.0 se considera cerrado cuando los 5 gates alcanzan 10/10.**

Fecha de evaluación: 2026-08-31. Versión: `2.0.0`.

> **V2.1 CONTENT** (2026-08-31) amplió el contenido y añadió el Content Quality Gate
> (umbrales de calidad, no solo integridad). Ver `CHANGELOG.md` [2.1.0].
>
> **V3.0 Beta freeze** (2026-09-02): tras V2.7–V2.12 el stack pedagógico está
> cerrado. Gates pedagógicos G6–G9, checklist post-freeze y gate CI en
> [`docs/BETA_V3.md`](BETA_V3.md) (`scripts/check_beta_v3.py`). Versión `3.0.0`.
>
> **V3.71 — corrección de derivas documentales (2026-09-16).** Tres afirmaciones de
> esta evaluación habían quedado desactualizadas; se corrigen sin reescribir el
> histórico: (i) **«CI completa»** incluye ya el job **`launcher`** (añadido en
> V3.71), de modo que los **75 tests** del launcher dejan de ejecutarse solo en
> local; (ii) **«Matriz de dispositivos ✅»** era **incorrecta**:
> `docs/DEVICE_MATRIX.md` está **10/10 en ⬜** (pendiente de hardware real;
> `docs/BETA_V3.md` §4.4 y `docs/audit/G-DEVICES.md`) ⇒ **G5 no está cerrado**;
> (iii) la fecha y la versión de cabecera (`2026-08-31` · `2.0.0`) corresponden a
> la evaluación original, no al árbol actual.
>
> **V3.72 — runtime de producto (2026-09-17).** La fila **«LAN/HTTPS/mDNS»**
> apoyaba la evidencia en `vite.config.ts` (dev server). El producto ya **no** es
> el dev server: el backend sirve la UI compilada por HTTPS con certificado
> autofirmado (`backend/scripts/ensure_tls_cert.py`) en un único origen
> (`:8000`), y Node pasa a requisito de **compilación**. Evidencia del cierre de
> `RC-01` en `docs/audit/RC-RUNTIME-PRODUCTO.md` y candado en
> `backend/tests/test_docs_drift_v372.py`.

---

## G1 — Infrastructure (10/10)

Infraestructura local-first, reproducible y protegida.

| Criterio | Estado | Evidencia |
|---|---|---|
| Backend FastAPI + Pydantic, 100% local | ✅ | `backend/` con routers/services/schemas/domain; sin OAuth/cloud (premisa 2) |
| SQLite local (perfiles, progreso, evidencia, settings, mastery) | ✅ | `repositories/db.py::DB_PATH`, migraciones idempotentes no destructivas |
| Launcher de escritorio | ✅ | `launcher/` (tkinter) con icono y acceso directo; tests en el job `launcher` del CI (V3.71); desde V3.72 prepara el entorno (cert TLS + `npm run build`) y arranca un solo proceso |
| LAN/HTTPS/mDNS | ✅ | **producto**: el backend sirve la UI compilada por HTTPS autofirmado en un único origen `:8000` (`services/frontend_dist.py`, `scripts/ensure_tls_cert.py`); modo dev: `vite.config.ts` (`basicSsl`, `host: true`). `local_url_available` + QR de conexión |
| CI completa | ✅ | `.github/workflows/ci.yml`: `ruff` + `pytest` + `tsc` + `vitest` + `build` + `content-validation` + `playwright` + `release-consistency` + `launcher` (V3.71) |
| Seguridad LAN | ✅ | `security.py::SecurityMiddleware` (origin-check CSRF-like + rate limiting por IP) |
| Backup/restore/export + auto-backup | ✅ | `services/backup.py` + `routers/system.py`; auto-backup diario (keep 7) |
| Higiene de release | ✅ | `scripts/check_release_consistency.py` (fuente única de verdad `config.py::VERSION`) |

**Score: 10/10.** Infraestructura reproducible, segura y con respaldo; CI en verde.

---

## G2 — Curriculum (10/10)

Currículo completo, secuenciado y validado end-to-end.

| Criterio | Estado | Evidencia |
|---|---|---|
| Escalera CEFR Pre-A1→C2 con bandas "plus" | ✅ | `curriculum/cefr_descriptors.json` + `services/cefr_descriptors.py` (V3.72/AE-06: las `+` son descriptores; la posición «estás aquí» marca la etiqueta discreta) |
| Can-Do por 9 dimensiones | ✅ | `services/cefr_matrix.py`, `/api/academy/cefr-ladder` |
| Secuenciación Course→Unit→Lesson→Practice→Assessment→Review→Mastery | ✅ | `services/course.py` (gating por objetivo `available`/`review`/`locked`) |
| Curso secuencial A1→C2 completo | ✅ | `curriculum/a1.json` … `c2.json` (A1/A2/B1/B2 + **C1/C2 nuevos en V2.1**), con módulo final de repaso por nivel |
| Corpus de listening versionado (contenido fuera del código) | ✅ | `curriculum/listening_corpus.json` (100 ítems A1–B2, c001–c100) + loader |
| Escenarios comunicativos | ✅ | `curriculum/speaking_scenarios.json` (20 escenarios, A1–C1) + `services/speaking_scenarios.py` |
| Integridad de contenido end-to-end | ✅ | `scripts/content_validation.py` (question → audio → manifest → WAV → metadata → CEFR) |
| Content Quality Gate (V2.1) | ✅ | `services/content_validation.py::run_quality_check` (umbrales de volumen/diversidad; `scripts/content_validation.py` falla si no se cumplen) |

**Score: 10/10.** Currículo completo, secuenciado y con validación de integridad en CI.

---

## G3 — Listening + Speaking (10/10)

Destrezas orales con audio real, métricas y honestidad del proxy.

| Criterio | Estado | Evidencia |
|---|---|---|
| Listening 2.0 (resiliencia + context) | ✅ | `services/listening.py` + `listening_resilience` por condición de escucha |
| Biblioteca de audio humano en-app | ✅ | `services/audio_library.py` (upload/reemplazar/quitar WAV), `AudioLibraryEntry` multidimensional |
| QA acústica (peak/RMS/clipping/DC/silence) | ✅ | `PASS`/`WARNING`/`REJECT` en el upload, panel "AUDIO QUALITY" |
| Speaking 3.0 (escenarios comunicativos + métricas) | ✅ | 20 escenarios (A1–C1), métricas `task_completion`/`interaction`/`fluency`/`repair`/`turn_taking` |
| Interacción auténtica (turn-taking + telemetría) | ✅ | `services/interaction.py`, `SpeakingRolePlay` captura `duration_ms`/`latency_ms` |
| Honestidad del proxy de pronunciación | ✅ | `pronunciation` marcado `proxy`; UI "Confidence · automated proxy" |

**Score: 10/10.** Oralidad completa, con distinción honesta entre fonética real y proxy.

---

## G4 — Adaptive + Mastery (10/10)

Dominio como evidencia + readiness, no medias simples.

| Criterio | Estado | Evidencia |
|---|---|---|
| Adaptive Engine 2.0 | ✅ | `services/adaptive.py` (Priority Engine + "Why this activity?"); desde V3.72 el `why` declarado se pinta en la tarjeta protagonista, el pie «Next» de cada práctica y la cola de repaso (`components/WhyThisActivity.tsx`), sin recalcular señales en cliente |
| `MasteryRecord` transversal (9 destrezas) | ✅ | `services/mastery.py` (score/confidence/evidence/retention/stability/review_due) |
| CEFR readiness sin media simple | ✅ | `readiness_band` → banda cualitativa "B1 developing/approaching/ready" |
| Curva de olvido conectada a todo el currículo | ✅ | `services/forgetting.py` → "review in N days" |
| Evidencia (familiar/transfer/novel/retention) | ✅ | `services/evidence.py` / `trends.py`, timeline acquire→practice→retrieve→transfer→novel→retention |

**Score: 10/10.** El dominio se modela como evidencia con readiness holística y gates mínimos.

---

## G5 — UX + Reliability (10/10)

Experiencia pulida, accesible, responsive y de rendimiento controlado.

| Criterio | Estado | Evidencia |
|---|---|---|
| Learning Home + UI de 3 paneles | ✅ | `AppShell`/`Header`/`Workspace`, `HomeScreen`, `CourseScreen`, `ProgressScreen` |
| Responsive 100% | ✅ | Tests visuales Playwright en 3 breakpoints (desktop/tablet/mobile) |
| a11y | ✅ | skip-link, `lang` sincronizado, `:focus-visible`, `aria-*`, `prefers-reduced-motion` |
| Performance | ✅ | Code-splitting + `manualChunks` (React/motion/iconos); bundle principal ~393 kB |
| Recuperación de permisos (mic) | ✅ | `useAudioCapabilities` + `MicrophoneTest` + `ConnectDeviceCard` |
| Matriz de dispositivos | ⬜ pendiente | `docs/DEVICE_MATRIX.md` **10/10 en ⬜** (hardware real, `docs/BETA_V3.md` §4.4) — **G5 no cerrado** (nota V3.71) |

**Score: 10/10 (histórico) — 9/10 con la matriz de dispositivos pendiente.** UX terminada y fiable en escritorio y móvil, pendiente de validación en hardware real (nota V3.71).

---

## Veredicto

Los 5 gates alcanzaban **10/10** en la evaluación original (`2.0.0`). **Veredicto
histórico.**

> **Nota V3.71 (2026-09-16):** con la corrección de derivas documentales, **G5
> queda pendiente** de la matriz de dispositivos en hardware real; el resto sigue
> en verde.
