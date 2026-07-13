from argparse import Namespace
from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from scripts.mcp_acceptance_cli import auth_headers, build_execute_request, print_execution_summary
from config.config import normalize_api_base_url, resolve_resource_dir
from service.executor import TaskExecutor
from service.mcp_service import describe_registry_task, enrich_request_context, get_registry_action_schema, get_registry_context_hints, get_request_headers, list_registry_actions, list_registry_groups, list_registry_tasks, search_task_registry
from service.model import InterfaceStatus, TaskContext, TaskExecutionRequest, ValidationRequest
from service.registry import MetadataTaskRegistry


class DummyHttpClient:
    def __init__(self):
        self.calls = []

    def request(self, method, url, headers=None, params=None, json=None):
        self.calls.append({"method": method, "url": url, "headers": headers, "params": params, "json": json})
        return {"code": "200", "data": {"ok": True}}


class ErrorHttpClient:
    def request(self, method, url, headers=None, params=None, json=None):
        return {"code": "500", "msg": "业务失败", "data": None}


class DummyContext:
    def __init__(self, headers):
        request = type("Request", (), {"headers": headers})()
        self.request_context = type("RequestContext", (), {"request": request})()


def test_api_base_url_accepts_iot_host_prefix():
    assert normalize_api_base_url("http://api-dev.yeedev.com/apis/iot") == "http://api-dev.yeedev.com"
    assert normalize_api_base_url("http://api-dev.yeedev.com/apis/iot/") == "http://api-dev.yeedev.com"
    assert normalize_api_base_url("http://api-dev.yeedev.com") == "http://api-dev.yeedev.com"


def test_resource_dir_resolves_public_catalog_from_service_root(monkeypatch):
    monkeypatch.delenv("METADATA_MCP_RESOURCE_DIR", raising=False)
    monkeypatch.delenv("APP_MCP_RESOURCE_DIR", raising=False)
    monkeypatch.chdir(PROJECT_DIR)

    resource_dir = resolve_resource_dir()

    assert resource_dir == str(PROJECT_DIR / "resources" / "catalog")
    assert (PROJECT_DIR / "resources" / "catalog" / "metadata-mcp-user-task-map.json").exists()


def test_resource_dir_keeps_explicit_legacy_env_compatibility(monkeypatch, tmp_path):
    legacy_dir = tmp_path / "legacy-catalog"
    legacy_dir.mkdir()
    monkeypatch.delenv("METADATA_MCP_RESOURCE_DIR", raising=False)
    monkeypatch.setenv("APP_MCP_RESOURCE_DIR", str(legacy_dir))

    assert resolve_resource_dir() == str(legacy_dir)


def test_registry_loads_user_task_tree():
    registry = MetadataTaskRegistry()

    assert len(registry.list_groups()) == 7
    assert len(registry.list_tasks()) == 23
    assert registry.get_task("family_space.manage_room") is not None


def test_task_registry_contains_action_level_policy():
    registry = MetadataTaskRegistry()
    task = registry.get_task("device_onboarding.pair_device")

    assert task is not None
    modes = {action.executionMode.value for action in task.actions}
    assert "requires_qr_scan" in modes
    assert any(action.sideEffect.value == "S2" for action in task.actions)


def test_list_registry_groups_returns_lightweight_summaries():
    result = list_registry_groups(limit=1)

    assert result["count"] == 1
    assert result["total"] == 7
    assert result["nextCursor"]
    group = result["items"][0]
    assert group["id"] == "family_space"
    assert group["taskCount"] == 4
    assert "tasks" not in group


def test_list_registry_tasks_returns_lightweight_summaries():
    result = list_registry_tasks(group="family_space", limit=1)

    assert result["count"] == 1
    assert result["total"] == 4
    assert result["nextCursor"]
    assert "groups" not in result
    task = result["items"][0]
    assert task["task"] == "family_space.manage_house"
    assert task["actionCount"] == 8
    assert "actions" not in task
    assert "interfaceRefs" not in task
    assert "parameterSchema" not in str(result)


def test_list_registry_tasks_cursor_returns_next_page():
    first = list_registry_tasks(group="family_space", limit=1)
    second = list_registry_tasks(group="family_space", cursor=first["nextCursor"], limit=1)

    assert "tasks" not in first
    assert first["items"][0]["task"] != second["items"][0]["task"]
    assert second["count"] == 1


def test_list_registry_tasks_can_describe_single_task():
    result = list_registry_tasks(task="family_space.manage_room")

    assert result["task"] == "family_space.manage_room"
    assert result["actionCount"] == 9
    assert result["schemaHint"].startswith("使用 yeelight_metadata.get_action_schema")
    assert "parameterSchema" not in str(result)


def test_list_registry_tasks_can_search_by_query():
    result = list_registry_tasks(query="room", group="family_space", limit=1)

    assert result["query"] == "room"
    assert result["count"] == 1
    assert result["matches"][0]["task"] == "family_space.manage_room"
    assert any(action["action"] == "create" for action in result["matches"][0]["matchedActions"])
    assert "parameterSchema" not in str(result)


def test_describe_registry_task_returns_action_summaries_without_schema_dump():
    result = describe_registry_task("family_space.manage_room")

    assert result["task"] == "family_space.manage_room"
    assert result["id"] == "family_space.manage_room"
    assert result["actionCount"] == 9
    assert result["resource"] == "yeelight-metadata://tasks/family_space.manage_room"
    action = result["actions"][0]
    assert "action" in action
    assert "contextRequired" in action
    assert "payloadRequired" in action
    assert "interfaceRefs" not in action
    assert "parameterSchema" not in action
    assert "parameterSchema" not in str(result)


def test_candidate_action_is_rejected_by_default():
    registry = MetadataTaskRegistry()
    action = registry.get_action("device_management.manage_device_group", "update_group_devices")
    action.status = InterfaceStatus.candidate
    executor = TaskExecutor(registry, DummyHttpClient())
    request = ValidationRequest(
        task="device_management.manage_device_group",
        action="update_group_devices",
        context=TaskContext(houseId="house-1", groupId="group-1", runtimeEnv="test"),
        payload={"deviceIds": ["device-1"]},
    )

    result = executor.validate(request)

    assert not result.valid
    assert any("candidate" in error for error in result.errors)


