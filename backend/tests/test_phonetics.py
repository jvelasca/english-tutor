import pytest

from services.phonemes import to_phonemes
from services.phonetics import (
    composite_score,
    phonetic_similarity,
    soundex,
    tokenize,
    word_accuracy,
    word_alignment,
)


def test_tokenize_lowercases_and_strips_punct():
    assert tokenize("Hello, world!") == ["hello", "world"]


def test_soundex_hello():
    assert soundex("hello") == "H400"


def test_soundex_world():
    assert soundex("world") == "W643"


def test_soundex_coffee():
    assert soundex("coffee") == "C100"


def test_soundex_empty_word():
    assert soundex("") == ""


def test_word_alignment_exact_match():
    r = word_alignment("Hello world", "Hello world")
    assert r["correct"] == ["hello", "world"]
    assert r["missing"] == []
    assert r["extra"] == []
    assert r["substituted"] == []
    assert r["total"] == 2


def test_word_alignment_substitution():
    r = word_alignment("I have twenty years old", "I am twenty years old")
    assert r["substituted"] == [{"expected": "have", "heard": "am"}]
    assert r["correct"] == ["i", "twenty", "years", "old"]


def test_word_alignment_missing_words():
    r = word_alignment("Hello world", "Hello")
    assert r["missing"] == ["world"]
    assert r["correct"] == ["hello"]


def test_word_alignment_extra_words():
    r = word_alignment("Hello", "Hello world")
    assert r["extra"] == ["world"]
    assert r["correct"] == ["hello"]


def test_word_accuracy_partial():
    r = word_accuracy("I have twenty years old", "I am twenty years old")
    assert r == pytest.approx(0.8)


def test_phonetic_similarity_catches_near_miss():
    assert phonetic_similarity("hello", "helo") == 1.0


def test_composite_score_exact_empty_partial():
    assert composite_score("Hello world", "Hello world")["score"] == 100
    assert composite_score("Hello", "")["score"] == 0
    partial = composite_score(
        "I have twenty years old", "I am twenty years old"
    )["score"]
    assert 50 <= partial < 100


def test_composite_score_includes_phoneme_accuracy():
    assert composite_score("Hello world", "Hello world")["phoneme_accuracy"] == 100
    assert composite_score("Hello", "")["phoneme_accuracy"] == 0


def test_composite_score_includes_prosody_and_phoneme_breakdown():
    r = composite_score("Hello world", "Hello world")
    assert r["prosody_score"] == 100
    assert r["phoneme_breakdown"]["total"] == len(r["phoneme_breakdown"]["correct"])
    empty = composite_score("Hello", "")
    assert empty["prosody_score"] == 0
    assert empty["phoneme_breakdown"]["total"] == len(to_phonemes("Hello"))
