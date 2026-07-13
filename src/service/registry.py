import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from config.config import settings
from service.action_specs import DEV_CONFIRMED_OPERATIONS, OPERATION_ACTION_OVERRIDES, OPERATION_INTERFACE_OVERRIDES, get_operation_schema
from service.model import (
    ActionSchema,
    ExecutionMode,
    InterfaceRef,
    InterfaceStatus,
    SideEffectLevel,
    TaskAction,
    TaskCard,
    TaskGroup,
)


READ_KEYWORDS = {
    "list",
    "list_all",
    "get",
    "get_detail",
    "get_info",
    "get_by_pid",
    "query",
    "search",
    "fuzzy",
    "page",
    "exists",
    "recommend_device",
    "recommend_scene",
    "recommend_device_name",
    "recommend_scene_name",
    "get_house_snapshot",
    "list_device_snapshot",
    "list_room_snapshot",
    "list_group_snapshot",
    "list_gateway_snapshot",
    "list_scene_snapshot",
    "list_automation_snapshot",
    "list_relation_device",
    "list_ptx_device",
    "list_ptx_ota_update",
    "get_latest_app",
    "get_electricity_stat",
}
CREATE_KEYWORDS = {
    "create",
    "insert",
    "batch_create",
    "batch_insert",
    "apply",
    "pre_bind",
    "send_invite",
    "accept",
    "upload_image",
    "text_to_image",
}
UPDATE_KEYWORDS = {"update", "modify", "set", "configure", "enable", "disable", "reset", "batch_update", "add"}
DELETE_KEYWORDS = {"delete", "remove", "unbind", "quit", "transfer", "login", "bind", "unbind_and_clear_mac", "delete_images"}
DIAGNOSE_KEYWORDS = {"diagnose", "download", "poll", "progress", "get_progress", "cancel", "test"}

