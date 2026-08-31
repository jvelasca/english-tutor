"""Validación de integridad del contenido end-to-end (V1.37).

Recorre la cadena `question → audio_id → manifest → WAV → metadata → CEFR →
difficulty → subskills` y emite el "CONTENT INTEGRITY CHECK": ítems totales,
grabados vs TTS, referencias rotas, ids duplicados, transcripciones ausentes,
desfases CEFR y desfases de duración, reutilizando `validate_listening_bank`
(banca), `validate_manifest` (estructura del manifest) y `validate_audio_entry`
(contraste declarado↔WAV por entrada grabada).

Puro y determinista: no escribe nada, solo lee el banco, el manifest y los WAV.
"""
from __future__ import annotations

from collections import Counter

from services.audio_library import (
    load_manifest,
    resolve_file,
    validate_audio_entry,
    validate_manifest,
)
from services.curriculum import CEFR_ORDER
from services.listening import QUESTION_BANK, validate_listening_bank
from services.speaking_scenarios import list_scenarios


def _issues_by_severity(issues: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = Counter()
    for issue in issues:
        counts[issue["severity"]] += 1
    return dict(counts)


def content_stats() -> dict:
    """Métrica única de contenido validado (V2.2).

    `total_validated_learning_items` es la suma canónica de todo el material de
    aprendizaje validado: ítems de listening (banco heredado TTS + corpus de
    audio) + escenarios de speaking. README, CHANGELOG, validador y UI deben
    derivar de aquí para que la cifra sea única (anti-drift).

    El desglose separa explícitamente el corpus (`cNNN`) del banco heredado TTS
    (`lNN`), de modo que "100 ítems de listening" (corpus) y "123 totales"
    (banco completo) dejen de contradecirse.
    """
    corpus = [q for q in QUESTION_BANK if str(q.get("id", "")).startswith("c")]
    legacy = [q for q in QUESTION_BANK if not str(q.get("id", "")).startswith("c")]
    with_audio_id = sum(1 for q in QUESTION_BANK if q.get("audio_id"))
    scenarios = list_scenarios()
    return {
        "total_validated_learning_items": len(QUESTION_BANK) + len(scenarios),
        "listening": {
            "total": len(QUESTION_BANK),
            "corpus": len(corpus),
            "legacy_tts": len(legacy),
            "with_audio_id": with_audio_id,
        },
        "speaking_scenarios": len(scenarios),
        "levels": list(CEFR_ORDER),
    }


# --- Content Quality Gate (V2.1) ---------------------------------------------
# El integrity check garantiza que el contenido es *válido* (referencias, ids,
# CEFR). El Quality Gate añade umbrales de *volumen y diversidad pedagógica*: el
# banco de listening debe ser un corpus utilizable y variado, no solo válido.
# Se mide sobre el banco DECLARADO (metadata), no sobre el audio realizado: las
# dimensiones que una única voz TTS no realiza (acento, multihablante, ruido)
# cuentan aquí como diversidad declarada, pendiente de audio real.

QUALITY_THRESHOLDS: dict = {
    "min_total_items": 100,
    "min_items_per_level": {"A1": 20, "A2": 20, "B1": 20, "B2": 20},
    "min_speakers": 10,
    "min_accents": 4,
    "min_contexts": 5,
    "min_connected_speech_items": 8,
    "min_noise_items": 6,
    "min_multiple_speakers_items": 4,
    "min_fast_speech_items": 6,
}


def _quality_metrics(bank: list[dict]) -> dict:
    """Métricas de diversidad del banco de listening (sin comparar umbrales)."""
    per_level: dict[str, int] = {
        level: 0 for level in QUALITY_THRESHOLDS["min_items_per_level"]
    }
    speakers: set[str] = set()
    accents: set[str] = set()
    contexts: set[str] = set()
    connected_speech = 0
    noise = 0
    multiple_speakers = 0
    fast_speech = 0
    total = 0

    for q in bank:
        total += 1
        level = q.get("level")
        if level in per_level:
            per_level[level] += 1
        speaker_id = (q.get("speaker_id") or "").strip()
        if speaker_id:
            speakers.add(speaker_id)
        accent = (q.get("accent") or "").strip()
        if accent:
            accents.add(accent)
        context = (q.get("context") or "").strip()
        if context:
            contexts.add(context)
        vector = q.get("difficulty_vector") or {}
        if int(vector.get("connected_speech", 1)) >= 4:
            connected_speech += 1
        if int(vector.get("noise", 1)) >= 3:
            noise += 1
        if (
            q.get("skill") == "multiple_speakers"
            or int(vector.get("speaker_count", 1)) >= 2
        ):
            multiple_speakers += 1
        if q.get("skill") == "fast_speech" or int(vector.get("speed", 1)) >= 5:
            fast_speech += 1

    return {
        "total_items": total,
        "per_level": per_level,
        "speakers": len(speakers),
        "accents": len(accents),
        "contexts": len(contexts),
        "connected_speech": connected_speech,
        "noise": noise,
        "multiple_speakers": multiple_speakers,
        "fast_speech": fast_speech,
    }


def run_quality_check(bank: list[dict] | None = None) -> dict:
    """Evalúa los umbrales de calidad del banco (V2.1).

    Devuelve `{pass, passed, total, checks}` donde `checks` es una lista de
    `{name, label, required, actual, pass}`. `pass` es True solo si se cumplen
    todos los umbrales.
    """
    bank = bank if bank is not None else QUESTION_BANK
    metrics = _quality_metrics(bank)
    checks: list[dict] = []

    def _add(name: str, actual: int, required: int, label: str) -> None:
        checks.append(
            {
                "name": name,
                "label": label,
                "required": required,
                "actual": actual,
                "pass": actual >= required,
            }
        )

    _add(
        "total_items",
        metrics["total_items"],
        QUALITY_THRESHOLDS["min_total_items"],
        "Total listening items",
    )
    for level, required in QUALITY_THRESHOLDS["min_items_per_level"].items():
        _add(
            f"items_{level.lower()}",
            metrics["per_level"][level],
            required,
            f"Items at {level}",
        )
    _add(
        "speakers",
        metrics["speakers"],
        QUALITY_THRESHOLDS["min_speakers"],
        "Distinct speakers",
    )
    _add(
        "accents",
        metrics["accents"],
        QUALITY_THRESHOLDS["min_accents"],
        "Distinct accents",
    )
    _add(
        "contexts",
        metrics["contexts"],
        QUALITY_THRESHOLDS["min_contexts"],
        "Distinct contexts",
    )
    _add(
        "connected_speech_items",
        metrics["connected_speech"],
        QUALITY_THRESHOLDS["min_connected_speech_items"],
        "Connected-speech items",
    )
    _add(
        "noise_items",
        metrics["noise"],
        QUALITY_THRESHOLDS["min_noise_items"],
        "Noisy items",
    )
    _add(
        "multiple_speakers_items",
        metrics["multiple_speakers"],
        QUALITY_THRESHOLDS["min_multiple_speakers_items"],
        "Multiple-speaker items",
    )
    _add(
        "fast_speech_items",
        metrics["fast_speech"],
        QUALITY_THRESHOLDS["min_fast_speech_items"],
        "Fast-speech items",
    )

    passed = sum(1 for c in checks if c["pass"])
    return {
        "pass": passed == len(checks),
        "passed": passed,
        "total": len(checks),
        "checks": checks,
    }


def run_content_validation() -> dict:
    """Ejecuta el chequeo de integridad del contenido y devuelve el resumen."""
    issues: list[dict] = []

    def add(severity: str, category: str, item_id: str, message: str) -> None:
        issues.append(
            {
                "severity": severity,
                "category": category,
                "id": item_id,
                "message": message,
            }
        )

    # 1. Integridad estructural del banco y del manifest.
    for message in validate_listening_bank():
        add("error", "bank", "", message)
    for message in validate_manifest():
        add("error", "manifest", "", message)

    # 2. Manifest (fuente de verdad de lo grabado).
    try:
        manifest = load_manifest()
        entries = {e.audio_id: e for e in manifest.entries}
    except (FileNotFoundError, ValueError, OSError) as exc:
        add("error", "manifest", "", f"manifest no cargable: {exc}")
        entries = {}

    # 3. Ids duplicados en el banco.
    bank_ids = [q["id"] for q in QUESTION_BANK]
    for qid, count in Counter(bank_ids).items():
        if count > 1:
            add("error", "duplicate_id", qid, f"id duplicado ({count} veces)")

    audio_ids = [q.get("audio_id") for q in QUESTION_BANK if q.get("audio_id")]
    for aid, count in Counter(audio_ids).items():
        if count > 1:
            add("error", "duplicate_audio_id", aid, f"audio_id duplicado ({count})")

    # 4. Por ítem: transcripción, referencia, CEFR, duración y contraste WAV.
    recorded = 0
    tts = 0
    for q in QUESTION_BANK:
        qid = q["id"]
        audio_id = (q.get("audio_id") or "").strip()

        text = (q.get("transcript") or "").strip() or (q.get("script") or "").strip()
        if not text:
            add("warning", "missing_transcript", qid, "sin transcript")

        if not audio_id:
            tts += 1
            continue

        entry = entries.get(audio_id)
        if entry is None:
            tts += 1
            continue

        recorded += 1
        path = resolve_file(entry)
        if path is None:
            add("error", "broken_reference", qid, f"{audio_id}: ruta inválida")
        elif not path.exists():
            add("error", "broken_reference", qid, f"{audio_id}: WAV ausente")

        level = q.get("level")
        if (
            entry.cefr not in ("", "unknown")
            and level
            and entry.cefr != level
        ):
            add(
                "error",
                "cefr_mismatch",
                qid,
                f"{audio_id}: cefr {entry.cefr} != level {level}",
            )

        declared = q.get("duration")
        if declared:
            tolerance = max(0.5, 0.05 * float(declared))
            if abs(float(declared) - entry.duration) > tolerance:
                add(
                    "warning",
                    "duration_mismatch",
                    qid,
                    f"{audio_id}: duración {declared}s vs manifest {entry.duration}s",
                )

        for issue in validate_audio_entry(entry):
            add(issue.severity, f"audio:{issue.field}", qid, issue.message)

    stats = content_stats()
    return {
        "total_items": len(QUESTION_BANK),
        "recorded": recorded,
        "tts": tts,
        "issues": issues,
        "by_severity": _issues_by_severity(issues),
        "ok": not any(i["severity"] == "error" for i in issues),
        "quality": run_quality_check(QUESTION_BANK),
        "stats": stats,
        "total_validated_learning_items": stats["total_validated_learning_items"],
    }
