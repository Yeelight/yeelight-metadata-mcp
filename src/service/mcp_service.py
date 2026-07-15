import base64
import json
import re
from typing import Annotated, Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import Context
from pydantic import Field

from config.config import settings
from config.region import api_base_for_region, resolve_region
from service.executor import executor
from service.model import TaskExecutionRequest
from service.request_context import CloudRequestContext, HouseContextError, HouseResolver
from service.registry import registry
from utils.auth import normalize_authorization_header


SEARCH_TEXT_REPLACEMENTS = (
    ("添加", "创建"),
    ("新增", "创建"),
    ("新建", "创建"),
    ("加入", "创建"),
    ("修改", "更新"),
    ("编辑", "更新"),
    ("设置", "配置"),
    ("开启", "启用"),
    ("打开", "启用"),
    ("关闭", "禁用"),
    ("停用", "禁用"),
    ("移除", "删除"),
    ("清除", "删除"),
    ("查找", "查询"),
    ("搜索", "查询"),
    ("查看", "查询"),
    ("获取", "查询"),
    ("列出", "查询"),
    ("所有", "全部"),
    ("家", "家庭"),
    ("家人", "成员"),
    ("灯具", "设备"),
    ("灯", "设备"),
    ("坑位", "槽位"),
    ("灯组", "设备组"),
    ("mesh组", "设备组"),
    ("mesh group", "device group"),
    ("回家模式", "情景"),
    ("晚安模式", "情景"),
    ("规则", "自动化"),
    ("联动", "自动化"),
    ("语音控制", "语音"),
    ("屏保", "图片"),
    ("固件", "ota"),
    ("升级", "更新"),
    ("第三方", "三方"),
    ("二维码", "qrcode"),
    ("扫码", "qrcode"),
)

SEARCH_TOKEN_ALIASES = {
    "add": "create",
    "added": "create",
    "adding": "create",
    "new": "create",
    "insert": "create",
    "invite": "create",
    "send": "create",
    "apply": "create",
    "generate": "create",
    "upload": "create",
    "enable": "enable",
    "disable": "disable",
    "open": "enable",
    "close": "disable",
    "update": "update",
    "modify": "update",
    "edit": "update",
    "configure": "configure",
    "config": "configure",
    "set": "configure",
    "reset": "reset",
    "delete": "delete",
    "remove": "delete",
    "unbind": "delete",
    "clear": "delete",
    "query": "query",
    "get": "query",
    "list": "query",
    "search": "query",
    "find": "query",
    "check": "query",
    "page": "query",
    "recommend": "recommend",
    "test": "test",
    "diagnose": "diagnose",
    "download": "download",
    "sync": "sync",
    "bind": "bind",
    "login": "login",
    "transfer": "transfer",
    "quit": "quit",
    "accept": "accept",
    "cancel": "cancel",
    "device": "device",
    "devices": "device",
    "light": "device",
    "lights": "device",
    "lamp": "device",
    "lamps": "device",
    "bulb": "device",
    "bulbs": "device",
    "slot": "slot",
    "slots": "slot",
    "house": "house",
    "home": "house",
    "family": "house",
    "room": "room",
    "rooms": "room",
    "area": "area",
    "areas": "area",
    "member": "member",
    "members": "member",
    "user": "user",
    "users": "user",
    "share": "share",
    "sharing": "share",
    "gateway": "gateway",
    "gateways": "gateway",
    "group": "group",
    "groups": "group",
    "panel": "panel",
    "button": "button",
    "buttons": "button",
    "event": "event",
    "events": "event",
    "knob": "knob",
    "storage": "storage",
    "asset": "asset",
    "image": "image",
    "images": "image",
    "picture": "image",
    "photo": "image",
    "voice": "voice",
    "asr": "asr",
    "scene": "scene",
    "scenes": "scene",
    "automation": "automation",
    "automations": "automation",
    "rule": "automation",
    "rules": "automation",
    "capability": "capability",
    "favorite": "favorite",
    "favorites": "favorite",
    "sort": "sort",
    "order": "sort",
    "upgrade": "upgrade",
    "ota": "ota",
    "ptx": "ptx",
    "electricity": "electricity",
    "energy": "electricity",
    "account": "account",
    "accounts": "account",
    "qrcode": "qrcode",
    "qr": "qrcode",
    "barcode": "barcode",
    "third": "third",
    "thirdparty": "third",
    "sonos": "sonos",
    "lan": "lan",
    "thread": "thread",
    "matter": "matter",
    "pid": "pid",
    "mac": "mac",
}