ACTION_TITLE_MAP = {
    "list": "查询列表",
    "list_all": "查询全部",
    "get": "查询",
    "get_detail": "查询详情",
    "get_info": "查询信息",
    "search": "搜索",
    "fuzzy_search": "模糊搜索",
    "create": "创建",
    "batch_create": "批量创建",
    "update": "更新",
    "configure": "配置",
    "delete": "删除",
    "delete_device": "删除设备",
    "delete_gateway": "删除网关",
    "delete_area": "删除区域",
    "delete_area_group": "删除区域分组",
    "create_area": "创建区域",
    "create_area_group": "创建区域分组",
    "update_area": "更新区域",
    "update_area_group": "更新区域分组",
    "list_area": "查询区域",
    "list_area_group": "查询区域分组",
    "remove": "移除",
    "unbind": "解绑",
    "transfer": "转移",
    "accept": "接受",
    "send_invite": "发送邀请",
    "apply": "申请",
    "get_progress": "查询进度",
    "cancel": "取消",
    "enable": "启用",
    "disable": "禁用",
    "test": "测试",
    "batch_insert": "批量新增",
    "batch_update": "批量更新",
    "batch_delete": "批量删除",
    "upload_image": "上传图片",
    "delete_images": "删除图片",
    "text_to_image": "文字生成图片",
    "download": "下载",
    "manual_assist": "人工辅助",
    "accept_share_barcode": "接受扫码分享",
    "accept_share_invite": "接受分享邀请",
    "add_sort": "新增排序",
    "apply_pairing_code": "申请 Matter 配对码",
    "apply_secondary_pairing": "申请二次配对",
    "batch_create_device_slot": "批量创建设备槽位",
    "batch_create_room": "批量创建房间",
    "batch_delete_favorite": "批量删除收藏",
    "batch_insert_favorite": "批量新增收藏",
    "batch_update_event": "批量更新按键动作",
    "batch_update_favorite": "批量更新收藏",
    "batch_update_name": "批量更新名称",
    "bind_third_party": "绑定三方账号",
    "cancel_secondary_pairing": "取消二次配对",
    "check_account_exists": "检查账号",
    "check_scan_qrcode": "检查扫码二维码",
    "check_yeelight_connectivity": "检查 Yeelight 连通性",
    "confirm_scan_login": "确认扫码登录",
    "create_scan_qrcode": "创建扫码登录二维码",
    "create_share_barcode": "生成家庭分享码",
    "disable_rule": "禁用自动化",
    "discover_sonos_group": "发现 Sonos 分组",
    "download_ptx_ota_file": "下载 PTX OTA 文件",
    "enable_rule": "启用自动化",
    "fuzzy_search_area_group": "搜索区域分组",
    "generate_third_party_state": "生成三方登录 State",
    "get_asr_temp_credential": "获取 ASR 临时凭证",
    "get_by_pid": "按 PID 查询物模型",
    "get_current_member": "查询当前成员",
    "get_detail_area": "查询区域详情",
    "get_device_detail": "查询设备详情",
    "get_electricity_stat": "查询用电统计",
    "get_gateway_detail": "查询网关详情",
    "get_gateway_thread_info": "查询网关 Thread 信息",
    "get_group_detail": "查询设备组详情",
    "get_house_detail": "查询家庭详情",
    "get_house_property": "查询家庭属性",
    "get_house_snapshot": "查询家庭物模型概况",
    "get_latest_app": "查询 APP 最新版本",
    "get_multi_detail": "查询多键旋钮详情",
    "get_room_detail": "查询房间详情",
    "get_scene_detail": "查询情景详情",
    "get_secondary_pairing_progress": "查询二次配对进度",
    "get_single_detail": "查询旋钮详情",
    "get_storage": "查询设备存储",
    "get_user_info": "查询用户信息",
    "list_all_area_group": "查询全部区域分组",
    "list_all_device": "查询全部设备",
    "list_all_favorite": "查询全部收藏",
    "list_all_house": "查询全部家庭",
    "list_all_room": "查询全部房间",
    "list_all_scene": "查询全部情景",
    "list_automation_snapshot": "查询自动化快照",
    "list_capability": "查询自动化能力",
    "list_capability_v2": "查询自动化能力 V2",
    "list_control_node": "查询语音可控节点",
    "list_device_snapshot": "查询设备快照",
    "list_gateway_snapshot": "查询网关快照",
    "list_gateway_with_stats": "查询网关统计",
    "list_group_snapshot": "查询设备组快照",
    "list_ptx_device": "查询 D 寸屏设备",
    "list_ptx_ota_update": "查询 PTX OTA 更新",
    "list_relation_device": "按资源查询设备",
    "list_room_scene_sort": "查询房间情景排序",
    "list_room_snapshot": "查询房间快照",
    "list_scene_snapshot": "查询情景快照",
    "list_share_history": "查询分享历史",
    "list_third_party_binding": "查询三方绑定",
    "list_voice_product": "查询语音 PID 列表",
    "mark_qrcode_scanned": "标记二维码已扫描",
    "page_rule": "分页查询自动化",
    "pre_bind_screen": "预绑定 Wi-Fi 屏",
    "quit_house": "退出家庭",
    "recommend_device_name": "推荐设备名称",
    "recommend_scene_name": "推荐情景名称",
    "reset_event": "重置按键动作",
    "reset_multi": "重置多键旋钮",
    "reset_single": "重置旋钮",
    "scan_login": "扫码登录",
    "search_room": "搜索房间",
    "search_scene": "搜索情景",
    "send_share_invite": "发送分享邀请",
    "set_storage": "写入设备存储",
    "sync_lan_gateway_nodes": "同步局域网关节点",
    "test_rule": "测试自动化",
    "third_party_login": "三方登录",
    "transfer_house": "转移家庭管理员",
    "unbind_and_clear_mac": "解绑并清除 MAC",
    "unbind_third_party": "解绑三方账号",
    "update_control_node": "更新语音可控节点",
    "update_device_attribute": "更新设备属性",
    "update_event": "更新按键动作",
    "update_group_devices": "更新设备组成员",
    "update_house_property": "更新家庭属性",
    "update_layout": "更新面板布局",
    "update_member_role": "更新成员角色",
    "update_multi": "更新多键旋钮",
    "update_room_area": "更新房间区域",
    "update_single": "更新旋钮",
    "update_user_info": "更新用户信息",
    "upload_image": "上传图片",
}

