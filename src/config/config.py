import os

from config.region import DEFAULT_REGION, normalize_api_base_url, normalize_region


_SERVICE_NAME = "yeelight-online-metadata-mcp-server"
_DEFAULT_API_BASE_URL = "https://api.yeelight.com"
_RUNTIME_ENV = os.getenv("METADATA_MCP_RUNTIME_ENV", os.getenv("APP_MCP_RUNTIME_ENV", "prod")).lower()
_CONFIG_DIR = os.path.abspath(os.path.dirname(__file__))
_PROJECT_DIR = os.path.abspath(os.path.join(_CONFIG_DIR, "../.."))


def _env(name: str, default: str | None = None, legacy_name: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is not None:
        return value
    if legacy_name:
        legacy_value = os.getenv(legacy_name)
        if legacy_value is not None:
            return legacy_value
    return default


def resolve_resource_dir() -> str:
    explicit_dir = _env("METADATA_MCP_RESOURCE_DIR", legacy_name="APP_MCP_RESOURCE_DIR")
    if explicit_dir:
        return explicit_dir

    candidates = [
        os.path.join(_PROJECT_DIR, "resources/catalog"),
        os.path.join(os.getcwd(), "resources/catalog"),
        os.path.join(os.getcwd(), "docs/metadata-mcp"),
        os.path.join(_PROJECT_DIR, "docs/metadata-mcp"),
        os.path.join(_CONFIG_DIR, "../../docs/metadata-mcp"),
    ]
    for candidate in candidates:
        normalized = os.path.abspath(candidate)
        if os.path.exists(os.path.join(normalized, "metadata-mcp-user-task-map.json")):
            return normalized

    return os.path.abspath(os.path.join(_PROJECT_DIR, "resources/catalog"))


def default_bind_host() -> str:
    if _RUNTIME_ENV in {"local", "test"}:
        return "127.0.0.1"
    return "0.0.0.0"


_DEV_NACOS_CONFIG = {
    "enable": _env("METADATA_MCP_NACOS_ENABLE", "true" if _RUNTIME_ENV == "dev" else "false", "APP_MCP_NACOS_ENABLE").lower() == "true",
    "server": _env("METADATA_MCP_NACOS_SERVER", "192.168.0.41:8848,192.168.0.42:8848,192.168.0.43:8848", "APP_MCP_NACOS_SERVER"),
    "namespace": _env("METADATA_MCP_NACOS_NAMESPACE", "public", "APP_MCP_NACOS_NAMESPACE"),
    "service-name": f"{_SERVICE_NAME}-dev",
    "port": int(_env("METADATA_MCP_PORT", "9010", "APP_MCP_PORT")),
    "weight": 1.0,
    "cluster-name": "DEFAULT",
    "heartbeat-interval": 5,
}

_PROD_NACOS_CONFIG = {
    "enable": _env("METADATA_MCP_NACOS_ENABLE", "true", "APP_MCP_NACOS_ENABLE").lower() == "true",
    "server": _env("METADATA_MCP_NACOS_SERVER", "nacos.yeelight.com:8848", "APP_MCP_NACOS_SERVER"),
    "namespace": _env("METADATA_MCP_NACOS_NAMESPACE", "public", "APP_MCP_NACOS_NAMESPACE"),
    "service-name": f"{_SERVICE_NAME}-prod",
    "port": int(_env("METADATA_MCP_PORT", "9010", "APP_MCP_PORT")),
    "weight": 1.0,
    "cluster-name": "DEFAULT",
    "heartbeat-interval": 5,
}

_DEV_LOGGER_CONFIG = {
    "logger-name": _SERVICE_NAME,
    "file-path": f"./logs/{_SERVICE_NAME}",
    "file-name": f"{_SERVICE_NAME}.log",
}

_PROD_LOGGER_CONFIG = {
    "logger-name": _SERVICE_NAME,
    "file-path": f"/var/logs/{_SERVICE_NAME}",
    "file-name": f"{_SERVICE_NAME}.log",
}


class Config:
    MCP_SERVER_NAME = "Yeelight Metadata MCP Server"
    SERVICE_NAME = _SERVICE_NAME
    API_BASE_URL = normalize_api_base_url(_env("METADATA_MCP_API_BASE_URL", _env("METADATA_MCP_HOST_PREFIX", _env("APP_MCP_HOST_PREFIX", _DEFAULT_API_BASE_URL)), "APP_MCP_API_BASE_URL"))
    DEFAULT_REGION = normalize_region(_env("METADATA_MCP_DEFAULT_REGION", DEFAULT_REGION))
    HTTP_TIMEOUT = int(_env("METADATA_MCP_HTTP_TIMEOUT", "15", "APP_MCP_HTTP_TIMEOUT"))
    BIND_HOST = _env("METADATA_MCP_BIND_HOST", default_bind_host(), "APP_MCP_BIND_HOST")
    MCP_PATH = _env("METADATA_MCP_PATH", "/mcp", "APP_MCP_PATH")
    STATELESS_HTTP = True
    PORT = int(_env("METADATA_MCP_PORT", "9010", "APP_MCP_PORT"))

    AUTHORIZATION_HEADER_KEY = "Authorization"
    REGION_HEADER_KEY = "Yeelight-Region"
    HOUSE_ID_HEADER_KEY = "House-Id"

    RUNTIME_ENV = _RUNTIME_ENV
    ALLOW_CANDIDATE_EXECUTION = _env("METADATA_MCP_ALLOW_CANDIDATE_EXECUTION", "false", "APP_MCP_ALLOW_CANDIDATE_EXECUTION").lower() == "true"
    CANDIDATE_EXECUTION_ENVIRONMENTS = {"local", "test"}

    RESOURCE_DIR = resolve_resource_dir()

    NACOS_CONFIG = _DEV_NACOS_CONFIG if RUNTIME_ENV in {"dev", "local", "test"} else _PROD_NACOS_CONFIG
    LOGGER_CONFIG = _DEV_LOGGER_CONFIG if RUNTIME_ENV in {"local", "test"} else _PROD_LOGGER_CONFIG


settings = Config()
