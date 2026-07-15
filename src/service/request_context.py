from dataclasses import dataclass
from typing import Any, Dict, List

from service.model import TaskContext, TaskExecutionRequest, ValidationRequest
from utils.http import HttpClient


@dataclass(frozen=True)
class CloudRequestContext:
    authorization: str
    region: str
    api_base_url: str
    house_id: str | None = None


class HouseContextError(ValueError):
    pass


class HouseResolver:
    def __init__(self, http_client: HttpClient):
        self.http_client = http_client

    def list_houses(self, cloud: CloudRequestContext) -> List[Dict[str, str]]:
        response = self.http_client.request(
            "POST",
            f"{cloud.api_base_url}/apis/iot/v1/house/r/list",
            headers={"authorization": cloud.authorization, "bizType": "0"},
            json={},
        )
        if not isinstance(response, dict) or response.get("error") or response.get("success") is False:
            raise HouseContextError("查询 Pro 家庭列表失败，请检查 Authorization 与 Region。")
        code = response.get("code")
        if code is not None and str(code) != "200":
            raise HouseContextError("查询 Pro 家庭列表失败，请检查 Authorization 与 Region。")

        value: Any = response.get("data", response)
        items = self._extract_items(value)
        houses = []
        for item in items:
            if not isinstance(item, dict):
                continue
            house_id = self._pick(item, "houseId", "id", "value")
            if not house_id:
                continue
            houses.append({
                "houseId": house_id,
                "name": self._pick(item, "name", "houseName", "areaName", "text") or house_id,
                "source": "house",
                "region": cloud.region,
            })
        return houses

    def enrich(
        self,
        request: ValidationRequest | TaskExecutionRequest,
        required_context: List[str],
        cloud: CloudRequestContext,
    ) -> None:
        context_data = request.context.model_dump(exclude_none=True)
        if context_data.get("houseId") or "houseId" not in required_context:
            return
        if cloud.house_id:
            request.context = TaskContext(**{**context_data, "houseId": cloud.house_id})
            return

        houses = self.list_houses(cloud)
        if not houses:
            raise HouseContextError(
                "当前 Region 没有可用的 Pro 家庭。请在 Yeelight Pro APP 中创建家庭，或显式提供 context.houseId。"
            )
        request.context = TaskContext(**{**context_data, "houseId": houses[0]["houseId"]})

    @staticmethod
    def _extract_items(value: Any) -> List[Any]:
        if isinstance(value, list):
            return value
        if not isinstance(value, dict):
            return []
        for key in ("rows", "list", "houses", "houseList", "data"):
            if isinstance(value.get(key), list):
                return value[key]
        return []

    @staticmethod
    def _pick(source: Dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = source.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""
