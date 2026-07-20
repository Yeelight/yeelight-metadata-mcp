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

## 在 Yeelight AI 中的位置

[`yeelight-home`](https://github.com/Yeelight/yeelight-home) 是唯一安装、扫码和客户端配置入口。普通用户优先选择完整的 `yeelight-smart-home` Skill；客户端无法安装 Skill 时，本服务是推荐的云端轻量 MCP 主入口。只有需要 Metadata 尚未覆盖的实时控制或情景执行时，才增加 IoT MCP。

用普通人的话说：本服务让只能使用 MCP 的 AI 有条理地看懂家庭，并通过受保护的
方式管理家庭。它**不是**另一个 CLI，也不是 `yeelight-home` 或 Smart Home Skill
的运行依赖。

| 适合选择本项目 | 更适合选择其他路线 |
| --- | --- |
| AI 客户端支持 MCP，但不能安装 Agent Skill。 | 客户端能安装 Skill：优先用 `yeelight-smart-home` 获得完整引导。 |
| AI 需要理解房间、设备、设备组、情景、自动化、面板或家庭管理。 | 需要终端脚本或排障：直接使用 `yeelight-home`。 |
| 想先接入 Yeelight 云端 MCP 主入口，再决定是否增加 IoT。 | 只为兼容既有 `control_node` 或 `execute_scene`：把 IoT MCP 作为补充。 |

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

用户唯一必需的凭据是 `Authorization`。没有 `Yeelight-Region` 时，服务可先用 JWT
中的 Region claim 选择官方端点，再由该端点验证完整 Token。可信 Yeelight 上游会从
验证后的授权上下文解析客户端身份，用户不需要填写 Client ID。需要家庭的 action 按
`context.houseId` -> `House-Id` -> 同 Region 首个 Pro 家庭的顺序选择；自动回退只
作用于当前请求，不保存全局“当前家庭”。

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

### 推荐：让 Yeelight Home 一次完成扫码和配置

```bash
npm install --global yeelight-home
yeelight-home setup --lang zh-CN --mode mcp --agent cursor --mcp-source cloud --yes
```

命令会主动显示二维码。请在 Yeelight Pro APP 首页点击右上角 `+`，选择 **MCP 授权**扫码。只有一个 Pro 家庭时会自动选择；多个家庭时才按名称询问。把 `cursor` 换成你的客户端，或使用 `--agent auto` 自动探测。生成的客户端配置只启动本机凭据代理，不包含 Authorization。手动 Token 配置仅作为高级兼容路径；不要把 Token 粘贴到 AI 对话中。

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

两个可选 Header 都可以省略。JWT Token 可提供 Region claim，opaque Token 使用部署
默认 Region；显式选择端点时，host 必须与 Region 对应：`api.yeelight.com`、
`api-sg.yeelight.com`、`api-us.yeelight.com` 或 `api-de.yeelight.com`。切换家庭时先
调用 `yeelight_metadata.list_houses`，后续请求在 `request.context.houseId` 中显式传入
目标 ID。

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