SEARCH_CHINESE_TOKEN_GROUPS = {
    "create": ("创建",),
    "update": ("更新",),
    "configure": ("配置",),
    "enable": ("启用",),
    "disable": ("禁用",),
    "reset": ("重置",),
    "delete": ("删除", "解绑"),
    "query": ("查询",),
    "recommend": ("推荐",),
    "test": ("测试",),
    "diagnose": ("诊断", "检查"),
    "download": ("下载",),
    "sync": ("同步",),
    "bind": ("绑定",),
    "login": ("登录",),
    "transfer": ("转移",),
    "quit": ("退出",),
    "accept": ("接受",),
    "cancel": ("取消",),
    "device": ("设备",),
    "slot": ("槽位",),
    "house": ("家庭",),
    "room": ("房间",),
    "area": ("区域",),
    "member": ("成员",),
    "share": ("分享",),
    "gateway": ("网关",),
    "group": ("组", "分组"),
    "panel": ("面板",),
    "button": ("按键",),
    "event": ("事件", "动作"),
    "knob": ("旋钮",),
    "storage": ("存储",),
    "image": ("图片",),
    "voice": ("语音",),
    "asr": ("asr",),
    "scene": ("情景",),
    "automation": ("自动化",),
    "capability": ("能力",),
    "favorite": ("收藏",),
    "sort": ("排序", "顺序"),
    "upgrade": ("升级", "更新"),
    "ota": ("ota",),
    "ptx": ("ptx", "d寸屏"),
    "electricity": ("用电", "电量", "耗电"),
    "account": ("账号", "账户"),
    "user": ("用户",),
    "qrcode": ("qrcode",),
    "barcode": ("barcode", "分享码"),
    "third": ("三方",),
    "sonos": ("sonos",),
    "lan": ("lan", "局域网", "本地"),
    "thread": ("thread",),
    "matter": ("matter",),
    "pid": ("pid", "产品id", "产品 ID"),
    "mac": ("mac",),
}

NO_SEARCH_MATCH = 99
TOOL_NAMESPACE = "yeelight_metadata"
DEFAULT_TASK_LIMIT = 50
DEFAULT_GROUP_LIMIT = 20
DEFAULT_SEARCH_LIMIT = 20
DEFAULT_ACTION_LIMIT = 200
MAX_TASK_LIMIT = 100
MAX_GROUP_LIMIT = 100
MAX_ACTION_LIMIT = 500
house_resolver = HouseResolver(executor.http_client)


def _normalize_limit(value: Optional[int], default: int, maximum: int) -> int:
    try:
        limit = int(value) if value is not None else default
    except (TypeError, ValueError):
        limit = default
    return max(1, min(limit, maximum))


