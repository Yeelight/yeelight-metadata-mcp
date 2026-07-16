import httpx
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from config.config import settings
from config.region import RegionError, api_base_for_region, resolve_region
from utils.auth import extract_token_claims, normalize_authorization_header


class AuthMiddleware(BaseHTTPMiddleware):
    async def check_token_valid(self, token: str, api_base_url: str):
        url = f"{api_base_url}/apis/account/user/info"
        try:
            async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
                response = await client.get(
                    url,
                    headers={"authorization": normalize_authorization_header(token)},
                )
            return str(response.json().get("code")) == "200"
        except Exception:
            return False

    async def dispatch(self, request: Request, call_next):
        token = request.headers.get(settings.AUTHORIZATION_HEADER_KEY)
        if not token:
            return JSONResponse({"error": "缺少或无效的 Token"}, status_code=401)
        claims = extract_token_claims(token)
        try:
            region = resolve_region(
                request.headers.get(settings.REGION_HEADER_KEY) or claims.region,
                settings.DEFAULT_REGION,
            )
            api_base_url = api_base_for_region(
                region,
                settings.API_BASE_URL,
                settings.DEFAULT_REGION,
            )
        except RegionError as error:
            return JSONResponse({"error": str(error)}, status_code=400)

        authorization = normalize_authorization_header(token)
        if not await self.check_token_valid(authorization, api_base_url):
            return JSONResponse({"error": "Token 无效或已过期"}, status_code=401)
        request.state.authorization = authorization
        request.state.region = region
        request.state.api_base_url = api_base_url
        request.state.house_id = request.headers.get(settings.HOUSE_ID_HEADER_KEY)
        return await call_next(request)
