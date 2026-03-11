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
        return MockResponse()

    with patch("requests.post", mock_post), \
         patch("app.core.retry.time.sleep"):
        result = send_to_api({"foo": "bar"}, max_attempts=3)  # ← direct injection
        assert isinstance(result, MockResponse)
        assert len(calls) == 2


def test_send_to_api_retries_configured_times():
    calls = []
    def mock_post(*args, **kwargs):
        calls.append(1)
        raise requests.RequestException("Always fails")

    with patch("requests.post", mock_post), \
         patch("app.core.retry.time.sleep"):
        with pytest.raises(requests.RequestException):
            send_to_api({"foo": "bar"}, max_attempts=3)  # ← direct injection
    assert len(calls) == 3