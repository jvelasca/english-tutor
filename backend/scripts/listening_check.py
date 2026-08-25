"""Verificación determinista de la progresión de listening (sin red ni BD).

Simula a un usuario que responde correctamente cada pregunta del banco y
comprueba que la práctica avanza de nivel (A1 → A2 → B1) y no se queda atascada
en un bucle (regresión del bug "no pasa el nivel de aciertos").

Uso:
    .venv\\Scripts\\python.exe scripts/listening_check.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Windows usa cp1252 por defecto; forzamos UTF-8 para evitar UnicodeEncodeError.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Permite ejecutar el script desde cualquier directorio resolviendo `services`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.listening import (
    LEVEL_ORDER,
    QUESTION_BANK,
    current_level,
    level_status,
    pick_next_question,
)


def main() -> int:
    failures: list[str] = []

    # 1) Un usuario nuevo empieza en A1.
    seen: set[str] = set()
    correct: set[str] = set()
    first = pick_next_question(seen, correct)
    if first["level"] != "A1":
        failures.append(f"Esperaba empezar en A1, obtuve {first['level']}")

    # 2) Responder correctamente cada pregunta avanza el nivel y no se atasca.
    visited_levels: list[str] = []
    for _ in range(len(QUESTION_BANK)):
        q = pick_next_question(seen, correct)
        visited_levels.append(q["level"])
        seen.add(q["id"])
        correct.add(q["id"])  # respuesta correcta simulada

    status = level_status(correct)
    completed = [s["level"] for s in status if s["completed"]]
    if completed != LEVEL_ORDER:
        failures.append(
            f"Esperaba niveles completados {LEVEL_ORDER}, obtuve {completed}"
        )
    if current_level(correct) != "B1":
        failures.append(f"Tras completar todo, nivel actual = {current_level(correct)}")

    # 3) La secuencia de niveles visitados debe ser monótona (nunca retrocede).
    order = {lv: i for i, lv in enumerate(LEVEL_ORDER)}
    if any(order[visited_levels[i]] > order[visited_levels[i + 1]]
           for i in range(len(visited_levels) - 1)):
        failures.append(f"La progresión retrocedió: {visited_levels}")

    print("Banco:", len(QUESTION_BANK), "preguntas · Niveles:", LEVEL_ORDER)
    print("Secuencia de niveles:", " → ".join(visited_levels))
    print("Completados:", completed)

    if failures:
        for f in failures:
            print("[FAIL]", f)
        print("LISTENING CHECK FAILED")
        return 1
    print("LISTENING CHECK PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
