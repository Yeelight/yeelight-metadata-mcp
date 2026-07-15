# 接入指南

[English](integration.md) | [README](../README.zh-CN.md) | [使用指南](usage.zh-CN.md)

本文说明如何把 MCP 客户端连接到 Yeelight 官方远程或本地 Metadata MCP。工具名称和参数以运行时 `tools/list` 返回为准。

## 选择正确的 MCP

| 用户意图 | 推荐服务 |
| --- | --- |
| 控制设备、读取实时状态、执行情景 | [Yeelight IoT MCP](https://github.com/Yeelight/yeelight-iot-mcp) |
| 管理家庭、房间、设备、设备组、面板、情景或自动化 | Yeelight Metadata MCP |
| 使用网关本地发现或控制 | 本地网关暴露的 MCP 地址 |

IoT MCP 和 Metadata MCP 可以同时配置。两者使用相同的云端 Header，但能力边界不同。

## 凭据和上下文

官方远程服务只要求 `Authorization`；`Yeelight-Region` 和 `House-Id` 可选。凭据应放在客户端安全存储或本地环境变量中，不要写入仓库。

```text
Authorization: <YOUR_AUTHORIZATION>
Yeelight-Region: cn
House-Id: <YOUR_HOUSE_ID>
```

`Authorization` 可以是裸 token 或 `Bearer` token，服务会统一归一化。Region 缺省使用部署默认值（未配置时为 `cn`）。action 需要家庭且没有 `House-Id` 时，会自动选择同 Region 的首个 Pro 家庭；显式 `context.houseId` 始终优先。`roomId`、`deviceId`、`groupId` 等局部 ID 应放在具体工具请求的 `context` 中。

## 推荐扫码授权

```bash
npm install --global yeelight-ai
yeelight-ai login --method qr --region cn
yeelight-ai client configure cursor --write --yes
```

在 Yeelight Pro APP 首页点击右上角 `+`，选择 **MCP 授权**，扫描终端二维码。这是获取并配置 Region、Authorization 和家庭的推荐方式；Metadata MCP 本身不依赖 CLI。

## Cursor 与 Streamable HTTP 客户端

```json
{
  "mcpServers": {
    "yeelight-iot": {
      "url": "https://api.yeelight.com/apis/mcp_server/v1/mcp",
      "headers": {
        "Authorization": "<YOUR_AUTHORIZATION>",
        "Yeelight-Region": "cn",
        "House-Id": "<YOUR_HOUSE_ID>"
      }
    },
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

只保留当前工作流真正需要的服务即可。

## Claude Desktop 与 `mcp-remote`

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

## 本地源码服务

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e '.[test]'

METADATA_MCP_RUNTIME_ENV=local \
METADATA_MCP_BIND_HOST=127.0.0.1 \
PYTHONPATH=src \
.venv/bin/uvicorn main:streamable_http_app --host 127.0.0.1 --port 9010
```

客户端 URL 改为 `http://127.0.0.1:9010/mcp`。本地模式仍要求认证。需要覆盖资源目录时设置 `METADATA_MCP_RESOURCE_DIR`；旧 `APP_MCP_RESOURCE_DIR` 继续兼容。

## 推荐接入流程

1. 连接服务并完成 MCP initialize。
2. 调用 `tools/list` 获取当前工具 schema。
3. 使用 `list_groups`、`list_tasks` 或 `list_actions` 定位工作流。
4. 用户需要查看或切换家庭时调用 `list_houses`，后续请求在 `request.context.houseId` 中传入目标 ID。
5. 使用 `get_action_schema` 获取精确的 context、payload 和 options 要求。
6. 调用 `execute_task`，先传 `options.dryRun=true`。
7. 检查 HTTP 计划和副作用等级。
8. S2/S3 action 经确认后再真实执行，并在写入后回查验证。

## 常见问题

- `401`：补充有效的 `Authorization` Header。
- Region `400`：只使用 `cn`、`sg`、`us` 或 `eu`，并确保 endpoint host 与 Region 一致。
- 没有 Pro 家庭：配置 `House-Id`、传 `context.houseId`，或先在 Yeelight Pro APP 中创建/加入家庭；服务不会回退到 SaaS 项目。
- 连接超时：检查 URL、代理、监听地址和端口。
- `Invalid Host header`：检查 MCP 传输层允许的 Host，或修正网关/容器路由。
- 参数校验失败：刷新 `tools/list`，再读取精确 action schema。
- candidate 被拒绝：保持 dry run，除非接口已经审查且运行策略显式允许。

破坏性操作失败后，不要在未知当前状态时直接重试。
