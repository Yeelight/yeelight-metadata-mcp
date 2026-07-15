#!/usr/bin/env python3
"""通过 Streamable HTTP 真实调用 Yeelight Metadata MCP 的简易验收 CLI。"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shlex
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from mcp import ClientSession  # noqa: E402
from mcp.client.streamable_http import streamablehttp_client  # noqa: E402


DEFAULT_URL = "http://127.0.0.1:9010/mcp"
DEFAULT_CONTEXT = {"runtimeEnv": "local"}
SAFE_SMOKE_ACTIONS = [
    {
        "task": "family_space.manage_house",
        "action": "list",
        "context": {},
        "payload": {},
        "options": {"dryRun": True, "allowCandidate": True},
    },
    {
        "task": "maintenance_account.manage_account",
        "action": "get_user_info",
        "context": {},
        "payload": {},
        "options": {"dryRun": False},
    },
]


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def print_table(headers: List[str], rows: Iterable[Iterable[Any]]) -> None:
    row_values = [[str(value) for value in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in row_values:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    def line(values: List[str]) -> str:
        return "  ".join(value.ljust(widths[index]) for index, value in enumerate(values))

    print(line(headers))
    print(line(["-" * width for width in widths]))
    for row in row_values:
        print(line(row))


def format_bool(value: Any) -> str:
    return "是" if value else "否"


def format_preview(value: Any, max_chars: int = 6000) -> str:
    text = json.dumps(value, ensure_ascii=False, indent=2)
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}\n... 已截断，完整内容请使用 --full 查看"


def print_indented_block(value: str, indent: str = "  ") -> None:
    for line in value.splitlines() or [""]:
        print(f"{indent}{line}")


def print_execution_summary(result: Dict[str, Any], full: bool = False) -> None:
    if full:
        print_json(result)
        return

    plan = result.get("plan", {})
    validation = result.get("validation", {})
    http_request = plan.get("httpRequest") or {}
    print(f"ok: {format_bool(result.get('ok'))}")
    print(f"code: {result.get('code')}")
    print(f"message: {result.get('message')}")
    print(f"task/action: {plan.get('task')}/{plan.get('action')}")
    print(f"dryRun: {format_bool(result.get('dryRun'))}")
    print(f"风险: {plan.get('sideEffect')}")
    print(f"状态: {plan.get('status')}")
    print(f"执行模式: {plan.get('executionMode')}")
    print(f"直连支持: {format_bool(plan.get('directExecutionSupported'))}")
    print(f"校验: {format_bool(validation.get('valid'))} ({validation.get('code')})")
    if validation.get("errors"):
        print("错误:")
        for item in validation.get("errors", []):
            print(f"  - {item}")
    if validation.get("warnings"):
        print("警告:")
        for item in validation.get("warnings", []):
            print(f"  - {item}")
    if http_request:
        print("HTTP 计划:")
        print(f"  {http_request.get('method')} {http_request.get('url')}")
        if http_request.get("params"):
            print(f"  params: {json.dumps(http_request.get('params'), ensure_ascii=False)}")
        if http_request.get("body") is not None:
            print(f"  body: {json.dumps(http_request.get('body'), ensure_ascii=False)}")
    if result.get("normalizedResponse"):
        response = result["normalizedResponse"]
        print("响应:")
        print(f"  ok: {format_bool(response.get('ok'))}")
        print(f"  code: {response.get('code')}")
        print(f"  message: {response.get('message')}")
        if "data" in response:
            print("  data:")
            print_indented_block(format_preview(response.get("data")), "    ")
    if plan.get("guidance"):
        print("指引:")
        for item in plan.get("guidance", []):
            print(f"  - {item}")
    if result.get("dryRun") and validation.get("valid") and plan.get("directExecutionSupported"):
        print("下一步:")
        print("  - 想看真实数据，请把 dryrun 换成 execute。")
        if plan.get("status") == "candidate":
            print("  - candidate action 需要显式传 --options '{\"dryRun\": false, \"allowCandidate\": true}'。")
        if plan.get("sideEffect") in {"S2", "S3"}:
            print("  - 该动作有副作用，真实执行还需要 options.confirmSideEffect=true。")


def load_json_arg(value: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not value:
        return dict(default or {})
    try:
        data = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"JSON 参数解析失败: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("JSON 参数必须是对象")
    return data


def auth_headers(token: str, house_id: str = "", region: str = "cn") -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if not token:
        return headers
    headers["Authorization"] = token if token.startswith("Bearer ") else f"Bearer {token}"
    if region:
        headers["Yeelight-Region"] = region
    if house_id:
        headers["House-Id"] = house_id
    return headers


def content_to_plain(result: Any) -> Any:
    if getattr(result, "isError", False):
        return {"isError": True, "content": [content_item_to_plain(item) for item in getattr(result, "content", [])]}
    content = getattr(result, "content", None)
    if content is None:
        if hasattr(result, "model_dump"):
            return result.model_dump()
        return result
    if len(content) == 1:
        item = content[0]
        plain = content_item_to_plain(item)
        if isinstance(plain, str):
            try:
                return json.loads(plain)
            except json.JSONDecodeError:
                return plain
        return plain
    return [content_item_to_plain(item) for item in content]


def content_item_to_plain(item: Any) -> Any:
    if hasattr(item, "text"):
        return item.text
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return item


class MetadataMcpClient:
    def __init__(self, url: str, token: str, house_id: str, timeout: float, region: str = ""):
        self.url = url
        self.token = token
        self.house_id = house_id
        self.region = region
        self.timeout = timeout

    async def run_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        headers = auth_headers(self.token, self.house_id, self.region)
        async with streamablehttp_client(self.url, headers=headers, timeout=self.timeout) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments or {})
                return content_to_plain(result)

    async def list_tools(self) -> Any:
        headers = auth_headers(self.token, self.house_id, self.region)
        async with streamablehttp_client(self.url, headers=headers, timeout=self.timeout) as (read, write, _):
            async with ClientSession(read, write) as session:
                init_result = await session.initialize()
                tools_result = await session.list_tools()
                return {
                    "server": init_result.serverInfo.model_dump() if hasattr(init_result.serverInfo, "model_dump") else init_result.serverInfo,
                    "tools": [tool.model_dump() if hasattr(tool, "model_dump") else tool for tool in tools_result.tools],
                }


def build_execute_request(args: argparse.Namespace, dry_run_default: bool) -> Dict[str, Any]:
    context = {**DEFAULT_CONTEXT, **load_json_arg(args.context)}
    payload = load_json_arg(args.payload)
    options = load_json_arg(args.options, {"dryRun": dry_run_default})
    options.setdefault("dryRun", dry_run_default)
    return {
        "request": {
            "task": args.task,
            "action": args.action,
            "context": context,
            "payload": payload,
            "options": options,
        }
    }


async def cmd_tools(client: MetadataMcpClient, _args: argparse.Namespace) -> None:
    print_json(await client.list_tools())


async def cmd_houses(client: MetadataMcpClient, _args: argparse.Namespace) -> None:
    print_json(await client.run_tool("yeelight_metadata.list_houses", {}))


async def cmd_tasks(client: MetadataMcpClient, args: argparse.Namespace) -> None:
    arguments = {}
    if args.group:
        arguments["group"] = args.group
    if getattr(args, "query", ""):
        arguments["query"] = args.query
    if getattr(args, "task", ""):
        arguments["task"] = args.task
    if getattr(args, "limit", None):
        arguments["limit"] = args.limit
    result = await client.run_tool("yeelight_metadata.list_tasks", arguments)
    if args.full:
        print_json(result)
        return
    if result.get("task") or result.get("id"):
        await print_task_detail(result)
        return
    if result.get("matches") is not None:
        print_search_rows(result)
        return
    rows = []
    for task in result.get("items") or result.get("tasks", []):
        rows.append(
            [
                task.get("task") or task.get("id", ""),
                task.get("title", ""),
                task.get("priority", ""),
                task.get("maxSideEffect", ""),
                task.get("actionCount", len(task.get("actions", []))),
            ]
        )
    print_table(["task", "标题", "优先级", "最高风险", "action数"], rows)


async def cmd_groups(client: MetadataMcpClient, args: argparse.Namespace) -> None:
    result = await client.run_tool("yeelight_metadata.list_groups", {})
    if args.full:
        print_json(result)
        return
    rows = []
    for group in result.get("items") or result.get("groups", []):
        rows.append(
            [
                group.get("id", ""),
                group.get("title", ""),
                group.get("taskCount", len(group.get("tasks", []))),
                group.get("summary", ""),
            ]
        )
    print_table(["group", "标题", "任务数", "说明"], rows)


async def cmd_describe(client: MetadataMcpClient, args: argparse.Namespace) -> None:
    result = await client.run_tool("yeelight_metadata.list_tasks", {"task": args.task})
    if args.full:
        print_json(result)
        return
    await print_task_detail(result)


async def print_task_detail(result: Dict[str, Any]) -> None:
    print(f"task: {result.get('task') or result.get('id')}")
    print(f"标题: {result.get('title')}")
    print(f"摘要: {result.get('summary')}")
    print(f"最高风险: {result.get('maxSideEffect')}")
    rows = []
    for action in result.get("items") or result.get("actions", []):
        rows.append(
            [
                action.get("action") or action.get("id", ""),
                action.get("title", ""),
                action.get("status", ""),
                action.get("sideEffect", ""),
                action.get("executionMode", ""),
                "是" if action.get("directExecutionSupported") else "否",
            ]
        )
    print_table(["action", "标题", "状态", "风险", "执行模式", "直连"], rows)


async def cmd_schema(client: MetadataMcpClient, args: argparse.Namespace) -> None:
    print_json(await client.run_tool("yeelight_metadata.get_action_schema", {"task": args.task, "action": args.action}))


async def cmd_search(client: MetadataMcpClient, args: argparse.Namespace) -> None:
    result = await client.run_tool("yeelight_metadata.list_tasks", {"query": args.query, "group": args.group or None, "limit": args.limit})
    if args.full:
        print_json(result)
        return
    print_search_rows(result)


def print_search_rows(result: Dict[str, Any]) -> None:
    rows = []
    for item in result.get("matches", []):
        rows.append(
            [
                item.get("task", ""),
                item.get("title", ""),
                item.get("group", ""),
                item.get("maxSideEffect", ""),
                ",".join(action.get("action", "") for action in item.get("matchedActions", [])),
            ]
        )
    print_table(["task", "标题", "分组", "最高风险", "匹配 actions"], rows)


async def cmd_actions(client: MetadataMcpClient, args: argparse.Namespace) -> None:
    arguments = {
        "task": args.task or None,
        "group": args.group or None,
        "status": args.status or None,
        "sideEffect": args.side_effect or None,
        "executionMode": args.execution_mode or None,
        "limit": args.limit,
    }
    result = await client.run_tool("yeelight_metadata.list_actions", arguments)
    if args.full:
        print_json(result)
        return
    rows = []
    for action in result.get("items") or result.get("actions", []):
        rows.append(
            [
                action.get("task", ""),
                action.get("action", ""),
                action.get("title", ""),
                action.get("status", ""),
                action.get("sideEffect", ""),
                action.get("executionMode", ""),
                ",".join(action.get("contextRequired", [])),
                ",".join(action.get("payloadRequired", [])),
            ]
        )
    print_table(["task", "action", "标题", "状态", "风险", "执行模式", "context", "payload"], rows)


async def cmd_hints(client: MetadataMcpClient, args: argparse.Namespace) -> None:
    result = await client.run_tool("yeelight_metadata.get_action_schema", {"task": args.task, "action": args.action})
    if args.full:
        print_json(result)
        return
    print(f"task/action: {result.get('task')}/{result.get('action')}")
    print(f"标题: {result.get('title')}")
    print(f"状态: {result.get('status')}")
    print(f"风险: {result.get('sideEffect')}")
    print(f"执行模式: {result.get('executionMode')}")
    print("全局 Header:")
    for header in result.get("globalContext", {}).get("headers", []):
        print(f"  - {header.get('name')}: required={header.get('required')}，{header.get('description')}")
    print(f"局部 context 必填: {','.join(result.get('localContextRequired', [])) or '无'}")
    print(f"payload 必填: {','.join(result.get('payloadRequired', [])) or '无'}")
    if result.get("optionHints"):
        print("options:")
        print_indented_block(format_preview(result.get("optionHints")), "  ")


async def cmd_validate(client: MetadataMcpClient, args: argparse.Namespace) -> None:
    request = build_execute_request(args, dry_run_default=True)["request"]
    request["options"] = {**request.get("options", {}), "dryRun": True}
    result = await client.run_tool("yeelight_metadata.execute_task", {"request": request})
    if args.full:
        print_json(result)
        return
    validation = result.get("validation", result)
    plan = result.get("plan", {})
    print(f"valid: {format_bool(validation.get('valid'))}")
    print(f"code: {validation.get('code')}")
    print(f"task/action: {validation.get('task') or plan.get('task')}/{validation.get('action') or plan.get('action')}")
    print(f"风险: {validation.get('sideEffect') or plan.get('sideEffect')}")
    print(f"状态: {validation.get('status') or plan.get('status')}")
    print(f"执行模式: {validation.get('executionMode') or plan.get('executionMode')}")
    if validation.get("errors"):
        print("错误:")
        for item in validation.get("errors", []):
            print(f"  - {item}")
    if validation.get("warnings"):
        print("警告:")
        for item in validation.get("warnings", []):
            print(f"  - {item}")


async def cmd_execute(client: MetadataMcpClient, args: argparse.Namespace) -> None:
    result = await client.run_tool("yeelight_metadata.execute_task", build_execute_request(args, dry_run_default=args.dry_run))
    print_execution_summary(result, args.full)


async def cmd_smoke(client: MetadataMcpClient, args: argparse.Namespace) -> None:
    extra_context = load_json_arg(getattr(args, "context", "{}"))
    results = []
    for item in SAFE_SMOKE_ACTIONS:
        request = {
            "task": item["task"],
            "action": item["action"],
            "context": {**DEFAULT_CONTEXT, **item["context"], **extra_context},
            "payload": {**item["payload"]},
            "options": {**item["options"]},
        }
        result = await client.run_tool("yeelight_metadata.execute_task", {"request": request})
        results.append({"task": item["task"], "action": item["action"], "result": result})
    if client.house_id:
        request = {
            "task": "family_space.manage_house",
            "action": "get_house_detail",
            "context": {**DEFAULT_CONTEXT},
            "payload": {},
            "options": {"dryRun": True, "allowCandidate": True},
        }
        result = await client.run_tool("yeelight_metadata.execute_task", {"request": request})
        results.append({"task": request["task"], "action": request["action"], "check": "house_id_header_context", "result": result})
    print_json({"generatedAt": datetime.now().isoformat(timespec="seconds"), "results": results})


async def cmd_repl(client: MetadataMcpClient, _args: argparse.Namespace) -> None:
    print("Yeelight Metadata MCP 验收 CLI")
    print("命令: groups | tools | tasks [group] | search <keyword> | actions [task] | describe <task> | schema <task> <action> | hints <task> <action> | dryrun <task> <action> [payload_json] [context_json] | execute <task> <action> [payload_json] [context_json] | smoke | quit")
    while True:
        try:
            line = input("metadata-mcp> ").strip()
        except EOFError:
            print()
            return
        if not line:
            continue
        if line in {"quit", "exit", "q"}:
            return
        try:
            parts = shlex.split(line)
            output = await dispatch_repl(client, parts)
            if output is not None:
                print_json(output)
        except Exception as exc:
            print_json({"ok": False, "error": str(exc)})


async def dispatch_repl(client: MetadataMcpClient, parts: List[str]) -> Any:
    command = parts[0]
    if command == "groups":
        result = await client.run_tool("yeelight_metadata.list_groups", {})
        return [
            {
                "id": group.get("id"),
                "title": group.get("title"),
                "taskCount": group.get("taskCount", len(group.get("tasks", []))),
                "summary": group.get("summary"),
            }
            for group in result.get("items") or result.get("groups", [])
        ]
    if command == "tools":
        return await client.list_tools()
    if command == "tasks":
        return await client.run_tool("yeelight_metadata.list_tasks", {"group": parts[1]} if len(parts) > 1 else {})
    if command == "search" and len(parts) >= 2:
        return await client.run_tool("yeelight_metadata.list_tasks", {"query": parts[1]})
    if command == "actions":
        return await client.run_tool("yeelight_metadata.list_actions", {"task": parts[1]} if len(parts) > 1 else {})
    if command == "describe" and len(parts) >= 2:
        return await client.run_tool("yeelight_metadata.list_tasks", {"task": parts[1]})
    if command == "schema" and len(parts) >= 3:
        return await client.run_tool("yeelight_metadata.get_action_schema", {"task": parts[1], "action": parts[2]})
    if command == "hints" and len(parts) >= 3:
        return await client.run_tool("yeelight_metadata.get_action_schema", {"task": parts[1], "action": parts[2]})
    if command in {"dryrun", "execute"} and len(parts) >= 3:
        payload = load_json_arg(parts[3]) if len(parts) >= 4 else {}
        context = {**DEFAULT_CONTEXT, **(load_json_arg(parts[4]) if len(parts) >= 5 else {})}
        request = {
            "task": parts[1],
            "action": parts[2],
            "context": context,
            "payload": payload,
            "options": {"dryRun": command == "dryrun", "allowCandidate": command == "dryrun", "confirmSideEffect": False},
        }
        return await client.run_tool("yeelight_metadata.execute_task", {"request": request})
    if command == "smoke":
        results = []
        for item in SAFE_SMOKE_ACTIONS:
            request = {
                "task": item["task"],
                "action": item["action"],
                "context": {**DEFAULT_CONTEXT, **item["context"]},
                "payload": {**item["payload"]},
                "options": {**item["options"]},
            }
            results.append(await client.run_tool("yeelight_metadata.execute_task", {"request": request}))
        return {"results": results}
    raise ValueError("未知命令或参数不足")


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--url", default=os.getenv("METADATA_MCP_URL", DEFAULT_URL), help="MCP Streamable HTTP 地址")
    parser.add_argument("--token", default=os.getenv("METADATA_MCP_ACCESS_TOKEN", ""), help="访问 token，建议使用 METADATA_MCP_ACCESS_TOKEN 环境变量")
    parser.add_argument("--house-id", default=os.getenv("METADATA_MCP_HOUSE_ID", ""), help="全局家庭 ID，会作为 House-Id Header 发送")
    parser.add_argument(
        "--region",
        default=os.getenv("METADATA_MCP_REGION") or None,
        choices=["cn", "sg", "us", "eu", "dev"],
        help="可选账号 Region；省略时不发送 Yeelight-Region，由服务端使用部署默认值。dev 仅用于开发验证",
    )
    parser.add_argument("--timeout", type=float, default=float(os.getenv("METADATA_MCP_CLIENT_TIMEOUT", "30")), help="HTTP 超时时间")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Yeelight Metadata MCP 简易验收 CLI")
    add_common_args(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("tools", help="列出 MCP 工具")
    subparsers.add_parser("houses", help="列出当前 Region 的 Pro 家庭")

    groups_parser = subparsers.add_parser("groups", help="列出任务分组")
    groups_parser.add_argument("--full", action="store_true", help="输出原始 JSON")

    tasks_parser = subparsers.add_parser("tasks", help="列出任务树")
    tasks_parser.add_argument("--group", default="", help="可选分组 ID")
    tasks_parser.add_argument("--query", default="", help="可选搜索关键词")
    tasks_parser.add_argument("--task", default="", help="可选任务 ID，传入后查看单任务详情")
    tasks_parser.add_argument("--limit", type=int, default=50, help="最多返回多少个任务")
    tasks_parser.add_argument("--full", action="store_true", help="输出原始 JSON")

    describe_parser = subparsers.add_parser("describe", help="查看任务详情")
    describe_parser.add_argument("task")
    describe_parser.add_argument("--full", action="store_true", help="输出原始 JSON")

    schema_parser = subparsers.add_parser("schema", help="查看 task/action schema")
    schema_parser.add_argument("task")
    schema_parser.add_argument("action")

    search_parser = subparsers.add_parser("search", help="按关键词搜索任务和 action")
    search_parser.add_argument("query")
    search_parser.add_argument("--group", default="", help="可选分组 ID")
    search_parser.add_argument("--limit", type=int, default=20, help="最多返回多少个任务")
    search_parser.add_argument("--full", action="store_true", help="输出原始 JSON")

    actions_parser = subparsers.add_parser("actions", help="列出或筛选 action")
    actions_parser.add_argument("--task", default="", help="可选任务 ID")
    actions_parser.add_argument("--group", default="", help="可选分组 ID")
    actions_parser.add_argument("--status", default="", help="可选状态，例如 confirmed/candidate")
    actions_parser.add_argument("--side-effect", default="", help="可选风险等级，例如 S0/S2/S3")
    actions_parser.add_argument("--execution-mode", default="", help="可选执行模式，例如 cloud_api")
    actions_parser.add_argument("--limit", type=int, default=200, help="最多返回多少个 action")
    actions_parser.add_argument("--full", action="store_true", help="输出原始 JSON")

    hints_parser = subparsers.add_parser("hints", help="查看 task/action 的上下文和参数提示")
    hints_parser.add_argument("task")
    hints_parser.add_argument("action")
    hints_parser.add_argument("--full", action="store_true", help="输出原始 JSON")

    validate_parser = subparsers.add_parser("validate", help="校验 task/action 请求")
    validate_parser.add_argument("task")
    validate_parser.add_argument("action")
    validate_parser.add_argument("--context", default="{}", help="context JSON")
    validate_parser.add_argument("--payload", default="{}", help="payload JSON")
    validate_parser.add_argument("--options", default='{"dryRun": true, "allowCandidate": true}', help="options JSON")
    validate_parser.add_argument("--full", action="store_true", help="输出原始 JSON")

    dryrun_parser = subparsers.add_parser("dryrun", help="生成 dryRun 执行计划")
    dryrun_parser.add_argument("task")
    dryrun_parser.add_argument("action")
    dryrun_parser.add_argument("--context", default="{}", help="context JSON")
    dryrun_parser.add_argument("--payload", default="{}", help="payload JSON")
    dryrun_parser.add_argument("--options", default='{"dryRun": true, "allowCandidate": true}', help="options JSON")
    dryrun_parser.add_argument("--full", action="store_true", help="输出原始 JSON")

    execute_parser = subparsers.add_parser("execute", help="真实执行 task/action")
    execute_parser.add_argument("task")
    execute_parser.add_argument("action")
    execute_parser.add_argument("--context", default="{}", help="context JSON")
    execute_parser.add_argument("--payload", default="{}", help="payload JSON")
    execute_parser.add_argument("--options", default='{"dryRun": false, "confirmSideEffect": false}', help="options JSON")
    execute_parser.add_argument("--full", action="store_true", help="输出原始 JSON")
    execute_parser.set_defaults(dry_run=False)

    smoke_parser = subparsers.add_parser("smoke", help="执行安全冒烟验收")
    smoke_parser.add_argument("--context", default="{}", help="附加 context JSON，例如 {\"houseId\":\"200084\"}")
    repl_parser = subparsers.add_parser("repl", help="进入交互模式")
    repl_parser.set_defaults(repl=True)
    return parser


async def run(args: argparse.Namespace) -> None:
    client = MetadataMcpClient(args.url, args.token, args.house_id, args.timeout, args.region)
    handlers = {
        "tools": cmd_tools,
        "houses": cmd_houses,
        "groups": cmd_groups,
        "tasks": cmd_tasks,
        "describe": cmd_describe,
        "schema": cmd_schema,
        "search": cmd_search,
        "actions": cmd_actions,
        "hints": cmd_hints,
        "validate": cmd_validate,
        "dryrun": cmd_execute,
        "execute": cmd_execute,
        "smoke": cmd_smoke,
        "repl": cmd_repl,
    }
    if args.command == "dryrun":
        args.dry_run = True
    await handlers[args.command](client, args)


def main() -> int:
    args = build_parser().parse_args()
    if not args.token:
        print("错误：缺少 token。请设置 METADATA_MCP_ACCESS_TOKEN 或传 --token。", file=sys.stderr)
        return 2
    asyncio.run(run(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