def _encode_cursor(offset: int) -> Optional[str]:
    if offset <= 0:
        return None
    payload = json.dumps({"offset": offset}, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(cursor: Optional[str]) -> int:
    if not cursor:
        return 0
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        offset = int(json.loads(payload).get("offset", 0))
        return offset if offset > 0 else 0
    except Exception:
        return 0


def _paginate(items: List[Dict[str, Any]], cursor: Optional[str], limit: int) -> Dict[str, Any]:
    offset = _decode_cursor(cursor)
    page = items[offset:offset + limit]
    next_offset = offset + len(page)
    return {
        "items": page,
        "nextCursor": _encode_cursor(next_offset) if next_offset < len(items) else None,
        "total": len(items),
    }


def get_cloud_request_context(context: Context) -> CloudRequestContext:
    request_context = getattr(context, "request_context", None)
    request = getattr(request_context, "request", None)
    if request is None:
        raise HouseContextError("当前 MCP 请求缺少 HTTP 上下文。")

    state = getattr(request, "state", None)
    authorization = getattr(state, "authorization", None) if state is not None else None
    authorization = authorization or request.headers.get(settings.AUTHORIZATION_HEADER_KEY)
    if not authorization:
        raise HouseContextError("当前 MCP 请求缺少 Authorization。")
    authorization = normalize_authorization_header(authorization)

    region = getattr(state, "region", None) if state is not None else None
    region = region or resolve_region(
        request.headers.get(settings.REGION_HEADER_KEY),
        settings.DEFAULT_REGION,
    )
    api_base_url = getattr(state, "api_base_url", None) if state is not None else None
    api_base_url = api_base_url or api_base_for_region(
        region,
        settings.API_BASE_URL,
        settings.DEFAULT_REGION,
    )
    house_id = getattr(state, "house_id", None) if state is not None else None
    house_id = house_id or request.headers.get(settings.HOUSE_ID_HEADER_KEY)
    return CloudRequestContext(
        authorization=authorization,
        region=region,
        api_base_url=api_base_url,
        house_id=house_id,
    )


def _normalize_search_text(value: Any) -> str:
    text = str(value).lower()
    for source, target in SEARCH_TEXT_REPLACEMENTS:
        text = text.replace(source, target)
    return text


def _compact_search_text(value: Any) -> str:
    return re.sub(r"\s+", "", _normalize_search_text(value))


def _search_tokens(value: Any) -> List[str]:
    text = _normalize_search_text(value)
    tokens = [SEARCH_TOKEN_ALIASES.get(token, token) for token in re.findall(r"[a-z0-9]+", text)]
    for token, words in SEARCH_CHINESE_TOKEN_GROUPS.items():
        if any(word in text for word in words):
            tokens.append(token)
    return tokens


def _matches_keyword(value: Any, keyword: str) -> bool:
    return _keyword_match_rank(value, keyword) < NO_SEARCH_MATCH


def _keyword_match_rank(value: Any, keyword: str) -> int:
    if not keyword:
        return 0
    if isinstance(value, list):
        ranks = [_keyword_match_rank(item, keyword) for item in value]
        return min(ranks) if ranks else NO_SEARCH_MATCH
    if isinstance(value, dict):
        ranks = [_keyword_match_rank(item, keyword) for item in value.values()]
        return min(ranks) if ranks else NO_SEARCH_MATCH

    keyword_compact = _compact_search_text(keyword)
    value_compact = _compact_search_text(value)
    if keyword_compact and keyword_compact == value_compact:
        return 0
    if keyword_compact and keyword_compact in value_compact:
        return 1

    keyword_tokens = _search_tokens(keyword)
    if keyword_tokens:
        value_tokens = set(_search_tokens(value))
        if all(token in value_tokens for token in keyword_tokens):
            return 2
    return NO_SEARCH_MATCH


def _contains_keyword(value: Any, keyword: str) -> bool:
    if not keyword:
        return True
    if isinstance(value, list):
        return any(_contains_keyword(item, keyword) for item in value)
    if isinstance(value, dict):
        return any(_contains_keyword(item, keyword) for item in value.values())
    return _matches_keyword(value, keyword)


def _action_summary(task_id: str, group: str, action: Any) -> Dict[str, Any]:
    return {
        "task": task_id,
        "group": group,
        "action": action.id,
        "title": action.title,
        "description": action.description,
        "status": action.status.value,
        "sideEffect": action.sideEffect.value,
        "executionMode": action.executionMode.value,
        "directExecutionSupported": action.directExecutionSupported,
        "contextRequired": action.parameterSchema.contextRequired,
        "payloadRequired": action.parameterSchema.payloadRequired,
    }


def _task_summary(task: Any) -> Dict[str, Any]:
    return {
        "task": task.id,
        "group": task.group,
        "title": task.title,
        "summary": task.summary,
        "priority": task.priority,
        "maxSideEffect": task.maxSideEffect.value,
        "actionCount": len(task.actions),
    }


def _group_summary(group: Any, task_count: int) -> Dict[str, Any]:
    return {
        "id": group.id,
        "title": group.title,
        "summary": group.summary,
        "taskCount": task_count,
    }


def _describe_action_summary(action: Any) -> Dict[str, Any]:
    return {
        "action": action.id,
        "title": action.title,
        "description": action.description,
        "status": action.status.value,
        "sideEffect": action.sideEffect.value,
        "executionMode": action.executionMode.value,
        "directExecutionSupported": action.directExecutionSupported,
        "contextRequired": action.parameterSchema.contextRequired,
        "payloadRequired": action.parameterSchema.payloadRequired,
    }


def list_registry_groups(cursor: Optional[str] = None, limit: int = DEFAULT_GROUP_LIMIT) -> Dict[str, Any]:
    group_counts: Dict[str, int] = {}
    for task in registry.list_tasks():
        group_counts[task.group] = group_counts.get(task.group, 0) + 1
    page = _paginate(
        [_group_summary(item, group_counts.get(item.id, 0)) for item in registry.list_groups()],
        cursor,
        _normalize_limit(limit, DEFAULT_GROUP_LIMIT, MAX_GROUP_LIMIT),
    )
    return {
        "items": page["items"],
        "nextCursor": page["nextCursor"],
        "total": page["total"],
        "count": len(page["items"]),
    }


def list_registry_tasks(
    group: Optional[str] = None,
    query: Optional[str] = None,
    task: Optional[str] = None,
    cursor: Optional[str] = None,
    limit: int = DEFAULT_TASK_LIMIT,
) -> Dict[str, Any]:
    if task:
        return describe_registry_task(task)
    if query:
        return search_task_registry(query, group=group, cursor=cursor, limit=limit)

    filtered_tasks = [task for task in registry.list_tasks() if not group or task.group == group]
    page = _paginate([_task_summary(task) for task in filtered_tasks], cursor, _normalize_limit(limit, DEFAULT_TASK_LIMIT, MAX_TASK_LIMIT))
    return {
        "items": page["items"],
        "nextCursor": page["nextCursor"],
        "total": page["total"],
        "count": len(page["items"]),
    }


def describe_registry_task(task: str) -> Dict[str, Any]:
    task_card = registry.get_task(task)
    if task_card is None:
        return {"isError": True, "errorMessage": f"未知任务: {task}"}
    return {
        "task": task_card.id,
        "id": task_card.id,
        "group": task_card.group,
        "title": task_card.title,
        "summary": task_card.summary,
        "userPhrases": task_card.userPhrases,
        "priority": task_card.priority,
        "maxSideEffect": task_card.maxSideEffect.value,
        "requiredContext": task_card.requiredContext,
        "commonInputs": task_card.commonInputs,
        "actionCount": len(task_card.actions),
        "actions": [_describe_action_summary(action) for action in task_card.actions],
        "schemaHint": "使用 yeelight_metadata.get_action_schema 按 task/action 查询完整参数 schema 和上下文提示。",
        "resource": f"yeelight-metadata://tasks/{task_card.id}",
    }


def _priority_weight(priority: str) -> int:
    priority_map = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    return priority_map.get(priority, 9)


def search_task_registry(query: str, group: Optional[str] = None, limit: int = DEFAULT_SEARCH_LIMIT, cursor: Optional[str] = None) -> Dict[str, Any]:
    keyword = (query or "").strip().lower()
    ranked_matches: List[tuple[int, int, int, int, int, str, Dict[str, Any]]] = []
    for task in registry.list_tasks():
        if group and task.group != group:
            continue
        task_text = [task.id, task.title, task.summary, task.userPhrases]
        user_phrase_rank = _keyword_match_rank(task.userPhrases, keyword)
        task_rank = _keyword_match_rank(task_text, keyword)
        task_matched = task_rank < NO_SEARCH_MATCH
        matched_actions = []
        action_rank = NO_SEARCH_MATCH
        for action in task.actions:
            action_text = [
                action.id,
                action.title,
                action.description,
                action.status.value,
                action.sideEffect.value,
                action.executionMode.value,
                [ref.operation for ref in action.interfaceRefs],
            ]
            current_action_rank = _keyword_match_rank(action_text, keyword)
            if current_action_rank < NO_SEARCH_MATCH:
                action_rank = min(action_rank, current_action_rank)
                matched_actions.append(_action_summary(task.id, task.group, action))

        if task_matched or matched_actions:
            ranked_matches.append(
                (
                    user_phrase_rank,
                    min(task_rank, action_rank),
                    0 if task_matched else 1,
                    0 if matched_actions else 1,
                    _priority_weight(task.priority),
                    task.id,
                    {
                        "task": task.id,
                        "group": task.group,
                        "title": task.title,
                        "summary": task.summary,
                        "priority": task.priority,
                        "maxSideEffect": task.maxSideEffect.value,
                        "matchedActions": matched_actions[:8],
                        "actionCount": len(task.actions),
                    },
                )
            )
    ranked_matches.sort(key=lambda item: item[:6])
    page = _paginate([item[6] for item in ranked_matches], cursor, _normalize_limit(limit, DEFAULT_SEARCH_LIMIT, MAX_TASK_LIMIT))
    return {
        "query": query,
        "group": group,
        "count": len(page["items"]),
        "matches": page["items"],
        "nextCursor": page["nextCursor"],
        "total": page["total"],
    }


def list_registry_actions(
    task: Optional[str] = None,
    group: Optional[str] = None,
    status: Optional[str] = None,
    side_effect: Optional[str] = None,
    execution_mode: Optional[str] = None,
    limit: int = DEFAULT_ACTION_LIMIT,
    cursor: Optional[str] = None,
) -> Dict[str, Any]:
    actions: List[Dict[str, Any]] = []
    tasks = [registry.get_task(task)] if task else registry.list_tasks()
    for task_card in tasks:
        if task_card is None:
            continue
        if group and task_card.group != group:
            continue
        for action in task_card.actions:
            if status and action.status.value != status:
                continue
            if side_effect and action.sideEffect.value != side_effect:
                continue
            if execution_mode and action.executionMode.value != execution_mode:
                continue
            actions.append(_action_summary(task_card.id, task_card.group, action))
    page = _paginate(actions, cursor, _normalize_limit(limit, DEFAULT_ACTION_LIMIT, MAX_ACTION_LIMIT))
    return {
        "count": len(page["items"]),
        "items": page["items"],
        "nextCursor": page["nextCursor"],
        "total": page["total"],
    }


def get_registry_context_hints(task: str, action: str) -> Dict[str, Any]:
    task_card = registry.get_task(task)
    action_card = registry.get_action(task, action)
    if task_card is None or action_card is None:
        return {"isError": True, "errorMessage": f"未知 task/action: {task}/{action}"}

    schema = action_card.parameterSchema
    global_context = [field for field in schema.contextRequired if field == "houseId"]
    local_context = [field for field in schema.contextRequired if field != "houseId"]
    return {
        "task": task_card.id,
        "action": action_card.id,
        "title": action_card.title,
        "status": action_card.status.value,
        "sideEffect": action_card.sideEffect.value,
        "executionMode": action_card.executionMode.value,
        "directExecutionSupported": action_card.directExecutionSupported,
        "globalContext": {
            "headers": [
                {"name": "Authorization", "required": True, "description": "访问令牌"},
                {"name": "Yeelight-Region", "required": False, "description": "账号 Region；缺省使用服务部署默认值"},
                {"name": "House-Id", "required": False, "description": "默认家庭 ID；缺省时按需自动选择首个 Pro 家庭"},
            ],
            "fields": global_context,
        },
        "localContextRequired": local_context,
        "payloadRequired": schema.payloadRequired,
        "payloadProperties": schema.payloadProperties,
        "optionHints": schema.optionHints,
        "notes": [
            "如果 Header House-Id 与 context.houseId 同时存在，以 context.houseId 为准。",
            "需要家庭上下文且两者均缺失时，服务会选择当前 Region 的首个 Pro 家庭。",
            "roomId、deviceId、groupId 等局部业务 ID 应放在 context 中。",
        ],
    }


def get_registry_action_schema(task: str, action: str) -> Dict[str, Any]:
    task_card = registry.get_task(task)
    action_card = registry.get_action(task, action)
    if task_card is None or action_card is None:
        return {"isError": True, "errorMessage": f"未知 task/action: {task}/{action}"}

    schema = action_card.parameterSchema
    hints = get_registry_context_hints(task, action)
    if hints.get("isError"):
        return hints

    return {
        "task": task_card.id,
        "action": action_card.id,
        "taskTitle": task_card.title,
        "title": action_card.title,
        "description": action_card.description,
        "status": action_card.status.value,
        "sideEffect": action_card.sideEffect.value,
        "executionMode": action_card.executionMode.value,
        "directExecutionSupported": action_card.directExecutionSupported,
        "contextRequired": schema.contextRequired,
        "payloadRequired": schema.payloadRequired,
        "payloadProperties": schema.payloadProperties,
        "optionHints": schema.optionHints,
        "globalContext": hints.get("globalContext", {}),
        "localContextRequired": hints.get("localContextRequired", []),
        "notes": [
            "context.houseId 优先于 Header House-Id；两者缺失时按需自动选择首个 Pro 家庭。",
            "真实写入、删除、解绑、转移等操作应先调用 execute_task 且 options.dryRun=true 查看计划。",
            "确认真实执行时再设置 options.dryRun=false；S2/S3 操作还必须传 options.confirmSideEffect=true。",
        ],
    }


def get_action_schema_resource(task: str, action: str) -> Dict[str, Any]:
    schema = registry.get_schema(task, action)
    if schema is None:
        return {"isError": True, "errorMessage": f"未知 task/action: {task}/{action}"}
    return schema.model_dump()


def register_resources(mcp: FastMCP) -> None:
    @mcp.resource(
        "yeelight-metadata://tasks",
        name="yeelight_metadata.tasks",
        title="Yeelight Metadata MCP 任务树",
        description="返回 Metadata MCP 可处理的家庭空间、设备管理、配置、情景自动化和账号维护任务。",
        mime_type="application/json",
    )
    def tasks_resource() -> Dict[str, Any]:
        return {
            "groups": [item.model_dump() for item in registry.list_groups()],
            "tasks": [item.model_dump() for item in registry.list_tasks()],
        }

    @mcp.resource(
        "yeelight-metadata://tasks/{task}",
        name="yeelight_metadata.task_detail",
        title="Yeelight Metadata MCP 任务完整详情",
        description="按 task ID 返回完整任务卡片，包含 action schema 和接口映射。",
        mime_type="application/json",
    )
    def task_resource(task: str) -> Dict[str, Any]:
        task_card = registry.get_task(task)
        if task_card is None:
            return {"isError": True, "errorMessage": f"未知任务: {task}"}
        return task_card.model_dump()

    @mcp.resource(
        "yeelight-metadata://actions",
        name="yeelight_metadata.actions",
        title="Yeelight Metadata MCP Action 清单",
        description="返回所有 action 的任务归属、执行模式、副作用等级和接口映射摘要。",
        mime_type="application/json",
    )
    def actions_resource() -> Dict[str, Any]:
        return list_registry_actions(limit=1000)

    @mcp.resource(
        "yeelight-metadata://schema/{task}/{action}",
        name="yeelight_metadata.schema",
        title="Yeelight Metadata MCP Action Schema",
        description="按 task/action 返回 context、payload 和 options schema。",
        mime_type="application/json",
    )
    def schema_resource(task: str, action: str) -> Dict[str, Any]:
        return get_action_schema_resource(task, action)


def register_prompts(mcp: FastMCP) -> None:
    @mcp.prompt(
        name="yeelight_metadata.inspect_home_metadata",
        title="检查家庭元数据配置",
        description="引导模型先读取任务树，再查询家庭、房间、区域、设备组和首页组织配置。",
    )
    def inspect_home_metadata() -> str:
        return (
            "请使用 yeelight_metadata.list_groups、yeelight_metadata.list_tasks 找到或搜索家庭、房间、区域、"
            "设备组与首页组织相关任务；优先 dryRun，确认需要的 House-Id 后再查询实际元数据，并输出配置概览和异常项。"
        )

    @mcp.prompt(
        name="yeelight_metadata.plan_metadata_change",
        title="生成元数据变更计划",
        description="在创建房间、设备组、面板配置或自动化前生成 dry-run 执行计划。",
    )
    def plan_metadata_change(task: str, action: str) -> str:
        return (
            f"请为 {task}/{action} 生成变更计划。先调用 yeelight_metadata.get_action_schema 查看 context、payload 和 options 要求，"
            "随后调用 yeelight_metadata.execute_task 且 options.dryRun=true。"
            "不要真实执行 S2/S3 操作，除非用户明确确认 confirmSideEffect=true。"
        )

    @mcp.prompt(
        name="yeelight_metadata.troubleshoot_automation_metadata",
        title="排查自动化元数据",
        description="引导模型检查自动化能力、规则详情、动作结构和执行前风险。",
    )
    def troubleshoot_automation_metadata() -> str:
        return (
            "请使用 yeelight_metadata.list_tasks 的 query 参数搜索自动化任务，读取自动化列表、能力 schema 和目标规则详情；"
            "只在 dryRun 模式下生成修复建议，并说明每个建议的副作用等级。"
        )


def register_task_tools(mcp: FastMCP):
    @mcp.tool(
        name=f"{TOOL_NAMESPACE}.list_houses",
        description="列出当前 Authorization 与 Region 可访问的 Pro 家庭。选择后在 execute_task 的 request.context.houseId 中显式传入家庭 ID，即可请求级切换家庭。",
    )
    def list_houses(context: Context) -> Dict[str, Any]:
        try:
            cloud = get_cloud_request_context(context)
            houses = house_resolver.list_houses(cloud)
            return {
                "items": houses,
                "count": len(houses),
                "region": cloud.region,
                "switchHint": "后续调用在 request.context.houseId 中传入目标 houseId；本服务不会保存全局当前家庭。",
            }
        except HouseContextError as error:
            return {"isError": True, "errorMessage": str(error)}

    @mcp.tool(
        name=f"{TOOL_NAMESPACE}.list_groups",
        description="分页返回 Metadata 任务分组摘要，帮助选择 list_tasks 的 group 参数。",
    )
    def list_groups(
        cursor: Annotated[Optional[str], Field(None, description="分页游标；来自上一次返回的 nextCursor")] = None,
        limit: Annotated[int, Field(DEFAULT_GROUP_LIMIT, description="最多返回多少个分组")] = DEFAULT_GROUP_LIMIT,
    ) -> Dict[str, Any]:
        return list_registry_groups(cursor=cursor, limit=limit)

    @mcp.tool(
        name=f"{TOOL_NAMESPACE}.list_tasks",
        description="浏览、搜索或查看 Metadata 任务。传 task 返回单任务详情；传 query 搜索任务和 action；都不传则按 group 分页列出任务摘要。",
    )
    def list_tasks(
        group: Annotated[Optional[str], Field(None, description="可选分组 ID，例如 family_space")] = None,
        query: Annotated[Optional[str], Field(None, description="可选搜索关键词，例如 room、房间、device、automation")] = None,
        task: Annotated[Optional[str], Field(None, description="可选任务 ID，例如 family_space.manage_room；传入后返回该任务详情和 action 摘要")] = None,
        cursor: Annotated[Optional[str], Field(None, description="分页游标；来自上一次返回的 nextCursor")] = None,
        limit: Annotated[int, Field(DEFAULT_TASK_LIMIT, description="最多返回多少个任务")] = DEFAULT_TASK_LIMIT,
    ) -> Dict[str, Any]:
        return list_registry_tasks(group=group, query=query, task=task, cursor=cursor, limit=limit)

    @mcp.tool(
        name=f"{TOOL_NAMESPACE}.list_actions",
        description="列出或筛选 action，支持按 task、group、status、sideEffect、executionMode 过滤。",
    )
    def list_actions(
        task: Annotated[Optional[str], Field(None, description="可选任务 ID，例如 family_space.manage_room")] = None,
        group: Annotated[Optional[str], Field(None, description="可选分组 ID，例如 family_space")] = None,
        status: Annotated[Optional[str], Field(None, description="可选 action 状态，例如 confirmed、candidate")] = None,
        sideEffect: Annotated[Optional[str], Field(None, description="可选副作用等级，例如 S0、S2、S3")] = None,
        executionMode: Annotated[Optional[str], Field(None, description="可选执行模式，例如 cloud_api、manual_assist")] = None,
        cursor: Annotated[Optional[str], Field(None, description="分页游标；来自上一次返回的 nextCursor")] = None,
        limit: Annotated[int, Field(DEFAULT_ACTION_LIMIT, description="最多返回多少个 action")] = DEFAULT_ACTION_LIMIT,
    ) -> Dict[str, Any]:
        return list_registry_actions(task=task, group=group, status=status, side_effect=sideEffect, execution_mode=executionMode, cursor=cursor, limit=limit)

    @mcp.tool(
        name=f"{TOOL_NAMESPACE}.get_action_schema",
        description="返回指定 task/action 的参数 schema、全局 Header、局部 context、payload 和 options 提示。",
    )
    def get_action_schema(
        task: Annotated[str, Field(description="任务 ID，例如 family_space.manage_room")],
        action: Annotated[str, Field(description="动作 ID，例如 create、list、delete 或 get_house_detail")],
    ) -> Dict[str, Any]:
        return get_registry_action_schema(task, action)

    @mcp.tool(
        name=f"{TOOL_NAMESPACE}.execute_task",
        description="校验或执行元数据管理任务。默认 options.dryRun=true 只生成执行计划；真实执行前会校验 schema、候选状态和副作用确认。",
    )
    def execute_task(
        context: Context,
        request: Annotated[TaskExecutionRequest, Field(description="任务执行请求，必须包含 task、action、context、payload 和 options")],
    ) -> Dict[str, Any]:
        try:
            cloud = get_cloud_request_context(context)
            action = registry.get_action(request.task, request.action)
            required_context = action.parameterSchema.contextRequired if action is not None else []
            house_resolver.enrich(request, required_context, cloud)
            return executor.execute(
                request,
                headers={"authorization": cloud.authorization},
                api_base_url=cloud.api_base_url,
            ).model_dump()
        except HouseContextError as error:
            return {"isError": True, "errorMessage": str(error), "code": "HOUSE_CONTEXT_ERROR"}


def register_tools(mcp: FastMCP):
    register_resources(mcp)
    register_prompts(mcp)
    register_task_tools(mcp)