FIELD_TYPE_HINTS = {
    "houseId": "string",
    "roomId": "string",
    "deviceId": "string",
    "nodeId": "string",
    "userId": "string",
    "gatewayId": "string",
    "sceneId": "string",
    "automationId": "string",
    "groupId": "string",
    "memberId": "string",
    "name": "string",
    "description": "string",
    "pageNo": "integer",
    "pageSize": "integer",
    "timeout": "integer",
    "enabled": "boolean",
    "clearMac": "boolean",
    "items": "array",
    "deviceIds": "array",
    "sceneIds": "array",
    "roomIds": "array",
    "events": "array",
    "actions": "array",
    "conditions": "array",
    "properties": "object",
    "attributes": "object",
    "config": "object",
    "profile": "object",
}

PATH_PARAM_ALIASES = {
    "deviceID": "deviceId",
    "slotId": "deviceId",
}

RESOURCE_ID_ALIASES = {
    "automation": "automationId",
    "legacy_rule": "automationId",
    "rule": "automationId",
    "scene": "sceneId",
    "room": "roomId",
    "house": "houseId",
    "gateway": "gatewayId",
    "area": "areaId",
    "mesh_group": "groupId",
    "device_group": "groupId",
    "share": "shareId",
    "group": "groupId",
}

KNOWN_CONTEXT_FIELDS = ("houseId", "roomId", "deviceId", "nodeId", "userId", "gatewayId")
RESOURCE_CONTEXT_FIELDS = {
    "gateway": {"houseId", "gatewayId"},
    "device": {"deviceId"},
    "panel": {"deviceId"},
    "knob": {"deviceId"},
    "room": {"houseId", "roomId"},
    "area": {"houseId", "areaId"},
    "area_group": {"houseId", "groupId"},
    "house": {"houseId"},
    "scene": {"houseId", "sceneId"},
    "automation": {"houseId", "automationId"},
}


@dataclass(frozen=True)
class RawInterface:
    status: InterfaceStatus
    operation: str
    method: Optional[str]
    path: Optional[str]
    runtime_path: Optional[str]
    title: Optional[str]
    source_type: Optional[str]
    yapi_status: Optional[str]


