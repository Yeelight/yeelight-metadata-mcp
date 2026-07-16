# Integration Guide

[简体中文](integration.zh-CN.md) | [README](../README.md) | [Usage](usage.md)

Repository access: [GitHub](https://github.com/Yeelight/yeelight-metadata-mcp)
is canonical; use the read-only
[Gitee](https://gitee.com/yeelight/yeelight-metadata-mcp) or
[GitCode](https://gitcode.com/Yeelight/yeelight-metadata-mcp) mirror when GitHub
is not reachable, with
[GitLab.com](https://gitlab.com/Yeelight/yeelight-metadata-mcp) as a global
fallback.

This guide connects an MCP client to the hosted or local Yeelight Metadata MCP
server. Tool names and schemas returned by `tools/list` are authoritative.

## Choose the Right Server

| Intent | Server |
| --- | --- |
| First Yeelight MCP integration | Yeelight Metadata MCP |
| Manage homes, rooms, devices, groups, panels, scenes, automations, favorites, maintenance, or accounts | Yeelight Metadata MCP |
| Focused direct control, live state, or scene execution not yet covered by Metadata MCP | Add [Yeelight IoT MCP](https://github.com/Yeelight/yeelight-iot-mcp) only for that capability |
| Use gateway-local discovery or control | The MCP endpoint exposed by the local gateway |

Start with Metadata MCP. IoT MCP can be configured as a focused companion when
an integration specifically requires a direct-control capability that Metadata
MCP does not yet expose. Together they form the Yeelight cloud MCP suite, with
Metadata MCP remaining the primary user and context entry.

## Credentials and Context

The hosted service requires only `Authorization`. `Yeelight-Region` and
`House-Id` are optional. Keep credentials in the client's secret storage or
local environment, never in a repository.

```text
Authorization: <YOUR_AUTHORIZATION>
Yeelight-Region: cn
House-Id: <YOUR_HOUSE_ID>
```

The server accepts a raw token or a `Bearer` token and normalizes it internally.
Region defaults to the deployment default (`cn` unless configured otherwise).
When a selected action needs a home and `House-Id` is absent, the server chooses
the first Pro home in the same Region. An explicit `context.houseId` always wins.
Local IDs such as `roomId`, `deviceId`, and `groupId` belong in the tool request
`context`.

## Recommended QR Authorization

```bash
npm install --global yeelight-ai
yeelight-ai login --method qr --region cn
yeelight-ai client configure cursor --write --yes
```

In Yeelight Pro APP, tap Home's top-right `+`, choose **MCP Authorization**, and
scan the terminal QR code. This is the recommended way to obtain and configure
Region, Authorization, and a home. The server does not depend on the CLI.

## Cursor and Streamable HTTP Clients

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

This Metadata-only configuration is the recommended default. Add IoT MCP only
when the workflow requires one of its focused direct-control capabilities.

### Optional: add IoT MCP as a companion

When direct live-state access, `control_node`, or `execute_scene` is required,
expose both servers to the same AI client:

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
    },
    "yeelight-iot": {
      "url": "https://api.yeelight.com/apis/mcp_server/v1/mcp",
      "headers": {
        "Authorization": "<YOUR_AUTHORIZATION>",
        "Client-Id": "<YOUR_CLIENT_ID>",
        "House-Id": "<YOUR_HOUSE_ID>"
      }
    }
  }
}
```

Route discovery, context selection, and broad management through Metadata MCP;
use IoT MCP only for its focused tools. IoT MCP currently has its own header
contract, documented in the
[IoT MCP README](https://github.com/Yeelight/yeelight-iot-mcp#hosted-service).

## Claude Desktop with `mcp-remote`

```json
{
  "mcpServers": {
    "yeelight-metadata": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://api.yeelight.com/apis/metadata_mcp_server/v1/mcp",
        "--header", "Authorization:${AUTHORIZATION}",
        "--header", "Yeelight-Region:${YEELIGHT_REGION}",
        "--header", "House-Id:${HOUSE_ID}",
        "--allow-http", "true"
      ],
      "env": {
        "AUTHORIZATION": "<YOUR_AUTHORIZATION>",
        "YEELIGHT_REGION": "cn",
        "HOUSE_ID": "<YOUR_HOUSE_ID>"
      }
    }
  }
}
```

## Local Source Server

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e '.[test]'

METADATA_MCP_RUNTIME_ENV=local \
METADATA_MCP_BIND_HOST=127.0.0.1 \
PYTHONPATH=src \
.venv/bin/uvicorn main:streamable_http_app --host 127.0.0.1 --port 9010
```

Then configure the client URL as `http://127.0.0.1:9010/mcp`. Authentication is
still required locally. To use another catalog directory, set
`METADATA_MCP_RESOURCE_DIR`; legacy `APP_MCP_RESOURCE_DIR` remains supported.

## Integration Workflow

1. Connect and initialize the MCP session.
2. Call `tools/list` and read the current schemas.
3. Use `list_groups`, `list_tasks`, or `list_actions` to find a workflow.
4. Call `list_houses` when the user wants to inspect or switch homes, then put
   the selected ID in later `request.context.houseId` values.
5. Call `get_action_schema` for exact context, payload, and option requirements.
6. Call `execute_task` with `options.dryRun=true`.
7. Review the HTTP plan and side-effect level.
8. Confirm S2/S3 actions before live execution and verify writes afterwards.

## Troubleshooting

- `401`: add a valid `Authorization` header.
- `400` with a Region error: use `cn`, `sg`, `us`, or `eu`, and ensure the
  endpoint host belongs to the same Region.
- No Pro home: configure `House-Id`, use `context.houseId`, or create/join a Pro
  home in Yeelight Pro APP. The server does not fall back to SaaS projects.
- Connection timeout: verify URL, proxy, bind address, and port.
- `Invalid Host header`: check the host accepted by the MCP transport or use the
  correct gateway/container routing.
- Validation error: refresh `tools/list`, then fetch the exact action schema.
- Candidate rejection: keep the action in dry-run mode unless it has been
  reviewed and the runtime policy explicitly permits it.

Do not retry a failed destructive action until its current state is known.
