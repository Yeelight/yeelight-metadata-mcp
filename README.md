# Yeelight Metadata MCP Server

[简体中文](README.zh-CN.md)

An MCP server for Yeelight home metadata and management workflows. It gives AI
clients a guarded task interface for homes, rooms, devices, device groups,
panels, scenes, automations, favorites, maintenance, and account operations.

Use [Yeelight IoT MCP](https://github.com/Yeelight/yeelight-iot-mcp) for device
control and live state. Use this server when the intent is to create, update,
organize, configure, bind, unbind, or inspect application metadata.

## Yeelight AI Capability Matrix

These projects form a complementary stack. Choose the entry point that matches
how you integrate with Yeelight; they can also be combined.

| Project | Role and capabilities | Best for | GitHub |
| --- | --- | --- | --- |
| Yeelight AI CLI | Unified terminal workspace and MCP client for Cloud, Metadata, and LAN services, with local profiles, safe shortcuts, diagnostics, and client configuration. | People, scripts, and CI that want one command-line entry point. | [Yeelight/yeelight-cli](https://github.com/Yeelight/yeelight-cli) |
| `yeelight-home` | Local semantic Runtime CLI for home queries, control, configuration, diagnostics, product knowledge, and the structured `invoke --stdin` contract. | Skills, generated apps, and local automation that need a stable execution layer. | [Yeelight/yeelight-home](https://github.com/Yeelight/yeelight-home) |
| Yeelight IoT MCP | Hosted or self-hosted Streamable HTTP MCP server for topology, live state, device control, and scene execution. | MCP clients that need direct IoT discovery and control. | [Yeelight/yeelight-iot-mcp](https://github.com/Yeelight/yeelight-iot-mcp) |
| Yeelight Metadata MCP | Hosted or self-hosted Streamable HTTP MCP server for guarded home, room, group, panel, scene, automation, favorite, and account metadata workflows. | MCP clients that need metadata inspection and management. | [Yeelight/yeelight-metadata-mcp](https://github.com/Yeelight/yeelight-metadata-mcp) |
| Yeelight Smart Home Skills | Official Agent Skills: Smart Home translates natural language into safe `yeelight-home` operations, while PRO App Builder generates local smart-home apps from proven Runtime capabilities. | Agent hosts that need conversational smart-home workflows or app generation. | [Yeelight/yeelight-smart-home-skills](https://github.com/Yeelight/yeelight-smart-home-skills) |

Typical paths: terminal users and scripts -> `yeelight-ai`; MCP clients -> IoT MCP
and/or Metadata MCP; agent hosts -> Yeelight Smart Home Skill -> `yeelight-home`.
PRO App Builder also uses proven `yeelight-home` capabilities when generating
local applications.

## Highlights

- Five namespaced tools instead of a large set of low-level HTTP operations.
- 7 task groups, 23 tasks, and a runtime action catalog.
- Safe-by-default execution: `dryRun` defaults to `true`.
- Explicit confirmation for S2/S3 side effects.
- Candidate actions are blocked from live execution by default.
- MCP resources and prompts for task discovery and change planning.
- Compatible `METADATA_MCP_*` and legacy `APP_MCP_*` environment variables.

## Hosted Service

The official Streamable HTTP endpoint is:

```text
https://api.yeelight.com/apis/metadata_mcp_server/v1/mcp
```

Required request header:

- `Authorization`

Recommended optional headers:

- `Client-Id`
- `House-Id`

`House-Id` is used as the default global home context. An explicit
`context.houseId` in a tool request takes precedence.

## MCP Capabilities

Tools:

- `yeelight_metadata.list_groups`
- `yeelight_metadata.list_tasks`
- `yeelight_metadata.list_actions`
- `yeelight_metadata.get_action_schema`
- `yeelight_metadata.execute_task`

Resources:

- `yeelight-metadata://tasks`
- `yeelight-metadata://actions`
- `yeelight-metadata://schema/{task}/{action}`

Prompts:

- `yeelight_metadata.inspect_home_metadata`
- `yeelight_metadata.plan_metadata_change`
- `yeelight_metadata.troubleshoot_automation_metadata`

Treat the live MCP `tools/list` response as the source of truth for tool schemas.

## Quick Start

### Connect to the hosted server

```json
{
  "mcpServers": {
    "yeelight-metadata": {
      "url": "https://api.yeelight.com/apis/metadata_mcp_server/v1/mcp",
      "headers": {
        "Authorization": "<YOUR_AUTHORIZATION>",
        "Client-Id": "<YOUR_CLIENT_ID>",
        "House-Id": "<YOUR_HOUSE_ID>"
      }
    }
  }
}
```

See the [integration guide](guides/integration.md) for Cursor, Claude Desktop,
local source, and combined IoT/Metadata configurations.

### Run from source

Requirements: Python 3.10 or newer. Python 3.12 is recommended for local
development.

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e '.[test]'

METADATA_MCP_RUNTIME_ENV=local ./service.sh start
./service.sh status
```

The local endpoint is `http://127.0.0.1:9010/mcp`. A request without an
`Authorization` header returns `401` by design.

Direct startup is also supported:

```bash
METADATA_MCP_RUNTIME_ENV=local \
METADATA_MCP_BIND_HOST=127.0.0.1 \
PYTHONPATH=src \
.venv/bin/uvicorn main:streamable_http_app --host 127.0.0.1 --port 9010
```

## Safety Model

Every action has an execution mode, side-effect level, status, and parameter
schema.

| Level | Meaning | Examples |
| --- | --- | --- |
| S0 | Read-only | list, get, search |
| S1 | Diagnostic or external activity | diagnose, download, poll |
| S2 | Create or update | create, update, configure |
| S3 | Destructive or identity-sensitive | delete, unbind, transfer, login |

`execute_task` defaults to a plan-only request:

```json
{
  "task": "family_space.manage_room",
  "action": "create",
  "payload": {"name": "Sample Room"},
  "options": {"dryRun": true}
}
```

Live S2/S3 execution requires `confirmSideEffect=true`. Candidate actions also
require `allowCandidate=true` and are restricted by runtime policy. Start with a
dry run, review `plan.httpRequest`, then execute only with testable or recoverable
data.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `METADATA_MCP_RUNTIME_ENV` | `prod` | `prod`, `dev`, `local`, or `test` |
| `METADATA_MCP_BIND_HOST` | local/test: `127.0.0.1`; prod/dev: `0.0.0.0` | Listen address |
| `METADATA_MCP_PORT` | `9010` | Listen port |
| `METADATA_MCP_PATH` | `/mcp` | MCP route |
| `METADATA_MCP_HOST_PREFIX` | `https://api.yeelight.com` | Yeelight API host |
| `METADATA_MCP_API_BASE_URL` | host prefix | Explicit API base URL |
| `METADATA_MCP_HTTP_TIMEOUT` | `15` | Upstream timeout in seconds |
| `METADATA_MCP_RESOURCE_DIR` | `resources/catalog` | Runtime catalog override |
| `METADATA_MCP_NACOS_ENABLE` | environment-dependent | Nacos registration switch |
| `METADATA_MCP_NACOS_SERVER` | environment-dependent | Nacos servers |
| `METADATA_MCP_ALLOW_CANDIDATE_EXECUTION` | `false` | Candidate execution gate |

Legacy `APP_MCP_*` names remain supported for deployment compatibility.

## Documentation

- [Integration guide](guides/integration.md)
- [Usage guide](guides/usage.md)
- [中文接入指南](guides/integration.zh-CN.md)
- [中文使用指南](guides/usage.zh-CN.md)

## Development

```bash
PYTHONPATH=src python -m pytest -q
python -m compileall -q main.py src tests scripts
```

The repository also includes protocol and acceptance utilities under `scripts/`.
Live acceptance commands can change cloud data; use explicit credentials, a
non-production home, and recoverable fixtures.

## License

Licensed under the [Apache License 2.0](LICENSE).
