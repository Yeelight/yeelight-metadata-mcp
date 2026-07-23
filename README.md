# Yeelight Metadata MCP Server

[简体中文](README.zh-CN.md)

## Official Repository And Mirrors

[GitHub](https://github.com/Yeelight/yeelight-metadata-mcp) is the canonical
source for issues, contributions, CI, and releases. Read-only mirrors are
available on [Gitee](https://gitee.com/yeelight/yeelight-metadata-mcp) and
[GitCode](https://gitcode.com/Yeelight/yeelight-metadata-mcp) for users who
cannot reach GitHub reliably, with
[GitLab.com](https://gitlab.com/Yeelight/yeelight-metadata-mcp) as an additional
global fallback. Clone from any reachable source, but report issues and
contribute changes on GitHub.

This repository contains the home-understanding and management service inside
**Yeelight MCP**. Ordinary users connect the complete Yeelight MCP suite once;
they do not choose or install this server separately. Its guarded task interface
covers homes, rooms, devices, groups, panels, scenes, automations, favorites,
maintenance, and account operations.

> [!TIP]
> New to Yeelight MCP? Follow the [official English Yeelight MCP tutorial](https://ai-tutorials.yeelight.com/en/guides/yeelight-mcp/) to prepare Yeelight Home, connect the complete Metadata and IoT capability suite, and verify the first real response. A [Simplified Chinese tutorial](https://ai-tutorials.yeelight.com/zh/guides/yeelight-mcp/) is also available.

## Yeelight Cloud MCP Suite

[Yeelight Metadata MCP](https://github.com/Yeelight/yeelight-metadata-mcp) and
[Yeelight IoT MCP](https://github.com/Yeelight/yeelight-iot-mcp) form the
official Yeelight MCP cloud suite. They are independently deployed services
configured together by the ordinary-user setup:

| Server | Role in the suite | Core capabilities |
| --- | --- | --- |
| **[Metadata MCP](https://github.com/Yeelight/yeelight-metadata-mcp)** | Home understanding and guarded management. | Broad discovery and guarded workflows for homes, rooms, devices, groups, panels, scenes, automations, favorites, maintenance, accounts, multi-region authorization, and request-scoped home selection. |
| [IoT MCP](https://github.com/Yeelight/yeelight-iot-mcp) | Live state and focused control. | Direct topology and live-state access, device control through `control_node`, and scene execution through `execute_scene`. |

**Recommended composition:** run one Yeelight MCP setup. It configures both
services in the same AI client so the model receives home understanding,
management, live state, and control without a second install or scan.

## Place In Yeelight AI

[`yeelight-home`](https://github.com/Yeelight/yeelight-home) provides the recommended installation, QR sign-in, and client-configuration flow. Ordinary users should prefer the complete `yeelight-smart-home` Skill. When a client cannot install Skills, one cloud setup connects the complete Yeelight MCP suite; the cloud services then execute independently of the local Runtime.

In plain language: this server gives an MCP-only AI a structured view of your
home and guarded ways to manage it. It is **not** another CLI and it is **not**
required by `yeelight-home` or the Smart Home Skill.

| Choose this when | Choose something else when |
| --- | --- |
| Your AI client supports MCP but cannot install Agent Skills. | Your client can install Skills: use `yeelight-smart-home` for the complete guided experience. |
| The AI needs rooms, devices, groups, scenes, automations, panels, or home management. | You are scripting or troubleshooting in a terminal: use `yeelight-home` directly. |
| You need to develop or troubleshoot the home-understanding service inside Yeelight MCP. | You only need an existing specialized `control_node` or `execute_scene` integration: use the IoT service documentation. |

## Highlights

- Six namespaced tools instead of a large set of low-level HTTP operations.
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

- `Yeelight-Region`: `cn`, `sg`, `us`, or `eu`; defaults to the deployment Region (`cn` by default)
- `House-Id`

`Authorization` is the only required user credential. When `Yeelight-Region` is
absent, the server can use the JWT Region claim to select an official endpoint,
then validates the complete token there. Yeelight services derive client identity
from that verified authorization context; users never enter a Client ID. For
actions that need a home, precedence is `context.houseId` -> `House-Id` -> first
Pro home in the same Region. The fallback is request-scoped, not a global
current-home state.

## MCP Capabilities

Tools:

- `yeelight_metadata.list_groups`
- `yeelight_metadata.list_houses`
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

### Recommended: let Yeelight Home complete sign-in and configuration

```bash
npm install --global yeelight-home
yeelight-home setup --lang en-US --mode mcp --agent cursor --mcp-source cloud --yes
```

The command displays the QR code. In Yeelight Pro app, tap Home's top-right `+`, choose **MCP Authorization**, and scan it. A single Pro home is selected automatically; only multiple homes require a choice by name. Replace `cursor` with your client or use `--agent auto` for detection. The generated client configuration starts a local credential proxy and contains no Authorization value. Manual token configuration remains an advanced compatibility path; never paste a token into an AI chat.

### Connect to the hosted server

```json
{
  "mcpServers": {
    "yeelight-metadata": {
      "url": "https://api.yeelight.com/apis/metadata_mcp_server/v1/mcp",
      "headers": {
        "Authorization": "<YOUR_AUTHORIZATION>",
        "Yeelight-Region": "cn",
        "House-Id": "<YOUR_HOUSE_ID>"
      }
    }
  }
}
```

Both optional headers may be omitted. A JWT token supplies its Region claim;
opaque tokens use the deployment default. Match an explicitly selected endpoint host to the Region
(`api.yeelight.com`, `api-sg.yeelight.com`, `api-us.yeelight.com`, or
`api-de.yeelight.com`). To switch homes, call `yeelight_metadata.list_houses`,
then pass the chosen ID as `request.context.houseId` on subsequent calls.

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
  "request": {
    "task": "family_space.manage_room",
    "action": "create",
    "payload": {"name": "Sample Room"},
    "options": {"dryRun": true}
  }
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
| `METADATA_MCP_DEFAULT_REGION` | `cn` | Default Region when `Yeelight-Region` is absent |
| `METADATA_MCP_HOST_PREFIX` | `https://api.yeelight.com` | Yeelight API host |
| `METADATA_MCP_API_BASE_URL` | host prefix | Explicit API base URL |
| `METADATA_MCP_HTTP_TIMEOUT` | `15` | Upstream timeout in seconds |
| `METADATA_MCP_RESOURCE_DIR` | `resources/catalog` | Runtime catalog override |
| `METADATA_MCP_NACOS_ENABLE` | environment-dependent | Nacos registration switch |
| `METADATA_MCP_NACOS_SERVER` | environment-dependent | Nacos servers |
| `METADATA_MCP_ALLOW_CANDIDATE_EXECUTION` | `false` | Candidate execution gate |

Legacy `APP_MCP_*` names remain supported for deployment compatibility.
Standard Yeelight cloud origins support per-request Region routing. A custom
API base is fixed to `METADATA_MCP_DEFAULT_REGION`; requests naming another
Region are rejected instead of being silently misrouted.

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
