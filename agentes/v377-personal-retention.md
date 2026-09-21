/**
 * Briefing: Personal como motor de retención léxica (FSRS + colecciones).
 *
 * Implementado sobre el plan «Personal Retention Vocab»:
 * - Ingestión: palabra suelta, lista pegada, packs temáticos (`vocab_packs`).
 * - Sesión Anki-lite: `GET/POST /api/vocabulary/retention/*` → grades FSRS
 *   lexicon + eventos `retention:<word>:<grade>` (rol informative).
 * - Consulta intacta (D3); «Añadir a Personal» es acción explícita.
 * - No SM-2 paralelo; no mastery/Assessment por grade de retención.
 */
