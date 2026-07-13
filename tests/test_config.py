import importlib
import os
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


def load_config(monkeypatch, runtime_env=None, nacos_enable=None):
    legacy_env_names = [
        "APP_MCP_RUNTIME_ENV",
        "APP_MCP_NACOS_ENABLE",
        "APP_MCP_NACOS_SERVER",
        "APP_MCP_NACOS_NAMESPACE",
        "APP_MCP_PORT",
        "APP_MCP_BIND_HOST",
        "APP_MCP_RESOURCE_DIR",
        "APP_MCP_HOST_PREFIX",
        "APP_MCP_API_BASE_URL",
        "APP_MCP_HTTP_TIMEOUT",
        "APP_MCP_PATH",
        "APP_MCP_ALLOW_CANDIDATE_EXECUTION",
    ]
    for name in legacy_env_names:
        monkeypatch.delenv(name, raising=False)

    if runtime_env is None:
        monkeypatch.delenv("METADATA_MCP_RUNTIME_ENV", raising=False)
    else:
        monkeypatch.setenv("METADATA_MCP_RUNTIME_ENV", runtime_env)

    if nacos_enable is None:
        monkeypatch.delenv("METADATA_MCP_NACOS_ENABLE", raising=False)
    else:
        monkeypatch.setenv("METADATA_MCP_NACOS_ENABLE", nacos_enable)

    for name in list(sys.modules):
        if name == "config.config" or name.startswith("config."):
            sys.modules.pop(name)
    return importlib.import_module("config.config")


def test_default_runtime_registers_prod_nacos_like_iot_mcp(monkeypatch):
    config = load_config(monkeypatch)

    assert config.settings.RUNTIME_ENV == "prod"
    assert config.settings.NACOS_CONFIG["enable"] is True
    assert config.settings.NACOS_CONFIG["server"] == "nacos.yeelight.com:8848"
    assert config.settings.NACOS_CONFIG["service-name"] == "yeelight-online-metadata-mcp-server-prod"
    assert config.settings.NACOS_CONFIG["port"] == 9010
    assert config.settings.BIND_HOST == "0.0.0.0"


def test_dev_runtime_registers_dev_nacos_by_default(monkeypatch):
    config = load_config(monkeypatch, runtime_env="dev")

    assert config.settings.RUNTIME_ENV == "dev"
    assert config.settings.NACOS_CONFIG["enable"] is True
    assert config.settings.NACOS_CONFIG["service-name"] == "yeelight-online-metadata-mcp-server-dev"
    assert config.settings.NACOS_CONFIG["server"] == "192.168.0.41:8848,192.168.0.42:8848,192.168.0.43:8848"
    assert config.settings.BIND_HOST == "0.0.0.0"


def test_local_runtime_keeps_nacos_disabled_by_default(monkeypatch):
    config = load_config(monkeypatch, runtime_env="local")

    assert config.settings.RUNTIME_ENV == "local"
    assert config.settings.NACOS_CONFIG["enable"] is False
    assert config.settings.NACOS_CONFIG["service-name"] == "yeelight-online-metadata-mcp-server-dev"
    assert config.settings.BIND_HOST == "127.0.0.1"


def test_nacos_enable_env_can_override_runtime_default(monkeypatch):
    config = load_config(monkeypatch, runtime_env="prod", nacos_enable="false")

    assert config.settings.NACOS_CONFIG["enable"] is False


def test_bind_host_env_can_override_runtime_default(monkeypatch):
    config = load_config(monkeypatch, runtime_env="prod")

    assert config.settings.BIND_HOST == "0.0.0.0"

    monkeypatch.setenv("METADATA_MCP_BIND_HOST", "127.0.0.1")
    for name in list(sys.modules):
        if name == "config.config" or name.startswith("config."):
            sys.modules.pop(name)
    config = importlib.import_module("config.config")

    assert config.settings.BIND_HOST == "127.0.0.1"
