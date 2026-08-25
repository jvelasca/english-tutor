"""Banco de preguntas de listening y puntuación determinista (puro)."""
from __future__ import annotations

QUESTION_BANK: list[dict] = [
    {
        "id": "l1",
        "level": "A1",
        "script": "Tom gets up at seven o'clock and has toast for breakfast.",
        "question": "What time does Tom get up?",
        "options": ["At six", "At seven", "At eight", "At nine"],
        "answer_index": 1,
    },
    {
        "id": "l2",
        "level": "A1",
        "script": "Maria goes to the supermarket every Saturday morning.",
        "question": "When does Maria go to the supermarket?",
        "options": ["On Sunday", "On Saturday", "On Friday", "On Monday"],
        "answer_index": 1,
    },
    {
        "id": "l3",
        "level": "A1",
        "script": "The children are playing football in the park.",
        "question": "What are the children doing?",
        "options": ["Reading", "Swimming", "Playing football", "Sleeping"],
        "answer_index": 2,
    },
    {
        "id": "l4",
        "level": "A2",
        "script": "John bought a blue shirt and a pair of black shoes.",
        "question": "What did John buy?",
        "options": [
            "A blue shirt and black shoes",
            "A red jacket",
            "A white hat",
            "A green bag",
        ],
        "answer_index": 0,
    },
    {
        "id": "l5",
        "level": "A2",
        "script": "Anna prefers to travel by train because it is cheaper than flying.",
        "question": "Why does Anna prefer the train?",
        "options": [
            "It is faster",
            "It is cheaper",
            "It is more comfortable",
            "It is safer",
        ],
        "answer_index": 1,
    },
    {
        "id": "l6",
        "level": "A2",
        "script": "The meeting will start at half past nine and finish at noon.",
        "question": "How long does the meeting last?",
        "options": [
            "One hour",
            "Two hours and a half",
            "Three hours",
            "Half an hour",
        ],
        "answer_index": 1,
    },
    {
        "id": "l7",
        "level": "B1",
        "script": "Despite the heavy rain, the team decided to continue the match.",
        "question": "What did the team decide?",
        "options": ["To stop", "To continue", "To postpone", "To go home"],
        "answer_index": 1,
    },
    {
        "id": "l8",
        "level": "B1",
        "script": "If you arrive early, you will have time to review your notes.",
        "question": "What happens if you arrive early?",
        "options": [
            "You miss the review",
            "You have time to review",
            "You must wait",
            "Nothing",
        ],
        "answer_index": 1,
    },
]


LEVEL_ORDER: list[str] = ["A1", "A2", "B1"]


def get_question(question_id: str) -> dict | None:
    """Devuelve la pregunta por id o None si no existe."""
    for q in QUESTION_BANK:
        if q["id"] == question_id:
            return q
    return None


def questions_for_level(level: str) -> list[dict]:
    """Preguntas del banco pertenecientes a un nivel CEFR concreto."""
    return [q for q in QUESTION_BANK if q["level"] == level]


def level_status(correct_question_ids: set[str]) -> list[dict]:
    """Progreso por nivel CEFR.

    Un nivel se considera completado cuando el usuario ha respondido
    correctamente (al menos una vez) todas sus preguntas. Devuelve una lista con
    `{level, total, mastered, completed}` en orden CEFR."""
    status = []
    for level in LEVEL_ORDER:
        questions = questions_for_level(level)
        total = len(questions)
        mastered = sum(1 for q in questions if q["id"] in correct_question_ids)
        status.append(
            {
                "level": level,
                "total": total,
                "mastered": mastered,
                "completed": total > 0 and mastered == total,
            }
        )
    return status


def current_level(correct_question_ids: set[str]) -> str:
    """Nivel CEFR en el que el usuario está trabajando.

    Es el primer nivel aún no completado; si todos están completados, devuelve el
    último nivel para permitir seguir practicando sin quedarse atascado."""
    for level in LEVEL_ORDER:
        questions = questions_for_level(level)
        if not questions:
            continue
        mastered = sum(1 for q in questions if q["id"] in correct_question_ids)
        if mastered < len(questions):
            return level
    return LEVEL_ORDER[-1]


def pick_next_question(
    seen_ids: set[str], correct_ids: set[str] | None = None
) -> dict:
    """Siguiente pregunta respetando la progresión por nivel CEFR.

    Prioriza, dentro del nivel actual, las preguntas aún no dominadas (respondidas
    correctamente): primero las no vistas y luego las vistas pero falladas, para
    reintentarlas. Al dominar un nivel se avanza al siguiente; al completar todos,
    rota sobre el banco para seguir practicando en lugar de quedarse atascado."""
    correct_ids = correct_ids or set()
    questions = questions_for_level(current_level(correct_ids))

    for q in questions:
        if q["id"] not in seen_ids and q["id"] not in correct_ids:
            return q
    for q in questions:
        if q["id"] not in correct_ids:
            return q

    # Nivel completado o sin preguntas: nunca se repite la misma pregunta en bucle.
    for q in QUESTION_BANK:
        if q["id"] not in correct_ids:
            return q
    return QUESTION_BANK[0]


def score_answer(answer_index: int, correct_index: int) -> bool:
    """True si el índice elegido coincide con el correcto."""
    return answer_index == correct_index
