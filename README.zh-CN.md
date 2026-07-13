# Yeelight Metadata MCP Server

[English](README.md)

面向 Yeelight 家庭元数据和管理流程的 MCP 服务。它为 AI 客户端提供受安全策略保护的统一任务入口，覆盖家庭、房间、设备、设备组、面板、情景、自动化、收藏、维护和账号相关操作。

设备控制和实时状态请使用 [Yeelight IoT MCP](https://github.com/Yeelight/yeelight-iot-mcp)；创建、更新、组织、配置、绑定、解绑或检查 APP 元数据时使用本项目。

## Yeelight AI 能力矩阵

这些项目组成互补的 Yeelight AI 技术栈。可以根据接入方式选择入口，也可以组合使用。

| 项目 | 定位与核心能力 | 适用场景 | GitHub |
| --- | --- | --- | --- |
| Yeelight Home | 首选本地语义 Runtime，通过统一结构化 `invoke --stdin` 边界提供查询、控制、场景、自动化、灯光设计、诊断、产品知识和生成应用能力。 | 需要稳定、受策略保护的智能家居执行层的 Agent host、本地自动化和应用。 | [Yeelight/yeelight-home](https://github.com/Yeelight/yeelight-home) |
| Yeelight Smart Home Skills | 官方 Agent Skills：Smart Home 把自然语言转换为安全的 Runtime 操作；PRO App Builder 基于已验证能力生成专用本地应用。 | 需要智能家居对话工作流或应用生成能力的 Agent host。 | [Yeelight/yeelight-smart-home-skills](https://github.com/Yeelight/yeelight-smart-home-skills) |
| Yeelight AI CLI | 统一终端工作台和 MCP 客户端，连接 Cloud、Metadata 和 LAN 服务，提供本地 profile、安全快捷命令、诊断、脚本和 AI 客户端配置。 | 希望通过通用 MCP 与自动化命令行入口操作的用户、脚本和 CI。 | [Yeelight/yeelight-cli](https://github.com/Yeelight/yeelight-cli) |
| Yeelight IoT MCP | 官方托管或可自行部署的 Streamable HTTP MCP 服务，提供拓扑、实时状态、设备控制和场景执行。 | 需要直接发现和控制 IoT 设备的 MCP 客户端。 | [Yeelight/yeelight-iot-mcp](https://github.com/Yeelight/yeelight-iot-mcp) |
| Yeelight Metadata MCP | 官方托管或可自行部署的 Streamable HTTP MCP 服务，提供受保护的家庭、房间、组、面板、场景、自动化、收藏和账号元数据工作流。 | 需要检查和管理元数据的 MCP 客户端。 | [Yeelight/yeelight-metadata-mcp](https://github.com/Yeelight/yeelight-metadata-mcp) |

Yeelight Home 还提供系统凭据存储、本地 QR 登录、秘密脱敏诊断、预览与校验、调用方确认和 Runtime 策略/写后读取、本地记忆与推荐、实操经验，以及机器可读的 intent schema 和解释。跨平台二进制通过 GitHub Release、npm 和已支持的包管理器分发。

典型组合：智能家居 Agent 和生成应用 -> Skills -> Yeelight Home；终端用户和脚本 -> Yeelight AI CLI；MCP 客户端 -> IoT MCP 和/或 Metadata MCP。

## 核心特性

- 通过 5 个命名空间工具统一承载管理流程，避免暴露大量底层 HTTP 操作。
- 运行时目录覆盖 7 个任务分组、23 个任务及对应 action。
- `dryRun` 默认为 `true`，优先返回执行计划。
- S2/S3 副作用操作必须显式确认。
- candidate action 默认禁止真实执行。
- 提供任务发现、变更规划和自动化排查所需的 MCP resources/prompts。
- 同时兼容 `METADATA_MCP_*` 与旧 `APP_MCP_*` 环境变量。

## 官方远程服务

Streamable HTTP 地址：

```text
https://api.yeelight.com/apis/metadata_mcp_server/v1/mcp
```

必需 Header：

- `Authorization`

建议同时提供：

- `Client-Id`
- `House-Id`

`House-Id` 会作为默认的全局家庭上下文；如果单次工具请求显式传入 `context.houseId`，则以显式值为准。

## MCP 能力

Tools：

- `yeelight_metadata.list_groups`
- `yeelight_metadata.list_tasks`
- `yeelight_metadata.list_actions`
- `yeelight_metadata.get_action_schema`
- `yeelight_metadata.execute_task`

Resources：

- `yeelight-metadata://tasks`
- `yeelight-metadata://actions`
- `yeelight-metadata://schema/{task}/{action}`

Prompts：

- `yeelight_metadata.inspect_home_metadata`
- `yeelight_metadata.plan_metadata_change`
- `yeelight_metadata.troubleshoot_automation_metadata`

工具名称、参数和约束以实时 `tools/list` 返回为准。

## 快速开始

### 连接官方远程服务

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

Cursor、Claude Desktop、本地源码以及 IoT/Metadata 同时接入的完整配置见[接入指南](guides/integration.zh-CN.md)。

### 本地源码运行

需要 Python 3.10 及以上版本，本地开发建议使用 Python 3.12。

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e '.[test]'

METADATA_MCP_RUNTIME_ENV=local ./service.sh start
./service.sh status
```

本地地址为 `http://127.0.0.1:9010/mcp`。未携带 `Authorization` 访问时返回 `401`，这是认证中间件的预期行为。

也可以直接启动：

```bash
METADATA_MCP_RUNTIME_ENV=local \
METADATA_MCP_BIND_HOST=127.0.0.1 \
PYTHONPATH=src \
.venv/bin/uvicorn main:streamable_http_app --host 127.0.0.1 --port 9010
```

## 安全模型

每个 action 都有独立的执行模式、副作用等级、状态和参数 schema。

| 等级 | 含义 | 示例 |
| --- | --- | --- |
| S0 | 只读 | list、get、search |
| S1 | 诊断或外部活动 | diagnose、download、poll |
| S2 | 创建或更新 | create、update、configure |
| S3 | 删除或身份敏感操作 | delete、unbind、transfer、login |

`execute_task` 默认只生成计划：

```json
{
  "task": "family_space.manage_room",
  "action": "create",
  "payload": {"name": "示例房间"},
  "options": {"dryRun": true}
}
```

S2/S3 真实执行必须传 `confirmSideEffect=true`。candidate action 还需要 `allowCandidate=true`，并受运行环境策略限制。建议先 dry run，检查 `plan.httpRequest`，再使用测试数据或可回收数据执行。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `METADATA_MCP_RUNTIME_ENV` | `prod` | `prod`、`dev`、`local` 或 `test` |
| `METADATA_MCP_BIND_HOST` | local/test: `127.0.0.1`；prod/dev: `0.0.0.0` | 监听地址 |
| `METADATA_MCP_PORT` | `9010` | 监听端口 |
| `METADATA_MCP_PATH` | `/mcp` | MCP 路径 |
| `METADATA_MCP_HOST_PREFIX` | `https://api.yeelight.com` | Yeelight API host |
| `METADATA_MCP_API_BASE_URL` | 取 host prefix | 显式 API 根地址 |
| `METADATA_MCP_HTTP_TIMEOUT` | `15` | 上游请求超时秒数 |
| `METADATA_MCP_RESOURCE_DIR` | `resources/catalog` | 运行时目录覆盖路径 |
| `METADATA_MCP_NACOS_ENABLE` | 按环境决定 | Nacos 注册开关 |
| `METADATA_MCP_NACOS_SERVER` | 按环境决定 | Nacos 地址 |
| `METADATA_MCP_ALLOW_CANDIDATE_EXECUTION` | `false` | candidate 执行开关 |

旧 `APP_MCP_*` 变量继续保留，用于兼容现有部署。

## 文档

- [中文接入指南](guides/integration.zh-CN.md)
- [中文使用指南](guides/usage.zh-CN.md)
- [Integration guide](guides/integration.md)
- [Usage guide](guides/usage.md)

## 开发验证

```bash
PYTHONPATH=src python -m pytest -q
python -m compileall -q main.py src tests scripts
```

`scripts/` 还提供 MCP 协议和 action 验收工具。真实验收可能修改云端数据，必须使用显式凭据、非生产家庭和可回收测试数据。

## 许可证

本项目采用 [Apache License 2.0](LICENSE)。
