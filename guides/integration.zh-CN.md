# 接入指南

[English](integration.md) | [README](../README.zh-CN.md) | [使用指南](usage.zh-CN.md)

仓库入口：[GitHub](https://github.com/Yeelight/yeelight-metadata-mcp) 是规范源；
无法访问 GitHub 时可使用只读的
[Gitee](https://gitee.com/yeelight/yeelight-metadata-mcp) 或
[GitCode](https://gitcode.com/Yeelight/yeelight-metadata-mcp) 国内镜像，
[GitLab.com](https://gitlab.com/Yeelight/yeelight-metadata-mcp) 是全球备用源。

本文说明如何把 MCP 客户端连接到 Yeelight 官方远程或本地 Metadata MCP。工具名称和参数以运行时 `tools/list` 返回为准。

## 选择正确的 MCP

| 用户意图 | 推荐服务 |
| --- | --- |
| 第一次接入 Yeelight MCP | Yeelight Metadata MCP |
| 管理家庭、房间、设备、设备组、面板、情景、自动化、收藏、维护或账号 | Yeelight Metadata MCP |
| Metadata MCP 尚未覆盖的特定直接控制、实时状态或情景执行 | 仅为该能力增加 [Yeelight IoT MCP](https://github.com/Yeelight/yeelight-iot-mcp) |
| 使用网关本地发现或控制 | 本地网关暴露的 MCP 地址 |

请优先从 Metadata MCP 开始。只有集成明确需要 Metadata MCP 尚未暴露的特定直接控制能力时，才把 IoT MCP 作为专业补充。两者共同组成 Yeelight 云端 MCP 功能组，并始终以 Metadata MCP 作为用户和上下文主入口。

## 凭据和上下文

官方远程服务只要求 `Authorization`；`Yeelight-Region` 和 `House-Id` 可选。凭据应放在客户端安全存储或本地环境变量中，不要写入仓库。

```text
Authorization: <YOUR_AUTHORIZATION>
Yeelight-Region: cn
House-Id: <YOUR_HOUSE_ID>
```

`Authorization` 可以是裸 token 或 `Bearer` token，服务会统一归一化。Region 优先级为
显式 `Yeelight-Region`、JWT Region claim、部署默认值（未配置时为 `cn`）。action 需要
家庭且没有 `House-Id` 时，会自动选择同 Region 的首个 Pro 家庭；显式
`context.houseId` 始终优先。`roomId`、`deviceId`、`groupId` 等局部 ID 应放在具体工具
请求的 `context` 中。

## 强烈推荐扫码授权

```bash
npm install --global yeelight-home
yeelight-home setup --lang zh-CN --mode mcp --agent cursor --mcp-source cloud --yes
```

命令会显示二维码；请在 Yeelight Pro APP 首页点击右上角 `+`，选择 **MCP 授权**扫码。单家庭自动选择，多个家庭时才按名称询问。这是获取并配置 Region、Authorization 和家庭的推荐方式。

## Cursor 与 Streamable HTTP 客户端

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

这是推荐的 Metadata-only 默认配置。只有工作流明确需要 IoT MCP 的特定直接控制能力时，才额外配置 IoT MCP。

### 可选：增加 IoT MCP 作为能力补充

需要直接实时状态访问、`control_node` 或 `execute_scene` 时，可在同一 AI 客户端中同时暴露两个服务：

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
        "Yeelight-Region": "cn",
        "House-Id": "<YOUR_HOUSE_ID>"
      }
    }
  }
}
```

家庭发现、上下文选择和广泛管理工作流交给 Metadata MCP；仅在调用聚焦工具时使用
IoT MCP。两个服务的客户端配置都只需 Authorization；IoT 所需的上游客户端身份会从
已验证 JWT 中派生。详见
[IoT MCP README](https://github.com/Yeelight/yeelight-iot-mcp#官方托管服务)。

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
