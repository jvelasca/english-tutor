"""Tests del módulo fonémico determinista (grapheme→phoneme + precisión)."""

from services.phonemes import G2P, levenshtein, phoneme_accuracy, to_phonemes


def test_g2p_covers_common_words():
    # Muestreo del vocabulario que debe cubrir el diccionario compacto.
    for word in ("hello", "world", "name", "student", "twenty", "cheap", "exam"):
        assert word in G2P


def test_to_phonemes_non_empty():
    assert to_phonemes("hello") == ["HH", "AH", "L", "OW"]
    assert to_phonemes("hello world")


def test_to_phonemes_oov_falls_back_to_letters():
    # Palabras fuera de vocabulario se mapean letra a letra (nunca falla).
    assert to_phonemes("zzz") == ["z", "z", "z"]
    assert to_phonemes("hello zzz") == ["HH", "AH", "L", "OW", "z", "z", "z"]


def test_to_phonemes_empty():
    assert to_phonemes("") == []


def test_levenshtein_known_cases():
    assert levenshtein([], []) == 0
    assert levenshtein(["A"], ["A"]) == 0
    assert levenshtein(["A"], ["B"]) == 1
    assert levenshtein(["A", "B"], ["A", "C"]) == 1
    assert levenshtein(["A", "B"], ["A"]) == 1
    assert levenshtein(["A"], ["A", "B"]) == 1
    assert levenshtein(["A", "B", "C"], ["A", "C"]) == 1
    # "kitten" → "sitting" clásico sobre secuencias de fonemas.
    assert levenshtein(list("kitten"), list("sitting")) == 3


def test_phoneme_accuracy_exact_match_is_one():
    assert phoneme_accuracy("hello", "hello") == 1.0
    assert phoneme_accuracy("Hello world", "Hello world") == 1.0


def test_phoneme_accuracy_empty_vs_something_is_zero():
    assert phoneme_accuracy("", "hello") == 0.0
    assert phoneme_accuracy("hello", "") == 0.0


def test_phoneme_accuracy_near_miss_below_exact():
    exact = phoneme_accuracy("like", "like")
    near = phoneme_accuracy("like", "likes")
    assert exact == 1.0
    assert 0.0 < near < 1.0
    assert near < exact


def test_phoneme_accuracy_in_range():
    for expected, heard in (
        ("hello", "hello"),
        ("hello", "help"),
        ("I am a student", "I am student"),
        ("", ""),
        ("twenty years old", "twenty years"),
    ):
        acc = phoneme_accuracy(expected, heard)
        assert 0.0 <= acc <= 1.0