class MetadataTaskRegistry:
    def __init__(self, resource_dir: Optional[str] = None):
        self.resource_dir = resource_dir or settings.RESOURCE_DIR
        self._groups: List[TaskGroup] = []
        self._tasks: Dict[str, TaskCard] = {}
        self._interfaces: Dict[str, RawInterface] = {}
        self._load()

    def list_groups(self) -> List[TaskGroup]:
        return self._groups

    def list_tasks(self) -> List[TaskCard]:
        return list(self._tasks.values())

    def get_task(self, task_id: str) -> Optional[TaskCard]:
        return self._tasks.get(task_id)

    def get_action(self, task_id: str, action_id: str) -> Optional[TaskAction]:
        task = self.get_task(task_id)
        if task is None:
            return None
        return next((action for action in task.actions if action.id == action_id), None)

    def get_schema(self, task_id: str, action_id: str) -> Optional[ActionSchema]:
        action = self.get_action(task_id, action_id)
        if action is None:
            return None
        return action.parameterSchema

    def _load(self) -> None:
        task_map = self._read_json("metadata-mcp-user-task-map.json")
        self._interfaces = self._load_interfaces()
        raw_groups = task_map.get("groups", [])
        raw_tasks = task_map.get("tasks", [])

        tasks_by_group: Dict[str, List[Dict[str, Any]]] = {}
        cards: Dict[str, TaskCard] = {}
        for raw_task in raw_tasks:
            card = self._build_task_card(raw_task)
            cards[card.id] = card
            tasks_by_group.setdefault(card.group, []).append(
                {
                    "id": card.id,
                    "title": card.title,
                    "summary": card.summary,
                    "priority": card.priority,
                    "maxSideEffect": card.maxSideEffect.value,
                    "actions": [action.id for action in card.actions],
                }
            )

        self._groups = [
            TaskGroup(
                id=group["id"],
                title=group["title"],
                summary=group["summary"],
                tasks=tasks_by_group.get(group["id"], []),
            )
            for group in raw_groups
        ]
        self._tasks = cards

    def _read_json(self, filename: str) -> Dict[str, Any]:
        path = os.path.join(self.resource_dir, filename)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_interfaces(self) -> Dict[str, RawInterface]:
        interfaces: Dict[str, RawInterface] = {}
        for item in self._read_json("metadata-mcp-interface-tree.json").get("interfaces", []):
            operation = item["operation"]
            interfaces[operation] = self._to_raw_interface(InterfaceStatus.confirmed, operation, item)

        for item in self._read_json("metadata-mcp-missing-candidate-interface-tree.json").get("interfaces", []):
            operation = item["operation"]
            interfaces.setdefault(operation, self._to_raw_interface(InterfaceStatus.candidate, operation, item))
        return interfaces

    def _to_raw_interface(self, status: InterfaceStatus, operation: str, item: Dict[str, Any]) -> RawInterface:
        override = OPERATION_INTERFACE_OVERRIDES.get(operation, {})
        return RawInterface(
            status=status,
            operation=operation,
            method=override.get("method") or item.get("http_method"),
            path=item.get("path"),
            runtime_path=override.get("runtime_path") or item.get("runtime_path"),
            title=override.get("title") or item.get("operation_title") or item.get("title"),
            source_type=override.get("source_type") or item.get("source_type"),
            yapi_status=item.get("yapi_status"),
        )

    def _build_task_card(self, raw_task: Dict[str, Any]) -> TaskCard:
        refs = raw_task.get("interface_refs", [])
        actions = self._build_actions(raw_task, refs)
        max_side_effect = self._max_side_effect(actions, raw_task.get("side_effect", "S0"))
        return TaskCard(
            id=raw_task["id"],
            group=raw_task["group"],
            title=raw_task["title"],
            summary=raw_task["summary"],
            userPhrases=raw_task.get("user_phrases", []),
            priority=raw_task["priority"],
            maxSideEffect=max_side_effect,
            requiredContext=raw_task.get("required_context", []),
            commonInputs=raw_task.get("common_inputs", []),
            interfaceRefs=refs,
            actions=actions,
        )

    def _build_actions(self, raw_task: Dict[str, Any], refs: List[str]) -> List[TaskAction]:
        grouped: Dict[str, List[InterfaceRef]] = {}
        for ref in refs:
            interface_ref = self._parse_interface_ref(ref)
            action_id = self._action_id_from_operation(raw_task["id"], interface_ref.operation)
            grouped.setdefault(action_id, []).append(interface_ref)

        actions = []
        for action_id, interface_refs in grouped.items():
            action = self._build_action(raw_task, action_id, interface_refs)
            actions.append(action)
        return sorted(actions, key=lambda item: (self._sort_weight(item.sideEffect), item.id))

    def _parse_interface_ref(self, ref: str) -> InterfaceRef:
        prefix, value = self._split_ref(ref)
        status = self._status_from_prefix(prefix)
        if status in {InterfaceStatus.external, InterfaceStatus.non_rest}:
            return InterfaceRef(ref=ref, status=status, operation=value, title=value)

        raw = self._interfaces.get(value)
        if raw is None:
            return InterfaceRef(ref=ref, status=self._dev_confirmed_status(value, status), operation=value, title=value)

        resolved_status = status if status != InterfaceStatus.confirmed else raw.status
        resolved_status = self._dev_confirmed_status(value, resolved_status)
        return InterfaceRef(
            ref=ref,
            status=resolved_status,
            operation=value,
            method=raw.method,
            path=raw.path,
            runtimePath=raw.runtime_path,
            title=raw.title,
            sourceType=raw.source_type,
            yapiStatus=raw.yapi_status,
        )

    def _split_ref(self, ref: str) -> Tuple[str, str]:
        if ":" not in ref:
            return "candidate", ref
        prefix, value = ref.split(":", 1)
        return prefix, value

    def _status_from_prefix(self, prefix: str) -> InterfaceStatus:
        try:
            return InterfaceStatus(prefix)
        except ValueError:
            return InterfaceStatus.candidate

    def _dev_confirmed_status(self, operation: str, status: InterfaceStatus) -> InterfaceStatus:
        if status == InterfaceStatus.candidate and operation in DEV_CONFIRMED_OPERATIONS:
            return InterfaceStatus.confirmed
        return status

    def _action_id_from_operation(self, task_id: str, operation: str) -> str:
        if operation in OPERATION_ACTION_OVERRIDES:
            return OPERATION_ACTION_OVERRIDES[operation]
        tail = operation.rsplit(".", 1)[-1]
        if task_id == "device_management.remove_device":
            if operation.startswith("device.slot.") and tail == "delete":
                return "delete_device"
            if operation.startswith("gateway.core.") and tail == "delete":
                return "delete_gateway"
        if task_id == "family_space.manage_area":
            if operation.startswith("area.core."):
                return f"{tail}_area"
            if operation.startswith("area_group.legacy_group."):
                suffix = "fuzzy_search" if tail == "fuzzy_search" else tail
                return f"{suffix}_area_group"
        if tail in {"list_all", "get_detail", "get_info", "batch_create", "batch_insert", "batch_update", "batch_delete"}:
            return tail
        if tail in {"update_devices"}:
            return "update"
        if tail in {"update_layout"}:
            return "configure"
        if tail in {"applyManualCode"}:
            return "apply"
        return tail

    def _build_action(self, raw_task: Dict[str, Any], action_id: str, interface_refs: List[InterfaceRef]) -> TaskAction:
        status = self._action_status(interface_refs)
        side_effect = self._side_effect_for_action(action_id, interface_refs)
        execution_mode = self._execution_mode_for_action(raw_task["id"], action_id, interface_refs)
        schema = self._build_schema(raw_task, action_id, side_effect, execution_mode, interface_refs)
        direct_execution_supported = execution_mode in {
            ExecutionMode.cloud_api,
            ExecutionMode.cloud_api_with_polling,
            ExecutionMode.requires_qr_scan,
        }
        return TaskAction(
            id=action_id,
            title=self._action_title(raw_task, action_id, interface_refs),
            description=self._action_description(raw_task, action_id, interface_refs),
            executionMode=execution_mode,
            sideEffect=side_effect,
            status=status,
            interfaceRefs=interface_refs,
            parameterSchema=schema,
            directExecutionSupported=direct_execution_supported,
        )

    def _action_status(self, interface_refs: List[InterfaceRef]) -> InterfaceStatus:
        if any(ref.status == InterfaceStatus.non_rest for ref in interface_refs):
            return InterfaceStatus.non_rest
        if any(ref.status == InterfaceStatus.external for ref in interface_refs):
            return InterfaceStatus.external
        if any(ref.status == InterfaceStatus.candidate for ref in interface_refs):
            return InterfaceStatus.candidate
        return InterfaceStatus.confirmed

    def _side_effect_for_action(self, action_id: str, refs: List[InterfaceRef]) -> SideEffectLevel:
        operation_tails = {self._base_action_id(action_id), *[ref.operation.rsplit(".", 1)[-1] for ref in refs]}
        operations = {ref.operation for ref in refs}
        if operations and all(operation.startswith("thing_schema.") for operation in operations):
            return SideEffectLevel.S0
        if operations and all(operation.startswith(("device.relation.", "device.schema.", "upgrade.")) for operation in operations):
            return SideEffectLevel.S0
        if operation_tails & DELETE_KEYWORDS or any(operation.endswith(".bind") for operation in operations):
            return SideEffectLevel.S3
        if operation_tails & DIAGNOSE_KEYWORDS:
            return SideEffectLevel.S1
        if operation_tails & (CREATE_KEYWORDS | UPDATE_KEYWORDS):
            return SideEffectLevel.S2
        if operation_tails & READ_KEYWORDS:
            return SideEffectLevel.S0
        return SideEffectLevel.S1

    def _execution_mode_for_action(
        self,
        task_id: str,
        action_id: str,
        refs: List[InterfaceRef],
    ) -> ExecutionMode:
        operation_text = " ".join([task_id, action_id, *[ref.operation for ref in refs]]).lower()
        operation_tokens = set(re.split(r"[^a-z0-9]+", operation_text))
        if any(ref.status == InterfaceStatus.non_rest for ref in refs):
            if "lan" in operation_tokens:
                return ExecutionMode.requires_lan
            return ExecutionMode.manual_assist
        if any(ref.status == InterfaceStatus.external for ref in refs):
            return ExecutionMode.manual_assist
        if task_id == "device_onboarding.pair_device":
            if "progress" in operation_tokens:
                return ExecutionMode.cloud_api_with_polling
            if {"matter", "qrcode", "manualcode"} & operation_tokens or "matter" in operation_text:
                return ExecutionMode.requires_qr_scan
            return ExecutionMode.requires_mobile_app
        if "ble" in operation_tokens:
            return ExecutionMode.requires_ble
        if "lan" in operation_tokens:
            return ExecutionMode.requires_lan
        if {"progress", "poll"} & operation_tokens:
            return ExecutionMode.cloud_api_with_polling
        return ExecutionMode.cloud_api

    def _build_schema(
        self,
        raw_task: Dict[str, Any],
        action_id: str,
        side_effect: SideEffectLevel,
        execution_mode: ExecutionMode,
        refs: List[InterfaceRef],
    ) -> ActionSchema:
        context_required = self._context_required(raw_task, action_id, refs)
        payload_required = self._payload_required(raw_task, action_id, refs)
        payload_properties = self._payload_properties(raw_task.get("common_inputs", []), payload_required)
        operation_schema = get_operation_schema([ref.operation for ref in refs])
        if operation_schema["matched"]:
            context_required = operation_schema["context_required"]
            payload_required = operation_schema["payload_required"]
            payload_properties.update(operation_schema["payload_properties"])
            for field in operation_schema.get("payload_excluded", []):
                payload_properties.pop(field, None)
        return ActionSchema(
            contextRequired=context_required,
            payloadRequired=payload_required,
            payloadProperties=payload_properties,
            optionHints={
                "dryRunDefault": True,
                "requiresConfirmSideEffect": side_effect in {SideEffectLevel.S2, SideEffectLevel.S3},
                "requiresAllowCandidate": any(ref.status == InterfaceStatus.candidate for ref in refs),
                "executionMode": execution_mode.value,
            },
        )

    def _context_required(self, raw_task: Dict[str, Any], action_id: str, refs: List[InterfaceRef]) -> List[str]:
        fields = self._required_context_from_task(raw_task)
        for ref in refs:
            fields.update(self._path_params(ref.runtimePath or ref.path or "", ref.operation))
        resource_fields = self._resource_context_fields(refs)
        if resource_fields:
            fields = fields.intersection(resource_fields).union(
                field for field in fields if field not in KNOWN_CONTEXT_FIELDS
            )
        if raw_task["id"].endswith("manage_account"):
            fields.discard("houseId")
        return sorted(fields)

    def _payload_required(self, raw_task: Dict[str, Any], action_id: str, refs: List[InterfaceRef]) -> List[str]:
        common_inputs = set(raw_task.get("common_inputs", []))
        required: set[str] = set()
        base_action_id = self._base_action_id(action_id)
        action_text = " ".join([action_id, *[ref.operation for ref in refs]])
        path_params = set()
        for ref in refs:
            path_params.update(self._path_params(ref.runtimePath or ref.path or "", ref.operation))
        if base_action_id in {"create", "batch_create", "batch_insert"}:
            required.update(field for field in ("name", "items", "devices") if field in common_inputs)
        if base_action_id == "configure":
            if "events" in common_inputs:
                required.add("events")
            elif "config" in common_inputs:
                required.add("config")
        if base_action_id in {"remove", "transfer"} and not path_params:
            required.update(field for field in ("memberId", "targetUser") if field in common_inputs)
        if "pairing" in action_text.lower() or "matterdac" in action_text.lower():
            required.update(field for field in ("manualCode", "qrCode", "nodeId") if field in common_inputs)
        return sorted(required)

    def _payload_properties(self, common_inputs: Iterable[str], required: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        required_set = set(required)
        properties = {}
        for field in common_inputs:
            properties[field] = {
                "type": FIELD_TYPE_HINTS.get(field, "string"),
                "required": field in required_set,
                "description": f"{field} 参数",
            }
        for field in required_set:
            properties.setdefault(
                field,
                {
                    "type": FIELD_TYPE_HINTS.get(field, "string"),
                    "required": True,
                    "description": f"{field} 参数",
                },
            )
        return properties

    def _action_description(self, raw_task: Dict[str, Any], action_id: str, refs: List[InterfaceRef]) -> str:
        titles = [ref.title for ref in refs if ref.title]
        if titles:
            return "；".join(titles)
        return f"{raw_task['title']} - {ACTION_TITLE_MAP.get(action_id, action_id)}"

    def _action_title(self, raw_task: Dict[str, Any], action_id: str, refs: List[InterfaceRef]) -> str:
        base_title = self._action_description(raw_task, action_id, refs).split("；", 1)[0]
        if not base_title:
            base_title = ACTION_TITLE_MAP.get(action_id, action_id.replace("_", " "))
        if base_title == raw_task["title"] or raw_task["title"] in base_title:
            return base_title
        return f"{base_title}（{raw_task['title']}）"

    def _max_side_effect(self, actions: List[TaskAction], fallback: str) -> SideEffectLevel:
        if not actions:
            return SideEffectLevel(fallback)
        return max((action.sideEffect for action in actions), key=self._sort_weight)

    def _sort_weight(self, side_effect: SideEffectLevel) -> int:
        return {"S0": 0, "S1": 1, "S2": 2, "S3": 3}[side_effect.value]

    def _path_params(self, path: str, operation: str = "") -> List[str]:
        return [self._normalize_path_param(param, operation, path) for param in re.findall(r"{([^}]+)}", path)]

    def _normalize_path_param(self, param: str, operation: str, path: str = "") -> str:
        if param in PATH_PARAM_ALIASES:
            return PATH_PARAM_ALIASES[param]
        if param != "id":
            return param

        path_alias_patterns = (
            (r"/room/\{id\}", "roomId"),
            (r"/house/\{id\}", "houseId"),
            (r"/device/\{id\}", "deviceId"),
            (r"/gateway/\{id\}", "gatewayId"),
            (r"/area/\{id\}", "areaId"),
            (r"/meshgroup/\{id\}", "groupId"),
            (r"/group/\{id\}", "groupId"),
            (r"/scene/\{id\}", "sceneId"),
            (r"/share/\{id\}", "shareId"),
            (r"/rule/\{id\}", "automationId"),
            (r"/automations/\{id\}", "automationId"),
        )
        for pattern, alias in path_alias_patterns:
            if re.search(pattern, path):
                return alias

        parts = operation.split(".")
        for part in reversed(parts[:-1]):
            alias = RESOURCE_ID_ALIASES.get(part)
            if alias:
                return alias
        return param

    def _required_context_from_task(self, raw_task: Dict[str, Any]) -> set[str]:
        fields: set[str] = set()
        for item in raw_task.get("required_context", []):
            if "或" in item:
                continue
            for field in KNOWN_CONTEXT_FIELDS:
                if field in item:
                    fields.add(field)
        return fields

    def _base_action_id(self, action_id: str) -> str:
        for prefix in ("delete", "create", "update", "list"):
            if action_id.startswith(f"{prefix}_"):
                return prefix
        return action_id

    def _resource_context_fields(self, refs: List[InterfaceRef]) -> set[str]:
        fields: set[str] = set()
        for ref in refs:
            parts = ref.operation.split(".")
            if len(parts) < 2:
                continue
            domain, resource = parts[0], parts[1]
            key = "area_group" if domain == "area_group" else resource
            fields.update(RESOURCE_CONTEXT_FIELDS.get(key, set()))
            fields.update(RESOURCE_CONTEXT_FIELDS.get(domain, set()))
        return fields


registry = MetadataTaskRegistry()
