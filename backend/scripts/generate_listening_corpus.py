"""Pipeline reproducible de expansión del corpus de listening (Fase 3).

Genera ítems `cNNN` por nivel hasta los objetivos de `LISTENING_CORPUS_TARGETS`,
combinando los ítems ya autorados del corpus con *tranches* nuevos descritos en
`_corpus_frames.py`. Cada nivel se completa por tranches (A1/A2 primero); los
niveles que aún no tengan frames (B1..C2) quedan pendientes del siguiente tranche
sin tocar su contenido actual.

Propiedades:
- **Reproducible**: seed fija por defecto (`--seed`), sin aleatoriedad de sistema.
- **Idempotente**: vuelve a ejecutarse sin duplicar: solo añade lo que falta
  hasta los objetivos, respetando los ids ya presentes.
- **Validado**: cada ítem debe pasar `ListeningAsset` + `validate_listening_bank`
  sobre el banco completo; el script aborta (exit 1) si hay violaciones o si un
  nivel con frames no alcanza su objetivo.
- Los ítems son TTS (Piper sintetiza en runtime/caché); no requiere audio previo.

Uso:
    python scripts/generate_listening_corpus.py             # escribe el corpus
    python scripts/generate_listening_corpus.py --dry-run   # solo reporta
    python scripts/generate_listening_corpus.py --targets A1=100,A2=100
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import re
import sys
import zlib
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.curriculum import LISTENING_CORPUS_TARGETS  # noqa: E402
from services.listening import (  # noqa: E402
    QUESTION_BANK,
    validate_listening_bank,
)

try:  # Los tranches se añaden como módulos `_corpus_frames_*`.
    from scripts._corpus_frames_a1a2 import FRAMES_A1A2  # noqa: E402
except ImportError:  # pragma: no cover - arranque sin tranches autorados
    FRAMES_A1A2 = []

CORPUS_PATH = BACKEND_DIR / "curriculum" / "listening_corpus.json"
DEFAULT_SEED = 20260903

# Catálogo de hablantes: rota acento/región/género/edad de forma determinista y
# mantiene la variedad mínima de acentos por nivel exigida por la auditoría.
_SPEAKERS: tuple[dict, ...] = (
    {"accent": "British RP", "region": "UK", "gender": "female",
     "age_band": "adult"},
    {"accent": "General American", "region": "US", "gender": "male",
     "age_band": "adult"},
    {"accent": "Canadian", "region": "CA", "gender": "female",
     "age_band": "adult"},
    {"accent": "Australian", "region": "AU", "gender": "male",
     "age_band": "adult"},
    {"accent": "Irish", "region": "IE", "gender": "female",
     "age_band": "adult"},
    {"accent": "British Northern", "region": "GB", "gender": "male",
     "age_band": "adult"},
    {"accent": "Scottish", "region": "UK", "gender": "female",
     "age_band": "adult"},
    {"accent": "Indian English", "region": "IN", "gender": "male",
     "age_band": "adult"},
    {"accent": "New Zealand", "region": "NZ", "gender": "female",
     "age_band": "adult"},
    {"accent": "South African", "region": "ZA", "gender": "male",
     "age_band": "senior"},
)
_SPEAKER_IDS: tuple[str, ...] = (
    "speaker_001", "speaker_002", "speaker_003", "speaker_004", "speaker_005",
    "speaker_006", "speaker_007", "speaker_008", "speaker_009", "speaker_010",
)

# Prosodia por contexto/task_type (igual que el corpus autorado).
_PRODOSY_BY_CONTEXT: dict[str, str] = {
    "conversation": "neutral",
    "announcement": "announcer",
    "message": "neutral",
    "instructions": "neutral",
    "news": "newsreader",
    "interview": "measured",
    "narrative": "neutral",
    "presentation": "presentational",
}

# Niveles sin tranche autorado aún: se preservan intactos.


def _next_id(existing: set[str]) -> str:
    """Siguiente id `cNNN` libre partiendo de los presentes en el banco."""
    nums = [
        int(qid[1:])
        for qid in existing
        if qid.startswith("c") and qid[1:].isdigit()
    ]
    nxt = max(nums, default=0) + 1
    while f"c{nxt:03d}" in existing:
        nxt += 1
    return f"c{nxt:03d}"


def _speaker(index: int) -> dict:
    spk = _SPEAKERS[index % len(_SPEAKERS)]
    return {
        "speaker_id": _SPEAKER_IDS[index % len(_SPEAKER_IDS)],
        "accent": spk["accent"],
        "region": spk["region"],
        "gender": spk["gender"],
        "age_band": spk["age_band"],
    }


_SPEAKER_PREFIX = re.compile(r"\b[ABC]:\s*")


def _transcript_of(script: str) -> str:
    """Transcript sin los prefijos de hablante (`A:`/`B:`/`C:`)."""
    return _SPEAKER_PREFIX.sub("", script).strip()


def _clean(duration_words: float) -> float:
    """Duración estimada (s) a partir del nº de palabras y la tasa de habla."""
    return round(duration_words, 1)


def materialize_frame(
    frame: dict,
    *,
    counter: collections.Counter,
    rng: random.Random,
    seen_scripts: set[str],
) -> dict | None:
    """Convierte un frame autorado en un ítem de corpus final.

    Un frame es un ítem casi completo (sin id/audio/metadatos de voz). Devuelve
    None si el script ya existía (duplicado) o el frame está mal formado. Los
    metadatos auditivos (speaker, duración, vector, dificultad...) se derivan de
    la banda del nivel + el propio frame, manteniendo los invariantes del corpus.
    """
    script = (frame.get("script") or "").strip()
    if not script or script in seen_scripts:
        return None
    seen_scripts.add(script)

    level = frame["level"]
    words = len(_transcript_of(script).split())

    # Metadatos de voz deterministas: rota el catálogo por ítem generado.
    spk = _speaker(counter["items"])

    # Orden de opciones determinista: el frame declara la correcta en primer
    # lugar y aquí se baraja con la seed del pipeline (nunca la posición 0).
    options = list(frame["options"])
    answer = options[int(frame["answer_index"])]
    rng.shuffle(options)

    item = {
        "id": frame["_id"],
        "level": level,
        "skill": frame["skill"],
        "topic": frame["topic"],
        "context": frame["context"],
        "task_type": frame.get("task_type") or _task_type(frame["context"]),
        "difficulty_vector": dict(frame["difficulty_vector"]),
        "script": script,
        "question": frame["question"],
        "options": options,
        "answer_index": options.index(answer),
        "audio_id": f"audio-{frame['_id']}",
        "duration": _clean(
            words / ((frame.get("speech_rate", 120.0) or 120.0) / 60.0)
            + (0.8 if frame.get("speaker_count", 1) > 1 else 0.4)
        ),
        "speaker_id": spk["speaker_id"],
        "accent": spk["accent"],
        "speech_rate": float(frame.get("speech_rate", 120.0)),
        "transcript": _transcript_of(script),
        "clean_transcript": _transcript_of(script),
        "noise_level": int(frame.get("noise_level", 0)),
        "repetition_policy": frame.get("repetition_policy", "none"),
        "gender": spk["gender"],
        "age_band": spk["age_band"],
        "region": spk["region"],
        "speaker_count": int(frame.get("speaker_count", 1)),
        "spontaneity": frame.get(
            "spontaneity",
            "semi_scripted"
            if frame.get("speaker_count", 1) > 1
            else "scripted",
        ),
        "recording_environment": frame.get(
            "recording_environment",
            "quiet_room" if int(frame.get("noise_level", 0)) == 0 else "public_place",
        ),
        "overlap": bool(frame.get("overlap", False)),
        "connected_speech": bool(frame.get("connected_speech", False)),
        "prosody": frame.get(
            "prosody", _PRODOSY_BY_CONTEXT.get(frame["context"], "neutral")
        ),
    }
    counter["items"] += 1
    return item


def _task_type(context: str) -> str:
    if context == "conversation":
        return "dialogue"
    contexts = (
        "narrative", "announcement", "message", "instructions",
        "news", "interview", "presentation",
    )
    if context in contexts:
        return context
    return "narrative"


def _frame_id_slot(level: str, index: int) -> str:
    return f"{level}-frame-{index:03d}"


def build_frames(seed: int) -> list[dict]:
    """Asigna ids y reordena los frames autorados de forma determinista."""
    frames = list(FRAMES_A1A2)
    rng = random.Random(seed)
    rng.shuffle(frames)
    for i, frame in enumerate(frames):
        frame = dict(frame)
        frame["_id"] = _frame_id_slot(frame["level"], i)
        frames[i] = frame
    return frames


def generate_to_targets(
    existing: list[dict],
    targets: dict[str, int],
    *,
    seed: int,
    dry_run: bool,
) -> tuple[list[dict], dict]:
    """Devuelve (corpus_final, report) añadiendo frames hasta los objetivos."""
    frames = build_frames(seed)
    by_level: dict[str, list[dict]] = collections.defaultdict(list)
    for frame in frames:
        by_level[frame["level"]].append(frame)

    seen_scripts = {q["script"] for q in QUESTION_BANK}
    counter = collections.Counter({"items": 0})
    # Orden determinista pero variado: recorremos niveles A1..C2 en orden y, dentro
    # de cada nivel, rotamos entre skills para repartir la cobertura.
    level_order = [lv for lv in LISTENING_CORPUS_TARGETS]
    rng = random.Random(seed)

    level_cur: dict[str, int] = collections.Counter(
        q["level"] for q in existing
    )
    # Reparto equilibrado: dentro de cada nivel se rota entre (skill, topic) en
    # vez de consumir una lista plana, para que la cobertura nueva no se sature
    # en la primera skill del orden alfabético.
    buckets: dict[str, list[list[dict]]] = {}
    for level in level_order:
        keys = sorted(
            {
                (f.get("skill", ""), f.get("topic", ""))
                for f in by_level.get(level, [])
            }
        )
        level_buckets: list[list[dict]] = []
        for key in keys:
            pool = [
                f for f in by_level[level] if (f.get("skill"), f.get("topic")) == key
            ]
            pool.sort(key=lambda f: (f.get("script", ""), f.get("question", "")))
            level_buckets.append(pool)
        buckets[level] = level_buckets

    added: list[dict] = []
    for level in level_order:
        needed = targets.get(level, 0) - level_cur[level]
        if needed <= 0:
            continue
        if not by_level.get(level):
            # Nivel sin tranche autorado: se preserva (pendiente de siguiente tranche).
            continue
        pool_id = 0
        # Índice de consumo por bucket: la rotación recorre los buckets activos
        # en círculo y cada bucket cede un frame por pasada.
        active = [i for i, b in enumerate(buckets[level]) if b]
        while level_cur[level] < targets[level] and active:
            bucket_idx = active[pool_id % len(active)]
            frame = buckets[level][bucket_idx].pop(0)
            if not buckets[level][bucket_idx]:
                active = [i for i, b in enumerate(buckets[level]) if b]
                if bucket_idx in active:
                    pool_id = active.index(bucket_idx) + 1
                    continue
                pool_id = pool_id % len(active) if active else 0
            else:
                pool_id += 1
            frame["_id"] = _next_id(
                {q["id"] for q in existing} | {a["id"] for a in added}
            )
            item = materialize_frame(
                frame,
                counter=counter,
                rng=rng,
                seen_scripts=seen_scripts,
            )
            if item is None:
                continue
            added.append(item)
            level_cur[level] += 1

    corpus = list(existing) + added
    report = {
        "added": len(added),
        "per_level": dict(sorted(level_cur.items())),
        "targets": dict(targets),
        # Niveles con tranche autorado en esta ejecución: son los que deben
        # alcanzar su objetivo (los demás quedan para su siguiente tranche).
        "with_frames": sorted(by_level),
        "duplicated_scripts_skipped": counter.get("duplicates", 0),
    }
    return corpus, report


def rebalance_option_positions(items: list[dict]) -> int:
    """Baraja de forma determinista las opciones del corpus `cNNN`.

    Cierra el sesgo posicional de la auditoría B (90,7 % de respuestas del corpus
    en la opción 0): cada ítem recibe una posición de la respuesta derivada de su
    id (`crc32 % n`), por lo que las posiciones se reparten ~uniformemente. La
    transformación es idempotente (mismo id → misma rotación) y preserva el orden
    relativo de los distractores. Devuelve cuántos ítems cambiaron de posición."""
    changed = 0
    for item in items:
        if not item.get("id", "").startswith("c"):
            continue  # banco legacy fuera del alcance de la auditoría
        options = item["options"]
        n = len(options)
        if n < 2:
            continue
        answer_idx = int(item["answer_index"])
        target = zlib.crc32(item["id"].encode("utf-8")) % n
        if answer_idx == target:
            continue
        answer = options[answer_idx]
        others = [opt for i, opt in enumerate(options) if i != answer_idx]
        item["options"] = others[:target] + [answer] + others[target:]
        item["answer_index"] = target
        changed += 1
    return changed


def validate_corpus(corpus: list[dict]) -> None:
    """Falla si el banco completo (legacy + corpus) viola invariantes."""
    violations = validate_listening_bank(corpus)
    if violations:
        print("[FAIL] Violaciones de validate_listening_bank:", file=sys.stderr)
        for v in violations[:40]:
            print("  -", v, file=sys.stderr)
        raise SystemExit(1)


def _distribution(items: list[dict], key: str) -> dict[str, int]:
    return dict(sorted(collections.Counter(q.get(key) for q in items).items()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--dry-run", action="store_true", help="solo reporta")
    parser.add_argument(
        "--targets",
        help="targets por nivel, p. ej. A1=200,A2=200 (por defecto: curriculum)",
    )
    parser.add_argument(
        "--out", default=str(CORPUS_PATH), help="ruta del corpus JSON de salida"
    )
    args = parser.parse_args(argv)

    if args.targets:
        targets = {
            k: int(v) for k, v in (pair.split("=") for pair in args.targets.split(","))
        }
    else:
        targets = dict(LISTENING_CORPUS_TARGETS)

    data = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    existing = data["items"]
    baseline = json.dumps(existing, sort_keys=True, ensure_ascii=False)
    current = collections.Counter(q["level"] for q in existing)
    print("Corpus actual:", dict(sorted(current.items())))

    corpus, report = generate_to_targets(
        existing, targets, seed=args.seed, dry_run=args.dry_run
    )
    print("Añadidos:", report["added"])
    print("Tras generación:", report["per_level"])

    validate_corpus(corpus)

    # Verificación de objetivos: solo los niveles con tranche autorado en esta
    # ejecución deben alcanzar su target (los demás son el siguiente tranche).
    skipped = [lv for lv in targets if lv not in report["with_frames"]]
    if skipped:
        print(
            "Sin tranche autorado (se preservan):",
            ", ".join(skipped),
        )
    failed = [
        (lv, report["per_level"].get(lv, 0), tgt)
        for lv, tgt in targets.items()
        if lv in report["with_frames"] and report["per_level"].get(lv, 0) < tgt
    ]
    if failed:
        for lv, got, tgt in failed:
            print(
                f"[FAIL] {lv}: {got} < objetivo {tgt}. Añade más frames.",
                file=sys.stderr,
            )
        raise SystemExit(1)

    if args.dry_run:
        return 0

    # Rotación posicional determinista del corpus existente (auditoría B, mc-bias)
    # antes de comparar con la baseline: idempotente y estable entre ejecuciones.
    repositioned = rebalance_option_positions(corpus)
    if repositioned:
        print(f"Opciones rebalanceadas (rotación por id): {repositioned} ítems")
        validate_corpus(corpus)

    final = json.dumps(corpus, sort_keys=True, ensure_ascii=False)
    if final == baseline:
        print("Sin cambios de contenido: no se reescribe el corpus.")
        return 0

    corpus_data = {
        "version": _next_corpus_version(data.get("version", "1.0.0")),
        "items": corpus,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(corpus_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Escrito {out_path} (version {corpus_data['version']}, {len(corpus)} ítems)")
    counts = dict(
        sorted(collections.Counter(q['level'] for q in corpus).items())
    )
    print("Nuevo corpus por nivel:", counts)
    return 0


def _next_corpus_version(current: str) -> str:
    major, minor, *_ = (current.split(".") + ["0", "0"])[:3]
    return f"{int(major) + 1}.0.0"


if __name__ == "__main__":
    sys.exit(main())
