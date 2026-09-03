"""Tranche autorado A1 + A2 del corpus de listening (Fase 3, primera entrega).

Cada tranche vive en `_corpus_frames_a1.py` / `_corpus_frames_a2.py` y expone su
lista de frames. Este módulo las une en el orden estable que consume
`generate_listening_corpus.py`.

Un frame es un ítem casi completo (sin id/audio/metadatos de voz); el pipeline
materializa los metadatos auditivos deterministas. El script es **la única fuente
de verdad de la frase** y debe respetar las bandas auditadas por nivel
(velocidad, palabras máx. por script, dificultad 1..2 para A1 y 2..3 para A2),
así como los invariantes de `validate_listening_bank`.
"""
from __future__ import annotations

from scripts._corpus_frames_a1 import FRAMES_A1
from scripts._corpus_frames_a2 import FRAMES_A2

# Orden estable: primero A1, después A2.
FRAMES_A1A2: list[dict] = FRAMES_A1 + FRAMES_A2
