# Integration Guide

[简体中文](integration.zh-CN.md) | [README](../README.md) | [Usage](usage.md)

This guide connects an MCP client to the hosted or local Yeelight Metadata MCP
server. Tool names and schemas returned by `tools/list` are authoritative.

## Choose the Right Server

| Intent | Server |
| --- | --- |
| Control devices, read live state, run scenes | [Yeelight IoT MCP](https://github.com/Yeelight/yeelight-iot-mcp) |
| Manage homes, rooms, devices, groups, panels, scenes, or automations | Yeelight Metadata MCP |
| Use gateway-local discovery or control | The MCP endpoint exposed by the local gateway |

IoT MCP and Metadata MCP can be configured together. They use the same cloud
headers but expose different capabilities.

## Credentials and Context

The hosted service requires `Authorization`. `Client-Id` and `House-Id` are
recommended. Keep all three values in the client's secret storage or local
environment, never in a repository.

```text
Authorization: <YOUR_AUTHORIZATION>
Client-Id: <YOUR_CLIENT_ID>
House-Id: <YOUR_HOUSE_ID>
```

The server accepts a raw token or a `Bearer` token and normalizes it internally.
Local IDs such as `roomId`, `deviceId`, and `groupId` belong in the tool request
`context`.

## Cursor and Streamable HTTP Clients

```json
{
  "mcpServers": {
    "yeelight-iot": {
      "url": "https://api.yeelight.com/apis/mcp_server/v1/mcp",
      "headers": {
        "Authorization": "<YOUR_AUTHORIZATION>",
        "Client-Id": "<YOUR_CLIENT_ID>",
        "House-Id": "<YOUR_HOUSE_ID>"
      }
    },
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

Keep only the servers needed by your workflow.

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
        "--header", "Client-Id:${CLIENT_ID}",
        "--header", "House-Id:${HOUSE_ID}",
        "--allow-http", "true"
      ],
      "env": {
        "AUTHORIZATION": "<YOUR_AUTHORIZATION>",
        "CLIENT_ID": "<YOUR_CLIENT_ID>",
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
4. Call `get_action_schema` for exact context, payload, and option requirements.
5. Call `execute_task` with `options.dryRun=true`.
6. Review the HTTP plan and side-effect level.
7. Confirm S2/S3 actions before live execution.
8. Query the affected object after a write when verification is possible.

## Troubleshooting

- `401`: add a valid `Authorization` header.
- Connection timeout: verify URL, proxy, bind address, and port.
- `Invalid Host header`: check the host accepted by the MCP transport or use the
  correct gateway/container routing.
- Validation error: refresh `tools/list`, then fetch the exact action schema.
- Candidate rejection: keep the action in dry-run mode unless it has been
  reviewed and the runtime policy explicitly permits it.

Do not retry a failed destructive action until its current state is known.