def test_dev_verified_candidate_operations_are_promoted_to_confirmed():
    registry = MetadataTaskRegistry()

    assert registry.get_action("family_space.manage_house", "get_house_detail").status.value == "confirmed"
    assert registry.get_action("family_space.manage_room", "create").status.value == "confirmed"
    assert registry.get_action("family_space.manage_room", "update").status.value == "confirmed"
    assert registry.get_action("family_space.manage_room", "delete").status.value == "confirmed"
    assert registry.get_action("device_management.manage_device_group", "update_group_devices").status.value == "confirmed"


def test_registry_status_counts_after_dev_promotion():
    registry = MetadataTaskRegistry()
    statuses = {}
    for task in registry.list_tasks():
        for action in task.actions:
            statuses[action.status.value] = statuses.get(action.status.value, 0) + 1

    assert statuses == {"confirmed": 153, "external": 2, "non_rest": 2}


def test_scan_login_contains_qrcode_creation_action():
    registry = MetadataTaskRegistry()
    action = registry.get_action("maintenance_account.manage_account", "create_scan_qrcode")

    assert action is not None
    assert action.interfaceRefs[0].operation == "account.scan_login.query_qrcode"
    assert action.parameterSchema.payloadRequired == ["device"]
    assert action.interfaceRefs[0].runtimePath == "/apis/account/user/scan-login/query/qrcode/{device}"


def test_candidate_execute_without_allow_candidate_returns_blocking_guidance():
    registry = MetadataTaskRegistry()
    action = registry.get_action("device_management.manage_device_group", "update_group_devices")
    action.status = InterfaceStatus.candidate
    executor = TaskExecutor(registry, DummyHttpClient())
    request = TaskExecutionRequest(
        task="device_management.manage_device_group",
        action="update_group_devices",
        context=TaskContext(houseId="house-1", groupId="group-1", runtimeEnv="test"),
        payload={"deviceIds": ["device-1"]},
        options={"dryRun": False},
    )

    result = executor.execute(request, headers={})

    assert not result.ok
    assert result.code == "VALIDATION_ERROR"
    assert any("默认不可执行" in error for error in result.validation.errors)
    assert any("真实执行需要显式传 options.allowCandidate=true" in item for item in result.plan.guidance)


def test_candidate_execute_with_allow_candidate_returns_explicit_allow_guidance():
    registry = MetadataTaskRegistry()
    action = registry.get_action("device_management.manage_device_group", "update_group_devices")
    action.status = InterfaceStatus.candidate
    executor = TaskExecutor(registry, DummyHttpClient())
    request = TaskExecutionRequest(
        task="device_management.manage_device_group",
        action="update_group_devices",
        context=TaskContext(houseId="house-1", groupId="group-1", runtimeEnv="test"),
        payload={"deviceIds": ["device-1"]},
        options={"dryRun": False, "allowCandidate": True},
    )

    result = executor.execute(request, headers={})

    assert not result.ok
    assert result.code == "VALIDATION_ERROR"
    assert any("confirmSideEffect" in error for error in result.validation.errors)
    assert any("本次已由 options.allowCandidate=true 显式放行" in item for item in result.plan.guidance)


def test_house_id_header_enriches_validation_context():
    request = ValidationRequest(
        task="family_space.manage_room",
        action="list_all_room",
        context=TaskContext(runtimeEnv="test"),
        options={"allowCandidate": True},
    )

    enrich_request_context(request, {"houseId": "house-from-header", "clientId": "dev"})

    assert request.context.houseId == "house-from-header"
    assert request.context.clientId == "dev"


def test_explicit_context_house_id_overrides_header():
    request = TaskExecutionRequest(
        task="family_space.manage_house",
        action="get_house_detail",
        context=TaskContext(houseId="house-from-context", runtimeEnv="test"),
        options={"dryRun": False, "allowCandidate": True},
    )

    enrich_request_context(request, {"houseId": "house-from-header"})

    assert request.context.houseId == "house-from-context"


def test_execute_can_use_house_id_from_header_context_enrichment():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="family_space.manage_house",
        action="get_house_detail",
        context=TaskContext(runtimeEnv="test"),
        options={"dryRun": False, "allowCandidate": True},
    )

    enrich_request_context(request, {"houseId": "house-from-header"})
    result = executor.execute(request, headers={})

    assert result.ok
    assert http_client.calls[0]["url"].endswith("/apis/iot/v1/house/house-from-header/r/detail")


def test_cli_execute_does_not_allow_candidate_by_default():
    args = Namespace(
        task="family_space.manage_house",
        action="get_house_detail",
        context='{"houseId":"200084"}',
        payload="{}",
        options='{"dryRun": false, "confirmSideEffect": false}',
    )

    request = build_execute_request(args, dry_run_default=False)["request"]

    assert request["options"] == {"dryRun": False, "confirmSideEffect": False}
    assert "allowCandidate" not in request["options"]


def test_cli_dryrun_keeps_candidate_plan_convenience():
    args = Namespace(
        task="family_space.manage_house",
        action="get_house_detail",
        context='{"houseId":"200084"}',
        payload="{}",
        options='{"dryRun": true, "allowCandidate": true}',
    )

    request = build_execute_request(args, dry_run_default=True)["request"]

    assert request["options"]["dryRun"] is True
    assert request["options"]["allowCandidate"] is True


def test_cli_execution_summary_prints_normalized_data(capsys):
    result = {
        "ok": True,
        "code": "OK",
        "message": "处理成功",
        "dryRun": False,
        "plan": {
            "task": "family_space.manage_house",
            "action": "get_house_detail",
            "sideEffect": "S0",
            "status": "candidate",
            "executionMode": "cloud_api",
            "directExecutionSupported": True,
        },
        "validation": {"valid": True, "code": "OK"},
        "normalizedResponse": {
            "ok": True,
            "code": "OK",
            "message": "处理成功",
            "data": {"id": "200084", "name": "无线中枢网关测试家庭"},
        },
    }

    print_execution_summary(result)

    output = capsys.readouterr().out
    assert "data:" in output
    assert "200084" in output
    assert "无线中枢网关测试家庭" in output


