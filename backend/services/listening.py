"""Banco de preguntas de listening y puntuación determinista (puro)."""
from __future__ import annotations

LISTENING_SUBSKILLS: tuple[str, ...] = (
    "gist",
    "detail",
    "inference",
    "vocabulary",
    "numbers",
)

QUESTION_BANK: list[dict] = [
    {
        "id": "l1",
        "level": "A1",
        "skill": "numbers",
        "difficulty": 1,
        "script": "Tom gets up at seven o'clock and has toast for breakfast.",
        "question": "What time does Tom get up?",
        "options": ["At six", "At seven", "At eight", "At nine"],
        "answer_index": 1,
    },
    {
        "id": "l2",
        "level": "A1",
        "skill": "detail",
        "difficulty": 2,
        "script": "Maria goes to the supermarket every Saturday morning.",
        "question": "When does Maria go to the supermarket?",
        "options": ["On Sunday", "On Saturday", "On Friday", "On Monday"],
        "answer_index": 1,
    },
    {
        "id": "l3",
        "level": "A1",
        "skill": "detail",
        "difficulty": 1,
        "script": "The children are playing football in the park.",
        "question": "What are the children doing?",
        "options": ["Reading", "Swimming", "Playing football", "Sleeping"],
        "answer_index": 2,
    },
    {
        "id": "l4",
        "level": "A2",
        "skill": "detail",
        "difficulty": 3,
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
        "skill": "inference",
        "difficulty": 4,
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
        "skill": "numbers",
        "difficulty": 3,
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
        "skill": "inference",
        "difficulty": 5,
        "script": "Despite the heavy rain, the team decided to continue the match.",
        "question": "What did the team decide?",
        "options": ["To stop", "To continue", "To postpone", "To go home"],
        "answer_index": 1,
    },
    {
        "id": "l8",
        "level": "B1",
        "skill": "inference",
        "difficulty": 6,
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
    {
        "id": "l9",
        "level": "A1",
        "skill": "gist",
        "difficulty": 2,
        "script": "Sarah and Mike are planning a trip. They talk about tickets and "
        "hotels. They want to visit Paris.",
        "question": "What are they mainly talking about?",
        "options": [
            "Planning a trip",
            "Cooking dinner",
            "Fixing a car",
            "Buying clothes",
        ],
        "answer_index": 0,
    },
    {
        "id": "l10",
        "level": "A2",
        "skill": "gist",
        "difficulty": 4,
        "script": "Last weekend was very busy. First, we cleaned the house. Then, "
        "we went shopping and cooked a big dinner for our friends.",
        "question": "What are they mainly talking about?",
        "options": [
            "Their busy weekend",
            "A football match",
            "A problem at work",
            "The weather",
        ],
        "answer_index": 0,
    },
    {
        "id": "l11",
        "level": "A1",
        "skill": "vocabulary",
        "difficulty": 1,
        "script": "This restaurant is very cheap. A full meal costs only five euros.",
        "question": "Which word means 'not expensive'?",
        "options": ["Cheap", "Expensive", "Noisy", "Cold"],
        "answer_index": 0,
    },
    {
        "id": "l12",
        "level": "A2",
        "skill": "vocabulary",
        "difficulty": 3,
        "script": "She was delighted when she passed the exam. She could not stop "
        "smiling.",
        "question": "Which word means 'very happy'?",
        "options": ["Delighted", "Sad", "Bored", "Afraid"],
        "answer_index": 0,
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


def listening_diagnostic(attempt_rows: list[dict]) -> dict:
    """Perfil de sub-destrezas de listening y recomendación (vista derivada).

    `attempt_rows` son las filas de `listening_attempts` del usuario (con `skill`,
    `difficulty`, `response_time_ms`, `replay_count`, `correct`). Devuelve un dict
    con `subskills` (lista de {skill, attempts, correct, accuracy, avg_response_ms,
    avg_replay_count}, ordenadas por LISTENING_SUBSKILLS y luego alfabético), y
    `weak` (lista de skills con `review_due` True) y `recommendation` (texto corto)."""
    groups: dict[str, list[dict]] = {}
    for row in attempt_rows:
        skill = row.get("skill") or ""
        groups.setdefault(skill, []).append(row)

    def _stats(rows: list[dict]) -> dict:
        attempts = len(rows)
        correct = sum(1 for r in rows if r.get("correct"))
        accuracy = round(correct / attempts * 100, 1) if attempts else None
        rts = [
            r.get("response_time_ms")
            for r in rows
            if r.get("response_time_ms") is not None
        ]
        avg_response_ms = round(sum(rts) / len(rts), 0) if rts else None
        replays = [r.get("replay_count") or 0 for r in rows]
        avg_replay_count = round(sum(replays) / len(replays), 2) if replays else 0.0
        return {
            "attempts": attempts,
            "correct": correct,
            "accuracy": accuracy,
            "avg_response_ms": avg_response_ms,
            "avg_replay_count": avg_replay_count,
        }

    known = list(LISTENING_SUBSKILLS)
    extras = sorted(set(groups) - set(known))
    ordered_skills = known + extras

    subskills: list[dict] = []
    for skill in ordered_skills:
        stats = _stats(groups.get(skill, []))
        attempts = stats["attempts"]
        accuracy = stats["accuracy"]
        review_due = attempts == 0 or (
            attempts >= 3 and accuracy is not None and accuracy < 70
        )
        subskills.append(
            {
                "skill": skill,
                "attempts": attempts,
                "correct": stats["correct"],
                "accuracy": accuracy,
                "avg_response_ms": stats["avg_response_ms"],
                "avg_replay_count": stats["avg_replay_count"],
                "review_due": review_due,
            }
        )

    def _rank(skill: str) -> int:
        if skill in known:
            return known.index(skill)
        return len(known) + extras.index(skill)

    def _acc(skill: str) -> float | None:
        for s in subskills:
            if s["skill"] == skill:
                return s["accuracy"]
        return None

    weak = [s["skill"] for s in subskills if s["review_due"]]
    weak.sort(
        key=lambda sk: (
            _acc(sk) is None,
            _acc(sk) if _acc(sk) is not None else 0.0,
            _rank(sk),
        )
    )

    if not weak:
        recommendation = "All listening sub-skills look strong."
    else:
        recommendation = "Focus on: " + ", ".join(weak)

    return {"subskills": subskills, "weak": weak, "recommendation": recommendation}
