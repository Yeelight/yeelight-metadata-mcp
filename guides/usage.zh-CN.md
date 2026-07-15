# 使用指南

[English](usage.md) | [README](../README.zh-CN.md) | [接入指南](integration.zh-CN.md)

Metadata MCP 使用 `task + action + context + payload + options` 描述 APP 管理流程。发现类响应保持轻量，选定 action 后再读取精确 schema。

## 发现任务

先调用 `yeelight_metadata.list_groups`：

```json
{}
```

再通过 `yeelight_metadata.list_tasks` 浏览分组：

```json
{
  "group": "family_space",
  "limit": 20
}
```

传入精确 task 可以查看 action 摘要：

```json
{
  "task": "family_space.manage_room"
}
```

`yeelight_metadata.list_actions` 支持按 task、group、状态、副作用等级或执行模式筛选。

## 查看和切换家庭

使用 `{}` 调用 `yeelight_metadata.list_houses`，可以列出当前 Authorization 与 Region 可访问的 Pro 家庭。选择稳定的 `houseId` 后，在后续每次请求中显式传入：

```json
{
  "request": {
    "task": "family_space.manage_house",
    "action": "get_house_detail",
    "context": {"houseId": "<目标家庭 ID>"},
    "options": {"dryRun": false}
  }
}
```

服务端不保存全局“当前家庭”。action 需要家庭时，优先级为 `context.houseId` -> `House-Id` -> 首个 Pro 家庭。

## 读取 Action Schema

调用 `yeelight_metadata.get_action_schema`：

```json
{
  "task": "family_space.manage_room",
  "action": "create"
}
```

响应会说明全局 Header、局部 context、payload、options、副作用、执行模式和 action 状态。

## 生成 Dry-Run 计划

调用 `yeelight_metadata.execute_task`：

```json
{
  "request": {
    "task": "family_space.manage_room",
    "action": "create",
    "payload": {"name": "临时测试房间"},
    "options": {"dryRun": true}
  }
}
```

dry run 会校验请求并返回 `plan.httpRequest`，不会调用业务接口。

## 执行只读查询

```json
{
  "request": {
    "task": "family_space.manage_house",
    "action": "get_house_detail",
    "options": {"dryRun": false}
  }
}
```

真实响应会归一化为 `ok`、`code`、`message` 和 `data`。

## 执行已确认写操作

```json
{
  "request": {
    "task": "family_space.manage_room",
    "action": "create",
    "payload": {"name": "临时测试房间"},
    "options": {
      "dryRun": false,
      "confirmSideEffect": true
    }
  }
}
```

只有 candidate action 已完成人工审查，且运行环境显式允许 candidate 执行时，才添加 `allowCandidate=true`。

## 协议验收 CLI

仓库内提供真实 MCP 协议客户端：

```bash
export METADATA_MCP_ACCESS_TOKEN='<YOUR_AUTHORIZATION>'
export METADATA_MCP_REGION='cn'
export METADATA_MCP_HOUSE_ID='<YOUR_HOUSE_ID>'

PYTHONPATH=src .venv/bin/python scripts/mcp_acceptance_cli.py tools
PYTHONPATH=src .venv/bin/python scripts/mcp_acceptance_cli.py houses
PYTHONPATH=src .venv/bin/python scripts/mcp_acceptance_cli.py groups
PYTHONPATH=src .venv/bin/python scripts/mcp_acceptance_cli.py tasks --group family_space
PYTHONPATH=src .venv/bin/python scripts/mcp_acceptance_cli.py actions --task family_space.manage_room
PYTHONPATH=src .venv/bin/python scripts/mcp_acceptance_cli.py schema family_space.manage_room create
PYTHONPATH=src .venv/bin/python scripts/mcp_acceptance_cli.py dryrun family_space.manage_room create \
  --payload '{"name":"临时测试房间"}'
PYTHONPATH=src .venv/bin/python scripts/mcp_acceptance_cli.py smoke
```

常用参数包括 `--url`、`--token`、`--region`、`--house-id`、`--timeout`、`--full` 和 `--context`。`smoke` 除 dry run 外还会执行一次真实只读账号查询，因此只能对预期的测试端点和测试凭据使用。

## 全 Action 矩阵

以下命令默认不访问云端，会校验全部注册 action 并生成 dry-run 计划：

```bash
PYTHONPATH=src .venv/bin/python scripts/action_acceptance_matrix.py
```

live 模式和 `scripts/live_write_acceptance.py` 会修改云端数据。必须使用非生产家庭，并确保每个测试对象都能查询、回查和清理。

## 操作规则

- 写入或控制前，先把名称解析为真实 ID。
- 参数校验失败后刷新 action schema。
- token、House-Id 和业务 payload 不得进入日志或报告。
- 所有写入和破坏性动作先执行 dry run。
- API 支持查询时，写入后必须回查验证。
- 删除、解绑、转移、登录和绑定失败后不得盲目重试。
