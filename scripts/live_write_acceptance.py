#!/usr/bin/env python3
"""按 Pro API 巡检思路执行 Metadata MCP 写接口真实闭环验收。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


PROJECT_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = PROJECT_DIR.parent
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config.config import settings  # noqa: E402
from service.executor import TaskExecutor  # noqa: E402
from service.model import SideEffectLevel, TaskContext, TaskExecutionRequest  # noqa: E402
from service.registry import MetadataTaskRegistry  # noqa: E402
from utils.http import HttpClient  # noqa: E402

from action_acceptance_matrix import (  # noqa: E402
    SeedState,
    compact_response,
    discover_seeds,
    extract_created_id,
    extract_data,
    find_nested_list,
)


DEFAULT_OUTPUT_JSON = REPO_DIR / ".claude" / "metadata-mcp-live-write-acceptance.json"
DEFAULT_OUTPUT_MD = REPO_DIR / ".claude" / "metadata-mcp-live-write-acceptance.md"
DEFAULT_HOUSE_ID = "200084"


class RecordingHttpClient(HttpClient):
    """记录非敏感请求摘要，便于验收报告复盘。"""

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
                "json": deepcopy(json),
                "headers": sorted((headers or {}).keys()),
            }
        )
        return super().request(method, url, headers=headers, params=params, json=json)


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_token(args: argparse.Namespace) -> str:
    return (args.access_token or os.getenv("METADATA_MCP_ACCESS_TOKEN", "")).strip()


def build_headers(token: str, house_id: str) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = token if token.startswith("Bearer ") else f"Bearer {token}"
    if house_id:
        headers["House-Id"] = house_id
    return headers


def contains_resource(data: Any, resource_id: Optional[str] = None, name: Optional[str] = None) -> bool:
    if isinstance(data, list):
        return any(contains_resource(item, resource_id, name) for item in data)
    if not isinstance(data, dict):
        return False

    if resource_id:
        for key in ("id", "houseId", "roomId", "areaId", "groupId", "userGroupId", "deviceId", "gatewayId", "sceneId", "resId"):
            value = data.get(key)
            if value is not None and str(value) == str(resource_id):
                return True
    if name and data.get("name") == name:
        return True
    return any(contains_resource(value, resource_id, name) for value in data.values())


def find_resource_by_id(data: Any, resource_id: str) -> Optional[Dict[str, Any]]:
    if isinstance(data, list):
        for item in data:
            found = find_resource_by_id(item, resource_id)
            if found:
                return found
        return None
    if not isinstance(data, dict):
        return None
    for key in ("id", "houseId", "roomId", "areaId", "groupId", "userGroupId", "deviceId", "gatewayId", "sceneId", "resId"):
        value = data.get(key)
        if value is not None and str(value) == str(resource_id):
            return data
    for value in data.values():
        found = find_resource_by_id(value, resource_id)
        if found:
            return found
    return None


def find_resource_by_name(data: Any, name: str) -> Optional[Dict[str, Any]]:
    if isinstance(data, list):
        for item in data:
            found = find_resource_by_name(item, name)
            if found:
                return found
        return None
    if not isinstance(data, dict):
        return None
    if data.get("name") == name:
        return data
    for value in data.values():
        found = find_resource_by_name(value, name)
        if found:
            return found
    return None


def extract_resource_id(resource: Optional[Dict[str, Any]], keys: Iterable[str]) -> Optional[str]:
    if not resource:
        return None
    for key in keys:
        value = resource.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def collect_resource_ids(data: Any, keys: Iterable[str], limit: int = 10) -> List[str]:
    found: List[str] = []
    seen = set()

    def visit(value: Any) -> None:
        if len(found) >= limit:
            return
        if isinstance(value, list):
            for item in value:
                visit(item)
            return
        if not isinstance(value, dict):
            return
        for key in keys:
            item_id = value.get(key)
            if item_id not in (None, "") and str(item_id) not in seen:
                seen.add(str(item_id))
                found.append(str(item_id))
                break
        for item in value.values():
            visit(item)

    visit(data)
    return found


def nested_list(data: Any) -> List[Any]:
    return find_nested_list(data, ("rows", "list", "records", "items", "rooms", "areas", "devices", "groups"))


def extract_data_dict(result: Any) -> Dict[str, Any]:
    data = extract_data(result)
    return data if isinstance(data, dict) else {}


class LiveWriteAcceptance:
    def __init__(
        self,
        registry: MetadataTaskRegistry,
        executor: TaskExecutor,
        seeds: SeedState,
        headers: Dict[str, str],
    ):
        self.registry = registry
        self.executor = executor
        self.seeds = seeds
        self.headers = headers

    def run_action(
        self,
        task: str,
        action_id: str,
        context: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
        confirm_side_effect: Optional[bool] = None,
    ) -> Any:
        action = self.registry.get_action(task, action_id)
        if action is None:
            raise RuntimeError(f"缺少 action: {task}/{action_id}")
        if confirm_side_effect is None:
            confirm_side_effect = action.sideEffect in {SideEffectLevel.S2, SideEffectLevel.S3}
        context_data = {"runtimeEnv": "test", **(context or {})}
        request = TaskExecutionRequest(
            task=task,
            action=action_id,
            context=TaskContext(**context_data),
            payload=payload or {},
            options={
                "dryRun": False,
                "allowCandidate": True,
                "confirmSideEffect": confirm_side_effect,
                "reason": "Metadata MCP 写接口真实闭环验收",
            },
        )
        return self.executor.execute(request, headers=self.headers)

    def business_seed_gap_suite(self, suite_id: str, title: str, steps: List[Dict[str, Any]], reason: str) -> Dict[str, Any]:
        return {
            "id": suite_id,
            "title": title,
            "skipped": True,
            "ok": True,
            "skippedReason": reason,
            "businessSeedGap": True,
            "steps": steps,
        }

    def step_from_result(self, name: str, result: Any, note: str = "") -> Dict[str, Any]:
        plan = getattr(result, "plan", None)
        http_request = getattr(plan, "httpRequest", None) if plan else None
        return {
            "name": name,
            "ok": bool(getattr(result, "ok", False)),
            "code": getattr(result, "code", None),
            "message": getattr(result, "message", None),
            "note": note,
            "httpRequest": http_request,
            "validation": getattr(result, "validation", None).model_dump() if getattr(result, "validation", None) else None,
            "response": compact_response(getattr(result, "response", None)),
        }

    def assertion_step(self, name: str, ok: bool, note: str, data: Optional[Any] = None) -> Dict[str, Any]:
        return {
            "name": name,
            "ok": ok,
            "code": "OK" if ok else "ASSERTION_FAILED",
            "message": note,
            "note": note,
            "response": compact_response(data),
        }

    def run_room_crud(self) -> Dict[str, Any]:
        task = "family_space.manage_room"
        name = f"METADATA_MCP_真实验收房间_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        updated_name = f"{name}_已更新"
        created_id: Optional[str] = None
        steps: List[Dict[str, Any]] = []
        original_room_id = self.seeds.room_id

        try:
            create = self.run_action(task, "create", {"houseId": self.seeds.house_id}, {"name": name})
            steps.append(self.step_from_result("room.create", create, "创建临时房间"))
            if not create.ok:
                raise RuntimeError("room.create 失败")
            created_id = extract_created_id(extract_data(create), ("id", "roomId"))
            if not created_id:
                raise RuntimeError("room.create 未返回 roomId")
            self.seeds.room_id = created_id

            detail = self.run_action(task, "get_room_detail", {"houseId": self.seeds.house_id, "roomId": created_id})
            steps.append(self.step_from_result("room.get_detail.after_create", detail, "创建后查详情"))
            steps.append(self.assertion_step("room.assert_created_detail", contains_resource(extract_data(detail), created_id, name), "详情中能找到新房间", extract_data(detail)))

            update = self.run_action(task, "update", {"houseId": self.seeds.house_id, "roomId": created_id}, {"name": updated_name})
            steps.append(self.step_from_result("room.update", update, "更新临时房间名称"))
            if not update.ok:
                raise RuntimeError("room.update 失败")

            detail_after_update = self.run_action(task, "get_room_detail", {"houseId": self.seeds.house_id, "roomId": created_id})
            steps.append(self.step_from_result("room.get_detail.after_update", detail_after_update, "更新后查详情"))
            detail_data = extract_data(detail_after_update)
            resource = find_resource_by_id(detail_data, created_id)
            name_ok = bool(resource and resource.get("name") == updated_name) or contains_resource(detail_data, None, updated_name)
            steps.append(self.assertion_step("room.assert_updated_name", name_ok, "详情中名称已更新", detail_data))

            delete = self.run_action(task, "delete", {"houseId": self.seeds.house_id, "roomId": created_id})
            steps.append(self.step_from_result("room.delete", delete, "删除临时房间"))
            if not delete.ok:
                raise RuntimeError("room.delete 失败")
            cleanup_id = created_id
            created_id = None

            listing = self.run_action(task, "list", {"houseId": self.seeds.house_id}, {"pageNo": 1, "pageSize": 50}, confirm_side_effect=False)
            steps.append(self.step_from_result("room.list.after_delete", listing, "删除后查列表"))
            steps.append(self.assertion_step("room.assert_deleted_absent", not contains_resource(extract_data(listing), cleanup_id, updated_name), "列表中已不存在临时房间", extract_data(listing)))
        except Exception as exc:
            steps.append(self.assertion_step("room.exception", False, str(exc)))
        finally:
            if created_id:
                cleanup = self.run_action(task, "delete", {"houseId": self.seeds.house_id, "roomId": created_id})
                steps.append(self.step_from_result("room.finally_cleanup", cleanup, "异常时兜底删除临时房间"))
            self.seeds.room_id = original_room_id

        return self.suite_result("room_crud", "房间 create/update/delete 写后查询闭环", steps)

    def run_house_crud(self) -> Dict[str, Any]:
        task = "family_space.manage_house"
        name = f"METADATA_MCP_真实验收家庭_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        updated_name = f"{name}_已更新"
        created_id: Optional[str] = None
        steps: List[Dict[str, Any]] = []

        try:
            create = self.run_action(task, "create", {"houseId": self.seeds.house_id}, {"name": name})
            steps.append(self.step_from_result("house.create", create, "创建临时家庭"))
            if not create.ok:
                raise RuntimeError("house.create 失败")
            created_id = extract_created_id(extract_data(create), ("id", "houseId"))
            if not created_id:
                raise RuntimeError("house.create 未返回 houseId")

            detail = self.run_action(task, "get_house_detail", {"houseId": created_id}, confirm_side_effect=False)
            steps.append(self.step_from_result("house.get_detail.after_create", detail, "创建后查详情"))
            steps.append(self.assertion_step("house.assert_created_detail", contains_resource(extract_data(detail), created_id, name), "详情中能找到新家庭", extract_data(detail)))

            update = self.run_action(
                task,
                "update",
                {"houseId": created_id},
                {"name": updated_name, "areaCode": "8200", "areaName": "澳门"},
            )
            steps.append(self.step_from_result("house.update", update, "更新临时家庭名称和地区"))
            if not update.ok:
                raise RuntimeError("house.update 失败")

            detail_after_update = self.run_action(task, "get_house_detail", {"houseId": created_id}, confirm_side_effect=False)
            steps.append(self.step_from_result("house.get_detail.after_update", detail_after_update, "更新后查详情"))
            detail_data = extract_data(detail_after_update)
            resource = find_resource_by_id(detail_data, created_id)
            name_ok = bool(resource and resource.get("name") == updated_name) or contains_resource(detail_data, None, updated_name)
            steps.append(self.assertion_step("house.assert_updated_name", name_ok, "详情中名称已更新", detail_data))

            delete = self.run_action(task, "delete", {"houseId": created_id})
            steps.append(self.step_from_result("house.delete", delete, "删除临时家庭"))
            if not delete.ok:
                raise RuntimeError("house.delete 失败")
            cleanup_id = created_id
            created_id = None

            listing = self.run_action(task, "list", {"houseId": self.seeds.house_id}, confirm_side_effect=False)
            steps.append(self.step_from_result("house.list.after_delete", listing, "删除后查列表"))
            steps.append(self.assertion_step("house.assert_deleted_absent", not contains_resource(extract_data(listing), cleanup_id, updated_name), "列表中已不存在临时家庭", extract_data(listing)))
        except Exception as exc:
            steps.append(self.assertion_step("house.exception", False, str(exc)))
        finally:
            if created_id:
                cleanup = self.run_action(task, "delete", {"houseId": created_id})
                steps.append(self.step_from_result("house.finally_cleanup", cleanup, "异常时兜底删除临时家庭"))

        return self.suite_result("house_crud", "家庭 create/update/delete 写后查询闭环", steps)

    def run_room_batch_create(self) -> Dict[str, Any]:
        task = "family_space.manage_room"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        names = [f"METADATA_MCP_批量房间_{timestamp}_1", f"METADATA_MCP_批量房间_{timestamp}_2"]
        created_ids: List[str] = []
        steps: List[Dict[str, Any]] = []

        try:
            rooms = [{"name": name, "icon": "room_1"} for name in names]
            if self.seeds.gateway_id:
                for room in rooms:
                    room["gatewayDeviceId"] = self.seeds.gateway_id
                    room["gatewayDeviceIds"] = [self.seeds.gateway_id]

            create = self.run_action(task, "batch_create_room", {"houseId": self.seeds.house_id}, {"rooms": rooms})
            steps.append(self.step_from_result("room.batch_create", create, "批量创建临时房间"))
            if not create.ok:
                raise RuntimeError("room.batch_create 失败")

            listing = self.run_action(task, "list", {"houseId": self.seeds.house_id}, {"pageNo": 1, "pageSize": 100}, confirm_side_effect=False)
            steps.append(self.step_from_result("room.list.after_batch_create", listing, "批量创建后查列表"))
            listing_data = extract_data(listing)
            for name in names:
                resource = find_resource_by_name(listing_data, name)
                room_id = extract_resource_id(resource, ("id", "roomId"))
                if room_id:
                    created_ids.append(room_id)
                steps.append(self.assertion_step(f"room.assert_batch_created.{name}", bool(room_id), f"列表中能找到批量创建房间 {name}", resource))
        except Exception as exc:
            steps.append(self.assertion_step("room_batch.exception", False, str(exc)))
        finally:
            for room_id in created_ids:
                cleanup = self.run_action(task, "delete", {"houseId": self.seeds.house_id, "roomId": room_id})
                steps.append(self.step_from_result(f"room.batch_cleanup.{room_id}", cleanup, "删除批量创建的临时房间"))

            if created_ids:
                listing_after_delete = self.run_action(task, "list", {"houseId": self.seeds.house_id}, {"pageNo": 1, "pageSize": 100}, confirm_side_effect=False)
                steps.append(self.step_from_result("room.list.after_batch_cleanup", listing_after_delete, "批量房间删除后查列表"))
                steps.append(self.assertion_step("room.assert_batch_deleted_absent", all(not contains_resource(extract_data(listing_after_delete), room_id) for room_id in created_ids), "批量房间已全部删除", extract_data(listing_after_delete)))

        return self.suite_result("room_batch_create", "房间 batch_create 写后查询和清理闭环", steps)

    def run_area_crud(self) -> Dict[str, Any]:
        task = "family_space.manage_area"
        name = f"METADATA_MCP_真实验收区域_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        updated_name = f"{name}_已更新"
        created_id: Optional[str] = None
        steps: List[Dict[str, Any]] = []
        original_area_id = self.seeds.area_id

        if not self.seeds.room_id:
            return self.skipped_suite("area_crud", "缺少 roomId，无法按巡检模式创建包含房间的区域")

        try:
            create = self.run_action(
                task,
                "create_area",
                {"houseId": self.seeds.house_id},
                {"name": name, "roomIds": [self.seeds.room_id]},
            )
            steps.append(self.step_from_result("area.create", create, "创建临时区域"))
            if not create.ok:
                raise RuntimeError("area.create 失败")
            created_id = extract_created_id(extract_data(create), ("id", "areaId", "groupId"))
            if not created_id:
                raise RuntimeError("area.create 未返回 areaId")
            self.seeds.area_id = created_id

            detail = self.run_action(task, "get_detail_area", {"houseId": self.seeds.house_id, "areaId": created_id})
            steps.append(self.step_from_result("area.get_detail.after_create", detail, "创建后查详情"))
            steps.append(self.assertion_step("area.assert_created_detail", contains_resource(extract_data(detail), created_id, name), "详情中能找到新区域", extract_data(detail)))

            update = self.run_action(
                task,
                "update_area",
                {"houseId": self.seeds.house_id, "areaId": created_id},
                {"name": updated_name, "roomIds": [self.seeds.room_id]},
            )
            steps.append(self.step_from_result("area.update", update, "更新临时区域名称"))
            if not update.ok:
                raise RuntimeError("area.update 失败")

            detail_after_update = self.run_action(task, "get_detail_area", {"houseId": self.seeds.house_id, "areaId": created_id})
            steps.append(self.step_from_result("area.get_detail.after_update", detail_after_update, "更新后查详情"))
            detail_data = extract_data(detail_after_update)
            resource = find_resource_by_id(detail_data, created_id)
            name_ok = bool(resource and resource.get("name") == updated_name) or contains_resource(detail_data, None, updated_name)
            steps.append(self.assertion_step("area.assert_updated_name", name_ok, "详情中名称已更新", detail_data))

            delete = self.run_action(task, "delete_area", {"houseId": self.seeds.house_id, "areaId": created_id})
            steps.append(self.step_from_result("area.delete", delete, "删除临时区域"))
            if not delete.ok:
                raise RuntimeError("area.delete 失败")
            cleanup_id = created_id
            created_id = None

            listing = self.run_action(task, "list_area", {"houseId": self.seeds.house_id}, {"pageNo": 1, "pageSize": 50}, confirm_side_effect=False)
            steps.append(self.step_from_result("area.list.after_delete", listing, "删除后查列表"))
            steps.append(self.assertion_step("area.assert_deleted_absent", not contains_resource(extract_data(listing), cleanup_id, updated_name), "列表中已不存在临时区域", extract_data(listing)))
        except Exception as exc:
            steps.append(self.assertion_step("area.exception", False, str(exc)))
        finally:
            if created_id:
                cleanup = self.run_action(task, "delete_area", {"houseId": self.seeds.house_id, "areaId": created_id})
                steps.append(self.step_from_result("area.finally_cleanup", cleanup, "异常时兜底删除临时区域"))
            self.seeds.area_id = original_area_id

        return self.suite_result("area_crud", "区域 create/update/delete 写后查询闭环", steps)

    def run_room_area_update(self) -> Dict[str, Any]:
        room_task = "family_space.manage_room"
        area_task = "family_space.manage_area"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        room_name = f"METADATA_MCP_区域调整房间_{timestamp}"
        area_name = f"METADATA_MCP_区域调整区域_{timestamp}"
        room_id: Optional[str] = None
        area_id: Optional[str] = None
        steps: List[Dict[str, Any]] = []

        try:
            create_room = self.run_action(room_task, "create", {"houseId": self.seeds.house_id}, {"name": room_name})
            steps.append(self.step_from_result("room_area.create_room", create_room, "创建临时房间"))
            if not create_room.ok:
                raise RuntimeError("room_area.create_room 失败")
            room_id = extract_created_id(extract_data(create_room), ("id", "roomId"))
            if not room_id:
                raise RuntimeError("room_area.create_room 未返回 roomId")

            create_area = self.run_action(area_task, "create_area", {"houseId": self.seeds.house_id}, {"name": area_name, "roomIds": [self.seeds.room_id] if self.seeds.room_id else []})
            steps.append(self.step_from_result("room_area.create_area", create_area, "创建临时区域"))
            if not create_area.ok:
                raise RuntimeError("room_area.create_area 失败")
            area_id = extract_created_id(extract_data(create_area), ("id", "areaId", "groupId"))
            if not area_id:
                raise RuntimeError("room_area.create_area 未返回 areaId")

            add = self.run_action("family_space.manage_room", "update_room_area", {"houseId": self.seeds.house_id, "roomId": room_id}, {"addAreaList": [area_id]})
            steps.append(self.step_from_result("room_area.add", add, "将临时房间加入临时区域"))
            if not add.ok:
                raise RuntimeError("room_area.add 失败")

            detail_after_add = self.run_action(area_task, "get_detail_area", {"houseId": self.seeds.house_id, "areaId": area_id}, confirm_side_effect=False)
            steps.append(self.step_from_result("room_area.area_detail.after_add", detail_after_add, "添加后查询区域详情"))
            add_data = extract_data(detail_after_add)
            steps.append(self.assertion_step("room_area.assert_added", contains_resource(add_data, room_id), "区域详情中能找到新增房间", add_data))

            remove = self.run_action("family_space.manage_room", "update_room_area", {"houseId": self.seeds.house_id, "roomId": room_id}, {"removeAreaList": [area_id]})
            steps.append(self.step_from_result("room_area.remove", remove, "将临时房间移出临时区域"))
            if not remove.ok:
                raise RuntimeError("room_area.remove 失败")

            detail_after_remove = self.run_action(area_task, "get_detail_area", {"houseId": self.seeds.house_id, "areaId": area_id}, confirm_side_effect=False)
            steps.append(self.step_from_result("room_area.area_detail.after_remove", detail_after_remove, "移除后查询区域详情"))
            remove_data = extract_data(detail_after_remove)
            steps.append(self.assertion_step("room_area.assert_removed", not contains_resource(remove_data, room_id), "区域详情中已不存在临时房间", remove_data))
        except Exception as exc:
            steps.append(self.assertion_step("room_area.exception", False, str(exc)))
        finally:
            if area_id:
                cleanup_area = self.run_action(area_task, "delete_area", {"houseId": self.seeds.house_id, "areaId": area_id})
                steps.append(self.step_from_result("room_area.cleanup_area", cleanup_area, "删除临时区域"))
            if room_id:
                cleanup_room = self.run_action(room_task, "delete", {"houseId": self.seeds.house_id, "roomId": room_id})
                steps.append(self.step_from_result("room_area.cleanup_room", cleanup_room, "删除临时房间"))

        return self.suite_result("room_area_update", "房间区域 add/remove 写后查询和恢复闭环", steps)

    def run_legacy_area_group_crud(self) -> Dict[str, Any]:
        task = "family_space.manage_area"
        room_task = "family_space.manage_room"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"METADATA_MCP_真实验收旧区域组_{timestamp}"
        updated_name = f"{name}_已更新"
        extra_room_name = f"METADATA_MCP_旧区域组附加房间_{timestamp}"
        created_id: Optional[str] = None
        extra_room_id: Optional[str] = None
        steps: List[Dict[str, Any]] = []

        if not self.seeds.room_id:
            return self.skipped_suite("legacy_area_group_crud", "缺少 roomId，无法按巡检模式创建 legacy 区域组")

        try:
            create_room = self.run_action(room_task, "create", {"houseId": self.seeds.house_id}, {"name": extra_room_name})
            steps.append(self.step_from_result("area_group.create_extra_room", create_room, "创建区域组更新用临时房间"))
            if not create_room.ok:
                raise RuntimeError("area_group.create_extra_room 失败")
            extra_room_id = extract_created_id(extract_data(create_room), ("id", "roomId"))
            if not extra_room_id:
                raise RuntimeError("area_group.create_extra_room 未返回 roomId")

            create = self.run_action(task, "create_area_group", {"houseId": self.seeds.house_id}, {"name": name, "roomIds": [self.seeds.room_id]})
            steps.append(self.step_from_result("area_group.create", create, "创建临时 legacy 区域组"))
            if not create.ok:
                raise RuntimeError("area_group.create 失败")
            created_id = extract_created_id(extract_data(create), ("id", "groupId", "userGroupId"))
            if not created_id:
                listing_after_create = self.run_action(task, "list_area_group", {"houseId": self.seeds.house_id}, confirm_side_effect=False)
                steps.append(self.step_from_result("area_group.list.find_created", listing_after_create, "创建后通过列表定位区域组 ID"))
                created_id = extract_resource_id(find_resource_by_name(extract_data(listing_after_create), name), ("id", "groupId", "userGroupId"))
            if not created_id:
                raise RuntimeError("area_group.create 未返回 groupId")

            fuzzy = self.run_action(task, "fuzzy_search_area_group", {"houseId": self.seeds.house_id}, {"fuzzyName": name}, confirm_side_effect=False)
            steps.append(self.step_from_result("area_group.fuzzy_search", fuzzy, "按名称模糊查询临时区域组"))
            steps.append(self.assertion_step("area_group.assert_fuzzy_found", contains_resource(extract_data(fuzzy), created_id, name), "模糊查询能找到临时区域组", extract_data(fuzzy)))

            update = self.run_action(task, "update_area_group", {"houseId": self.seeds.house_id, "groupId": created_id}, {"name": updated_name, "roomIds": [self.seeds.room_id, extra_room_id]})
            steps.append(self.step_from_result("area_group.update", update, "更新 legacy 区域组名称和房间"))
            if not update.ok:
                raise RuntimeError("area_group.update 失败")

            listing_after_update = self.run_action(task, "list_area_group", {"houseId": self.seeds.house_id}, confirm_side_effect=False)
            steps.append(self.step_from_result("area_group.list.after_update", listing_after_update, "更新后查列表"))
            update_data = extract_data(listing_after_update)
            updated_resource = find_resource_by_id(update_data, created_id) or find_resource_by_name(update_data, updated_name)
            steps.append(self.assertion_step("area_group.assert_updated", bool(updated_resource and updated_resource.get("name") == updated_name), "列表中名称已更新", updated_resource))

            delete = self.run_action(task, "delete_area_group", {"houseId": self.seeds.house_id, "groupId": created_id})
            steps.append(self.step_from_result("area_group.delete", delete, "删除临时 legacy 区域组"))
            if not delete.ok:
                raise RuntimeError("area_group.delete 失败")
            cleanup_id = created_id
            created_id = None

            listing_after_delete = self.run_action(task, "list_area_group", {"houseId": self.seeds.house_id}, confirm_side_effect=False)
            steps.append(self.step_from_result("area_group.list.after_delete", listing_after_delete, "删除后查列表"))
            steps.append(self.assertion_step("area_group.assert_deleted_absent", not contains_resource(extract_data(listing_after_delete), cleanup_id, updated_name), "列表中已不存在临时区域组", extract_data(listing_after_delete)))
        except Exception as exc:
            steps.append(self.assertion_step("area_group.exception", False, str(exc)))
        finally:
            if created_id:
                cleanup_group = self.run_action(task, "delete_area_group", {"houseId": self.seeds.house_id, "groupId": created_id})
                steps.append(self.step_from_result("area_group.finally_cleanup", cleanup_group, "异常时兜底删除临时 legacy 区域组"))
            if extra_room_id:
                cleanup_room = self.run_action(room_task, "delete", {"houseId": self.seeds.house_id, "roomId": extra_room_id})
                steps.append(self.step_from_result("area_group.cleanup_extra_room", cleanup_room, "删除区域组更新用临时房间"))

        return self.suite_result("legacy_area_group_crud", "legacy 区域组 create/update/delete 与 fuzzy 查询闭环", steps)

    def run_scene_and_favorite(self) -> Dict[str, Any]:
        scene_task = "scene_automation.manage_scene"
        favorite_task = "home_organization.manage_favorite"
        name = f"METADATA_MCP_真实验收情景_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        updated_name = f"{name}_已更新"
        created_id: Optional[str] = None
        steps: List[Dict[str, Any]] = []
        original_scene_id = self.seeds.scene_id

        if not self.seeds.room_id:
            return self.skipped_suite("scene_favorite_crud", "缺少 roomId，无法构造不会触发真实设备的房间情景动作")

        actions = [
            {
                "typeId": "1",
                "resId": self.seeds.room_id,
                "resName": "Metadata MCP 验收房间",
                "params": {"set": {"p": True}},
                "rank": 0,
            }
        ]
        favorite_item: Optional[Dict[str, Any]] = None

        try:
            create = self.run_action(scene_task, "create", {"houseId": self.seeds.house_id}, {"name": name, "actions": actions, "img": "scene_1", "valid": 1})
            steps.append(self.step_from_result("scene.create", create, "创建临时情景"))
            if not create.ok:
                raise RuntimeError("scene.create 失败")
            created_id = extract_created_id(extract_data(create), ("id", "sceneId"))
            if not created_id:
                raise RuntimeError("scene.create 未返回 sceneId")
            self.seeds.scene_id = created_id

            detail = self.run_action(scene_task, "get_scene_detail", {"sceneId": created_id})
            steps.append(self.step_from_result("scene.get_detail.after_create", detail, "创建后查详情"))
            detail_data = extract_data_dict(detail)
            steps.append(self.assertion_step("scene.assert_created_detail", contains_resource(detail_data, created_id, name), "详情中能找到新情景", detail_data))

            update = self.run_action(
                scene_task,
                "update",
                {"houseId": self.seeds.house_id, "sceneId": created_id},
                {
                    "name": updated_name,
                    "actions": detail_data.get("details") or actions,
                    "addToFav": "0",
                    "gatewayDeviceId": detail_data.get("gatewayDeviceId", self.seeds.gateway_id or "0"),
                    "img": detail_data.get("img", "scene_1"),
                    "roomId": detail_data.get("roomId", "0"),
                    "valid": 1,
                },
            )
            steps.append(self.step_from_result("scene.update", update, "更新临时情景名称和动作"))
            if not update.ok:
                raise RuntimeError("scene.update 失败")

            detail_after_update = self.run_action(scene_task, "get_scene_detail", {"sceneId": created_id})
            steps.append(self.step_from_result("scene.get_detail.after_update", detail_after_update, "更新后查详情"))
            detail_data = extract_data(detail_after_update)
            resource = find_resource_by_id(detail_data, created_id)
            name_ok = bool(resource and resource.get("name") == updated_name) or contains_resource(detail_data, None, updated_name)
            steps.append(self.assertion_step("scene.assert_updated_name", name_ok, "详情中名称已更新", detail_data))

            test_scene = self.run_action(
                scene_task,
                "test",
                {"houseId": self.seeds.house_id},
                {
                    "name": f"{name}_测试执行",
                    "actions": detail_data.get("details") or actions,
                    "addToFav": "0",
                    "gatewayDeviceId": detail_data.get("gatewayDeviceId", self.seeds.gateway_id or "0") if isinstance(detail_data, dict) else self.seeds.gateway_id or "0",
                    "img": detail_data.get("img", "scene_1") if isinstance(detail_data, dict) else "scene_1",
                    "valid": 1,
                },
            )
            steps.append(self.step_from_result("scene.test", test_scene, "测试执行临时情景动作"))

            favorite_item = {"resId": created_id, "houseId": self.seeds.house_id, "typeId": "6", "rank": 999}
            favorite_update = self.run_action(favorite_task, "batch_update_favorite", {"houseId": self.seeds.house_id}, {"items": [favorite_item]})
            steps.append(self.step_from_result("favorite.batch_update_scene", favorite_update, "将临时情景加入首页收藏"))
            if favorite_update.ok:
                favorite_list = self.run_action(favorite_task, "list_all_favorite", {"houseId": self.seeds.house_id}, confirm_side_effect=False)
                steps.append(self.step_from_result("favorite.list.after_update", favorite_list, "收藏后查列表"))
                steps.append(self.assertion_step("favorite.assert_scene_present", contains_resource(extract_data(favorite_list), created_id), "收藏列表中能找到临时情景", extract_data(favorite_list)))

                favorite_delete = self.run_action(favorite_task, "batch_delete_favorite", {"houseId": self.seeds.house_id}, {"items": [favorite_item]}, confirm_side_effect=False)
                steps.append(self.step_from_result("favorite.batch_delete_scene", favorite_delete, "删除临时情景收藏"))
                if favorite_delete.ok:
                    favorite_list_after_delete = self.run_action(favorite_task, "list_all_favorite", {"houseId": self.seeds.house_id}, confirm_side_effect=False)
                    steps.append(self.step_from_result("favorite.list.after_delete", favorite_list_after_delete, "删除收藏后查列表"))
                    steps.append(self.assertion_step("favorite.assert_scene_absent", not contains_resource(extract_data(favorite_list_after_delete), created_id), "收藏列表中已不存在临时情景", extract_data(favorite_list_after_delete)))

            favorite_insert = self.run_action(favorite_task, "batch_insert_favorite", {"houseId": self.seeds.house_id}, {"items": [favorite_item]})
            steps.append(self.step_from_result("favorite.batch_insert_scene", favorite_insert, "用 batch_insert 添加临时情景收藏"))
            if favorite_insert.ok:
                favorite_list_after_insert = self.run_action(favorite_task, "list_all_favorite", {"houseId": self.seeds.house_id}, confirm_side_effect=False)
                steps.append(self.step_from_result("favorite.list.after_insert", favorite_list_after_insert, "batch_insert 后查收藏列表"))
                steps.append(self.assertion_step("favorite.assert_scene_inserted", contains_resource(extract_data(favorite_list_after_insert), created_id), "收藏列表中能找到 batch_insert 添加的临时情景", extract_data(favorite_list_after_insert)))

                favorite_delete_after_insert = self.run_action(favorite_task, "batch_delete_favorite", {"houseId": self.seeds.house_id}, {"items": [favorite_item]}, confirm_side_effect=False)
                steps.append(self.step_from_result("favorite.batch_delete_after_insert", favorite_delete_after_insert, "删除 batch_insert 添加的临时情景收藏"))
                if favorite_delete_after_insert.ok:
                    favorite_list_after_insert_delete = self.run_action(favorite_task, "list_all_favorite", {"houseId": self.seeds.house_id}, confirm_side_effect=False)
                    steps.append(self.step_from_result("favorite.list.after_insert_delete", favorite_list_after_insert_delete, "batch_insert 收藏删除后查列表"))
                    steps.append(self.assertion_step("favorite.assert_scene_insert_absent", not contains_resource(extract_data(favorite_list_after_insert_delete), created_id), "收藏列表中已不存在 batch_insert 临时情景", extract_data(favorite_list_after_insert_delete)))

            delete = self.run_action(scene_task, "delete", {"sceneId": created_id})
            steps.append(self.step_from_result("scene.delete", delete, "删除临时情景"))
            if not delete.ok:
                raise RuntimeError("scene.delete 失败")
            cleanup_id = created_id
            created_id = None

            listing = self.run_action(scene_task, "list_all_scene", {"houseId": self.seeds.house_id}, confirm_side_effect=False)
            steps.append(self.step_from_result("scene.list.after_delete", listing, "删除后查列表"))
            steps.append(self.assertion_step("scene.assert_deleted_absent", not contains_resource(extract_data(listing), cleanup_id, updated_name), "列表中已不存在临时情景", extract_data(listing)))
        except Exception as exc:
            steps.append(self.assertion_step("scene_favorite.exception", False, str(exc)))
        finally:
            if favorite_item:
                cleanup_favorite = self.run_action(favorite_task, "batch_delete_favorite", {"houseId": self.seeds.house_id}, {"items": [favorite_item]}, confirm_side_effect=False)
                steps.append(self.step_from_result("favorite.finally_cleanup", cleanup_favorite, "兜底删除临时情景收藏"))
            if created_id:
                cleanup = self.run_action(scene_task, "delete", {"sceneId": created_id})
                steps.append(self.step_from_result("scene.finally_cleanup", cleanup, "异常时兜底删除临时情景"))
            self.seeds.scene_id = original_scene_id

        return self.suite_result("scene_favorite_crud", "情景 create/update/delete 与收藏 update/delete 写后查询闭环", steps)

    def run_device_group_crud(self, device_ids: List[str]) -> Dict[str, Any]:
        task = "device_management.manage_device_group"
        name = f"METADATA_MCP_真实验收设备组_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        updated_name = f"{name}_已更新"
        created_id: Optional[str] = None
        steps: List[Dict[str, Any]] = []
        original_group_id = self.seeds.group_id

        if not self.seeds.room_id:
            return self.skipped_suite("device_group_crud", "缺少 roomId，无法创建设备组")
        if not device_ids:
            return self.skipped_suite("device_group_crud", "缺少 deviceIds，未执行设备组写接口")

        try:
            create = self.run_action(
                task,
                "create",
                {"houseId": self.seeds.house_id, "roomId": self.seeds.room_id},
                {"name": name, "deviceIds": device_ids},
            )
            steps.append(self.step_from_result("device_group.create", create, "创建临时设备组"))
            if not create.ok:
                raise RuntimeError("device_group.create 失败")
            created_id = extract_created_id(extract_data(create), ("id", "groupId", "meshGroupId"))
            if not created_id:
                raise RuntimeError("device_group.create 未返回 groupId")
            self.seeds.group_id = created_id

            detail = self.run_action(task, "get_group_detail", {"groupId": created_id})
            steps.append(self.step_from_result("device_group.get_detail.after_create", detail, "创建后查详情"))
            steps.append(self.assertion_step("device_group.assert_created_detail", contains_resource(extract_data(detail), created_id, name), "详情中能找到新设备组", extract_data(detail)))

            update = self.run_action(task, "update", {"groupId": created_id}, {"name": updated_name})
            steps.append(self.step_from_result("device_group.update", update, "更新临时设备组名称"))
            if not update.ok:
                raise RuntimeError("device_group.update 失败")

            detail_after_update = self.run_action(task, "get_group_detail", {"groupId": created_id})
            steps.append(self.step_from_result("device_group.get_detail.after_update", detail_after_update, "更新后查详情"))
            detail_data = extract_data(detail_after_update)
            resource = find_resource_by_id(detail_data, created_id)
            name_ok = bool(resource and resource.get("name") == updated_name) or contains_resource(detail_data, None, updated_name)
            steps.append(self.assertion_step("device_group.assert_updated_name", name_ok, "详情中名称已更新", detail_data))

            delete = self.run_action(task, "delete", {"groupId": created_id})
            steps.append(self.step_from_result("device_group.delete", delete, "删除临时设备组"))
            if not delete.ok:
                raise RuntimeError("device_group.delete 失败")
            created_id = None
        except Exception as exc:
            steps.append(self.assertion_step("device_group.exception", False, str(exc)))
        finally:
            if created_id:
                cleanup = self.run_action(task, "delete", {"groupId": created_id})
                steps.append(self.step_from_result("device_group.finally_cleanup", cleanup, "异常时兜底删除临时设备组"))
            self.seeds.group_id = original_group_id

        return self.suite_result("device_group_crud", "设备组 create/update/delete 写后查询闭环", steps)

    def run_device_group_member_update(self, _device_ids: List[str]) -> Dict[str, Any]:
        task = "device_management.manage_device_group"
        create_task = "device_onboarding.create_device_slot"
        remove_task = "device_management.remove_device"
        name = f"METADATA_MCP_成员变更设备组_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        created_id: Optional[str] = None
        temp_device_ids: List[str] = []
        steps: List[Dict[str, Any]] = []

        if not self.seeds.room_id:
            return self.skipped_suite("device_group_member_update", "缺少 roomId，无法创建设备组")
        try:
            while len(temp_device_ids) < 3:
                index = len(temp_device_ids) + 1
                temp_name = f"{name}_临时设备_{index}"
                payload = {
                    "name": temp_name,
                    "pid": "264193",
                    "virtual": False,
                    "connectType": 1,
                }
                if self.seeds.gateway_id:
                    payload["gatewayDeviceId"] = self.seeds.gateway_id
                create_device = self.run_action(create_task, "create", {"houseId": self.seeds.house_id, "roomId": self.seeds.room_id}, payload)
                steps.append(self.step_from_result(f"device_group_member.create_temp_device.{index}", create_device, "创建成员变更用临时设备坑位"))
                if not create_device.ok:
                    raise RuntimeError("device_group_member.create_temp_device 失败")
                temp_device_id = extract_created_id(extract_data(create_device), ("id", "deviceId"))
                if not temp_device_id:
                    listing = self.run_action(create_task, "list_all_device", {"houseId": self.seeds.house_id}, confirm_side_effect=False)
                    steps.append(self.step_from_result(f"device_group_member.list.find_temp_device.{index}", listing, "通过设备列表定位临时设备坑位"))
                    temp_device_id = extract_resource_id(find_resource_by_name(extract_data(listing), temp_name), ("id", "deviceId"))
                if not temp_device_id:
                    raise RuntimeError("device_group_member.create_temp_device 未返回 deviceId")
                temp_device_ids.append(temp_device_id)

            first_device_id, removed_device_id, added_device_id = temp_device_ids

            create = self.run_action(
                task,
                "create",
                {"houseId": self.seeds.house_id, "roomId": self.seeds.room_id},
                {"name": name, "deviceIds": [first_device_id, removed_device_id]},
            )
            steps.append(self.step_from_result("device_group_member.create_group", create, "使用前两个同型号临时设备创建临时设备组"))
            if not create.ok:
                raise RuntimeError("device_group_member.create_group 失败")
            created_id = extract_created_id(extract_data(create), ("id", "groupId", "meshGroupId"))
            if not created_id:
                raise RuntimeError("device_group_member.create_group 未返回 groupId")

            detail_after_create = self.run_action(task, "get_group_detail", {"groupId": created_id}, confirm_side_effect=False)
            steps.append(self.step_from_result("device_group_member.detail.after_create", detail_after_create, "创建后查设备组详情"))
            created_detail_data = extract_data(detail_after_create)
            initial_members_ok = contains_resource(created_detail_data, first_device_id) and contains_resource(created_detail_data, removed_device_id)
            steps.append(self.assertion_step("device_group_member.assert_initial_members", initial_members_ok, "设备组详情中能找到前两个初始成员", created_detail_data))

            remove = self.run_action(task, "update_group_devices", {"houseId": self.seeds.house_id, "groupId": created_id}, {"removeDeviceList": [{"id": removed_device_id}]})
            steps.append(self.step_from_result("device_group_member.update_remove", remove, "从临时设备组移除第二个设备"))
            if not remove.ok:
                raise RuntimeError("device_group_member.update_remove 失败")

            detail_after_remove = self.run_action(task, "get_group_detail", {"groupId": created_id}, confirm_side_effect=False)
            steps.append(self.step_from_result("device_group_member.detail.after_remove", detail_after_remove, "移除后查设备组详情"))
            remove_detail_data = extract_data(detail_after_remove)
            removed_ok = contains_resource(remove_detail_data, first_device_id) and not contains_resource(remove_detail_data, removed_device_id)
            steps.append(self.assertion_step("device_group_member.assert_removed", removed_ok, "设备组详情中保留第一个设备且已不存在被移除成员", remove_detail_data))

            add = self.run_action(task, "update_group_devices", {"houseId": self.seeds.house_id, "groupId": created_id}, {"addDeviceList": [{"id": added_device_id}]})
            steps.append(self.step_from_result("device_group_member.update_add", add, "向临时设备组添加第三个同型号设备"))
            if not add.ok:
                raise RuntimeError("device_group_member.update_add 失败")

            detail_after_add = self.run_action(task, "get_group_detail", {"groupId": created_id}, confirm_side_effect=False)
            steps.append(self.step_from_result("device_group_member.detail.after_add", detail_after_add, "添加后查设备组详情"))
            add_detail_data = extract_data(detail_after_add)
            added_ok = contains_resource(add_detail_data, first_device_id) and contains_resource(add_detail_data, added_device_id) and not contains_resource(add_detail_data, removed_device_id)
            steps.append(self.assertion_step("device_group_member.assert_added", added_ok, "设备组详情中能找到第一个设备和新增第三个设备，且不存在被移除成员", add_detail_data))

            delete = self.run_action(task, "delete", {"groupId": created_id})
            steps.append(self.step_from_result("device_group_member.delete_group", delete, "删除临时设备组"))
            if delete.ok:
                created_id = None
        except RuntimeError as exc:
            steps.append(self.assertion_step("device_group_member.exception", False, str(exc)))
        except Exception as exc:
            steps.append(self.assertion_step("device_group_member.exception", False, str(exc)))
        finally:
            if created_id:
                cleanup = self.run_action(task, "delete", {"groupId": created_id})
                steps.append(self.step_from_result("device_group_member.finally_cleanup", cleanup, "异常时兜底删除临时设备组"))
            for temp_device_id in temp_device_ids:
                cleanup_device = self.run_action(remove_task, "delete_device", {"deviceId": temp_device_id})
                steps.append(self.step_from_result(f"device_group_member.delete_temp_device.{temp_device_id}", cleanup_device, "删除成员变更用临时设备坑位"))

        return self.suite_result("device_group_member_update", "设备组成员 add/remove 写后查询和恢复闭环", steps)

    def run_device_slot_crud(self) -> Dict[str, Any]:
        create_task = "device_onboarding.create_device_slot"
        query_task = "device_management.query_device"
        update_task = "device_management.update_device"
        remove_task = "device_management.remove_device"
        name = f"METADATA_MCP_真实验收设备坑位_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        updated_name = f"{name}_已更新"
        created_id: Optional[str] = None
        steps: List[Dict[str, Any]] = []

        if not self.seeds.room_id:
            return self.skipped_suite("device_slot_crud", "缺少 roomId，无法创建设备坑位")

        try:
            payload = {
                "name": name,
                "pid": "264193",
                "virtual": False,
                "connectType": 1,
            }
            if self.seeds.gateway_id:
                payload["gatewayDeviceId"] = self.seeds.gateway_id
            create = self.run_action(create_task, "create", {"houseId": self.seeds.house_id, "roomId": self.seeds.room_id}, payload)
            steps.append(self.step_from_result("device_slot.create", create, "创建临时设备坑位"))
            if not create.ok:
                raise RuntimeError("device_slot.create 失败")
            created_id = extract_created_id(extract_data(create), ("id", "deviceId"))
            if not created_id:
                listing = self.run_action(create_task, "list_all_device", {"houseId": self.seeds.house_id}, confirm_side_effect=False)
                steps.append(self.step_from_result("device_slot.list.find_created", listing, "创建后通过设备列表定位设备坑位 ID"))
                created_id = extract_resource_id(find_resource_by_name(extract_data(listing), name), ("id", "deviceId"))
            if not created_id:
                raise RuntimeError("device_slot.create 未返回 deviceId")

            detail = self.run_action(query_task, "get_device_detail", {"deviceId": created_id}, confirm_side_effect=False)
            steps.append(self.step_from_result("device_slot.get_detail.after_create", detail, "创建后查设备详情"))
            steps.append(self.assertion_step("device_slot.assert_created_detail", contains_resource(extract_data(detail), created_id, name), "详情中能找到新设备坑位", extract_data(detail)))

            update = self.run_action(update_task, "update", {"houseId": self.seeds.house_id, "deviceId": created_id}, {"name": updated_name, "mac": "F8:24:41:00:0B:65"})
            steps.append(self.step_from_result("device_slot.update", update, "更新临时设备坑位名称和 MAC"))
            if not update.ok:
                raise RuntimeError("device_slot.update 失败")

            detail_after_update = self.run_action(query_task, "get_device_detail", {"deviceId": created_id}, confirm_side_effect=False)
            steps.append(self.step_from_result("device_slot.get_detail.after_update", detail_after_update, "更新后查设备详情"))
            update_data = extract_data(detail_after_update)
            resource = find_resource_by_id(update_data, created_id)
            name_ok = bool(resource and resource.get("name") == updated_name) or contains_resource(update_data, None, updated_name)
            steps.append(self.assertion_step("device_slot.assert_updated_name", name_ok, "详情中名称已更新", update_data))

            delete = self.run_action(remove_task, "delete_device", {"deviceId": created_id})
            steps.append(self.step_from_result("device_slot.delete", delete, "删除临时设备坑位"))
            if not delete.ok:
                raise RuntimeError("device_slot.delete 失败")
            cleanup_id = created_id
            created_id = None

            listing_after_delete = self.run_action(create_task, "list_all_device", {"houseId": self.seeds.house_id}, confirm_side_effect=False)
            steps.append(self.step_from_result("device_slot.list.after_delete", listing_after_delete, "删除后查设备列表"))
            steps.append(self.assertion_step("device_slot.assert_deleted_absent", not contains_resource(extract_data(listing_after_delete), cleanup_id, updated_name), "列表中已不存在临时设备坑位", extract_data(listing_after_delete)))
        except Exception as exc:
            steps.append(self.assertion_step("device_slot.exception", False, str(exc)))
        finally:
            if created_id:
                cleanup = self.run_action(remove_task, "delete_device", {"deviceId": created_id})
                steps.append(self.step_from_result("device_slot.finally_cleanup", cleanup, "异常时兜底删除临时设备坑位"))

        return self.suite_result("device_slot_crud", "设备坑位 create/update/delete 写后查询闭环", steps)

    def run_device_slot_batch_create(self) -> Dict[str, Any]:
        create_task = "device_onboarding.create_device_slot"
        remove_task = "device_management.remove_device"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        names = [f"METADATA_MCP_批量设备坑位_{timestamp}_1", f"METADATA_MCP_批量设备坑位_{timestamp}_2"]
        created_ids: List[str] = []
        steps: List[Dict[str, Any]] = []

        if not self.seeds.room_id:
            return self.skipped_suite("device_slot_batch_create", "缺少 roomId，无法批量创建设备坑位")

        try:
            devices = [{"name": name, "virtual": False, "connectType": 1} for name in names]
            if self.seeds.gateway_id:
                for device in devices:
                    device["gatewayDeviceId"] = self.seeds.gateway_id
            create = self.run_action(create_task, "batch_create_device_slot", {"houseId": self.seeds.house_id, "roomId": self.seeds.room_id}, {"devices": devices})
            steps.append(self.step_from_result("device_slot.batch_create", create, "批量创建临时设备坑位"))
            if not create.ok:
                raise RuntimeError("device_slot.batch_create 失败")

            listing = self.run_action(create_task, "list_all_device", {"houseId": self.seeds.house_id}, confirm_side_effect=False)
            steps.append(self.step_from_result("device_slot.list.after_batch_create", listing, "批量创建后查设备列表"))
            listing_data = extract_data(listing)
            for name in names:
                resource = find_resource_by_name(listing_data, name)
                device_id = extract_resource_id(resource, ("id", "deviceId"))
                if device_id:
                    created_ids.append(device_id)
                steps.append(self.assertion_step(f"device_slot.assert_batch_created.{name}", bool(device_id), f"列表中能找到批量创建设备坑位 {name}", resource))
        except Exception as exc:
            steps.append(self.assertion_step("device_slot_batch.exception", False, str(exc)))
        finally:
            for device_id in created_ids:
                cleanup = self.run_action(remove_task, "delete_device", {"deviceId": device_id})
                steps.append(self.step_from_result(f"device_slot.batch_cleanup.{device_id}", cleanup, "删除批量创建的临时设备坑位"))

            if created_ids:
                listing_after_delete = self.run_action(create_task, "list_all_device", {"houseId": self.seeds.house_id}, confirm_side_effect=False)
                steps.append(self.step_from_result("device_slot.list.after_batch_cleanup", listing_after_delete, "批量设备坑位删除后查列表"))
                steps.append(self.assertion_step("device_slot.assert_batch_deleted_absent", all(not contains_resource(extract_data(listing_after_delete), device_id) for device_id in created_ids), "批量设备坑位已全部删除", extract_data(listing_after_delete)))

        return self.suite_result("device_slot_batch_create", "设备坑位 batch_create 写后查询和清理闭环", steps)

    def run_device_unbind_and_clear_mac(self) -> Dict[str, Any]:
        create_task = "device_onboarding.create_device_slot"
        query_task = "device_management.query_device"
        update_task = "device_management.update_device"
        remove_task = "device_management.remove_device"
        name = f"METADATA_MCP_MAC清除设备坑位_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        created_id: Optional[str] = None
        steps: List[Dict[str, Any]] = []

        if not self.seeds.room_id:
            return self.skipped_suite("device_unbind_clear_mac", "缺少 roomId，无法创建 MAC 清除验收设备坑位")

        try:
            payload = {"name": name, "pid": "264193", "virtual": False, "connectType": 1}
            if self.seeds.gateway_id:
                payload["gatewayDeviceId"] = self.seeds.gateway_id
            create = self.run_action(create_task, "create", {"houseId": self.seeds.house_id, "roomId": self.seeds.room_id}, payload)
            steps.append(self.step_from_result("device_unbind.create", create, "创建临时设备坑位"))
            if not create.ok:
                raise RuntimeError("device_unbind.create 失败")
            created_id = extract_created_id(extract_data(create), ("id", "deviceId"))
            if not created_id:
                listing = self.run_action(create_task, "list_all_device", {"houseId": self.seeds.house_id}, confirm_side_effect=False)
                steps.append(self.step_from_result("device_unbind.list.find_created", listing, "创建后通过设备列表定位设备坑位 ID"))
                created_id = extract_resource_id(find_resource_by_name(extract_data(listing), name), ("id", "deviceId"))
            if not created_id:
                raise RuntimeError("device_unbind.create 未返回 deviceId")

            update = self.run_action(update_task, "update", {"houseId": self.seeds.house_id, "deviceId": created_id}, {"mac": "F8:24:41:00:0B:66"})
            steps.append(self.step_from_result("device_unbind.set_mac", update, "先写入 MAC 供清除校验"))
            if not update.ok:
                raise RuntimeError("device_unbind.set_mac 失败")

            clear = self.run_action(remove_task, "unbind_and_clear_mac", {"deviceId": created_id})
            steps.append(self.step_from_result("device_unbind.unbind_and_clear_mac", clear, "解绑并清除临时设备 MAC"))
            if not clear.ok:
                raise RuntimeError("device_unbind.unbind_and_clear_mac 失败")

            detail = self.run_action(query_task, "get_device_detail", {"deviceId": created_id}, confirm_side_effect=False)
            steps.append(self.step_from_result("device_unbind.get_detail.after_clear", detail, "清除后查设备详情"))
            resource = find_resource_by_id(extract_data(detail), created_id)
            mac_value = resource.get("mac") if resource else None
            steps.append(self.assertion_step("device_unbind.assert_mac_cleared", mac_value in (None, "", "00:00:00:00:00:00"), "MAC 已清除或不再返回", resource))

            delete = self.run_action(remove_task, "delete_device", {"deviceId": created_id})
            steps.append(self.step_from_result("device_unbind.cleanup_delete", delete, "删除 MAC 清除验收设备坑位"))
            if delete.ok:
                created_id = None
        except Exception as exc:
            steps.append(self.assertion_step("device_unbind.exception", False, str(exc)))
        finally:
            if created_id:
                cleanup = self.run_action(remove_task, "delete_device", {"deviceId": created_id})
                steps.append(self.step_from_result("device_unbind.finally_cleanup", cleanup, "异常时兜底删除临时设备坑位"))

        return self.suite_result("device_unbind_clear_mac", "设备 unbind_and_clear_mac 仅作用于临时坑位的写后查询闭环", steps)

    def run_device_unbind(self) -> Dict[str, Any]:
        create_task = "device_onboarding.create_device_slot"
        query_task = "device_management.query_device"
        update_task = "device_management.update_device"
        remove_task = "device_management.remove_device"
        name = f"METADATA_MCP_解绑设备坑位_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        created_id: Optional[str] = None
        steps: List[Dict[str, Any]] = []

        if not self.seeds.room_id:
            return self.skipped_suite("device_unbind", "缺少 roomId，无法创建解绑验收设备坑位")

        try:
            payload = {"name": name, "pid": "264193", "virtual": False, "connectType": 1}
            if self.seeds.gateway_id:
                payload["gatewayDeviceId"] = self.seeds.gateway_id
            create = self.run_action(create_task, "create", {"houseId": self.seeds.house_id, "roomId": self.seeds.room_id}, payload)
            steps.append(self.step_from_result("device_unbind_plain.create", create, "创建临时设备坑位"))
            if not create.ok:
                raise RuntimeError("device_unbind_plain.create 失败")
            created_id = extract_created_id(extract_data(create), ("id", "deviceId"))
            if not created_id:
                listing = self.run_action(create_task, "list_all_device", {"houseId": self.seeds.house_id}, confirm_side_effect=False)
                steps.append(self.step_from_result("device_unbind_plain.list.find_created", listing, "创建后通过设备列表定位设备坑位 ID"))
                created_id = extract_resource_id(find_resource_by_name(extract_data(listing), name), ("id", "deviceId"))
            if not created_id:
                raise RuntimeError("device_unbind_plain.create 未返回 deviceId")

            update = self.run_action(update_task, "update", {"houseId": self.seeds.house_id, "deviceId": created_id}, {"mac": "F8:24:41:00:0B:67"})
            steps.append(self.step_from_result("device_unbind_plain.set_mac", update, "先写入 MAC 供解绑校验"))
            if not update.ok:
                raise RuntimeError("device_unbind_plain.set_mac 失败")

            unbind = self.run_action(remove_task, "unbind", {"deviceId": created_id})
            steps.append(self.step_from_result("device_unbind_plain.unbind", unbind, "解绑临时设备坑位"))
            if not unbind.ok:
                raise RuntimeError("device_unbind_plain.unbind 失败")

            detail = self.run_action(query_task, "get_device_detail", {"deviceId": created_id}, confirm_side_effect=False)
            steps.append(self.step_from_result("device_unbind_plain.get_detail.after_unbind", detail, "解绑后查设备详情"))
            steps.append(self.assertion_step("device_unbind_plain.assert_detail_query_ok", bool(getattr(detail, "ok", False)), "解绑后设备详情接口仍可查询", getattr(detail, "response", None)))

            delete = self.run_action(remove_task, "delete_device", {"deviceId": created_id})
            steps.append(self.step_from_result("device_unbind_plain.cleanup_delete", delete, "删除解绑验收设备坑位"))
            if delete.ok:
                created_id = None
        except Exception as exc:
            steps.append(self.assertion_step("device_unbind_plain.exception", False, str(exc)))
        finally:
            if created_id:
                cleanup = self.run_action(remove_task, "delete_device", {"deviceId": created_id})
                steps.append(self.step_from_result("device_unbind_plain.finally_cleanup", cleanup, "异常时兜底删除临时设备坑位"))

        return self.suite_result("device_unbind", "设备 unbind 仅作用于临时坑位的写后查询闭环", steps)

    def run_gateway_crud(self) -> Dict[str, Any]:
        task = "device_onboarding.manage_gateway_onboarding"
        remove_task = "device_management.remove_device"
        name = f"METADATA_MCP_真实验收网关坑位_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        updated_name = f"{name}_已更新"
        created_id: Optional[str] = None
        steps: List[Dict[str, Any]] = []

        try:
            create = self.run_action(task, "create", {"houseId": self.seeds.house_id}, {"name": name, "pid": "14336"})
            steps.append(self.step_from_result("gateway.create", create, "创建临时网关坑位"))
            if not create.ok:
                raise RuntimeError("gateway.create 失败")
            created_id = extract_created_id(extract_data(create), ("id", "gatewayId", "deviceId"))
            if not created_id:
                listing = self.run_action(task, "list", {"houseId": self.seeds.house_id}, confirm_side_effect=False)
                steps.append(self.step_from_result("gateway.list.find_created", listing, "创建后通过网关列表定位网关 ID"))
                created_id = extract_resource_id(find_resource_by_name(extract_data(listing), name), ("id", "gatewayId", "deviceId"))
            if not created_id:
                raise RuntimeError("gateway.create 未返回 gatewayId")

            detail = self.run_action(task, "get_gateway_detail", {"houseId": self.seeds.house_id, "gatewayId": created_id}, confirm_side_effect=False)
            steps.append(self.step_from_result("gateway.get_detail.after_create", detail, "创建后查网关详情"))
            steps.append(self.assertion_step("gateway.assert_created_detail", contains_resource(extract_data(detail), created_id, name), "详情中能找到新网关坑位", extract_data(detail)))

            update = self.run_action(task, "update", {"houseId": self.seeds.house_id, "gatewayId": created_id}, {"name": updated_name, "mac": "F8:24:41:06:A1:06"})
            steps.append(self.step_from_result("gateway.update", update, "更新临时网关名称和 MAC"))
            if not update.ok:
                raise RuntimeError("gateway.update 失败")

            detail_after_update = self.run_action(task, "get_gateway_detail", {"houseId": self.seeds.house_id, "gatewayId": created_id}, confirm_side_effect=False)
            steps.append(self.step_from_result("gateway.get_detail.after_update", detail_after_update, "更新后查网关详情"))
            update_data = extract_data(detail_after_update)
            resource = find_resource_by_id(update_data, created_id)
            name_ok = bool(resource and resource.get("name") == updated_name) or contains_resource(update_data, None, updated_name)
            steps.append(self.assertion_step("gateway.assert_updated_name", name_ok, "详情中名称已更新", update_data))

            thread_info = self.run_action(task, "get_gateway_thread_info", {"houseId": self.seeds.house_id, "gatewayId": created_id}, confirm_side_effect=False)
            steps.append(self.step_from_result("gateway.thread_info", thread_info, "查询临时网关 Thread 信息"))
            steps.append(self.assertion_step("gateway.assert_thread_call_ok", bool(getattr(thread_info, "ok", False)), "Thread 信息接口调用成功", getattr(thread_info, "response", None)))

            delete = self.run_action(remove_task, "delete_gateway", {"houseId": self.seeds.house_id, "gatewayId": created_id})
            steps.append(self.step_from_result("gateway.delete", delete, "删除临时网关坑位"))
            if not delete.ok:
                raise RuntimeError("gateway.delete 失败")
            cleanup_id = created_id
            created_id = None

            listing_after_delete = self.run_action(task, "list", {"houseId": self.seeds.house_id}, confirm_side_effect=False)
            steps.append(self.step_from_result("gateway.list.after_delete", listing_after_delete, "删除后查网关列表"))
            steps.append(self.assertion_step("gateway.assert_deleted_absent", not contains_resource(extract_data(listing_after_delete), cleanup_id, updated_name), "列表中已不存在临时网关坑位", extract_data(listing_after_delete)))
        except Exception as exc:
            steps.append(self.assertion_step("gateway.exception", False, str(exc)))
        finally:
            if created_id:
                cleanup = self.run_action(remove_task, "delete_gateway", {"houseId": self.seeds.house_id, "gatewayId": created_id})
                steps.append(self.step_from_result("gateway.finally_cleanup", cleanup, "异常时兜底删除临时网关坑位"))

        return self.suite_result("gateway_crud", "网关 create/update/delete 和 Thread 查询闭环", steps)

    def suite_result(self, suite_id: str, title: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "id": suite_id,
            "title": title,
            "skipped": False,
            "ok": all(step.get("ok") for step in steps),
            "steps": steps,
        }

    def skipped_suite(self, suite_id: str, reason: str) -> Dict[str, Any]:
        return {
            "id": suite_id,
            "title": suite_id,
            "skipped": True,
            "ok": True,
            "skippedReason": reason,
            "steps": [],
        }


def parse_device_ids(raw: str, fallback: Optional[str]) -> List[str]:
    if raw:
        return [item.strip() for item in raw.split(",") if item.strip()]
    return [fallback] if fallback else []


def summarize(suites: List[Dict[str, Any]]) -> Dict[str, Any]:
    executable = [suite for suite in suites if not suite.get("skipped")]
    seed_gap_suites = [suite for suite in suites if suite.get("businessSeedGap")]
    return {
        "suites": len(suites),
        "executedSuites": len(executable),
        "skippedSuites": len(suites) - len(executable),
        "businessSeedGapSuites": [suite["id"] for suite in seed_gap_suites],
        "okSuites": sum(1 for suite in executable if suite.get("ok")),
        "failedSuites": [suite["id"] for suite in executable if not suite.get("ok")],
        "writeSteps": sum(1 for suite in executable for step in suite.get("steps", []) if any(token in step.get("name", "") for token in ("create", "update", "delete", "batch"))),
        "assertionFailures": [
            f"{suite['id']}/{step['name']}"
            for suite in executable
            for step in suite.get("steps", [])
            if not step.get("ok")
        ],
    }


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: Path, payload: Dict[str, Any]) -> None:
    lines = [
        "# Metadata MCP 写接口真实闭环验收报告",
        "",
        f"生成时间：{payload['generatedAt']}",
        "",
        "## 结论",
        "",
        f"- 执行套件：`{payload['summary']['executedSuites']}/{payload['summary']['suites']}`",
        f"- 通过套件：`{payload['summary']['okSuites']}`",
        f"- 失败套件：`{len(payload['summary']['failedSuites'])}`",
        f"- 业务种子缺口：`{len(payload['summary'].get('businessSeedGapSuites', []))}`",
        f"- 写接口步骤：`{payload['summary']['writeSteps']}`",
        f"- 断言失败：`{len(payload['summary']['assertionFailures'])}`",
        "",
        "## 环境",
        "",
        f"- API Base URL：`{payload['settings']['apiBaseUrl']}`",
        f"- houseId：`{payload['settings']['houseId']}`",
        f"- token：`{'已提供' if payload['settings']['tokenProvided'] else '未提供'}`",
        "",
        "## 套件明细",
        "",
    ]
    for suite in payload["suites"]:
        if suite.get("skipped"):
            lines.extend([f"### {suite['id']}", "", f"- 跳过：{suite.get('skippedReason')}", ""])
            if suite.get("businessSeedGap") and suite.get("steps"):
                lines.extend(["| 步骤 | 结果 | code | message |", "| --- | --- | --- | --- |"])
                for step in suite.get("steps", []):
                    lines.append(f"| `{step.get('name')}` | {'通过' if step.get('ok') else '未闭环'} | `{step.get('code')}` | {step.get('message') or step.get('note') or ''} |")
                lines.append("")
            continue
        lines.extend([f"### {suite['id']}", "", f"- 结果：`{'通过' if suite.get('ok') else '失败'}`", ""])
        lines.extend(["| 步骤 | 结果 | code | message |", "| --- | --- | --- | --- |"])
        for step in suite.get("steps", []):
            lines.append(f"| `{step.get('name')}` | {'通过' if step.get('ok') else '失败'} | `{step.get('code')}` | {step.get('message') or step.get('note') or ''} |")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按 Pro API 巡检思路真实验收 Metadata MCP 写接口")
    parser.add_argument("--access-token", default="", help="访问 token。建议使用 METADATA_MCP_ACCESS_TOKEN 环境变量")
    parser.add_argument("--house-id", default=os.getenv("METADATA_MCP_HOUSE_ID", os.getenv("METADATA_MCP_ACCEPTANCE_HOUSE_ID", DEFAULT_HOUSE_ID)))
    parser.add_argument("--device-ids", default=os.getenv("METADATA_MCP_ACCEPTANCE_DEVICE_IDS", ""), help="设备组验收使用的设备 ID，多个用逗号分隔")
    parser.add_argument("--include-device-group", action="store_true", help="执行设备组写接口闭环。需要提供可组组的 deviceIds")
    parser.add_argument("--include-house", action="store_true", help="执行家庭 create/update/delete 闭环，会创建并删除临时家庭")
    parser.add_argument("--include-device-slot", action="store_true", help="执行设备坑位 create/update/delete、batch_create、清 MAC 闭环")
    parser.add_argument("--include-gateway", action="store_true", help="执行网关坑位 create/update/delete 和 Thread 查询闭环")
    parser.add_argument("--include-legacy-area-group", action="store_true", help="执行 legacy 区域组 create/update/delete 与 fuzzy 查询闭环")
    parser.add_argument("--include-room-batch", action="store_true", help="执行房间 batch_create 闭环")
    parser.add_argument("--include-room-area", action="store_true", help="执行房间区域 add/remove 闭环")
    parser.add_argument("--include-expanded", action="store_true", help="执行除默认套件外的全部扩展闭环")
    parser.add_argument("--skip-room", action="store_true", help="跳过房间 CRUD")
    parser.add_argument("--skip-area", action="store_true", help="跳过区域 CRUD")
    parser.add_argument("--skip-scene-favorite", action="store_true", help="跳过情景和收藏闭环")
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = read_token(args)
    headers = build_headers(token, str(args.house_id))
    registry = MetadataTaskRegistry()
    http_client = RecordingHttpClient(settings.HTTP_TIMEOUT)
    executor = TaskExecutor(registry, http_client)
    seeds = SeedState(house_id=str(args.house_id))

    if not headers.get("Authorization"):
        raise SystemExit("缺少 METADATA_MCP_ACCESS_TOKEN，无法执行真实写接口验收")

    discover_seeds(registry, executor, seeds, headers, live=True)
    acceptance = LiveWriteAcceptance(registry, executor, seeds, headers)
    expanded = args.include_expanded

    suites: List[Dict[str, Any]] = []
    if args.include_house or expanded:
        suites.append(acceptance.run_house_crud())
    if not args.skip_room:
        suites.append(acceptance.run_room_crud())
    if args.include_room_batch or expanded:
        suites.append(acceptance.run_room_batch_create())
    if not args.skip_area:
        suites.append(acceptance.run_area_crud())
    if args.include_room_area or expanded:
        suites.append(acceptance.run_room_area_update())
    if args.include_legacy_area_group or expanded:
        suites.append(acceptance.run_legacy_area_group_crud())
    if not args.skip_scene_favorite:
        suites.append(acceptance.run_scene_and_favorite())
    acceptance_device_ids = parse_device_ids(args.device_ids, seeds.device_id)
    if args.include_device_slot or expanded:
        suites.append(acceptance.run_device_slot_crud())
        suites.append(acceptance.run_device_slot_batch_create())
        suites.append(acceptance.run_device_unbind())
        suites.append(acceptance.run_device_unbind_and_clear_mac())
    if args.include_gateway or expanded:
        suites.append(acceptance.run_gateway_crud())
    if args.include_device_group or expanded:
        suites.append(acceptance.run_device_group_crud(acceptance_device_ids))
        suites.append(acceptance.run_device_group_member_update(acceptance_device_ids))

    payload = {
        "generatedAt": now_iso(),
        "settings": {
            "apiBaseUrl": settings.API_BASE_URL,
            "runtimeEnv": settings.RUNTIME_ENV,
            "houseId": seeds.house_id,
            "tokenProvided": bool(headers.get("Authorization")),
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
        "summary": summarize(suites),
        "suites": suites,
        "httpCalls": http_client.calls,
    }
    write_json(Path(args.output_json), payload)
    write_markdown(Path(args.output_md), payload)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0 if not payload["summary"]["failedSuites"] and not payload["summary"]["assertionFailures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
