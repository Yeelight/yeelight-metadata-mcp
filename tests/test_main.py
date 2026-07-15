import importlib
import asyncio
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


def load_main(monkeypatch, bind_host=None):
    legacy_env_names = [
        "APP_MCP_RUNTIME_ENV",
        "APP_MCP_NACOS_ENABLE",
        "APP_MCP_BIND_HOST",
        "APP_MCP_PORT",
        "APP_MCP_PATH",
    ]
    for name in legacy_env_names:
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv("METADATA_MCP_RUNTIME_ENV", "test")
    monkeypatch.delenv("METADATA_MCP_NACOS_ENABLE", raising=False)
    if bind_host is None:
        monkeypatch.delenv("METADATA_MCP_BIND_HOST", raising=False)
    else:
        monkeypatch.setenv("METADATA_MCP_BIND_HOST", bind_host)

    for name in list(sys.modules):
        if name == "main" or name == "config.config" or name.startswith("config."):
            sys.modules.pop(name)
    return importlib.import_module("main")


def test_fastmcp_uses_local_bind_host_by_default(monkeypatch):
    main = load_main(monkeypatch)

    assert main.mcp.settings.host == "127.0.0.1"
    assert main.mcp.settings.port == 9010
    assert main.mcp.settings.transport_security.enable_dns_rebinding_protection is True
    assert "127.0.0.1:*" in main.mcp.settings.transport_security.allowed_hosts


def test_fastmcp_bind_host_can_be_overridden(monkeypatch):
    main = load_main(monkeypatch, bind_host="127.0.0.1")

    assert main.mcp.settings.host == "127.0.0.1"


def test_fastmcp_registers_request_scoped_house_tool(monkeypatch):
    main = load_main(monkeypatch)

    tools = asyncio.run(main.mcp.list_tools())
    names = [tool.name for tool in tools]

    assert "yeelight_metadata.list_houses" in names
    assert "yeelight_metadata.execute_task" in names
