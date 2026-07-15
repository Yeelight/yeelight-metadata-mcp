import asyncio
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from middleware.auth import AuthMiddleware


class DummyResponse:
    def json(self):
        return {"code": "200"}


class DummyAsyncClient:
    calls = []

    def __init__(self, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url, headers):
        self.calls.append({"url": url, "headers": headers})
        return DummyResponse()


class FailingAsyncClient(DummyAsyncClient):
    async def get(self, url, headers):
        raise RuntimeError("network down")


class Headers(dict):
    def get(self, key, default=None):
        lowered = key.lower()
        for name, value in self.items():
            if name.lower() == lowered:
                return value
        return default


class State:
    pass


class Request:
    def __init__(self, headers):
        self.headers = Headers(headers)
        self.state = State()


def test_token_validation_uses_request_region_base(monkeypatch):
    DummyAsyncClient.calls = []
    monkeypatch.setattr("middleware.auth.httpx.AsyncClient", DummyAsyncClient)
    middleware = object.__new__(AuthMiddleware)

    result = asyncio.run(middleware.check_token_valid("token", "https://api-us.yeelight.com"))

    assert result is True
    assert DummyAsyncClient.calls == [{
        "url": "https://api-us.yeelight.com/apis/account/user/info",
        "headers": {"authorization": "Bearer token"},
    }]


def test_token_validation_treats_upstream_failure_as_invalid(monkeypatch):
    monkeypatch.setattr("middleware.auth.httpx.AsyncClient", FailingAsyncClient)
    middleware = object.__new__(AuthMiddleware)

    result = asyncio.run(middleware.check_token_valid("token", "https://api.yeelight.com"))

    assert result is False


def test_dispatch_writes_isolated_request_region_context(monkeypatch):
    middleware = object.__new__(AuthMiddleware)

    async def valid(token, api_base_url):
        return True

    middleware.check_token_valid = valid
    requests = [
        Request({"Authorization": "token-cn", "Yeelight-Region": "cn", "House-Id": "house-cn"}),
        Request({"Authorization": "token-eu", "Yeelight-Region": "eu"}),
    ]

    async def call_next(request):
        return request.state

    states = [asyncio.run(middleware.dispatch(request, call_next)) for request in requests]

    assert states[0].region == "cn"
    assert states[0].api_base_url == "https://api.yeelight.com"
    assert states[0].house_id == "house-cn"
    assert states[1].region == "eu"
    assert states[1].api_base_url == "https://api-de.yeelight.com"
    assert states[1].house_id is None


def test_dispatch_rejects_unknown_region_before_token_validation():
    middleware = object.__new__(AuthMiddleware)
    called = False

    async def valid(token, api_base_url):
        nonlocal called
        called = True
        return True

    middleware.check_token_valid = valid

    async def call_next(request):
        raise AssertionError("不应继续处理未知 Region")

    response = asyncio.run(middleware.dispatch(
        Request({"Authorization": "token", "Yeelight-Region": "mars"}),
        call_next,
    ))

    assert response.status_code == 400
    assert called is False
