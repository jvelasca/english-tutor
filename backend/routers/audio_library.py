"""Gestión en-app de la biblioteca de audio humano (subir/reemplazar/borrar WAV).

Permite cambiar las grabaciones reales de listening desde la propia app, sin tocar
la terminal. El manifest es la fuente de verdad en tiempo de ejecución: subir un WAV
convierte el ítem correspondiente de TTS a grabado, y borrarlo lo revierte a TTS.

Desde V1.37 los endpoints de escritura (subir/borrar) y el panel de auditoría
requieren **modo admin** (PIN local), y la subida devuelve un **panel de QA
acústica** (PASS/WARNING/REJECT) y aplica límites de tamaño/duración/MIME.
"""
from __future__ import annotations

import wave

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

import config
from dependencies import read_audio_limited, require_admin
from services import audio_library
from services.audio_library import (
    AUDIO_LIBRARY_VERSION,
    AudioLibraryEntry,
    entry_for,
    load_manifest,
    resolve_file,
    wav_probe_bytes,
    wav_quality_bytes,
)
from services.content_validation import run_content_validation
from services.listening import QUESTION_BANK

router = APIRouter()

_WAV_MIME = {"audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave"}


def _slot_audio_ids() -> set[str]:
    """`audio_id` declarados por los ítems de listening (los slots grabables)."""
    return {
        (q.get("audio_id") or "").strip()
        for q in QUESTION_BANK
        if (q.get("audio_id") or "").strip()
    }


def _slots() -> list[dict]:
    """Ítems del banco con `audio_id` y su estado respecto al manifest."""
    manifest = load_manifest()
    slots: list[dict] = []
    for q in QUESTION_BANK:
        audio_id = (q.get("audio_id") or "").strip()
        if not audio_id:
            continue
        entry = entry_for(manifest, audio_id)
        state = "empty"
        if entry is not None:
            path = resolve_file(entry)
            state = "recorded" if (path is not None and path.exists()) else "missing"
        slots.append(
            {
                "question_id": q["id"],
                "audio_id": audio_id,
                "level": q.get("level", ""),
                "skill": q.get("skill", ""),
                "topic": q.get("topic", ""),
                "transcript": q.get("transcript", ""),
                "clean_transcript": q.get("clean_transcript", ""),
                "speech_rate": q.get("speech_rate", 0.0),
                "noise_level": q.get("noise_level", 0),
                "speaker_id": q.get("speaker_id", ""),
                "accent": q.get("accent", "neutral"),
                "duration": q.get("duration", 0.0),
                "state": state,
                "entry": entry.model_dump() if entry is not None else None,
            }
        )
    return slots


@router.get("/api/audio-library/status")
async def status() -> dict:
    """Estado de la biblioteca: si requiere PIN de admin y versión del manifest."""
    return {
        "admin_required": bool(config.ADMIN_PIN),
        "version": AUDIO_LIBRARY_VERSION,
    }


@router.get("/api/audio-library/slots")
async def list_slots() -> dict:
    slots = await run_in_threadpool(_slots)
    return {"slots": slots}


@router.get("/api/audio-library/audit")
async def audit(_: None = Depends(require_admin)) -> dict:
    """CONTENT INTEGRITY CHECK: resumen de integridad del contenido end-to-end."""
    return await run_in_threadpool(run_content_validation)


@router.post("/api/audio-library/upload")
async def upload(
    file: UploadFile = File(...),
    audio_id: str = Form(...),
    speaker_id: str = Form(""),
    accent: str = Form("neutral"),
    speaker_count: int = Form(1),
    noise_level: int = Form(0),
    transcript: str = Form(""),
    gender: str = Form("unknown"),
    age_band: str = Form("unknown"),
    region: str = Form("unknown"),
    speech_rate: float | None = Form(None),
    spontaneity: str = Form("scripted"),
    recording_environment: str = Form("studio"),
    overlap: bool = Form(False),
    connected_speech: bool = Form(False),
    prosody: str = Form("unknown"),
    task_type: str = Form("unknown"),
    cefr: str = Form("unknown"),
    context: str = Form("unknown"),
    _: None = Depends(require_admin),
) -> dict:
    audio_id = audio_id.strip()
    if audio_id not in _slot_audio_ids():
        raise HTTPException(
            status_code=400, detail="audio_id no corresponde a un ítem de listening"
        )

    mime = file.content_type or ""
    if mime.split(";")[0].strip().lower() not in _WAV_MIME:
        raise HTTPException(
            status_code=415, detail="El archivo debe ser un WAV PCM sin comprimir"
        )

    data = await read_audio_limited(file)

    try:
        meta = wav_probe_bytes(data)
    except (wave.Error, ValueError, OSError, EOFError):
        raise HTTPException(
            status_code=400, detail="El archivo no es un WAV válido"
        ) from None

    if meta["duration"] > config.MAX_AUDIO_DURATION_SECONDS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Audio demasiado largo: {meta['duration']:.1f}s "
                f"(máx {config.MAX_AUDIO_DURATION_SECONDS:.0f}s)"
            ),
        )

    quality = wav_quality_bytes(data)

    try:
        entry = AudioLibraryEntry(
            audio_id=audio_id,
            file=f"{audio_id}.wav",
            speaker_id=speaker_id,
            accent=accent,
            speaker_count=speaker_count,
            noise_level=noise_level,
            duration=meta["duration"],
            transcript=transcript,
            gender=gender,
            age_band=age_band,
            region=region,
            speech_rate=speech_rate,
            spontaneity=spontaneity,
            recording_environment=recording_environment,
            overlap=overlap,
            connected_speech=connected_speech,
            prosody=prosody,
            task_type=task_type,
            cefr=cefr,
            context=context,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    try:
        await run_in_threadpool(audio_library.write_entry, entry, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    return {**entry.model_dump(), "quality": quality}


@router.get("/api/audio-library/{audio_id}/audio")
async def preview(
    audio_id: str, _: None = Depends(require_admin)
) -> Response:
    """Sirve el WAV grabado del `audio_id` (previsualizar, sin usuario)."""
    manifest = await run_in_threadpool(load_manifest)
    entry = entry_for(manifest, audio_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Audio no encontrado")
    path = resolve_file(entry)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="Archivo de audio no encontrado")
    data = await run_in_threadpool(path.read_bytes)
    return Response(content=data, media_type="audio/wav")


@router.delete("/api/audio-library/{audio_id}")
async def delete(
    audio_id: str, _: None = Depends(require_admin)
) -> dict:
    removed = await run_in_threadpool(audio_library.remove_entry, audio_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Audio no encontrado")
    return {"removed": True, "audio_id": audio_id}
