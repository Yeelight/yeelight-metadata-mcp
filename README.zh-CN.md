# Yeelight Metadata MCP Server

[English](README.md)

## 官方仓库与国内镜像

[GitHub](https://github.com/Yeelight/yeelight-metadata-mcp) 是 Issue、贡献、CI
和发布的规范源。国内无法稳定访问 GitHub 时，可使用只读的
[Gitee 镜像](https://gitee.com/yeelight/yeelight-metadata-mcp) 或
[GitCode 镜像](https://gitcode.com/Yeelight/yeelight-metadata-mcp)；
[GitLab.com](https://gitlab.com/Yeelight/yeelight-metadata-mcp) 是额外的全球
备用源。可以从任一可访问平台克隆代码，但请仍在 GitHub 提交 Issue 和贡献修改。

新 Yeelight 集成推荐的统一云端 MCP 入口。它为 AI 客户端提供受安全策略保护的任务接口，覆盖家庭、房间、设备、设备组、面板、情景、自动化、收藏、维护和账号相关操作。

请优先从本项目开始。只有集成明确需要 Metadata MCP 尚未覆盖的特定直接设备控制、实时状态或情景执行能力时，才增加 [Yeelight IoT MCP](https://github.com/Yeelight/yeelight-iot-mcp) 作为补充。

## Yeelight 云端 MCP 功能组

[Yeelight Metadata MCP](https://github.com/Yeelight/yeelight-metadata-mcp) 与
[Yeelight IoT MCP](https://github.com/Yeelight/yeelight-iot-mcp) 共同组成
Yeelight 官方云端 MCP 功能组。两者相互补充，但具有明确的主次关系：

| 服务 | 在功能组中的定位 | 核心能力 |
| --- | --- | --- |
| **[Metadata MCP](https://github.com/Yeelight/yeelight-metadata-mcp)（主入口）** | 新集成的默认入口和协调层。 | 广泛发现以及受保护的家庭、房间、设备、设备组、面板、情景、自动化、收藏、维护、账号工作流，并支持多 Region 授权和请求级家庭选择。 |
| [IoT MCP](https://github.com/Yeelight/yeelight-iot-mcp)（能力补充） | 仅在工作流需要其聚焦的 IoT 操作时增加。 | 直接拓扑和实时状态访问、通过 `control_node` 控制设备，以及通过 `execute_scene` 执行情景。 |

**推荐组合方式：**先配置 Metadata MCP；只有需要特定直接控制工具时，才在
同一 AI 客户端中增加 IoT MCP。这样既以 Metadata MCP 作为用户和上下文主入口，
又能把两个服务作为一个互补能力组提供给 AI。

## Yeelight AI 能力矩阵

这些项目组成互补的 Yeelight AI 技术栈。可以根据接入方式选择入口，也可以组合使用。

| 项目 | 定位与核心能力 | 适用场景 | GitHub |
| --- | --- | --- | --- |
| Yeelight Home | 首选本地语义 Runtime，通过统一结构化 `invoke --stdin` 边界提供查询、控制、场景、自动化、灯光设计、诊断、产品知识和生成应用能力。 | 需要稳定、受策略保护的智能家居执行层的 Agent host、本地自动化和应用。 | [Yeelight/yeelight-home](https://github.com/Yeelight/yeelight-home) |
| Yeelight Smart Home Skills | 官方 Agent Skills：Smart Home 把自然语言转换为安全的 Runtime 操作；PRO App Builder 基于已验证能力生成专用本地应用。 | 需要智能家居对话工作流或应用生成能力的 Agent host。 | [Yeelight/yeelight-smart-home-skills](https://github.com/Yeelight/yeelight-smart-home-skills) |
| Yeelight AI CLI | 统一终端工作台和 MCP 客户端，连接 Cloud、Metadata 和 LAN 服务，提供本地 profile、安全快捷命令、诊断、脚本和 AI 客户端配置。 | 希望通过通用 MCP 与自动化命令行入口操作的用户、脚本和 CI。 | [Yeelight/yeelight-cli](https://github.com/Yeelight/yeelight-cli) |
| Yeelight Metadata MCP | 新 MCP 用户推荐的统一云端入口，提供受保护的家庭、房间、设备、设备组、面板、情景、自动化、收藏、维护和账号工作流，并支持多 Region 授权和请求级家庭选择。 | 需要广泛发现、检查和管理工作流的新 MCP 集成与 AI 客户端。 | [Yeelight/yeelight-metadata-mcp](https://github.com/Yeelight/yeelight-metadata-mcp) |
| Yeelight IoT MCP | 面向特定直接控制场景的专业补充，提供 Metadata MCP 尚未完全覆盖的拓扑与实时状态访问、设备控制和情景执行。 | 依赖 `control_node`、`execute_scene` 或特定实时控制的既有集成与客户端。 | [Yeelight/yeelight-iot-mcp](https://github.com/Yeelight/yeelight-iot-mcp) |

Yeelight Home 还提供系统凭据存储、本地 QR 登录、秘密脱敏诊断、预览与校验、调用方确认和 Runtime 策略/写后读取、本地记忆与推荐、实操经验，以及机器可读的 intent schema 和解释。跨平台二进制通过 GitHub Release、npm 和已支持的包管理器分发。

典型组合：智能家居 Agent 和生成应用 -> Skills -> Yeelight Home；终端用户和脚本 -> Yeelight AI CLI；新 MCP 集成 -> Metadata MCP；仅在 Metadata MCP 尚未覆盖的特定直接控制或情景执行场景下增加 IoT MCP。

## 核心特性

- 通过 6 个命名空间工具统一承载管理流程，避免暴露大量底层 HTTP 操作。
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

- `Yeelight-Region`：`cn`、`sg`、`us` 或 `eu`；缺省使用部署 Region（默认 `cn`）
- `House-Id`

用户唯一必需的凭据是 `Authorization`，可信 Yeelight 上游会从已验证的授权上下文解析客户端身份。需要家庭的 action 按 `context.houseId` -> `House-Id` -> 同 Region 首个 Pro 家庭的顺序选择；自动回退只作用于当前请求，不保存全局“当前家庭”。

## MCP 能力

Tools：

- `yeelight_metadata.list_groups`
- `yeelight_metadata.list_houses`
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

### 推荐：使用 Yeelight AI CLI 扫码授权

```bash
npm install --global yeelight-ai
yeelight-ai login --method qr --region cn
yeelight-ai client configure cursor --write --yes
```

在 Yeelight Pro APP 首页点击右上角 `+`，选择 **MCP 授权**，扫描终端二维码。CLI 会保存 Region、Authorization 和选中的家庭，并生成客户端配置。Metadata MCP 运行时不依赖 CLI，仍可独立配置。

### 连接官方远程服务

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

两个可选 Header 都可以省略。端点 host 必须与 Region 对应：`api.yeelight.com`、`api-sg.yeelight.com`、`api-us.yeelight.com` 或 `api-de.yeelight.com`。切换家庭时先调用 `yeelight_metadata.list_houses`，后续请求在 `request.context.houseId` 中显式传入目标 ID。

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
  "request": {
    "task": "family_space.manage_room",
    "action": "create",
    "payload": {"name": "示例房间"},
    "options": {"dryRun": true}
  }
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
| `METADATA_MCP_DEFAULT_REGION` | `cn` | 缺少 `Yeelight-Region` 时使用的默认 Region |
| `METADATA_MCP_HOST_PREFIX` | `https://api.yeelight.com` | Yeelight API host |
| `METADATA_MCP_API_BASE_URL` | 取 host prefix | 显式 API 根地址 |
| `METADATA_MCP_HTTP_TIMEOUT` | `15` | 上游请求超时秒数 |
| `METADATA_MCP_RESOURCE_DIR` | `resources/catalog` | 运行时目录覆盖路径 |
| `METADATA_MCP_NACOS_ENABLE` | 按环境决定 | Nacos 注册开关 |
| `METADATA_MCP_NACOS_SERVER` | 按环境决定 | Nacos 地址 |
| `METADATA_MCP_ALLOW_CANDIDATE_EXECUTION` | `false` | candidate 执行开关 |

旧 `APP_MCP_*` 变量继续保留，用于兼容现有部署。
标准 Yeelight 云端 origin 支持请求级 Region 路由；自定义 API base 固定到 `METADATA_MCP_DEFAULT_REGION`，其他 Region 请求会被拒绝，避免静默路由到错误云区。

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