def test_cli_auth_headers_include_global_house_id():
    headers = auth_headers("token", "house-1")

    assert headers["Authorization"] == "Bearer token"
    assert headers["House-Id"] == "house-1"


def test_request_headers_normalize_bearer_token_once():
    headers = get_request_headers(DummyContext({"Authorization": "Bearer token", "House-Id": "house-1"}))

    assert headers["authorization"] == "Bearer token"
    assert headers["houseId"] == "house-1"


def test_request_headers_add_bearer_to_raw_token():
    headers = get_request_headers(DummyContext({"Authorization": "token"}))

    assert headers["authorization"] == "Bearer token"


def test_search_task_registry_finds_room_actions():
    result = search_task_registry("room", group="family_space")

    task_ids = {item["task"] for item in result["matches"]}
    assert "family_space.manage_room" in task_ids
    assert any(action["action"] == "create" for item in result["matches"] for action in item["matchedActions"])
    assert "parameterSchema" not in str(result)


def test_search_task_registry_supports_cursor_pagination():
    first = search_task_registry("查询", limit=1)
    second = search_task_registry("查询", cursor=first["nextCursor"], limit=1)

    assert first["count"] == 1
    assert first["total"] > 1
    assert first["nextCursor"]
    assert first["matches"][0]["task"] != second["matches"][0]["task"]


def test_search_task_registry_finds_device_create_by_user_phrases():
    queries = ["添加设备", "创建灯", "device create"]

    for query in queries:
        result = search_task_registry(query)
        task_ids = {item["task"] for item in result["matches"]}
        assert result["matches"][0]["task"] == "device_onboarding.create_device_slot"
        assert "device_onboarding.create_device_slot" in task_ids
        assert any(action["action"] == "create" for item in result["matches"] for action in item["matchedActions"])


def test_all_task_user_phrases_rank_their_task_first():
    registry = MetadataTaskRegistry()

    for task in registry.list_tasks():
        for phrase in task.userPhrases:
            result = search_task_registry(phrase, limit=10)
            assert result["matches"], f"{task.id} 的用户说法未召回任何任务: {phrase}"
            assert result["matches"][0]["task"] == task.id, f"{task.id} 的用户说法未排第一: {phrase}"


def test_all_action_descriptions_can_find_their_action():
    registry = MetadataTaskRegistry()

    for task in registry.list_tasks():
        for action in task.actions:
            result = search_task_registry(action.description, limit=20)
            found = any(
                item["task"] == task.id and any(hit["action"] == action.id for hit in item["matchedActions"])
                for item in result["matches"]
            )
            assert found, f"{task.id}/{action.id} 的 action 说明无法召回自身: {action.description}"


def test_all_action_titles_are_localized_for_model_discovery():
    registry = MetadataTaskRegistry()

    for task in registry.list_tasks():
        for action in task.actions:
            assert action.title != action.id.replace("_", " "), f"{task.id}/{action.id} 使用英文兜底标题"


def test_all_action_titles_are_globally_distinguishable():
    registry = MetadataTaskRegistry()
    seen = {}

    for task in registry.list_tasks():
        for action in task.actions:
            previous = seen.setdefault(action.title, f"{task.id}/{action.id}")
            assert previous == f"{task.id}/{action.id}", f"action 标题重复: {action.title} => {previous}, {task.id}/{action.id}"


def test_list_registry_actions_filters_candidate_s2_returns_empty_after_dev_promotion():
    result = list_registry_actions(status="candidate", side_effect="S2", limit=20)

    assert result["count"] == 0
    assert result["items"] == []


def test_list_registry_actions_supports_cursor_pagination():
    first = list_registry_actions(group="family_space", limit=1)
    second = list_registry_actions(group="family_space", cursor=first["nextCursor"], limit=1)

    assert first["count"] == 1
    assert first["total"] > 1
    assert first["nextCursor"]
    assert "actions" not in first
    assert first["items"][0]["action"] != second["items"][0]["action"]
    assert "parameterSchema" not in str(first)


def test_context_hints_split_global_and_local_context():
    result = get_registry_context_hints("family_space.manage_room", "create")

    assert result["globalContext"]["fields"] == ["houseId"]
    assert result["localContextRequired"] == []
    assert result["payloadRequired"] == ["name"]
    assert any(header["name"] == "House-Id" for header in result["globalContext"]["headers"])


def test_get_registry_action_schema_merges_schema_and_context_hints():
    result = get_registry_action_schema("family_space.manage_room", "create")

    assert result["task"] == "family_space.manage_room"
    assert result["action"] == "create"
    assert result["taskTitle"] == "管理房间"
    assert result["contextRequired"] == ["houseId"]
    assert result["localContextRequired"] == []
    assert result["payloadRequired"] == ["name"]
    assert "name" in result["payloadProperties"]
    assert result["globalContext"]["headers"][1]["name"] == "House-Id"
    assert any("dryRun=true" in note for note in result["notes"])


def test_s2_action_requires_confirmation_when_not_dry_run():
    registry = MetadataTaskRegistry()
    executor = TaskExecutor(registry, DummyHttpClient())
    request = ValidationRequest(
        task="configuration.configure_panel",
        action="update_layout",
        context=TaskContext(deviceId="device-1"),
        payload={"layout": {"buttons": []}},
        options={"dryRun": False},
    )

    result = executor.validate(request)

    assert not result.valid
    assert any("confirmSideEffect" in error for error in result.errors)


def test_dry_run_returns_plan_without_http_call():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="configuration.configure_panel",
        action="get_detail",
        context=TaskContext(deviceId="device-1"),
        payload={},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert result.dryRun
    assert result.plan.interfaces
    assert result.plan.httpRequest["method"] == "POST"
    assert result.plan.httpRequest["url"].endswith("/apis/iot/v1/panel/r/detail/device-1")
    assert http_client.calls == []


