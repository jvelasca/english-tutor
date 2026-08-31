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
from services.listening import QUESTION_BANK, validate_listening_bank


def _issues_by_severity(issues: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = Counter()
    for issue in issues:
        counts[issue["severity"]] += 1
    return dict(counts)


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

    return {
        "total_items": len(QUESTION_BANK),
        "recorded": recorded,
        "tts": tts,
        "issues": issues,
        "by_severity": _issues_by_severity(issues),
        "ok": not any(i["severity"] == "error" for i in issues),
    }
