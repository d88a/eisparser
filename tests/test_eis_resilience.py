import requests

from services.eis_downloader_service import EISDownloaderService


class _FakeResponse:
    def __init__(self, text: str = "", status_code: int = 200):
        self.text = text
        self.status_code = status_code
        self.headers = {}
        self.content = b""

    def raise_for_status(self):
        if 400 <= self.status_code:
            raise requests.HTTPError(response=self)


def test_fetch_search_page_retries_and_recovers(monkeypatch):
    service = EISDownloaderService()
    service.retry_count = 3
    service.retry_backoff_s = 0

    calls = {"n": 0}

    def _fake_get(_url, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.Timeout("timeout")
        return _FakeResponse(text="<html>ok</html>")

    monkeypatch.setattr(service.session, "get", _fake_get)
    html = service._fetch_search_page(1)

    assert html == "<html>ok</html>"
    assert calls["n"] == 2


def test_fetch_search_page_returns_none_after_retry_exhaustion(monkeypatch):
    service = EISDownloaderService()
    service.retry_count = 3
    service.retry_backoff_s = 0

    calls = {"n": 0}

    def _fake_get(_url, timeout):
        calls["n"] += 1
        raise requests.ConnectionError("network")

    monkeypatch.setattr(service.session, "get", _fake_get)
    html = service._fetch_search_page(1)

    assert html is None
    assert calls["n"] == service.retry_count


def test_error_classification():
    service = EISDownloaderService()

    assert service._classify_request_error(requests.Timeout("x")) == "timeout"

    resp_404 = requests.Response()
    resp_404.status_code = 404
    assert service._classify_request_error(requests.HTTPError(response=resp_404)) == "http_4xx"

    resp_503 = requests.Response()
    resp_503.status_code = 503
    assert service._classify_request_error(requests.HTTPError(response=resp_503)) == "http_5xx"

    assert service._classify_request_error(requests.ConnectionError("x")) == "network_error"
