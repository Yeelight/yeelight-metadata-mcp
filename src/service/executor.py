import json
import re
from typing import Any, Dict, List, Optional, Tuple

from config.config import settings
from service.model import (
    ExecutionMode,
    ExecutionPlan,
    ExecutionResult,
    ExecuteOptions,
    InterfaceRef,
    InterfaceStatus,
    SideEffectLevel,
    TaskContext,
    TaskExecutionRequest,
    ValidationRequest,
    ValidationResult,
)
from service.registry import MetadataTaskRegistry, registry
from utils.http import HttpClient


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


class TaskExecutor:
    def __init__(self, task_registry: MetadataTaskRegistry, http_client: HttpClient):
        self.registry = task_registry
        self.http_client = http_client

    def validate(self, request: ValidationRequest) -> ValidationResult:
        task = self.registry.get_task(request.task)
        if task is None:
            return ValidationResult(valid=False, code="UNKNOWN_TASK", errors=[f"未知任务: {request.task}"], task=request.task, action=request.action)

        action = self.registry.get_action(request.task, request.action)
        if action is None:
            return ValidationResult(
                valid=False,
                code="UNKNOWN_ACTION",
                errors=[f"任务 {request.task} 不支持 action: {request.action}"],
                task=request.task,
                action=request.action,
            )

        errors: List[str] = []
        warnings: List[str] = []
        context_data = request.context.model_dump(exclude_none=True)

        for field in action.parameterSchema.contextRequired:
            if field not in context_data and field not in request.payload:
                errors.append(f"缺少必要上下文字段: {field}")

        for field in action.parameterSchema.payloadRequired:
            if not self._has_required_payload_field(field, request.payload, context_data):
                errors.append(f"缺少必要 payload 字段: {field}")

        self._validate_operation_payload(action, request.payload, errors)

        if action.status == InterfaceStatus.candidate:
            self._validate_candidate_policy(request.options, request.context, errors, warnings)

        if action.sideEffect in {SideEffectLevel.S2, SideEffectLevel.S3} and not request.options.dryRun:
            if not request.options.confirmSideEffect:
                errors.append(f"{action.sideEffect.value} 副作用 action 必须显式传 options.confirmSideEffect=true")
            if action.sideEffect == SideEffectLevel.S3 and not request.options.reason:
                warnings.append("S3 高风险操作建议填写 options.reason 便于审计")

        if not action.directExecutionSupported and not request.options.dryRun:
            errors.append(f"{action.executionMode.value} action 不支持 MCP 云端直接执行，请使用 dryRun 获取执行指引")

        return ValidationResult(
            valid=not errors,
            code="OK" if not errors else "VALIDATION_ERROR",
            errors=errors,
            warnings=warnings,
            task=request.task,
            action=request.action,
            sideEffect=action.sideEffect,
            executionMode=action.executionMode,
            status=action.status,
        )

    def _has_required_payload_field(self, field: str, payload: Dict[str, Any], context_data: Dict[str, Any]) -> bool:
        if field in payload or field in context_data:
            return True
        return False

    def _validate_operation_payload(self, action: Any, payload: Dict[str, Any], errors: List[str]) -> None:
        operations = {ref.operation for ref in action.interfaceRefs}
        if "room.area.update" in operations and not any(key in payload for key in ("areaIds", "addAreaList", "removeAreaList")):
            errors.append("room.area.update 必须提供 areaIds、addAreaList 或 removeAreaList 之一")
        if "device_group.member.update_devices" in operations and not any(key in payload for key in ("deviceIds", "addDeviceList", "removeDeviceList")):
            errors.append("device_group.member.update_devices 必须提供 deviceIds、addDeviceList 或 removeDeviceList 之一")
        if "panel.button.update_layout" in operations and not any(key in payload for key in ("layout", "buttons")):
            errors.append("panel.button.update_layout 必须提供 layout 或 buttons 之一")
        if "panel.button_event.batch_update" in operations and not any(key in payload for key in ("events", "buttonEvents")):
            errors.append("panel.button_event.batch_update 必须提供 events 或 buttonEvents 之一")
        if "ai.control_node.update" in operations and not any(key in payload for key in ("controls", "deviceIds", "sceneIds")):
            errors.append("ai.control_node.update 必须提供 controls、deviceIds 或 sceneIds 之一")
        if "device.asset.text_to_image" in operations and not any(key in payload for key in ("texts", "prompt")):
            errors.append("device.asset.text_to_image 必须提供 texts 或 prompt 之一")

    def build_plan(self, request: TaskExecutionRequest, api_base_url: Optional[str] = None) -> ExecutionPlan:
        action = self.registry.get_action(request.task, request.action)
        if action is None:
            return ExecutionPlan(
                task=request.task,
                action=request.action,
                dryRun=request.options.dryRun,
                sideEffect=SideEffectLevel.S0,
                executionMode=ExecutionMode.manual_assist,
                status=InterfaceStatus.candidate,
                directExecutionSupported=False,
                interfaces=[],
                context=request.context.model_dump(exclude_none=True),
                payload=request.payload,
                guidance=["未找到 action 定义，请先调用 list_tasks 或 list_actions 查看可用 action"],
            )

        plan = ExecutionPlan(
            task=request.task,
            action=request.action,
            dryRun=request.options.dryRun,
            sideEffect=action.sideEffect,
            executionMode=action.executionMode,
            status=action.status,
            directExecutionSupported=action.directExecutionSupported,
            interfaces=action.interfaceRefs,
            context=request.context.model_dump(exclude_none=True),
            payload=request.payload,
            guidance=self._build_guidance(action.executionMode, action.status, action.sideEffect, request.options),
        )
        interface = self._select_executable_interface(plan.interfaces)
        if interface is not None:
            method, url, body, params = self._build_http_request(interface, request, api_base_url)
            plan.httpRequest = {
                "method": method,
                "url": url,
                "body": body,
                "params": params,
                "operation": interface.operation,
            }
        return plan

    def execute(
        self,
        request: TaskExecutionRequest,
        headers: Dict[str, str],
        api_base_url: Optional[str] = None,
    ) -> ExecutionResult:
        validation = self.validate(
            ValidationRequest(
                task=request.task,
                action=request.action,
                context=request.context,
                payload=request.payload,
                options=request.options,
            )
        )
        plan = self.build_plan(request, api_base_url)
        if not validation.valid:
            return ExecutionResult(ok=False, dryRun=request.options.dryRun, code=validation.code, plan=plan, validation=validation, message="任务校验失败")

        if request.options.dryRun:
            return ExecutionResult(ok=True, dryRun=True, code="DRY_RUN", plan=plan, validation=validation, message="dryRun 已生成执行计划，未调用底层接口")

        interface = self._select_executable_interface(plan.interfaces)
        if interface is None:
            return ExecutionResult(
                ok=False,
                dryRun=False,
                code="NO_EXECUTABLE_INTERFACE",
                plan=plan,
                validation=validation,
                message="未找到可直接执行的 HTTP 接口",
            )

        method, url, body, params = self._build_http_request(interface, request, api_base_url)
        response = self.http_client.request(method, url, headers=headers, params=params, json=body)
        normalized = self._normalize_response(response)
        return ExecutionResult(
            ok=normalized["ok"],
            dryRun=False,
            code=normalized["code"],
            plan=plan,
            validation=validation,
            response=response,
            normalizedResponse=normalized,
            message=normalized.get("message"),
        )

    def _validate_candidate_policy(
        self,
        options: ExecuteOptions,
        context: TaskContext,
        errors: List[str],
        warnings: List[str],
    ) -> None:
        if not options.allowCandidate:
            errors.append("candidate action 默认不可执行，请显式传 options.allowCandidate=true")
            return

        runtime_env = context.runtimeEnv or settings.RUNTIME_ENV
        if runtime_env not in settings.CANDIDATE_EXECUTION_ENVIRONMENTS and not settings.ALLOW_CANDIDATE_EXECUTION:
            errors.append("candidate action 仅允许 local/test 环境或显式开启 METADATA_MCP_ALLOW_CANDIDATE_EXECUTION 后执行")
            return

        warnings.append("当前 action 仍为 candidate，请仅在测试环境或白名单账号下执行")

    def _build_guidance(
        self,
        execution_mode: ExecutionMode,
        status: InterfaceStatus,
        side_effect: SideEffectLevel,
        options: ExecuteOptions,
    ) -> List[str]:
        guidance: List[str] = []
        if status == InterfaceStatus.candidate:
            if options.dryRun:
                guidance.append("该 action 来源仍为 candidate，当前为 dryRun，仅生成计划；真实执行需要显式传 options.allowCandidate=true。")
            elif options.allowCandidate:
                guidance.append("该 action 来源仍为 candidate，本次已由 options.allowCandidate=true 显式放行；请仅在测试环境或白名单账号下使用。")
            else:
                guidance.append("该 action 来源仍为 candidate，默认不会执行；真实执行需要显式传 options.allowCandidate=true。")
        if side_effect in {SideEffectLevel.S2, SideEffectLevel.S3}:
            guidance.append(f"该 action 副作用等级为 {side_effect.value}，非 dryRun 执行必须确认副作用。")
        if execution_mode == ExecutionMode.cloud_api_with_polling:
            guidance.append("该 action 需要云接口配合轮询，调用方应关注超时与进度状态。")
        elif execution_mode == ExecutionMode.requires_qr_scan:
            guidance.append("该 action 需要扫码或配对码输入，MCP 只负责云侧申请/查询。")
        elif execution_mode == ExecutionMode.requires_ble:
            guidance.append("该 action 需要蓝牙能力，必须由 APP 或本地 agent 配合。")
        elif execution_mode == ExecutionMode.requires_lan:
            guidance.append("该 action 需要局域网发现或通信，必须由本地 agent 配合。")
        elif execution_mode == ExecutionMode.requires_mobile_app:
            guidance.append("该 action 需要移动端 APP 配合完成本地交互。")
        elif execution_mode == ExecutionMode.manual_assist:
            guidance.append("该 action 只能生成步骤或参数引导，不能由在线 MCP 直接完成。")
        return guidance

    def _normalize_response(self, response: Any) -> Dict[str, Any]:
        if not isinstance(response, dict):
            return {"ok": True, "code": "OK", "message": "请求成功", "data": response}
        if "error" in response:
            return {"ok": False, "code": "HTTP_ERROR", "message": response.get("error"), "data": response}
        code = str(response.get("code", "200"))
        success = response.get("success")
        ok = code == "200" if success is None else bool(success) and code == "200"
        return {
            "ok": ok,
            "code": "OK" if ok else code,
            "message": response.get("msg") or ("请求成功" if ok else "请求失败"),
            "data": response.get("data", response),
        }

    def _select_executable_interface(self, interfaces: List[InterfaceRef]) -> Optional[InterfaceRef]:
        for interface in interfaces:
            if interface.runtimePath and interface.method and interface.status in {InterfaceStatus.confirmed, InterfaceStatus.candidate}:
                return interface
        return None

    def _build_http_request(
        self,
        interface: InterfaceRef,
        request: TaskExecutionRequest,
        api_base_url: Optional[str] = None,
    ) -> Tuple[str, str, Any, Dict[str, Any]]:
        method = (interface.method or "POST").upper()
        path = interface.runtimePath or interface.path or ""
        context_data = request.context.model_dump(exclude_none=True)
        merged = {**context_data, **request.payload}
        raw_path_params = set(re.findall(r"{([^}]+)}", path))
        body_exclude_keys = set()
        for raw_key in raw_path_params:
            key = self._normalize_path_param(raw_key, interface.operation, path)
            body_exclude_keys.add(key)
            value = merged.get(key)
            if value is None:
                continue
            path = path.replace("{" + raw_key + "}", str(value))

        url = f"{(api_base_url or settings.API_BASE_URL).rstrip('/')}{path}"
        context_body = {
            key: value
            for key, value in context_data.items()
            if key not in body_exclude_keys and key not in {"clientId", "runtimeEnv"}
        }
        payload_body = {key: value for key, value in request.payload.items() if key not in body_exclude_keys}
        body = self._transform_body(interface, {**context_body, **payload_body}, context_data, request.payload)
        params = body if method == "GET" else {}
        json_body = None if method == "DELETE" and not body else ({} if method == "GET" else body)
        return method, url, json_body, params

    def _transform_body(
        self,
        interface: InterfaceRef,
        body: Dict[str, Any],
        context_data: Dict[str, Any],
        payload: Dict[str, Any],
    ) -> Any:
        operation = interface.operation
        if operation.startswith("favorite.core.batch_"):
            return self._favorite_items_body(body, context_data, payload)
        if operation in {"device_group.mesh_group.create", "device_group.mesh_group.update"}:
            return self._device_group_body(body)
        if operation == "device_group.member.update_devices":
            return self._device_group_member_body(body)
        if operation == "device.slot.batch_create":
            return self._device_slot_batch_create_body(body, context_data)
        if operation == "device.slot.create":
            return self._device_slot_create_body(body)
        if operation in {"area_group.legacy_group.create", "area_group.legacy_group.update"}:
            return self._area_group_body(body, context_data)
        if operation == "room.area.update":
            return self._room_area_body(body)
        if operation == "gateway.core.delete":
            return {}
        if operation.startswith("scene.management."):
            return self._scene_body(body)
        if operation == "panel.button.update_layout":
            return self._panel_buttons_body(body, context_data, payload)
        if operation == "panel.button_event.update":
            return self._panel_event_body(body, context_data, payload)
        if operation == "panel.button_event.batch_update":
            return self._panel_events_body(body, context_data, payload)
        if operation in {"knob.single.update", "knob.multi.update"}:
            return self._knob_body(body, context_data, payload)
        if operation == "ai.control_node.update":
            return self._ai_control_node_body(body, context_data, payload)
        if operation == "ai.name.batch_update":
            return self._array_alias_body(body, payload, "names")
        if operation == "device.asset.text_to_image":
            return self._text_to_image_body(body)
        if operation in {"automation.rule.create", "automation.rule.update", "automation.rule.test"}:
            return self._automation_body(body)
        return body

    def _favorite_items_body(self, body: Dict[str, Any], context_data: Dict[str, Any], payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        raw_items = payload.get("items", body.get("items", []))
        if not isinstance(raw_items, list):
            raw_items = []
        house_id = context_data.get("houseId") or payload.get("houseId") or body.get("houseId")
        items: List[Dict[str, Any]] = []
        type_aliases = {
            "room": "1",
            "device": "2",
            "area": "3",
            "group": "4",
            "mesh_group": "4",
            "scene": "6",
        }
        for raw_item in raw_items:
            if isinstance(raw_item, dict):
                item = dict(raw_item)
            else:
                item = {"resId": raw_item}
            if house_id and "houseId" not in item:
                item["houseId"] = house_id
            if "resType" in item and "typeId" not in item:
                item["typeId"] = type_aliases.get(str(item.pop("resType")), item.get("typeId"))
            items.append(item)
        return items

    def _device_group_body(self, body: Dict[str, Any]) -> Dict[str, Any]:
        transformed = dict(body)
        device_ids = transformed.pop("deviceIds", None)
        if device_ids is not None and "details" not in transformed:
            if not isinstance(device_ids, list):
                device_ids = [device_ids]
            transformed["details"] = [{"deviceId": device_id} for device_id in device_ids]
        return transformed

    def _device_group_member_body(self, body: Dict[str, Any]) -> Dict[str, Any]:
        transformed = dict(body)
        if "addDeviceList" in transformed or "removeDeviceList" in transformed:
            transformed.pop("deviceIds", None)
            return transformed

        device_ids = transformed.pop("deviceIds", None)
        if device_ids is None:
            return transformed
        if not isinstance(device_ids, list):
            device_ids = [device_ids]
        transformed["addDeviceList"] = [{"id": device_id} for device_id in device_ids]
        return transformed

    def _device_slot_create_body(self, body: Dict[str, Any]) -> Dict[str, Any]:
        transformed = dict(body)
        if "isVirtual" in transformed and "virtual" not in transformed:
            transformed["virtual"] = transformed.pop("isVirtual")
        return transformed

    def _device_slot_batch_create_body(self, body: Dict[str, Any], context_data: Dict[str, Any]) -> Dict[str, Any]:
        transformed = dict(body)
        room_id = context_data.get("roomId") or transformed.pop("roomId", None)
        devices = transformed.get("devices")
        if isinstance(devices, list):
            normalized_devices = []
            for raw_device in devices:
                if not isinstance(raw_device, dict):
                    normalized_devices.append(raw_device)
                    continue
                device = dict(raw_device)
                if room_id and "roomId" not in device:
                    device["roomId"] = room_id
                if "isVirtual" in device and "virtual" not in device:
                    device["virtual"] = device.pop("isVirtual")
                normalized_devices.append(device)
            transformed["devices"] = normalized_devices
        transformed.pop("roomId", None)
        return transformed

    def _area_group_body(self, body: Dict[str, Any], context_data: Dict[str, Any]) -> Dict[str, Any]:
        transformed = dict(body)
        group_id = context_data.get("groupId")
        room_ids = transformed.pop("roomIds", None)
        if room_ids is not None and "details" not in transformed:
            if not isinstance(room_ids, list):
                room_ids = [room_ids]
            details = []
            for room_id in room_ids:
                detail = {"roomId": room_id}
                if group_id:
                    detail["userGroupId"] = group_id
                details.append(detail)
            transformed["details"] = details
        return transformed

    def _room_area_body(self, body: Dict[str, Any]) -> Dict[str, Any]:
        transformed = dict(body)
        if "addAreaList" in transformed or "removeAreaList" in transformed:
            transformed.pop("areaIds", None)
            return transformed

        area_ids = transformed.pop("areaIds", None)
        if area_ids is None:
            return transformed
        if not isinstance(area_ids, list):
            area_ids = [area_ids]
        transformed["addAreaList"] = area_ids
        return transformed

    def _scene_body(self, body: Dict[str, Any]) -> Dict[str, Any]:
        transformed = dict(body)
        actions = transformed.pop("actions", None)
        if actions is not None and "details" not in transformed:
            transformed["details"] = actions
        details = transformed.get("details")
        if isinstance(details, list):
            normalized_details = []
            for detail in details:
                if not isinstance(detail, dict):
                    normalized_details.append(detail)
                    continue
                normalized = dict(detail)
                params = normalized.get("params")
                if isinstance(params, dict):
                    normalized["params"] = json.dumps(params, ensure_ascii=False, separators=(",", ":"))
                normalized_details.append(normalized)
            transformed["details"] = normalized_details
        return transformed

    def _array_alias_body(self, body: Dict[str, Any], payload: Dict[str, Any], alias: str) -> Any:
        value = payload.get(alias, body.get(alias))
        if value is not None:
            return value
        return body

    def _panel_buttons_body(self, body: Dict[str, Any], context_data: Dict[str, Any], payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        raw_buttons = payload.get("buttons")
        if raw_buttons is None:
            raw_layout = payload.get("layout", body.get("layout", []))
            if isinstance(raw_layout, dict):
                raw_buttons = raw_layout.get("buttons", raw_layout.get("layout", raw_layout))
            else:
                raw_buttons = raw_layout
        if not isinstance(raw_buttons, list):
            raw_buttons = [raw_buttons]
        device_id = context_data.get("deviceId") or payload.get("deviceId") or body.get("deviceId")
        buttons = []
        for raw_button in raw_buttons:
            if not isinstance(raw_button, dict):
                buttons.append(raw_button)
                continue
            button = dict(raw_button)
            if device_id and "deviceId" not in button:
                button["deviceId"] = device_id
            buttons.append(button)
        return buttons

    def _panel_event_body(self, body: Dict[str, Any], context_data: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        raw_event = payload.get("event", body.get("event"))
        event = dict(raw_event) if isinstance(raw_event, dict) else dict(body)
        event.pop("event", None)
        device_id = context_data.get("deviceId") or payload.get("deviceId") or body.get("deviceId")
        if device_id and "deviceId" not in event:
            event["deviceId"] = device_id
        return event

    def _panel_events_body(self, body: Dict[str, Any], context_data: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        raw_events = payload.get("buttonEvents", payload.get("events", body.get("buttonEvents", body.get("events", []))))
        if not isinstance(raw_events, list):
            raw_events = [raw_events]
        device_id = context_data.get("deviceId") or payload.get("deviceId") or body.get("deviceId")
        events = []
        for raw_event in raw_events:
            if not isinstance(raw_event, dict):
                events.append(raw_event)
                continue
            event = dict(raw_event)
            if device_id and "deviceId" not in event:
                event["deviceId"] = device_id
            events.append(event)
        return {"buttonEvents": events}

    def _knob_body(self, body: Dict[str, Any], context_data: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        raw_config = payload.get("config", body.get("config"))
        config = dict(raw_config) if isinstance(raw_config, dict) else dict(body)
        config.pop("config", None)
        device_id = context_data.get("deviceId") or payload.get("deviceId") or body.get("deviceId")
        if device_id and "id" not in config:
            config["id"] = device_id
        return config

    def _ai_control_node_body(self, body: Dict[str, Any], context_data: Dict[str, Any], payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        raw_controls = payload.get("controls", body.get("controls"))
        house_id = context_data.get("houseId") or payload.get("houseId") or body.get("houseId")
        if raw_controls is not None:
            if not isinstance(raw_controls, list):
                raw_controls = [raw_controls]
            controls = []
            for raw_control in raw_controls:
                if not isinstance(raw_control, dict):
                    controls.append(raw_control)
                    continue
                control = dict(raw_control)
                if house_id and "houseId" not in control:
                    control["houseId"] = house_id
                controls.append(control)
            return controls

        screen_device_id = payload.get("screenDeviceId") or body.get("screenDeviceId") or context_data.get("deviceId")
        controls = []
        for res_type, ids_key in (("device", "deviceIds"), ("scene", "sceneIds")):
            resource_ids = payload.get(ids_key, body.get(ids_key, []))
            if resource_ids is None:
                continue
            if not isinstance(resource_ids, list):
                resource_ids = [resource_ids]
            for index, resource_id in enumerate(resource_ids):
                control = {"deviceId": screen_device_id, "resId": resource_id, "resType": res_type, "index": index}
                if house_id:
                    control["houseId"] = house_id
                controls.append(control)
        return controls

    def _text_to_image_body(self, body: Dict[str, Any]) -> Dict[str, Any]:
        transformed = dict(body)
        prompt = transformed.pop("prompt", None)
        if prompt is not None and "texts" not in transformed:
            transformed["texts"] = [prompt]
        return transformed

    def _automation_body(self, body: Dict[str, Any]) -> Dict[str, Any]:
        transformed = dict(body)
        transformed.pop("conditions", None)
        transformed["version"] = 2

        params = transformed.get("params")
        if isinstance(params, dict):
            transformed["params"] = json.dumps(params, ensure_ascii=False, separators=(",", ":"))
        return transformed

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


http_client = HttpClient(settings.HTTP_TIMEOUT)
executor = TaskExecutor(registry, http_client)
