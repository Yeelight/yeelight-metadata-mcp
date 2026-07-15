from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_DIR / "scripts" / "mcp_acceptance_cli.py"


def load_acceptance_cli():
    spec = spec_from_file_location("mcp_acceptance_cli", SCRIPT_PATH)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_region_header_is_optional_and_uses_server_default(monkeypatch):
    monkeypatch.delenv("METADATA_MCP_REGION", raising=False)
    cli = load_acceptance_cli()

    args = cli.build_parser().parse_args(["houses"])

    assert args.region is None
    assert "Yeelight-Region" not in cli.auth_headers("token", "", args.region)


def test_dev_region_is_available_for_explicit_development_validation(monkeypatch):
    monkeypatch.setenv("METADATA_MCP_REGION", "dev")
    cli = load_acceptance_cli()

    args = cli.build_parser().parse_args(["houses"])

    assert args.region == "dev"
    assert cli.auth_headers("token", "", args.region)["Yeelight-Region"] == "dev"
