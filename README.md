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

The recommended primary cloud MCP for new Yeelight integrations. It gives AI
clients a guarded task interface for homes, rooms, devices, device groups,
panels, scenes, automations, favorites, maintenance, and account operations.

Start with this server. Add [Yeelight IoT MCP](https://github.com/Yeelight/yeelight-iot-mcp)
only when an integration specifically needs focused direct device control,
current live state, or scene execution that Metadata MCP does not yet cover.

## Yeelight Cloud MCP Suite

[Yeelight Metadata MCP](https://github.com/Yeelight/yeelight-metadata-mcp) and
[Yeelight IoT MCP](https://github.com/Yeelight/yeelight-iot-mcp) form the
official Yeelight cloud MCP suite. They are complementary servers with a clear
primary-and-companion relationship:

| Server | Role in the suite | Core capabilities |
| --- | --- | --- |
| **[Metadata MCP](https://github.com/Yeelight/yeelight-metadata-mcp) (primary)** | Default entry point and coordination layer for new integrations. | Broad discovery and guarded workflows for homes, rooms, devices, groups, panels, scenes, automations, favorites, maintenance, accounts, multi-region authorization, and request-scoped home selection. |
| [IoT MCP](https://github.com/Yeelight/yeelight-iot-mcp) (companion) | Add only when a workflow needs its focused IoT operations. | Direct topology and live-state access, device control through `control_node`, and scene execution through `execute_scene`. |

**Recommended composition:** configure Metadata MCP first. Add IoT MCP to the
same AI client only when its focused direct-control tools are required. This
keeps Metadata MCP as the primary user and context entry while exposing the two
servers as one complementary capability group.

## Yeelight AI Capability Matrix

These projects form a complementary stack. Choose the entry point that matches
how you integrate with Yeelight; they can also be combined.

| Project | Role and capabilities | Best for | GitHub |
| --- | --- | --- | --- |
| Yeelight Home | Recommended local semantic Runtime with one structured `invoke --stdin` boundary for queries, control, scenes, automations, lighting design, diagnostics, product knowledge, and generated apps. | Agent hosts, local automation, and applications that need a stable and policy-aware smart-home execution layer. | [Yeelight/yeelight-home](https://github.com/Yeelight/yeelight-home) |
| Yeelight Smart Home Skills | Official Agent Skills: Smart Home turns natural language into safe Runtime operations; PRO App Builder generates focused local apps from proven Runtime capabilities. | Agent hosts that need conversational smart-home workflows or app generation. | [Yeelight/yeelight-smart-home-skills](https://github.com/Yeelight/yeelight-smart-home-skills) |
| Yeelight AI CLI | Unified terminal workspace and MCP client for Cloud, Metadata, and LAN services, with local profiles, safe shortcuts, diagnostics, scripting, and AI client configuration. | People, scripts, and CI that want one general MCP and automation entry point. | [Yeelight/yeelight-cli](https://github.com/Yeelight/yeelight-cli) |
| Yeelight Metadata MCP | Recommended cloud MCP entry for new integrations, with guarded workflows for homes, rooms, devices, groups, panels, scenes, automations, favorites, maintenance, accounts, multi-region authorization, and request-scoped home selection. | New MCP integrations and AI clients that need broad discovery, inspection, and management workflows. | [Yeelight/yeelight-metadata-mcp](https://github.com/Yeelight/yeelight-metadata-mcp) |
| Yeelight IoT MCP | Focused companion MCP for direct topology and live-state access, device control, and scene execution not yet fully covered by Metadata MCP. | Existing integrations or clients that specifically need `control_node`, `execute_scene`, or focused live control. | [Yeelight/yeelight-iot-mcp](https://github.com/Yeelight/yeelight-iot-mcp) |

Yeelight Home also provides system credential storage, local QR login, secret-redacted diagnostics, preview and validation, caller confirmation and Runtime policy/readback behavior, local memory and recommendation support, operation lessons, and machine-readable intent schema/explanations. Cross-platform binaries are distributed through GitHub Releases, npm, and supported package managers.

Typical paths: smart-home agents and generated apps -> Skills -> Yeelight Home; terminal users and scripts -> Yeelight AI CLI; new MCP integrations -> Metadata MCP; add IoT MCP only for focused direct control or scene execution that Metadata MCP does not yet cover.

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

`Authorization` is the only required user credential. Yeelight services derive
the client identity from its verified authorization context. For actions that
need a home, precedence is `context.houseId` -> `House-Id` -> first Pro home in
the same Region. The fallback is request-scoped, not a global current-home state.

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

### Recommended: authorize with Yeelight AI CLI

```bash
npm install --global yeelight-ai
yeelight-ai login --method qr --region cn
yeelight-ai client configure cursor --write --yes
```

In Yeelight Pro APP, tap the `+` button in the top-right corner of Home, choose
**MCP Authorization**, and scan the terminal QR code. The CLI saves the Region,
Authorization, and selected home, then generates client configuration. The MCP
server remains independently usable without the CLI.

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

Both optional headers may be omitted. Match the endpoint host to the Region
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
