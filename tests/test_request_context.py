from pathlib import Path
import sys

import pytest


PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from service.model import TaskContext, TaskExecutionRequest
from service.request_context import CloudRequestContext, HouseContextError, HouseResolver


class DummyHttpClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def request(self, method, url, headers=None, params=None, json=None):
        self.calls.append({"method": method, "url": url, "headers": headers, "params": params, "json": json})
        return self.response


def cloud_context(house_id=None):
    return CloudRequestContext(
        authorization="Bearer token",
        region="eu",
        api_base_url="https://api-de.yeelight.com",
        house_id=house_id,
    )


def house_request(house_id=None):
    return TaskExecutionRequest(
        task="family_space.manage_room",
        action="list_all_room",
        context=TaskContext(houseId=house_id),
    )


def test_explicit_context_house_precedes_header_and_does_not_query():
    client = DummyHttpClient({"success": True, "data": [{"id": "auto"}]})
    resolver = HouseResolver(client)
    request = house_request("explicit")

    resolver.enrich(request, ["houseId"], cloud_context("header"))

    assert request.context.houseId == "explicit"
    assert client.calls == []


def test_header_house_is_used_without_query():
    client = DummyHttpClient({"success": True, "data": [{"id": "auto"}]})
    resolver = HouseResolver(client)
    request = house_request()

    resolver.enrich(request, ["houseId"], cloud_context("header"))

    assert request.context.houseId == "header"
    assert client.calls == []


def test_first_pro_house_is_selected_for_house_required_action():
    client = DummyHttpClient({"success": True, "data": [{"id": "first", "name": "家"}, {"houseId": "second"}]})
    resolver = HouseResolver(client)
    request = house_request()

    resolver.enrich(request, ["houseId"], cloud_context())

    assert request.context.houseId == "first"
    assert client.calls[0]["url"] == "https://api-de.yeelight.com/apis/iot/v1/house/r/list"
    assert client.calls[0]["headers"] == {"authorization": "Bearer token", "bizType": "0"}


def test_action_without_house_requirement_does_not_query():
    client = DummyHttpClient({"success": True, "data": [{"id": "first"}]})
    resolver = HouseResolver(client)
    request = house_request()

    resolver.enrich(request, [], cloud_context())

    assert request.context.houseId is None
    assert client.calls == []


def test_empty_house_list_fails_clearly():
    resolver = HouseResolver(DummyHttpClient({"success": True, "data": []}))

    with pytest.raises(HouseContextError, match="没有可用的 Pro 家庭"):
        resolver.enrich(house_request(), ["houseId"], cloud_context())


def test_list_houses_normalizes_stable_fields():
    resolver = HouseResolver(DummyHttpClient({"code": "200", "data": {"rows": [{"houseId": 1001, "houseName": "主家庭"}]}}))

    assert resolver.list_houses(cloud_context()) == [
        {"houseId": "1001", "name": "主家庭", "source": "house", "region": "eu"}
    ]
