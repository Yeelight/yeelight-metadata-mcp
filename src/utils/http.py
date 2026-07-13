from typing import Any, Dict, Optional

import httpx

from log.logger import logger


class HttpClient:
    """基础 HTTP 工具类，统一处理 GET/POST/PUT/DELETE 请求。"""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Any] = None,
    ) -> Any:
        try:
            response = httpx.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"HTTP {method} 请求失败: {url}, 错误: {e}")
            return {"error": str(e)}

    def get(self, url: str, headers: Optional[Dict[str, str]] = None, params: Optional[Dict[str, Any]] = None) -> Any:
        return self.request("GET", url, headers=headers, params=params)

    def post(self, url: str, headers: Optional[Dict[str, str]] = None, json: Optional[Any] = None) -> Any:
        return self.request("POST", url, headers=headers, json=json)

    def put(self, url: str, headers: Optional[Dict[str, str]] = None, json: Optional[Any] = None) -> Any:
        return self.request("PUT", url, headers=headers, json=json)

    def delete(self, url: str, headers: Optional[Dict[str, str]] = None, json: Optional[Any] = None) -> Any:
        return self.request("DELETE", url, headers=headers, json=json)
