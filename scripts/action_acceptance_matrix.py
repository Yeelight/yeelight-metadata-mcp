#!/usr/bin/env python3
"""生成 Yeelight Metadata MCP 全 action 自动验收矩阵。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = PROJECT_DIR.parent
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config.config import settings  # noqa: E402
from service.executor import TaskExecutor  # noqa: E402
from service.model import (  # noqa: E402
    ExecutionMode,
    InterfaceStatus,
    SideEffectLevel,
    TaskAction,
    TaskContext,
    TaskExecutionRequest,
    ValidationRequest,
)
from service.registry import MetadataTaskRegistry  # noqa: E402
from utils.http import HttpClient  # noqa: E402


DEFAULT_OUTPUT_JSON = REPO_DIR / ".claude" / "metadata-mcp-action-acceptance-matrix.json"
DEFAULT_OUTPUT_MD = REPO_DIR / ".claude" / "metadata-mcp-action-acceptance-matrix.md"
DEFAULT_LIVE_HOUSE_ID = "200084"
AUTO_CONTEXT_KEYS = {
    "houseId",
    "roomId",
    "deviceId",
    "nodeId",
    "gatewayId",
    "groupId",
    "areaId",
    "sceneId",
    "automationId",
    "runtimeEnv",
}
NON_LIVE_MODES = {
    ExecutionMode.requires_ble,
    ExecutionMode.requires_lan,
    ExecutionMode.requires_mobile_app,
    ExecutionMode.manual_assist,
}
SAFE_LIVE_S0_ACTIONS = {
    "family_space.manage_house": {"list", "list_all_house", "get_house_detail", "get_house_property"},
    "family_space.manage_room": {"list", "list_all_room", "get_room_detail", "search_room"},
    "family_space.manage_area": {"list_area", "list_area_group", "list_all_area_group"},
    "family_space.manage_member_share": {"list", "list_share_history", "get_current_member"},
    "device_onboarding.create_device_slot": {"list_all_device", "list_device_snapshot"},
    "device_onboarding.manage_gateway_onboarding": {"list", "list_gateway_snapshot", "list_gateway_with_stats"},
    "device_management.query_device": {"get_house_snapshot", "list_all_device", "list_device_snapshot", "list_room_snapshot"},
    "device_management.update_device": {"list_device_snapshot"},
    "device_management.manage_device_group": {"list_group_snapshot"},
    "configuration.configure_ai_voice": {"list_voice_product", "list_control_node"},
    "scene_automation.manage_scene": {"list", "list_all_scene", "list_scene_snapshot", "search_scene"},
    "scene_automation.manage_automation": {"list", "list_automation_snapshot", "page_rule"},
    "home_organization.manage_favorite": {"list_all_favorite"},
    "home_organization.manage_sort": {"list_all_favorite", "list_room_scene_sort"},
    "maintenance_account.upgrade_and_stats": {"get_latest_app", "list_ptx_device"},
    "maintenance_account.manage_account": {"get_user_info", "list_third_party_binding"},
}
LIVE_S1_ACTIONS = {
    "configuration.configure_ai_voice": {"get_asr_temp_credential"},
}
ROOM_CRUD_TASK = "family_space.manage_room"


@dataclass
class SeedState:
    house_id: str
    room_id: Optional[str] = None
    device_id: Optional[str] = None
    gateway_id: Optional[str] = None
    group_id: Optional[str] = None
    area_id: Optional[str] = None
    scene_id: Optional[str] = None
    automation_id: Optional[str] = None
    node_id: Optional[str] = None
    discoveries: Dict[str, Any] = field(default_factory=dict)

    def context_value(self, field_name: str) -> Optional[str]:
        return {
            "houseId": self.house_id,
            "roomId": self.room_id,
            "deviceId": self.device_id,
            "gatewayId": self.gateway_id,
            "groupId": self.group_id,
            "areaId": self.area_id,
            "sceneId": self.scene_id,
            "automationId": self.automation_id,
            "nodeId": self.node_id,
        }.get(field_name)


class RedactingHttpClient(HttpClient):
    """HTTP 客户端薄封装，避免验收报告中泄漏敏感 Header。"""

    def __init__(self, timeout: int):
        super().__init__(timeout)
        self.calls: List[Dict[str, Any]] = []

    def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Any] = None,
    ) -> Any:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": params or {},
                "json": json,
                "headers": sorted((headers or {}).keys()),
            }
        )
        return super().request(method, url, headers=headers, params=params, json=json)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_token(args: argparse.Namespace) -> str:
    token = args.access_token or os.getenv("METADATA_MCP_ACCESS_TOKEN", "")
    return token.strip()


def build_headers(token: str) -> Dict[str, str]:
    if not token:
        return {}
    return {"authorization": token if token.startswith("Bearer ") else f"Bearer {token}"}


def action_key(task_id: str, action_id: str) -> str:
    return f"{task_id}/{action_id}"


def model_dump(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return dict(value)


def compact_response(response: Any) -> Any:
    if not isinstance(response, dict):
        return response
    compact: Dict[str, Any] = {}
    for key in ("code", "success", "msg", "message"):
        if key in response:
            compact[key] = response[key]
    data = response.get("data")
    if isinstance(data, list):
        compact["dataType"] = "list"
        compact["dataSize"] = len(data)
        if data:
            compact["dataSampleKeys"] = sorted(data[0].keys()) if isinstance(data[0], dict) else type(data[0]).__name__
    elif isinstance(data, dict):
        compact["dataType"] = "dict"
        compact["dataKeys"] = sorted(data.keys())
    elif data is not None:
        compact["dataType"] = type(data).__name__
    if "error" in response:
        compact["error"] = response["error"]
    return compact or response


def extract_data(result: Any) -> Any:
    response = getattr(result, "response", None)
    if isinstance(response, dict):
        return response.get("data")
    normalized = getattr(result, "normalizedResponse", None)
    if isinstance(normalized, dict):
        return normalized.get("data")
    return None


def first_id(items: Iterable[Any], keys: Iterable[str]) -> Optional[str]:
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in keys:
            value = item.get(key)
            if value not in (None, ""):
                return str(value)
    return None


def extract_created_id(data: Any, keys: Iterable[str]) -> Optional[str]:
    if isinstance(data, (str, int)):
        value = str(data).strip()
        return value or None
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if value not in (None, ""):
                return str(value)
        for value in data.values():
            nested = extract_created_id(value, keys)
            if nested:
                return nested
    return None


def find_item_id_by_name(items: Iterable[Any], name: str, keys: Iterable[str]) -> Optional[str]:
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("name") != name:
            continue
        for key in keys:
            value = item.get(key)
            if value not in (None, ""):
                return str(value)
    return None


def find_nested_list(data: Any, preferred_keys: Iterable[str]) -> List[Any]:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in preferred_keys:
        value = data.get(key)
        if isinstance(value, list):
            return value
    for value in data.values():
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = find_nested_list(value, preferred_keys)
            if nested:
                return nested
    return []


def build_context(required_fields: List[str], seeds: SeedState, runtime_env: str = "local") -> Dict[str, Any]:
    context: Dict[str, Any] = {"runtimeEnv": runtime_env}
    for field_name in required_fields:
        value = seeds.context_value(field_name)
        if value is not None:
            context[field_name] = value
        elif field_name == "houseId":
            context[field_name] = seeds.house_id
        else:
            context[field_name] = f"metadata_mcp_{field_name}_placeholder"
    if "houseId" not in context and any(field in required_fields for field in ("roomId", "gatewayId", "areaId", "sceneId", "automationId")):
        context["houseId"] = seeds.house_id
    return context


def sample_payload_for_field(field_name: str, seeds: SeedState, action: TaskAction) -> Any:
    if field_name in {"name", "target"}:
        return f"METADATA_MCP_验收_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if field_name in {"description", "prompt", "fuzzyName"}:
        return "METADATA_MCP_验收"
    if field_name in {"pageNo"}:
        return 1
    if field_name in {"pageSize"}:
        return 20
    if field_name in {"enabled", "clearMac"}:
        return True
    if field_name in {"areaIds", "deviceIds", "sceneIds", "roomIds", "imageUrls"}:
        seed_value = {
            "areaIds": seeds.area_id,
            "deviceIds": seeds.device_id,
            "sceneIds": seeds.scene_id,
            "roomIds": seeds.room_id,
        }.get(field_name)
        return [seed_value] if seed_value else []
    if field_name in {"items", "devices", "rooms", "actions", "conditions", "events", "names"}:
        if field_name == "rooms":
            return [{"name": f"METADATA_MCP_验收_{datetime.now().strftime('%H%M%S')}"}]
        if field_name == "names" and seeds.device_id:
            return [{"deviceId": seeds.device_id, "name": "METADATA_MCP_验收设备"}]
        return []
    if field_name in {"properties", "attributes", "config", "profile", "layout", "event", "storageValue"}:
        return {}
    if field_name == "role":
        return "member"
    if field_name == "memberId":
        return "metadata_mcp_member_placeholder"
    if field_name == "targetUser":
        return "metadata_mcp_user_placeholder"
    if field_name == "toUid":
        return "122390"
    if field_name == "barcode":
        return "metadata_mcp_barcode_placeholder"
    if field_name == "shareId":
        return "metadata_mcp_share_placeholder"
    if field_name == "manualCode":
        return "metadata_mcp_manual_code_placeholder"
    if field_name == "qrCode":
        return "metadata_mcp_qr_code_placeholder"
    if field_name == "qrCodeId":
        return "metadata_mcp_qrcode_placeholder"
    if field_name == "source":
        return "apple"
    if field_name == "thirdPartyToken":
        return "metadata_mcp_third_party_token_placeholder"
    if field_name == "storageKey":
        return "metadata_mcp_acceptance"
    if field_name == "imageBytes":
        return ""
    if field_name == "pid":
        return "yeelink.light.placeholder"
    if field_name == "type":
        return 1
    if field_name == "osType":
        return 1
    if field_name == "uid":
        return 122390
    if field_name == "languageCode":
        return "zh_CN"
    if field_name == "key":
        return seeds.gateway_id or "metadata_mcp_gateway_placeholder"
    if field_name == "theDl":
        return 1
    if field_name == "deviceId":
        return seeds.device_id or "metadata_mcp_device_placeholder"
    if field_name == "nodeType":
        return "device"
    if field_name == "resType":
        return "room"
    if field_name == "resId":
        return seeds.room_id or seeds.house_id
    if field_name == "startTime":
        return 0
    if field_name == "endTime":
        return 4102444800000
    if field_name == "index":
        return 1
    if field_name == "buttonEventId":
        return "metadata_mcp_button_event_placeholder"
    if field_name == "type":
        return "room"
    if field_name == "url":
        return "https://yeelight.com"

    property_schema = action.parameterSchema.payloadProperties.get(field_name, {})
    field_type = property_schema.get("type")
    if field_type == "integer":
        return 1
    if field_type == "boolean":
        return True
    if field_type == "array":
        return []
    if field_type == "object":
        return {}
    return f"metadata_mcp_{field_name}_placeholder"


def build_payload(required_fields: List[str], seeds: SeedState, action: TaskAction, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = {field_name: sample_payload_for_field(field_name, seeds, action) for field_name in required_fields}
    if extra:
        payload.update(extra)
    return payload


def request_for_action(
    task_id: str,
    action: TaskAction,
    seeds: SeedState,
    dry_run: bool,
    allow_candidate: bool,
    confirm_side_effect: bool,
    payload_extra: Optional[Dict[str, Any]] = None,
) -> TaskExecutionRequest:
    schema = action.parameterSchema
    context = build_context(schema.contextRequired, seeds)
    payload = build_payload(schema.payloadRequired, seeds, action, payload_extra)
    return TaskExecutionRequest(
        task=task_id,
        action=action.id,
        context=TaskContext(**context),
        payload=payload,
        options={
            "dryRun": dry_run,
            "allowCandidate": allow_candidate,
            "confirmSideEffect": confirm_side_effect,
            "reason": "Metadata MCP 自动化验收",
        },
    )


def execute_action(
    executor: TaskExecutor,
    task_id: str,
    action: TaskAction,
    seeds: SeedState,
    headers: Dict[str, str],
    dry_run: bool,
    allow_candidate: bool = True,
    confirm_side_effect: bool = False,
    payload_extra: Optional[Dict[str, Any]] = None,
) -> Any:
    request = request_for_action(task_id, action, seeds, dry_run, allow_candidate, confirm_side_effect, payload_extra)
    return executor.execute(request, headers=headers)


def discover_seeds(registry: MetadataTaskRegistry, executor: TaskExecutor, seeds: SeedState, headers: Dict[str, str], live: bool) -> None:
    if not live or not headers:
        return

    house_task = "family_space.manage_house"
    house_action = registry.get_action(house_task, "list")
    if house_action is not None:
        result = execute_action(executor, house_task, house_action, seeds, headers, dry_run=False, allow_candidate=True)
        seeds.discoveries["house.list"] = compact_response(getattr(result, "response", None))
        houses = find_nested_list(extract_data(result), ("list", "records", "items", "houses"))
        if houses:
            matched = next((item for item in houses if isinstance(item, dict) and str(item.get("id") or item.get("houseId")) == seeds.house_id), None)
            selected = matched or houses[0]
            if isinstance(selected, dict):
                seeds.house_id = str(selected.get("id") or selected.get("houseId") or seeds.house_id)
                seeds.discoveries["selectedHouse"] = {
                    "houseId": seeds.house_id,
                    "name": selected.get("name"),
                }

    room_action = registry.get_action(ROOM_CRUD_TASK, "list")
    if room_action is not None:
        result = execute_action(executor, ROOM_CRUD_TASK, room_action, seeds, headers, dry_run=False, allow_candidate=True)
        seeds.discoveries["room.list"] = compact_response(getattr(result, "response", None))
        rooms = find_nested_list(extract_data(result), ("list", "records", "items", "rooms"))
        seeds.room_id = first_id(rooms, ("id", "roomId"))

    for task_id, action_id, discovery_key, id_keys in (
        ("device_management.query_device", "list_device_snapshot", "device.snapshot", ("id", "deviceId", "did")),
        ("device_onboarding.manage_gateway_onboarding", "list_gateway_snapshot", "gateway.snapshot", ("id", "gatewayId", "deviceId")),
        ("device_management.manage_device_group", "list_group_snapshot", "group.snapshot", ("id", "groupId")),
        ("scene_automation.manage_scene", "list_scene_snapshot", "scene.snapshot", ("id", "sceneId")),
        ("scene_automation.manage_automation", "list_automation_snapshot", "automation.snapshot", ("id", "automationId")),
    ):
        action = registry.get_action(task_id, action_id)
        if action is None:
            continue
        result = execute_action(executor, task_id, action, seeds, headers, dry_run=False, allow_candidate=True)
        seeds.discoveries[discovery_key] = compact_response(getattr(result, "response", None))
        items = find_nested_list(extract_data(result), ("list", "records", "items", "data"))
        discovered_id = first_id(items, id_keys)
        if discovery_key.startswith("device") and discovered_id:
            seeds.device_id = discovered_id
            seeds.node_id = discovered_id
        elif discovery_key.startswith("gateway") and discovered_id:
            seeds.gateway_id = discovered_id
        elif discovery_key.startswith("group") and discovered_id:
            seeds.group_id = discovered_id
        elif discovery_key.startswith("scene") and discovered_id:
            seeds.scene_id = discovered_id
        elif discovery_key.startswith("automation") and discovered_id:
            seeds.automation_id = discovered_id


def should_live_call(task_id: str, action: TaskAction, seeds: SeedState, include_s1: bool) -> Tuple[bool, str]:
    if not action.directExecutionSupported or action.executionMode in NON_LIVE_MODES:
        return False, f"{action.executionMode.value} 不支持在线 MCP 直连实调"
    missing = [field_name for field_name in action.parameterSchema.contextRequired if field_name in AUTO_CONTEXT_KEYS and seeds.context_value(field_name) is None]
    if missing:
        return False, f"缺少可自动发现的上下文: {', '.join(missing)}"
    if action.sideEffect == SideEffectLevel.S0:
        if action.id in SAFE_LIVE_S0_ACTIONS.get(task_id, set()):
            return True, ""
        return False, "S0 查询需要真实业务种子或接口参数，本轮仅 dryRun 验收"
    if include_s1 and action.sideEffect == SideEffectLevel.S1 and action.id in LIVE_S1_ACTIONS.get(task_id, set()):
        return True, ""
    return False, f"{action.sideEffect.value} 非白名单动作默认不做真实调用"


def matrix_row(
    registry: MetadataTaskRegistry,
    executor: TaskExecutor,
    task_id: str,
    action: TaskAction,
    seeds: SeedState,
    headers: Dict[str, str],
    live: bool,
    include_s1: bool,
) -> Dict[str, Any]:
    schema = action.parameterSchema
    request = request_for_action(
        task_id,
        action,
        seeds,
        dry_run=True,
        allow_candidate=True,
        confirm_side_effect=False,
    )
    validation = executor.validate(
        ValidationRequest(
            task=request.task,
            action=request.action,
            context=request.context,
            payload=request.payload,
            options=request.options,
        )
    )
    dry_run_result = executor.execute(request, headers={})
    plan = dry_run_result.plan
    row: Dict[str, Any] = {
        "task": task_id,
        "action": action.id,
        "title": action.title,
        "sideEffect": action.sideEffect.value,
        "executionMode": action.executionMode.value,
        "status": action.status.value,
        "directExecutionSupported": action.directExecutionSupported,
        "interfaces": [ref.operation for ref in action.interfaceRefs],
        "httpMethod": plan.httpRequest.get("method") if plan.httpRequest else None,
        "urlPattern": plan.httpRequest.get("url") if plan.httpRequest else None,
        "contextRequired": list(schema.contextRequired),
        "payloadRequired": list(schema.payloadRequired),
        "validationOk": validation.valid,
        "validationCode": validation.code,
        "validationErrors": validation.errors,
        "validationWarnings": validation.warnings,
        "dryRunOk": dry_run_result.ok and dry_run_result.dryRun,
        "dryRunCode": dry_run_result.code,
        "dryRunMessage": dry_run_result.message,
        "guidance": plan.guidance,
        "liveOk": None,
        "liveCode": None,
        "liveMessage": None,
        "liveResponse": None,
        "skippedLiveReason": "",
    }
    if not validation.valid or not row["dryRunOk"]:
        row["skippedLiveReason"] = "基础 validation/dryRun 未通过，停止真实调用"
        return row
    if not live:
        row["skippedLiveReason"] = "未开启 --live，仅执行全量 validation + dryRun"
        return row
    allowed, reason = should_live_call(task_id, action, seeds, include_s1)
    if not allowed:
        row["skippedLiveReason"] = reason
        return row

    live_result = execute_action(
        executor,
        task_id,
        action,
        seeds,
        headers,
        dry_run=False,
        allow_candidate=True,
        confirm_side_effect=False,
    )
    row["liveOk"] = live_result.ok
    row["liveCode"] = live_result.code
    row["liveMessage"] = live_result.message
    row["liveResponse"] = compact_response(live_result.response)
    return row


def room_crud_acceptance(
    registry: MetadataTaskRegistry,
    executor: TaskExecutor,
    seeds: SeedState,
    headers: Dict[str, str],
    live: bool,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "enabled": live and bool(headers),
        "task": ROOM_CRUD_TASK,
        "steps": [],
        "createdRoomId": None,
        "cleanupOk": None,
        "ok": None,
        "skippedReason": "",
    }
    if not live:
        result["skippedReason"] = "未开启 --live"
        result["ok"] = True
        return result
    if not headers:
        result["skippedReason"] = "未提供 METADATA_MCP_ACCESS_TOKEN"
        result["ok"] = True
        return result

    original_room_id = seeds.room_id
    room_name = f"METADATA_MCP_矩阵验收_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    updated_name = f"{room_name}_已更新"
    created_room_id: Optional[str] = None

    def add_step(name: str, step_result: Any) -> None:
        result["steps"].append(
            {
                "name": name,
                "ok": bool(getattr(step_result, "ok", False)),
                "code": getattr(step_result, "code", None),
                "message": getattr(step_result, "message", None),
                "response": compact_response(getattr(step_result, "response", None)),
            }
        )

    try:
        create_action = registry.get_action(ROOM_CRUD_TASK, "create")
        if create_action is None:
            raise RuntimeError("缺少 room.create action")
        create_result = execute_action(
            executor,
            ROOM_CRUD_TASK,
            create_action,
            seeds,
            headers,
            dry_run=False,
            allow_candidate=True,
            confirm_side_effect=True,
            payload_extra={"name": room_name},
        )
        add_step("room.create", create_result)
        if not create_result.ok:
            raise RuntimeError("room.create 失败")
        data = extract_data(create_result)
        created_room_id = extract_created_id(data, ("id", "roomId"))
        if not created_room_id:
            list_action = registry.get_action(ROOM_CRUD_TASK, "list")
            if list_action is not None:
                list_result = execute_action(executor, ROOM_CRUD_TASK, list_action, seeds, headers, dry_run=False, allow_candidate=True)
                add_step("room.list.find_created", list_result)
                rooms = find_nested_list(extract_data(list_result), ("list", "records", "items", "rooms"))
                created_room_id = find_item_id_by_name(rooms, room_name, ("id", "roomId"))
        if not created_room_id:
            raise RuntimeError("room.create 响应中未找到 roomId，且列表反查失败")
        result["createdRoomId"] = created_room_id
        seeds.room_id = created_room_id

        for action_id, payload_extra in (
            ("get_room_detail", None),
            ("update", {"name": updated_name}),
            ("delete", None),
        ):
            action = registry.get_action(ROOM_CRUD_TASK, action_id)
            if action is None:
                raise RuntimeError(f"缺少 room.{action_id} action")
            step_result = execute_action(
                executor,
                ROOM_CRUD_TASK,
                action,
                seeds,
                headers,
                dry_run=False,
                allow_candidate=True,
                confirm_side_effect=action.sideEffect in {SideEffectLevel.S2, SideEffectLevel.S3},
                payload_extra=payload_extra,
            )
            add_step(f"room.{action_id}", step_result)
            if not step_result.ok:
                raise RuntimeError(f"room.{action_id} 失败")
            if action_id == "delete":
                result["cleanupOk"] = True
                created_room_id = None

        list_action = registry.get_action(ROOM_CRUD_TASK, "list")
        if list_action is not None:
            list_result = execute_action(executor, ROOM_CRUD_TASK, list_action, seeds, headers, dry_run=False, allow_candidate=True)
            add_step("room.list.after_cleanup", list_result)
            rooms = find_nested_list(extract_data(list_result), ("list", "records", "items", "rooms"))
            leftovers = [item for item in rooms if isinstance(item, dict) and str(item.get("id") or item.get("roomId")) == result["createdRoomId"]]
            result["cleanupOk"] = len(leftovers) == 0
        result["ok"] = all(step["ok"] for step in result["steps"]) and result["cleanupOk"] is True
        return result
    except Exception as exc:
        result["ok"] = False
        result["error"] = str(exc)
        return result
    finally:
        if created_room_id:
            seeds.room_id = created_room_id
            delete_action = registry.get_action(ROOM_CRUD_TASK, "delete")
            if delete_action is not None:
                cleanup = execute_action(
                    executor,
                    ROOM_CRUD_TASK,
                    delete_action,
                    seeds,
                    headers,
                    dry_run=False,
                    allow_candidate=True,
                    confirm_side_effect=True,
                )
                result["steps"].append(
                    {
                        "name": "room.delete.finally_cleanup",
                        "ok": bool(getattr(cleanup, "ok", False)),
                        "code": getattr(cleanup, "code", None),
                        "message": getattr(cleanup, "message", None),
                        "response": compact_response(getattr(cleanup, "response", None)),
                    }
                )
                result["cleanupOk"] = bool(getattr(cleanup, "ok", False))
        seeds.room_id = original_room_id


def summarize(rows: List[Dict[str, Any]], room_crud: Dict[str, Any]) -> Dict[str, Any]:
    summary = {
        "actions": len(rows),
        "validationOk": sum(1 for row in rows if row["validationOk"]),
        "dryRunOk": sum(1 for row in rows if row["dryRunOk"]),
        "liveAttempted": sum(1 for row in rows if row["liveOk"] is not None),
        "liveOk": sum(1 for row in rows if row["liveOk"] is True),
        "byStatus": dict(Counter(row["status"] for row in rows)),
        "bySideEffect": dict(Counter(row["sideEffect"] for row in rows)),
        "byExecutionMode": dict(Counter(row["executionMode"] for row in rows)),
        "directExecutionSupported": dict(Counter(str(row["directExecutionSupported"]) for row in rows)),
        "roomCrudOk": room_crud.get("ok"),
    }
    summary["registryFailed"] = [
        action_key(row["task"], row["action"])
        for row in rows
        if not row["validationOk"] or not row["dryRunOk"]
    ]
    summary["liveFailed"] = [
        action_key(row["task"], row["action"])
        for row in rows
        if row["liveOk"] is False
    ]
    return summary


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: Path, payload: Dict[str, Any]) -> None:
    summary = payload["summary"]
    rows = payload["rows"]
    registry_failed = summary["registryFailed"]
    live_failed = summary["liveFailed"]
    live_rows = [row for row in rows if row["liveOk"] is not None]
    skipped_reasons = Counter(row["skippedLiveReason"] for row in rows if row["skippedLiveReason"])
    lines = [
        "# Metadata MCP 全 action 自动验收矩阵",
        "",
        f"生成时间：{payload['generatedAt']}",
        "",
        "## 结论",
        "",
        f"- action 总数：`{summary['actions']}`",
        f"- validation 通过：`{summary['validationOk']}/{summary['actions']}`",
        f"- dryRun 通过：`{summary['dryRunOk']}/{summary['actions']}`",
        f"- 真实调用尝试：`{summary['liveAttempted']}`，成功：`{summary['liveOk']}`",
        f"- 房间可回收闭环：`{'通过' if summary['roomCrudOk'] else '未通过'}`",
        f"- 注册表失败项：`{len(registry_failed)}`",
        f"- 真实接口异常项：`{len(live_failed)}`",
        "",
        "## 分布",
        "",
        f"- 状态分布：`{summary['byStatus']}`",
        f"- 副作用分布：`{summary['bySideEffect']}`",
        f"- 执行模式分布：`{summary['byExecutionMode']}`",
        f"- 直连支持分布：`{summary['directExecutionSupported']}`",
        "",
        "## 真实调用策略",
        "",
        "- 全量 action 均执行 `execute_task(dryRun=true)`，覆盖 schema 校验与执行计划生成。",
        "- 真实云端调用仅覆盖白名单 S0/S1 查询动作，以及可回收的房间 create/update/delete 闭环。",
        "- S2/S3 默认不真实调用，除房间临时对象闭环外，避免解绑、转移、删除真实设备、账号绑定等不可逆副作用。",
        "- `requires_ble`、`requires_lan`、`requires_mobile_app`、`manual_assist` 只验收指引和 directExecutionSupported 策略。",
        "",
        "## 真实调用明细",
        "",
    ]
    if live_rows:
        lines.extend(["| task/action | 结果 | code | message |", "| --- | --- | --- | --- |"])
        for row in live_rows:
            lines.append(
                f"| `{row['task']}/{row['action']}` | {'通过' if row['liveOk'] else '失败'} | `{row['liveCode']}` | {row['liveMessage'] or ''} |"
            )
    else:
        lines.append("本次未开启真实调用。")
    lines.extend(["", "## 跳过真实调用原因 Top 10", "", "| 原因 | 数量 |", "| --- | ---: |"])
    for reason, count in skipped_reasons.most_common(10):
        lines.append(f"| {reason} | {count} |")
    lines.extend(["", "## 注册表失败项", ""])
    if registry_failed:
        for item in registry_failed:
            lines.append(f"- `{item}`")
    else:
        lines.append("无。")
    lines.extend(["", "## 真实接口异常项", ""])
    if live_failed:
        for item in live_failed:
            lines.append(f"- `{item}`")
    else:
        lines.append("无。")
    lines.extend(["", "## 房间闭环", "", f"```json\n{json.dumps(payload['roomCrud'], ensure_ascii=False, indent=2)}\n```", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 Yeelight Metadata MCP 全 action 自动验收矩阵")
    parser.add_argument("--live", action="store_true", help="开启 dev 云端真实调用白名单")
    parser.add_argument("--include-s1-live", action="store_true", help="允许白名单 S1 诊断类动作真实调用")
    parser.add_argument("--house-id", default=os.getenv("METADATA_MCP_ACCEPTANCE_HOUSE_ID", DEFAULT_LIVE_HOUSE_ID), help="验收家庭 ID")
    parser.add_argument("--access-token", default="", help="访问 token。建议使用 METADATA_MCP_ACCESS_TOKEN 环境变量，避免 shell 历史记录泄漏")
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON), help="JSON 输出路径")
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD), help="Markdown 输出路径")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = read_token(args)
    headers = build_headers(token)
    registry = MetadataTaskRegistry()
    http_client = RedactingHttpClient(settings.HTTP_TIMEOUT)
    executor = TaskExecutor(registry, http_client)
    seeds = SeedState(house_id=str(args.house_id))

    live = bool(args.live and headers)
    discover_seeds(registry, executor, seeds, headers, live)

    rows: List[Dict[str, Any]] = []
    for task in registry.list_tasks():
        for action in task.actions:
            rows.append(matrix_row(registry, executor, task.id, action, seeds, headers, live, args.include_s1_live))

    room_crud = room_crud_acceptance(registry, executor, seeds, headers, live)
    payload = {
        "generatedAt": now_iso(),
        "settings": {
            "apiBaseUrl": settings.API_BASE_URL,
            "runtimeEnv": settings.RUNTIME_ENV,
            "live": live,
            "includeS1Live": bool(args.include_s1_live),
            "houseId": seeds.house_id,
            "tokenProvided": bool(headers),
        },
        "seeds": {
            "houseId": seeds.house_id,
            "roomId": seeds.room_id,
            "deviceId": seeds.device_id,
            "gatewayId": seeds.gateway_id,
            "groupId": seeds.group_id,
            "areaId": seeds.area_id,
            "sceneId": seeds.scene_id,
            "automationId": seeds.automation_id,
            "nodeId": seeds.node_id,
            "discoveries": seeds.discoveries,
        },
        "summary": summarize(rows, room_crud),
        "roomCrud": room_crud,
        "rows": rows,
    }
    write_json(Path(args.output_json), payload)
    write_markdown(Path(args.output_md), payload)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0 if not payload["summary"]["registryFailed"] and payload["summary"].get("roomCrudOk") is not False else 1


if __name__ == "__main__":
    raise SystemExit(main())
