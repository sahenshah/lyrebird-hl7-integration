from unittest.mock import patch
import requests
import pytest
from app.listener import send_to_api

def test_send_to_api_retries_and_succeeds():
    """
    Test that send_to_api retries on transient network errors and eventually succeeds.
    """
    calls = []
    class MockResponse:
        def raise_for_status(self): pass

    def mock_post(*args, **kwargs):
        if len(calls) < 2:
            calls.append(1)
            raise requests.RequestException("Transient failure")
        return MockResponse()  # success

    with patch("requests.post", mock_post):
        result = send_to_api({"foo": "bar"})
        assert isinstance(result, MockResponse)
        assert len(calls) == 2  # retried twice

def test_send_to_api_retries_configured_times(monkeypatch):
    from app.core import config
    monkeypatch.setattr(config, "MAX_RETRIES", 3)
    calls = []
    def mock_post(*args, **kwargs):
        calls.append(1)
        raise requests.RequestException("Always fails")
    with patch("requests.post", mock_post):
        with pytest.raises(requests.RequestException):
            send_to_api({"foo": "bar"})
    assert len(calls) == 3  # matches MAX_RETRIES


def test_send_to_api_uses_cert_verification(monkeypatch):
    """
    Test that send_to_api enforces TLS verification with cert.pem.
    """
    captured = {}

    class MockResponse:
        def raise_for_status(self):
            pass

    def mock_post(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return MockResponse()

    monkeypatch.setattr("app.listener.API_URL", "https://localhost:8000/api/v1/messages")
    monkeypatch.setattr("app.listener.API_TIMEOUT", 7)
    monkeypatch.setattr("app.listener.CERT_PATH", "/tmp/test-cert.pem")

    with patch("requests.post", mock_post):
        send_to_api({"foo": "bar"})

    assert captured["args"][0] == "https://localhost:8000/api/v1/messages"
    assert captured["kwargs"]["timeout"] == 7
    assert captured["kwargs"]["verify"] == "/tmp/test-cert.pem"