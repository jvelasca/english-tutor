import pytest
from pydantic import ValidationError

from config import MAX_CHAT_MESSAGES, MAX_CONTENT_CHARS, MAX_TTS_CHARS
from schemas.chat import ChatRequest
from schemas.voz import TTSRequest


def test_chat_request_uses_default_model():
    req = ChatRequest(messages=[{"role": "user", "content": "Hi"}])
    assert req.model == "qwen3.5:9b"
    assert req.temperature == 0.7


def test_empty_content_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(messages=[{"role": "user", "content": ""}])


def test_temperature_out_of_range_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(messages=[{"role": "user", "content": "Hi"}], temperature=3.0)


def test_system_role_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(messages=[{"role": "system", "content": "you are a tutor"}])


def test_content_too_long_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(
            messages=[{"role": "user", "content": "x" * (MAX_CONTENT_CHARS + 1)}]
        )


def test_too_many_messages_rejected():
    msgs = [{"role": "user", "content": "x"}] * (MAX_CHAT_MESSAGES + 1)
    with pytest.raises(ValidationError):
        ChatRequest(messages=msgs)


def test_empty_messages_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(messages=[])


def test_tts_text_too_long_rejected():
    with pytest.raises(ValidationError):
        TTSRequest(text="x" * (MAX_TTS_CHARS + 1))