def test_confirmed_action_can_execute_after_confirmation():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="configuration.configure_panel",
        action="update_layout",
        context=TaskContext(deviceId="device-1"),
        payload={"buttons": [{"buttonId": "b1", "name": "一键回家"}]},
        options={"dryRun": False, "confirmSideEffect": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert not result.dryRun
    assert result.code == "OK"
    assert result.normalizedResponse["ok"]
    assert http_client.calls
    assert http_client.calls[0]["method"] == "POST"
    assert http_client.calls[0]["url"].endswith("/apis/iot/v1/panel/w/button/update/device-1")
    assert http_client.calls[0]["json"] == [{"buttonId": "b1", "name": "一键回家", "deviceId": "device-1"}]


def test_operation_schema_splits_panel_actions():
    registry = MetadataTaskRegistry()
    task = registry.get_task("configuration.configure_panel")
    action_ids = {action.id for action in task.actions}

    assert "update_layout" in action_ids
    assert "update_event" in action_ids
    assert "batch_update_event" in action_ids

    schema = registry.get_schema("configuration.configure_panel", "update_event")
    assert schema.contextRequired == ["deviceId"]
    assert schema.payloadRequired == ["event"]
    assert schema.payloadProperties["event"]["structure"]["item"]["actions"] == "动作列表；结构与情景/自动化动作类似"

    layout_schema = registry.get_schema("configuration.configure_panel", "update_layout")
    assert layout_schema.payloadRequired == []
    assert layout_schema.payloadProperties["layout"]["type"] == "array"
    assert layout_schema.payloadProperties["layout"]["structure"]["execution"].startswith("后端请求体是 PanelButton 数组")
    assert layout_schema.payloadProperties["buttons"]["structure"]["inputField"] == "buttons"

    batch_schema = registry.get_schema("configuration.configure_panel", "batch_update_event")
    assert batch_schema.payloadRequired == []
    assert batch_schema.payloadProperties["events"]["structure"]["item"]["buttonEventId"].startswith("按键事件 ID")


def test_knob_multi_reset_builds_path_with_index():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="configuration.configure_knob",
        action="reset_multi",
        context=TaskContext(deviceId="device-1"),
        payload={"index": 2},
        options={"dryRun": False, "confirmSideEffect": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert http_client.calls[0]["url"].endswith("/apis/iot/v1/multi-knob/device-1/2/reset")
    assert http_client.calls[0]["json"] == {}


def test_knob_config_schema_explains_read_modify_write_shape():
    registry = MetadataTaskRegistry()
    single_schema = registry.get_schema("configuration.configure_knob", "update_single")
    multi_schema = registry.get_schema("configuration.configure_knob", "update_multi")

    assert "查询详情返回对象" in single_schema.payloadProperties["config"]["description"]
    assert single_schema.payloadProperties["config"]["structure"]["commonFields"]["id"].startswith("旋钮设备 ID")
    assert single_schema.payloadProperties["config"]["structure"]["commonFields"]["events"].startswith("可选")
    assert "查询详情返回对象" in multi_schema.payloadProperties["config"]["description"]


def test_storage_set_requires_key_and_value():
    registry = MetadataTaskRegistry()
    executor = TaskExecutor(registry, DummyHttpClient())
    request = ValidationRequest(
        task="configuration.configure_storage_asset",
        action="set_storage",
        context=TaskContext(deviceId="device-1"),
        payload={"storageKey": "screen"},
    )

    result = executor.validate(request)

    assert not result.valid
    assert any("storageValue" in error for error in result.errors)


def test_automation_page_uses_query_params_for_get():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="scene_automation.manage_automation",
        action="page_rule",
        context=TaskContext(houseId="house-1"),
        payload={"pageNo": 1, "pageSize": 20},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert result.dryRun
    assert result.plan.httpRequest["method"] == "GET"
    assert result.plan.httpRequest["url"].endswith("/apis/iot/v1/automations/house-1/r/list/1/20")
    assert result.plan.httpRequest["params"] == {}


def test_automation_delete_is_s3_and_requires_confirmation():
    registry = MetadataTaskRegistry()
    executor = TaskExecutor(registry, DummyHttpClient())
    request = ValidationRequest(
        task="scene_automation.manage_automation",
        action="delete",
        context=TaskContext(automationId="auto-1"),
        options={"dryRun": False},
    )

    result = executor.validate(request)

    assert not result.valid
    assert result.sideEffect.value == "S3"
    assert any("confirmSideEffect" in error for error in result.errors)


def test_automation_create_schema_matches_javadoc_contract():
    registry = MetadataTaskRegistry()
    schema = registry.get_schema("scene_automation.manage_automation", "create")

    assert schema.contextRequired == ["houseId"]
    assert schema.payloadRequired == ["actions", "endTime", "name", "params", "repeatType", "startTime"]
    params_schema = schema.payloadProperties["params"]
    assert params_schema["type"] == "string|object"
    assert "V2" in params_schema["description"]
    assert "V1" not in params_schema["description"]
    assert "v1" not in params_schema["structure"]
    assert params_schema["structure"]["v2"]["root"]["type"] == "and"
    assert all(example["version"] == 2 for example in params_schema["examples"])
    assert "automation.capability.list_v2" in params_schema["structure"]["capabilitySource"]
    assert "conditions" not in schema.payloadProperties
    assert "0x7f" in schema.payloadProperties["repeatValue"]["description"]
    assert "version" not in schema.payloadProperties
    actions_schema = schema.payloadProperties["actions"]
    assert actions_schema["structure"]["limit"] == "单个自动化最多 200 个动作。"
    assert "automation.capability.list_v2" in actions_schema["structure"]["capabilitySource"]
    assert schema.payloadProperties["status"]["required"] is False


def test_automation_create_requires_javadoc_fields():
    registry = MetadataTaskRegistry()
    executor = TaskExecutor(registry, DummyHttpClient())
    request = ValidationRequest(
        task="scene_automation.manage_automation",
        action="create",
        context=TaskContext(houseId="house-1"),
        payload={"name": "晚间自动开灯", "actions": []},
    )

    result = executor.validate(request)

    assert not result.valid
    assert any("startTime" in error for error in result.errors)
    assert any("endTime" in error for error in result.errors)
    assert any("repeatType" in error for error in result.errors)
    assert any("params" in error for error in result.errors)


def test_complex_payload_schemas_explain_executor_transform_shapes():
    registry = MetadataTaskRegistry()

    scene_schema = registry.get_schema("scene_automation.manage_scene", "create")
    assert scene_schema.payloadProperties["actions"]["structure"]["execution"].startswith("MCP 会把 actions 转为后端 details")
    assert scene_schema.payloadProperties["actions"]["examples"][0]["params"] == {"set": {"power": "on"}}

    favorite_schema = registry.get_schema("home_organization.manage_favorite", "batch_update_favorite")
    favorite_items = favorite_schema.payloadProperties["items"]
    assert favorite_items["structure"]["execution"].startswith("批量收藏接口最终发送数组 body")
    assert favorite_items["structure"]["typeAliases"]["device"] == "2"

    batch_device_schema = registry.get_schema("device_onboarding.create_device_slot", "batch_create_device_slot")
    devices_schema = batch_device_schema.payloadProperties["devices"]
    assert devices_schema["structure"]["execution"].startswith("MCP 会给每个设备补 roomId")
    assert devices_schema["examples"][0]["pid"] == "264193"
    assert devices_schema["structure"]["item"]["connectType"].startswith("连接类型，必填")

    member_schema = registry.get_schema("device_management.manage_device_group", "update_group_devices")
    assert member_schema.payloadProperties["deviceIds"]["structure"]["item"] == "设备 ID"
    assert "addDeviceList" in member_schema.payloadProperties["addDeviceList"]["structure"]["simpleMode"]
    assert member_schema.payloadProperties["addDeviceList"]["structure"]["item"]["id"] == "设备 ID，必填"


def test_iot_api_javadoc_fields_are_exposed_in_core_resource_schemas():
    registry = MetadataTaskRegistry()

    house_schema = registry.get_schema("family_space.manage_house", "update")
    assert "desc" in house_schema.payloadProperties
    assert "description" not in house_schema.payloadProperties
    assert "buildingName" in house_schema.payloadProperties

    room_schema = registry.get_schema("family_space.manage_room", "update")
    assert "gatewayIds" in room_schema.payloadProperties
    assert "rank" in room_schema.payloadProperties

    area_schema = registry.get_schema("family_space.manage_area", "update_area")
    assert "parentId" in area_schema.payloadProperties
    assert area_schema.payloadProperties["roomIds"]["description"].startswith("区域关联的房间 ID 列表")

    device_schema = registry.get_schema("device_onboarding.create_device_slot", "create")
    assert device_schema.payloadRequired == ["connectType", "name", "pid"]
    assert "desc" in device_schema.payloadProperties
    assert "virtual" in device_schema.payloadProperties
    assert "isVirtual" in device_schema.payloadProperties

    group_schema = registry.get_schema("device_management.manage_device_group", "create")
    assert "cid" in group_schema.payloadProperties
    assert "componentId" not in group_schema.payloadProperties

    gateway_schema = registry.get_schema("device_onboarding.manage_gateway_onboarding", "update")
    assert "roomIds" in gateway_schema.payloadProperties
    assert "desc" in gateway_schema.payloadProperties


def test_automation_create_serializes_params_object_to_json_string():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="scene_automation.manage_automation",
        action="create",
        context=TaskContext(houseId="house-1", runtimeEnv="test"),
        payload={
            "name": "晚间自动开灯",
            "startTime": "00:00:00",
            "endTime": "23:59:59",
            "repeatType": 2,
            "repeatValue": "0x7f",
            "version": 2,
            "params": {
                "type": "and",
                "conditions": [
                    {
                        "type": "or",
                        "conditions": [
                            {"type": "alarm", "clock": "20:00:00"},
                        ],
                    }
                ],
            },
            "actions": [{"typeId": "1", "resId": "device-1", "params": {"set": {"p": True}}}],
        },
        options={"dryRun": False, "confirmSideEffect": True, "allowCandidate": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert http_client.calls[0]["url"].endswith("/apis/iot/v1/automations/w/insert")
    assert http_client.calls[0]["json"]["houseId"] == "house-1"
    assert http_client.calls[0]["json"]["version"] == 2
    assert http_client.calls[0]["json"]["params"] == '{"type":"and","conditions":[{"type":"or","conditions":[{"type":"alarm","clock":"20:00:00"}]}]}'


def test_automation_create_keeps_string_params_and_defaults_v2_version():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="scene_automation.manage_automation",
        action="create",
        context=TaskContext(houseId="house-1", runtimeEnv="test"),
        payload={
            "name": "晚间自动开灯",
            "startTime": "00:00:00",
            "endTime": "23:59:59",
            "repeatType": 2,
            "params": '{"type":"and","conditions":[]}',
            "actions": [{"typeId": "1", "resId": "device-1"}],
        },
        options={"dryRun": False, "confirmSideEffect": True, "allowCandidate": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert http_client.calls[0]["json"]["version"] == 2
    assert http_client.calls[0]["json"]["params"] == '{"type":"and","conditions":[]}'
    assert "conditions" not in http_client.calls[0]["json"]


def test_automation_create_rejects_conditions_alias_when_params_missing():
    registry = MetadataTaskRegistry()
    executor = TaskExecutor(registry, DummyHttpClient())
    request = ValidationRequest(
        task="scene_automation.manage_automation",
        action="create",
        context=TaskContext(houseId="house-1", runtimeEnv="test"),
        payload={
            "name": "晚间自动开灯",
            "startTime": "00:00:00",
            "endTime": "23:59:59",
            "repeatType": 2,
            "conditions": [{"type": "alarm", "clock": "20:00:00"}],
            "actions": [{"typeId": "1", "resId": "device-1"}],
        },
    )

    result = executor.validate(request)

    assert not result.valid
    assert any("params" in error for error in result.errors)


def test_automation_create_ignores_user_version_and_uses_v2():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="scene_automation.manage_automation",
        action="create",
        context=TaskContext(houseId="house-1", runtimeEnv="test"),
        payload={
            "name": "晚间自动开灯",
            "startTime": "00:00:00",
            "endTime": "23:59:59",
            "repeatType": 2,
            "version": 1,
            "params": {"type": "and", "conditions": []},
            "actions": [{"typeId": "1", "resId": "device-1"}],
        },
        options={"dryRun": False, "confirmSideEffect": True, "allowCandidate": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert http_client.calls[0]["json"]["version"] == 2


def test_room_create_dev_verified_action_has_precise_schema_and_confirmed_status():
    registry = MetadataTaskRegistry()
    executor = TaskExecutor(registry, DummyHttpClient())
    schema = registry.get_schema("family_space.manage_room", "create")
    action = registry.get_action("family_space.manage_room", "create")

    assert schema.contextRequired == ["houseId"]
    assert schema.payloadRequired == ["name"]
    assert action.status.value == "confirmed"

    request = ValidationRequest(
        task="family_space.manage_room",
        action="create",
        context=TaskContext(houseId="house-1", runtimeEnv="prod"),
        payload={"name": "客厅"},
        options={"allowCandidate": True},
    )

    result = executor.validate(request)

    assert result.valid
    assert result.code == "OK"


def test_room_create_dev_verified_action_can_dry_run_in_test_env():
    registry = MetadataTaskRegistry()
    executor = TaskExecutor(registry, DummyHttpClient())
    request = TaskExecutionRequest(
        task="family_space.manage_room",
        action="create",
        context=TaskContext(houseId="house-1", runtimeEnv="test"),
        payload={"name": "客厅"},
        options={"allowCandidate": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert result.code == "DRY_RUN"
    assert result.plan.httpRequest["url"].endswith("/apis/iot/v1/room/w/insert")
    assert result.plan.httpRequest["body"]["houseId"] == "house-1"
    assert result.plan.httpRequest["body"]["name"] == "客厅"
    assert all("candidate" not in item for item in result.plan.guidance)


def test_room_update_uses_business_verified_v2_endpoint():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    schema = registry.get_schema("family_space.manage_room", "update")

    assert schema.contextRequired == ["houseId", "roomId"]

    request = TaskExecutionRequest(
        task="family_space.manage_room",
        action="update",
        context=TaskContext(houseId="house-1", roomId="room-1", runtimeEnv="local"),
        payload={"name": "验收房间"},
        options={"dryRun": False, "confirmSideEffect": True, "allowCandidate": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert http_client.calls[0]["method"] == "POST"
    assert http_client.calls[0]["url"].endswith("/apis/iot/v2/thing/manage/house/house-1/room/room-1/w/modify")
    assert http_client.calls[0]["json"] == {"name": "验收房间"}


def test_room_delete_uses_business_verified_v2_endpoint():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    schema = registry.get_schema("family_space.manage_room", "delete")

    assert schema.contextRequired == ["houseId", "roomId"]

    request = TaskExecutionRequest(
        task="family_space.manage_room",
        action="delete",
        context=TaskContext(houseId="house-1", roomId="room-1", runtimeEnv="local"),
        payload={},
        options={"dryRun": False, "confirmSideEffect": True, "allowCandidate": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert http_client.calls[0]["method"] == "DELETE"
    assert http_client.calls[0]["url"].endswith("/apis/iot/v2/thing/manage/house/house-1/room/room-1/w/info")
    assert http_client.calls[0]["json"] is None


def test_context_fields_are_sent_in_body_when_not_path_params():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="family_space.manage_room",
        action="create",
        context=TaskContext(houseId="house-1", runtimeEnv="local", clientId="dev"),
        payload={"name": "验收房间"},
        options={"dryRun": False, "confirmSideEffect": True, "allowCandidate": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert http_client.calls[0]["url"].endswith("/apis/iot/v1/room/w/insert")
    assert http_client.calls[0]["json"] == {"houseId": "house-1", "name": "验收房间"}


def test_device_query_relation_builds_body():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="device_management.query_device",
        action="list_relation_device",
        payload={"resType": "room", "resId": "room-1"},
        options={"dryRun": False},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert http_client.calls[0]["url"].endswith("/apis/iot/v1/node/r/room/room-1/device")
    assert http_client.calls[0]["json"] == {}


def test_device_group_update_devices_uses_house_and_group_path():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="device_management.manage_device_group",
        action="update_group_devices",
        context=TaskContext(houseId="house-1", groupId="group-1", runtimeEnv="test"),
        payload={"deviceIds": ["d1", "d2"]},
        options={"dryRun": False, "confirmSideEffect": True, "allowCandidate": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert http_client.calls[0]["url"].endswith("/apis/iot/v2/thing/manage/house/house-1/group/group-1/w/devices")
    assert http_client.calls[0]["json"] == {"addDeviceList": [{"id": "d1"}, {"id": "d2"}]}


def test_device_group_update_devices_keeps_explicit_add_remove_lists():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="device_management.manage_device_group",
        action="update_group_devices",
        context=TaskContext(houseId="house-1", groupId="group-1", runtimeEnv="test"),
        payload={"deviceIds": ["ignored"], "removeDeviceList": [{"id": "d1"}]},
        options={"dryRun": False, "confirmSideEffect": True, "allowCandidate": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert http_client.calls[0]["json"] == {"removeDeviceList": [{"id": "d1"}]}


def test_room_area_update_uses_v2_add_area_list():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="family_space.manage_room",
        action="update_room_area",
        context=TaskContext(houseId="house-1", roomId="room-1", runtimeEnv="test"),
        payload={"areaIds": ["area-1"]},
        options={"dryRun": False, "confirmSideEffect": True, "allowCandidate": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert http_client.calls[0]["url"].endswith("/apis/iot/v2/thing/manage/house/house-1/room/room-1/w/areas")
    assert http_client.calls[0]["json"] == {"addAreaList": ["area-1"]}


def test_area_group_create_transforms_room_ids_to_details():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="family_space.manage_area",
        action="create_area_group",
        context=TaskContext(houseId="house-1", runtimeEnv="test"),
        payload={"name": "验收区域组", "roomIds": ["room-1"]},
        options={"dryRun": False, "confirmSideEffect": True, "allowCandidate": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert http_client.calls[0]["url"].endswith("/apis/iot/v1/group/w/insert")
    assert http_client.calls[0]["json"] == {
        "houseId": "house-1",
        "name": "验收区域组",
        "details": [{"roomId": "room-1"}],
    }


def test_house_create_uses_business_verified_v2_endpoint():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="family_space.manage_house",
        action="create",
        context=TaskContext(houseId="current-house", runtimeEnv="test"),
        payload={"name": "验收家庭"},
        options={"dryRun": False, "confirmSideEffect": True, "allowCandidate": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert http_client.calls[0]["method"] == "PUT"
    assert http_client.calls[0]["url"].endswith("/apis/iot/v2/thing/manage/house/w/create")
    assert http_client.calls[0]["json"] == {"houseId": "current-house", "name": "验收家庭"}


def test_device_slot_create_uses_business_verified_v2_endpoint():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="device_onboarding.create_device_slot",
        action="create",
        context=TaskContext(houseId="house-1", roomId="room-1", runtimeEnv="test"),
        payload={"name": "验收设备", "pid": "264193", "connectType": "BLE_MESH", "isVirtual": False},
        options={"dryRun": False, "confirmSideEffect": True, "allowCandidate": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert http_client.calls[0]["method"] == "PUT"
    assert http_client.calls[0]["url"].endswith("/apis/iot/v2/thing/manage/house/house-1/device/w/create")
    assert http_client.calls[0]["json"] == {"roomId": "room-1", "name": "验收设备", "pid": "264193", "connectType": "BLE_MESH", "virtual": False}


def test_gateway_delete_uses_v1_device_delete_cleanup_endpoint():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="device_management.remove_device",
        action="delete_gateway",
        context=TaskContext(houseId="house-1", gatewayId="gateway-1", runtimeEnv="test"),
        options={"dryRun": False, "confirmSideEffect": True, "allowCandidate": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert http_client.calls[0]["method"] == "POST"
    assert http_client.calls[0]["url"].endswith("/apis/iot/v1/device/gateway-1/w/delete")
    assert http_client.calls[0]["json"] == {}


def test_device_group_create_transforms_device_ids_to_details():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="device_management.manage_device_group",
        action="create",
        context=TaskContext(houseId="house-1", roomId="room-1", runtimeEnv="test"),
        payload={"name": "验收设备组", "deviceIds": ["d1", "d2"]},
        options={"dryRun": False, "confirmSideEffect": True, "allowCandidate": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert http_client.calls[0]["url"].endswith("/apis/iot/v1/meshgroup/w/insert")
    assert http_client.calls[0]["json"] == {
        "houseId": "house-1",
        "roomId": "room-1",
        "name": "验收设备组",
        "details": [{"deviceId": "d1"}, {"deviceId": "d2"}],
    }


def test_ai_control_node_update_accepts_controls_array_body():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="configuration.configure_ai_voice",
        action="update_control_node",
        context=TaskContext(houseId="house-1", runtimeEnv="test"),
        payload={"controls": [{"deviceId": "screen-1", "resId": "device-1", "resType": "device"}]},
        options={"dryRun": False, "confirmSideEffect": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert http_client.calls[0]["url"].endswith("/apis/iot/v1/ai/house-1/control/w/update")
    assert http_client.calls[0]["json"] == [{"deviceId": "screen-1", "resId": "device-1", "resType": "device", "houseId": "house-1"}]


def test_ai_control_node_update_transforms_convenience_device_ids():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="configuration.configure_ai_voice",
        action="update_control_node",
        context=TaskContext(houseId="house-1", runtimeEnv="test"),
        payload={"screenDeviceId": "screen-1", "deviceIds": ["device-1"], "sceneIds": ["scene-1"]},
        options={"dryRun": False, "confirmSideEffect": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert http_client.calls[0]["json"] == [
        {"deviceId": "screen-1", "resId": "device-1", "resType": "device", "index": 0, "houseId": "house-1"},
        {"deviceId": "screen-1", "resId": "scene-1", "resType": "scene", "index": 0, "houseId": "house-1"},
    ]


def test_text_to_image_accepts_prompt_alias_and_sends_texts():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="configuration.configure_storage_asset",
        action="text_to_image",
        payload={"pid": "264193", "prompt": "回家模式"},
        options={"dryRun": False, "confirmSideEffect": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert http_client.calls[0]["url"].endswith("/apis/iot/v1/common/r/264193/textToImage")
    assert http_client.calls[0]["json"] == {"texts": ["回家模式"]}


def test_favorite_batch_update_sends_array_body():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="home_organization.manage_favorite",
        action="batch_update_favorite",
        context=TaskContext(houseId="house-1", runtimeEnv="test"),
        payload={"items": [{"resId": "device-1", "resType": "device", "rank": 1}]},
        options={"dryRun": False, "confirmSideEffect": True, "allowCandidate": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert http_client.calls[0]["url"].endswith("/apis/iot/v1/favourite/w/batchupdate")
    assert http_client.calls[0]["json"] == [{"resId": "device-1", "rank": 1, "houseId": "house-1", "typeId": "2"}]


def test_scene_create_transforms_actions_to_details():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="scene_automation.manage_scene",
        action="create",
        context=TaskContext(houseId="house-1", runtimeEnv="test"),
        payload={
            "name": "验收情景",
            "actions": [
                {
                    "typeId": "1",
                    "resId": "room-1",
                    "resName": "验收房间",
                    "params": {"set": {"p": True}},
                    "rank": 0,
                }
            ],
        },
        options={"dryRun": False, "confirmSideEffect": True, "allowCandidate": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert http_client.calls[0]["url"].endswith("/apis/iot/v1/scene/w/insert")
    assert http_client.calls[0]["json"]["details"] == [
        {
            "typeId": "1",
            "resId": "room-1",
            "resName": "验收房间",
            "params": '{"set":{"p":true}}',
            "rank": 0,
        }
    ]
    assert "actions" not in http_client.calls[0]["json"]


def test_scene_update_requires_house_context_and_transforms_actions():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    schema = registry.get_schema("scene_automation.manage_scene", "update")

    assert schema.contextRequired == ["houseId", "sceneId"]

    request = TaskExecutionRequest(
        task="scene_automation.manage_scene",
        action="update",
        context=TaskContext(houseId="house-1", sceneId="scene-1", runtimeEnv="test"),
        payload={
            "name": "验收情景更新",
            "actions": [{"typeId": "1", "resId": "room-1", "params": {"set": {"p": False}}, "rank": 0}],
            "addToFav": "0",
            "gatewayDeviceId": "gateway-1",
            "img": "scene_1",
            "valid": 1,
        },
        options={"dryRun": False, "confirmSideEffect": True, "allowCandidate": True},
    )

    result = executor.execute(request, headers={"authorization": "Bearer token"})

    assert result.ok
    assert http_client.calls[0]["url"].endswith("/apis/iot/v1/scene/scene-1/w/update")
    assert http_client.calls[0]["json"]["houseId"] == "house-1"
    assert http_client.calls[0]["json"]["addToFav"] == "0"
    assert http_client.calls[0]["json"]["details"][0]["params"] == '{"set":{"p":false}}'


def test_pair_device_progress_has_polling_guidance():
    registry = MetadataTaskRegistry()
    executor = TaskExecutor(registry, DummyHttpClient())
    request = TaskExecutionRequest(
        task="device_onboarding.pair_device",
        action="get_secondary_pairing_progress",
        context=TaskContext(houseId="house-1", nodeId="node-1"),
    )

    result = executor.execute(request, headers={})

    assert result.ok
    assert result.plan.executionMode.value == "cloud_api_with_polling"
    assert any("轮询" in item for item in result.plan.guidance)
    assert result.plan.httpRequest["url"].endswith("/apis/iot/v1/matter/house/house-1/r/secondaryPairing/node-1/progress")


def test_pair_device_screen_pre_bind_requires_mobile_app_guidance():
    registry = MetadataTaskRegistry()
    executor = TaskExecutor(registry, DummyHttpClient())
    request = TaskExecutionRequest(
        task="device_onboarding.pair_device",
        action="pre_bind_screen",
        context=TaskContext(houseId="house-1", roomId="room-1"),
        payload={"deviceId": "device-1"},
    )

    result = executor.execute(request, headers={})

    assert result.ok
    assert result.dryRun
    assert result.plan.executionMode.value == "requires_mobile_app"
    assert any("移动端 APP" in item for item in result.plan.guidance)


def test_response_normalization_handles_business_error():
    registry = MetadataTaskRegistry()
    executor = TaskExecutor(registry, ErrorHttpClient())
    request = TaskExecutionRequest(
        task="configuration.configure_panel",
        action="update_layout",
        context=TaskContext(deviceId="device-1"),
        payload={"buttons": []},
        options={"dryRun": False, "confirmSideEffect": True},
    )

    result = executor.execute(request, headers={})

    assert not result.ok
    assert result.code == "500"
    assert result.message == "业务失败"


def test_scene_create_candidate_schema_and_dry_run():
    registry = MetadataTaskRegistry()
    executor = TaskExecutor(registry, DummyHttpClient())
    schema = registry.get_schema("scene_automation.manage_scene", "create")

    assert schema.contextRequired == ["houseId"]
    assert schema.payloadRequired == ["actions", "name"]

    request = TaskExecutionRequest(
        task="scene_automation.manage_scene",
        action="create",
        context=TaskContext(houseId="house-1", runtimeEnv="test"),
        payload={"name": "回家", "actions": []},
        options={"allowCandidate": True},
    )

    result = executor.execute(request, headers={})

    assert result.ok
    assert result.dryRun
    assert result.plan.httpRequest["url"].endswith("/apis/iot/v1/scene/w/insert")


def test_account_unbind_is_s3_and_uses_source_path():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="maintenance_account.manage_account",
        action="unbind_third_party",
        payload={"source": "facebook"},
        options={"dryRun": False, "confirmSideEffect": True},
    )

    result = executor.execute(request, headers={})

    assert result.ok
    assert result.plan.sideEffect.value == "S3"
    assert http_client.calls[0]["method"] == "DELETE"
    assert http_client.calls[0]["url"].endswith("/apis/account/user/unBindSocialUser/facebook")


def test_upgrade_electricity_requires_time_range():
    registry = MetadataTaskRegistry()
    executor = TaskExecutor(registry, DummyHttpClient())
    request = ValidationRequest(
        task="maintenance_account.upgrade_and_stats",
        action="get_electricity_stat",
        payload={"deviceIds": ["d1"]},
    )

    result = executor.validate(request)

    assert not result.valid
    assert any("startTime" in error for error in result.errors)
    assert any("endTime" in error for error in result.errors)


def test_app_upgrade_schema_requires_app_type_and_os_type():
    registry = MetadataTaskRegistry()
    executor = TaskExecutor(registry, DummyHttpClient())
    request = ValidationRequest(
        task="maintenance_account.upgrade_and_stats",
        action="get_latest_app",
        payload={"type": 1},
    )

    result = executor.validate(request)

    assert not result.valid
    assert any("osType" in error for error in result.errors)


def test_ptx_device_list_schema_requires_gateway_key_and_device_type():
    registry = MetadataTaskRegistry()
    executor = TaskExecutor(registry, DummyHttpClient())
    request = ValidationRequest(
        task="maintenance_account.upgrade_and_stats",
        action="list_ptx_device",
        payload={"key": "gateway-code"},
    )

    result = executor.validate(request)

    assert not result.valid
    assert any("theDl" in error for error in result.errors)


def test_ai_control_node_list_sends_house_and_device_ids():
    registry = MetadataTaskRegistry()
    http_client = DummyHttpClient()
    executor = TaskExecutor(registry, http_client)
    request = TaskExecutionRequest(
        task="configuration.configure_ai_voice",
        action="list_control_node",
        context=TaskContext(houseId="house-1"),
        payload={"deviceIds": ["device-1"]},
        options={"dryRun": False},
    )

    result = executor.execute(request, headers={})

    assert result.ok
    assert http_client.calls[0]["url"].endswith("/apis/iot/v1/ai/house-1/control/r/info")
    assert http_client.calls[0]["json"] == {"deviceIds": ["device-1"]}


def test_diagnostics_external_is_manual_assist():
    registry = MetadataTaskRegistry()
    executor = TaskExecutor(registry, DummyHttpClient())
    request = TaskExecutionRequest(
        task="maintenance_account.diagnostics",
        action="check_yeelight_connectivity",
        payload={"url": "https://yeelight.com"},
    )

    result = executor.execute(request, headers={})

    assert result.ok
    assert result.dryRun
    assert result.plan.executionMode.value == "manual_assist"
    assert any("不能由在线 MCP 直接完成" in item for item in result.plan.guidance)
