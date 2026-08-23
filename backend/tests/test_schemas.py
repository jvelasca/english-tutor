import pytest
from pydantic import ValidationError

from schemas.chat import ChatRequest


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
