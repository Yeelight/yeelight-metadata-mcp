from typing import Any, Dict, List


def string_field(description: str, required: bool = False) -> Dict[str, Any]:
    return {"type": "string", "required": required, "description": description}


def integer_field(description: str, required: bool = False) -> Dict[str, Any]:
    return {"type": "integer", "required": required, "description": description}


def boolean_field(description: str, required: bool = False) -> Dict[str, Any]:
    return {"type": "boolean", "required": required, "description": description}


def object_field(description: str, required: bool = False) -> Dict[str, Any]:
    return {"type": "object", "required": required, "description": description}


def array_field(description: str, required: bool = False) -> Dict[str, Any]:
    return {"type": "array", "required": required, "description": description}


def structured_field(
    field_type: str,
    description: str,
    required: bool = False,
    structure: Any = None,
    examples: Any = None,
) -> Dict[str, Any]:
    field = {"type": field_type, "required": required, "description": description}
    if structure is not None:
        field["structure"] = structure
    if examples is not None:
        field["examples"] = examples
    return field


ROOM_BATCH_STRUCTURE = {
    "item": {
        "name": "房间名称，必填",
        "desc": "房间描述，可选",
        "icon": "房间图标，可选",
        "gatewayDeviceId": "推荐网关设备 ID，可选",
        "gatewayIds": "房间关联的网关设备 ID 列表，可选",
        "areaIds": "MCP 扩展字段，可选，用于绑定所属区域",
    },
    "execution": "MCP 直传 rooms 数组；houseId 从 context 补入请求体。",
}


DEVICE_BATCH_STRUCTURE = {
    "item": {
        "name": "设备名称，必填",
        "pid": "产品 ID，必填",
        "pcId": "产品品类 ID，可选；与 pid 按产品配置要求传入",
        "type": "设备类型，可选；需与产品类型保持一致",
        "desc": "设备描述，可选",
        "icon": "设备图标，可选",
        "roomId": "可选；未传时使用 context.roomId",
        "gatewayDeviceId": "可选，网关设备 ID",
        "mac": "可选，设备 MAC",
        "connectType": "连接类型，必填；取值需使用系统支持的连接类型",
        "virtual": "后端字段，是否为虚拟设备",
        "isVirtual": "可选，MCP 会转换为后端字段 virtual",
        "ipPort": "IP 端口号，可选；直连或网络类设备按需传入",
    },
    "execution": "MCP 会给每个设备补 roomId，并把 isVirtual 改写为 virtual。",
}


DEVICE_GROUP_MEMBER_STRUCTURE = {
    "simpleMode": "传 deviceIds 时，MCP 会转换为 addDeviceList=[{id: deviceId}]，表示批量添加设备。",
    "patchMode": "也可直接传 addDeviceList/removeDeviceList；一旦传了这两个字段，MCP 会忽略 deviceIds 并原样透传。",
    "item": {"id": "设备 ID，必填"},
}


FAVORITE_ITEM_STRUCTURE = {
    "item": {
        "id": "收藏记录 ID；更新或按收藏记录删除时传",
        "resId": "收藏资源 ID，必填；设备/房间/区域/设备组/情景等资源 ID",
        "resType": "可选别名：room/device/area/group/mesh_group/scene；MCP 会转换为 typeId",
        "typeId": "后端资源类型；未传 typeId 但传 resType 时由 MCP 补齐",
        "rank": "可选，排序值",
        "valid": "是否有效，可选",
        "houseId": "可选；未传时 MCP 使用 context.houseId 补齐",
    },
    "typeAliases": {"room": "1", "device": "2", "area": "3", "group": "4", "mesh_group": "4", "scene": "6"},
    "execution": "批量收藏接口最终发送数组 body，而不是 {items:[...]} 包装对象。",
}


SCENE_ACTION_STRUCTURE = {
    "inputField": "actions",
    "execution": "MCP 会把 actions 转为后端 details，并把每个动作内的 params object 序列化为 JSON string。",
    "item": {
        "typeId": "动作资源类型，必填，取值需来自物模型/情景能力",
        "resId": "动作目标资源 ID，必填，例如设备、房间或组 ID",
        "resName": "可选，资源名称",
        "params": "string|object，动作参数；传 object 时 MCP 会序列化",
        "rank": "可选，执行顺序，从 0 开始",
    },
}


PANEL_LAYOUT_STRUCTURE = {
    "inputField": "buttons",
    "execution": "后端请求体是 PanelButton 数组；MCP 支持传 buttons 数组，也兼容旧 layout.buttons 并在执行前转为数组。",
    "item": {
        "id": "面板按键记录 ID，更新已有按键时传",
        "deviceId": "面板设备 ID；MCP 会从 context.deviceId 补入",
        "buttonId": "按键 ID",
        "name": "按键名称",
        "type": "按键类型；查询按键信息返回结果按 type 分组",
        "index": "按键序号",
        "icon": "按键图标",
        "rank": "排序值",
        "buttonEvents": "按键事件列表；配置动作前建议先查询按键信息",
    },
    "guidance": "优先先查询面板按键信息，再基于返回的 PanelButton 数组修改需要变更的字段，保留未知字段。",
}


PANEL_EVENT_STRUCTURE = {
    "execution": "单个更新接口请求体是 UpdatePanelButtonEventRequest；MCP 支持传 event 对象并会补 deviceId，也可直接传顶层字段。",
    "item": {
        "buttonEventId": "按键事件 ID；更新已有动作时传",
        "deviceId": "面板设备 ID；MCP 会从 context.deviceId 补入",
        "buttonId": "按键 ID",
        "eventType": "触发类型，例如 click/double_click/long_press，具体以详情返回为准",
        "actions": "动作列表；结构与情景/自动化动作类似",
        "params": "可选，事件扩展参数",
    },
    "guidance": "优先先查询按键信息，再基于返回的事件对象修改动作字段。",
}


KNOB_CONFIG_STRUCTURE = {
    "input": "旋钮完整配置对象，按查询详情返回结构修改后整体提交；执行时 MCP 会补 id=context.deviceId。",
    "commonFields": {
        "id": "旋钮设备 ID；MCP 会从 context.deviceId 补入",
        "events": "可选，旋钮事件配置列表",
        "index": "多键旋钮按键序号；多键场景常见",
        "actions": "可选，每个事件触发的动作列表",
        "params": "可选，旋钮扩展参数",
    },
    "guidance": "优先先查询单键/多键旋钮详情，再基于返回对象修改；保留未知字段。",
}


AUTOMATION_ACTION_STRUCTURE = {
    "item": {
        "typeId": "动作资源类型，必填，来自自动化能力列表",
        "resId": "动作目标资源 ID，必填",
        "params": "string|object，动作参数；后端动作结构以能力列表为准",
        "rank": "可选，执行顺序",
    },
    "limit": "单个自动化最多 200 个动作。",
    "capabilitySource": "typeId、resId、params 字段应来自 automation.capability.list_v2 或物模型能力。",
}


def room_batch_field(required: bool = True) -> Dict[str, Any]:
    return structured_field(
        "array",
        "批量房间定义。每项至少包含 name；可选 areaIds 绑定区域。",
        required,
        ROOM_BATCH_STRUCTURE,
        [{"name": "客厅", "areaIds": ["area-1"]}],
    )


def device_batch_field(required: bool = True) -> Dict[str, Any]:
    return structured_field(
        "array",
        "批量设备坑位定义。每项至少包含 name 和 pid；roomId 可省略，MCP 会使用 context.roomId。",
        required,
        DEVICE_BATCH_STRUCTURE,
        [{"name": "射灯 1", "pid": "264193", "isVirtual": False}],
    )


def device_ids_field(description: str, required: bool = False) -> Dict[str, Any]:
    return structured_field("array", description, required, {"itemType": "string", "item": "设备 ID"}, ["device-1", "device-2"])


def id_list_field(description: str, item_name: str, required: bool = False) -> Dict[str, Any]:
    example_by_item = {"设备 ID": "device-1", "房间 ID": "room-1", "区域 ID": "area-1", "情景 ID": "scene-1", "文字": "回家模式"}
    return structured_field("array", description, required, {"itemType": "string", "item": item_name}, [example_by_item.get(item_name, "id-1")])


def room_ids_to_details_field(description: str, required: bool = False) -> Dict[str, Any]:
    return structured_field(
        "array",
        description,
        required,
        {"itemType": "string", "item": "房间 ID", "execution": "legacy 区域组接口中 MCP 会把 roomIds 转换为 details=[{roomId: ...}]。"},
        ["room-1", "room-2"],
    )


def sort_items_field(required: bool = True) -> Dict[str, Any]:
    return structured_field(
        "array",
        "排序项列表；每项描述一个资源及其排序值。",
        required,
        {"item": {"resId": "资源 ID，必填", "rank": "排序值，必填", "typeId": "可选，资源类型"}},
        [{"resId": "scene-1", "rank": 1}],
    )


def name_update_items_field(required: bool = True) -> Dict[str, Any]:
    return structured_field(
        "array",
        "设备或情景名称更新列表；后端请求体是数组，MCP 执行时会把 names 数组作为 body。",
        required,
        {
            "item": {
                "resId": "资源 ID，必填",
                "name": "新名称，必填",
                "resType": "可选，资源类型，例如 device 或 scene",
                "typeId": "可选，后端资源类型",
            }
        },
        [{"resId": "device-1", "resType": "device", "name": "客厅主灯"}],
    )


def device_group_member_field(description: str, required: bool = False) -> Dict[str, Any]:
    return structured_field("array", description, required, DEVICE_GROUP_MEMBER_STRUCTURE, [{"id": "device-1"}])


def favorite_items_field(description: str, required: bool = True) -> Dict[str, Any]:
    return structured_field(
        "array",
        description,
        required,
        FAVORITE_ITEM_STRUCTURE,
        [{"resId": "device-1", "resType": "device", "rank": 1}],
    )


def scene_actions_field(description: str, required: bool = True) -> Dict[str, Any]:
    return structured_field(
        "array",
        description,
        required,
        SCENE_ACTION_STRUCTURE,
        [{"typeId": "1", "resId": "device-1", "params": {"set": {"power": "on"}}, "rank": 0}],
    )


def panel_layout_field(required: bool = True) -> Dict[str, Any]:
    return structured_field("array", "面板按键配置数组；建议基于查询按键信息返回的 PanelButton 列表修改后提交。", required, PANEL_LAYOUT_STRUCTURE)


def panel_event_field(description: str, required: bool = True) -> Dict[str, Any]:
    return structured_field("object", description, required, PANEL_EVENT_STRUCTURE)


def panel_events_field(required: bool = True) -> Dict[str, Any]:
    return structured_field("array", "批量按键动作配置列表；每项结构同 event。", required, PANEL_EVENT_STRUCTURE, [{"buttonEventId": "event-1", "actions": []}])


def knob_config_field(description: str, required: bool = True) -> Dict[str, Any]:
    return structured_field("object", description, required, KNOB_CONFIG_STRUCTURE)


def json_object_field(description: str, required: bool = True, examples: Any = None) -> Dict[str, Any]:
    return structured_field("object", description, required, {"input": "任意 JSON object；保留业务需要的嵌套字段，MCP 不会改写内部结构。"}, examples)


def sub_devices_field(description: str, required: bool = False) -> Dict[str, Any]:
    return structured_field(
        "array",
        description,
        required,
        {"item": {"id": "子设备 ID", "name": "子设备名称", "icon": "子设备图标", "desc": "子设备描述"}},
        [{"id": "sub-device-1", "name": "一路开关"}],
    )


def screen_voice_controls_field(required: bool = True) -> Dict[str, Any]:
    return structured_field(
        "array",
        "屏设备语音控制配置列表；后端请求体是 ScreenVoiceControl 数组，MCP 执行时会补 houseId。",
        required,
        {
            "item": {
                "deviceId": "屏设备 ID，必填",
                "resId": "被控制资源 ID，必填",
                "resType": "被控制资源类型，例如 device 或 scene",
                "index": "显示或控制顺序，可选",
                "valid": "是否有效，可选",
                "houseId": "家庭 ID；MCP 会从 context.houseId 补入",
            },
            "convenience": "也可传 screenDeviceId + deviceIds/sceneIds，MCP 会转换为 controls 数组；设备资源 resType=device，情景资源 resType=scene。",
        },
        [{"deviceId": "screen-1", "resId": "device-1", "resType": "device", "index": 0}],
    )


def automation_actions_field(description: str, required: bool = True) -> Dict[str, Any]:
    return structured_field(
        "array",
        description,
        required,
        AUTOMATION_ACTION_STRUCTURE,
        [{"typeId": "1", "resId": "device-1", "params": {"set": {"power": "on"}}, "rank": 0}],
    )


AUTOMATION_PARAMS_STRUCTURE = {
    "inputFormat": "调用方优先传 object；MCP 会在执行前序列化为紧凑 JSON 字符串写入 params。也兼容已经序列化好的 JSON string。",
    "versionRule": "MCP 只暴露 V2 自动化参数；调用方无需传 version，执行时固定补 2。",
    "v2": {
        "useWhen": "所有新建、更新和测试自动化都使用 V2，适合把事件/时间触发条件和状态条件分组表达。",
        "root": {"type": "and", "conditions": "ConditionGroup[]，顶层不能为空"},
        "groupRules": [
            "顶层每一项都是条件组，必须包含非空 type 和非空 conditions。",
            "事件组包含 event、alarm 或 fact_change 条件；事件组 type 不能为 and，通常传 or。",
            "状态组只包含 fact 条件；状态组 type 只能为 and 或 or。",
            "同一个 v2 params 中最多只能有一个事件组和一个状态组。",
        ],
        "conditionTypes": {
            "alarm": {"type": "alarm", "clock": "HH:mm:ss，例如 20:00:00"},
            "event": {"type": "event", "resId": "设备或资源 ID", "pid": "产品 ID", "id": "事件 ID", "extArgs": "可选，事件扩展参数"},
            "fact_change": {"type": "fact_change", "resId": "设备或资源 ID", "typeId": "属性类型 ID", "prop": "属性名"},
            "fact": {
                "type": "fact",
                "resId": "设备或资源 ID",
                "typeId": "属性类型 ID",
                "prop": "属性名",
                "operation": "可选，默认 eq；支持 eq、gt、ge、lt、le、ne、bt",
                "value": "比较值；operation=bt 时传两个英文逗号分隔的值，例如 10,20",
            },
        },
    },
    "capabilitySource": "resId、pid、id、typeId、prop 等能力字段应来自当前家庭设备和 automation.capability.list / automation.capability.list_v2 返回的能力。",
    "placeholderRule": "示例中的 <设备ID>、<产品ID>、<事件ID>、<属性类型ID>、<属性名> 都是占位符，真实调用前必须替换为能力列表中的实际值。",
}


AUTOMATION_PARAMS_EXAMPLES = [
    {
        "title": "V2：事件/时间组加状态组",
        "version": 2,
        "value": {
            "type": "and",
            "conditions": [
                {
                    "type": "or",
                    "conditions": [
                        {"type": "alarm", "clock": "20:00:00"},
                        {"type": "event", "resId": "<设备ID>", "pid": "<产品ID>", "id": "<事件ID>"},
                    ],
                },
                {
                    "type": "and",
                    "conditions": [
                        {
                            "type": "fact",
                            "resId": "<设备ID>",
                            "typeId": "<属性类型ID>",
                            "prop": "<属性名>",
                            "operation": "eq",
                            "value": "<期望值>",
                        },
                    ],
                },
            ],
        },
    },
    {
        "title": "V2：仅定时触发",
        "version": 2,
        "value": {
            "type": "and",
            "conditions": [
                {
                    "type": "or",
                    "conditions": [
                        {"type": "alarm", "clock": "20:00:00"},
                    ],
                },
            ],
        },
    },
]


def automation_params_field(required: bool = True, extra_description: str = "") -> Dict[str, Any]:
    description = (
        "自动化条件参数。优先传 object，MCP 执行前会序列化为接口要求的字符串 JSON；也可直接传 JSON string。"
        " MCP 只暴露 V2：根对象必须为 {type: and, conditions: [条件组...]}；顶层 conditions 不能为空。"
        " 事件组包含 event/alarm/fact_change 且 type 通常为 or；状态组只包含 fact 且 type 为 and 或 or；同一个 params 中最多一个事件组和一个状态组。"
        " 字段取值如 resId、pid、id、typeId、prop 应来自当前家庭设备及自动化能力列表。"
    )
    if extra_description:
        description = f"{description} {extra_description}"
    return {
        "type": "string|object",
        "required": required,
        "description": description,
        "structure": AUTOMATION_PARAMS_STRUCTURE,
        "examples": AUTOMATION_PARAMS_EXAMPLES,
    }


OPERATION_INTERFACE_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "house.core.create": {
        "method": "PUT",
        "runtime_path": "/apis/iot/v2/thing/manage/house/w/create",
        "title": "新建家庭",
        "source_type": "业务验收校准",
    },
    "house.core.update": {
        "method": "POST",
        "runtime_path": "/apis/iot/v2/thing/manage/house/{houseId}/w/modify",
        "title": "更新家庭详情",
        "source_type": "业务验收校准",
    },
    "room.core.batch_create": {
        "method": "PUT",
        "runtime_path": "/apis/iot/v2/thing/manage/house/{houseId}/room/w/batch_create",
        "title": "批量新建房间",
        "source_type": "业务验收校准",
    },
    "room.core.update": {
        "method": "POST",
        "runtime_path": "/apis/iot/v2/thing/manage/house/{houseId}/room/{id}/w/modify",
        "title": "更新房间详情",
        "source_type": "业务验收校准",
    },
    "room.core.delete": {
        "method": "DELETE",
        "runtime_path": "/apis/iot/v2/thing/manage/house/{houseId}/room/{id}/w/info",
        "title": "删除房间",
        "source_type": "业务验收校准",
    },
    "room.area.update": {
        "method": "POST",
        "runtime_path": "/apis/iot/v2/thing/manage/house/{houseId}/room/{id}/w/areas",
        "title": "更新房间所属区域",
        "source_type": "业务验收校准",
    },
    "device.slot.batch_create": {
        "method": "PUT",
        "runtime_path": "/apis/iot/v2/thing/manage/house/{houseId}/device/w/batch-create",
        "title": "批量新增设备坑位",
        "source_type": "业务验收校准",
    },
    "device.slot.create": {
        "method": "PUT",
        "runtime_path": "/apis/iot/v2/thing/manage/house/{houseId}/device/w/create",
        "title": "新增设备坑位",
        "source_type": "业务验收校准",
    },
    "device.slot.update": {
        "method": "POST",
        "runtime_path": "/apis/iot/v2/thing/manage/house/{houseId}/device/{id}/w/modify",
        "title": "更新设备详情",
        "source_type": "业务验收校准",
    },
    "gateway.core.delete": {
        "method": "POST",
        "runtime_path": "/apis/iot/v1/device/{gatewayId}/w/delete",
        "title": "删除网关坑位",
        "source_type": "业务验收校准",
    },
}


DEV_CONFIRMED_OPERATIONS = {
    "area.core.create",
    "area.core.delete",
    "area.core.get_detail",
    "area.core.list",
    "area.core.update",
    "area_group.legacy_group.create",
    "area_group.legacy_group.delete",
    "area_group.legacy_group.fuzzy_search",
    "area_group.legacy_group.list",
    "area_group.legacy_group.list_all",
    "area_group.legacy_group.update",
    "device.slot.batch_create",
    "device.slot.create",
    "device.slot.delete",
    "device.slot.get_detail",
    "device.slot.list_all",
    "device.slot.unbind",
    "device.slot.unbind_and_clear_mac",
    "device.slot.update",
    "device_group.mesh_group.create",
    "device_group.mesh_group.delete",
    "device_group.mesh_group.get_detail",
    "device_group.mesh_group.update",
    "device_group.member.update_devices",
    "favorite.core.batch_insert",
    "favorite.core.batch_delete",
    "favorite.core.batch_update",
    "favorite.core.list_all",
    "gateway.core.create",
    "gateway.core.delete",
    "gateway.core.get_detail",
    "gateway.core.list",
    "gateway.core.list_with_stats",
    "gateway.core.update",
    "gateway.thread.get_info",
    "house.core.create",
    "house.core.delete",
    "house.core.get_detail",
    "house.core.list",
    "house.core.list_all",
    "house.core.update",
    "house.property.get",
    "room.area.update",
    "room.core.batch_create",
    "room.core.create",
    "room.core.delete",
    "room.core.get_detail",
    "room.core.list",
    "room.core.list_all",
    "room.core.update",
    "room.search.fuzzy",
    "scene.management.create",
    "scene.management.delete",
    "scene.management.get_detail",
    "scene.management.list",
    "scene.management.list_all",
    "scene.management.test",
    "scene.management.update",
    "scene.search.fuzzy",
    "thing_schema.house_snapshot.get_house",
    "thing_schema.house_snapshot.list_automation",
    "thing_schema.house_snapshot.list_device",
    "thing_schema.house_snapshot.list_gateway",
    "thing_schema.house_snapshot.list_group",
    "thing_schema.house_snapshot.list_room",
    "thing_schema.house_snapshot.list_scene",
}


OPERATION_ACTION_OVERRIDES = {
    "house.core.get_detail": "get_house_detail",
    "house.core.list_all": "list_all_house",
    "house.property.get": "get_house_property",
    "house.property.update": "update_house_property",
    "room.core.get_detail": "get_room_detail",
    "room.core.list_all": "list_all_room",
    "room.core.batch_create": "batch_create_room",
    "room.search.fuzzy": "search_room",
    "room.area.update": "update_room_area",
    "device.slot.list_all": "list_all_device",
    "device.slot.get_detail": "get_device_detail",
    "device.slot.batch_create": "batch_create_device_slot",
    "device.slot.unbind_and_clear_mac": "unbind_and_clear_mac",
    "device.relation.list_devices": "list_relation_device",
    "device.attribute.update": "update_device_attribute",
    "thing_schema.house_snapshot.get_house": "get_house_snapshot",
    "thing_schema.house_snapshot.list_device": "list_device_snapshot",
    "thing_schema.house_snapshot.list_room": "list_room_snapshot",
    "thing_schema.house_snapshot.list_group": "list_group_snapshot",
    "thing_schema.house_snapshot.list_gateway": "list_gateway_snapshot",
    "thing_schema.house_snapshot.list_scene": "list_scene_snapshot",
    "thing_schema.house_snapshot.list_automation": "list_automation_snapshot",
    "device_group.mesh_group.get_detail": "get_group_detail",
    "device_group.member.update_devices": "update_group_devices",
    "gateway.core.get_detail": "get_gateway_detail",
    "gateway.core.list_with_stats": "list_gateway_with_stats",
    "gateway.thread.get_info": "get_gateway_thread_info",
    "favorite.core.list_all": "list_all_favorite",
    "favorite.core.batch_insert": "batch_insert_favorite",
    "favorite.core.batch_update": "batch_update_favorite",
    "favorite.core.batch_delete": "batch_delete_favorite",
    "scene.sort.add": "add_sort",
    "scene.sort.list_room_scene": "list_room_scene_sort",
    "house.member.get_current": "get_current_member",
    "house.member.update_role": "update_member_role",
    "house.share.create_barcode": "create_share_barcode",
    "house.share.list_history": "list_share_history",
    "house.share.send_invite": "send_share_invite",
    "house.share.accept_invite": "accept_share_invite",
    "house.share.accept_barcode": "accept_share_barcode",
    "house.membership.quit": "quit_house",
    "house.ownership.transfer": "transfer_house",
    "house.device_lock.lock_all": "lock_all_device",
    "house.device_lock.unlock_all": "unlock_all_device",
    "device.screen.pre_bind": "pre_bind_screen",
    "matter.pairing_code.apply": "apply_pairing_code",
    "matter.secondary_pairing.apply": "apply_secondary_pairing",
    "matter.secondary_pairing.get_progress": "get_secondary_pairing_progress",
    "matter.secondary_pairing.cancel": "cancel_secondary_pairing",
    "scene.management.get_detail": "get_scene_detail",
    "scene.management.list_all": "list_all_scene",
    "scene.search.fuzzy": "search_scene",
    "upgrade.app.get_latest": "get_latest_app",
    "upgrade.device_stat.get_electricity": "get_electricity_stat",
    "upgrade.ptx.list_devices": "list_ptx_device",
    "upgrade.ptx.list_ota_updates": "list_ptx_ota_update",
    "account.account.exists": "check_account_exists",
    "account.scan_login.query_qrcode": "create_scan_qrcode",
    "account.scan_login.check_qrcode": "check_scan_qrcode",
    "account.scan_login.mark_scanned": "mark_qrcode_scanned",
    "account.scan_login.confirm": "confirm_scan_login",
    "account.scan_login.login": "scan_login",
    "account.third_party_auth.generate_state": "generate_third_party_state",
    "account.third_party_auth.login": "third_party_login",
    "account.third_party_auth.bind": "bind_third_party",
    "account.third_party_auth.list_bindings": "list_third_party_binding",
    "account.third_party_auth.unbind": "unbind_third_party",
    "account.user.get_info": "get_user_info",
    "account.user.update_info": "update_user_info",
    "location.area.search": "search_location_area",
    "location.area.list_children": "list_location_children",
    "https://yeelight.com": "check_yeelight_connectivity",
    "ptx_ota_dynamic_file_url": "download_ptx_ota_file",
    "realtime.lan_gateway.sync_nodes_groups": "sync_lan_gateway_nodes",
    "sonos.group.discover_and_listen": "discover_sonos_group",
    "panel.button.update_layout": "update_layout",
    "panel.button_event.update": "update_event",
    "panel.button_event.batch_update": "batch_update_event",
    "panel.button_event.reset": "reset_event",
    "knob.single.get_detail": "get_single_detail",
    "knob.single.update": "update_single",
    "knob.single.reset": "reset_single",
    "knob.multi.get_detail": "get_multi_detail",
    "knob.multi.update": "update_multi",
    "knob.multi.reset": "reset_multi",
    "device.storage.get": "get_storage",
    "device.storage.set": "set_storage",
    "device.asset.upload_image": "upload_image",
    "device.asset.delete_images": "delete_images",
    "device.asset.text_to_image": "text_to_image",
    "ai.voice_product.list": "list_voice_product",
    "ai.control_node.list": "list_control_node",
    "ai.control_node.update": "update_control_node",
    "ai.name.recommend_device": "recommend_device_name",
    "ai.name.recommend_scene": "recommend_scene_name",
    "ai.name.batch_update": "batch_update_name",
    "ai.asr.get_temp_credential": "get_asr_temp_credential",
    "automation.capability.list": "list_capability",
    "automation.capability.list_v2": "list_capability_v2",
    "automation.rule.page": "page_rule",
    "automation.rule.enable": "enable_rule",
    "automation.rule.disable": "disable_rule",
    "automation.rule.test": "test_rule",
}


OPERATION_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "house.core.list": {
        "context_required": [],
        "payload_required": [],
        "payload_properties": {},
    },
    "house.core.list_all": {
        "context_required": [],
        "payload_required": [],
        "payload_properties": {},
    },
    "house.core.get_detail": {
        "context_required": ["houseId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "house.core.create": {
        "context_required": [],
        "payload_required": ["name"],
        "payload_excluded": ["description"],
        "payload_properties": {
            "name": string_field("家庭名称，不能为空", True),
            "desc": string_field("家庭描述，可为空；后端字段名为 desc"),
            "icon": string_field("家庭图标，可为空"),
            "areaCode": string_field("地区编码，可为空；建议与 areaName 保持一致"),
            "areaName": string_field("地区名称，可为空；填写后会影响家庭详情中的地区和时区信息"),
        },
    },
    "house.core.update": {
        "context_required": ["houseId"],
        "payload_required": ["name"],
        "payload_excluded": ["description"],
        "payload_properties": {
            "name": string_field("家庭名称，可为空；MCP 建议更新时明确传入", True),
            "desc": string_field("家庭描述，可为空；后端字段名为 desc"),
            "icon": string_field("家庭图标，可为空"),
            "areaId": string_field("地区 ID，可为空；传入时需为有效地区"),
            "areaCode": string_field("地区编码，可为空"),
            "areaName": string_field("地区名称，可为空"),
            "buildingName": string_field("建筑名称，可为空"),
            "buildingAddr": string_field("建筑地址，可为空"),
            "floorName": string_field("楼层名称，可为空"),
        },
    },
    "house.core.delete": {
        "context_required": ["houseId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "house.property.get": {
        "context_required": ["houseId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "house.property.update": {
        "context_required": ["houseId"],
        "payload_required": ["properties"],
        "payload_properties": {
            "properties": json_object_field("家庭属性配置对象；按业务键值整体提交，MCP 不改写内部结构。", True, {"theme": "default"}),
        },
    },
    "room.core.list": {
        "context_required": ["houseId"],
        "payload_required": [],
        "payload_properties": {
            "pageNo": integer_field("页码"),
            "pageSize": integer_field("每页数量"),
        },
    },
    "room.core.list_all": {
        "context_required": ["houseId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "room.core.get_detail": {
        "context_required": ["roomId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "room.core.create": {
        "context_required": ["houseId"],
        "payload_required": ["name"],
        "payload_properties": {
            "name": string_field("房间名称，不能为空", True),
            "desc": string_field("房间描述，可为空；后端字段名为 desc"),
            "icon": string_field("房间图标，可为空"),
            "gatewayDeviceId": string_field("推荐网关设备 ID，可为空；传入时应属于同一家庭"),
            "gatewayIds": id_list_field("房间关联的网关设备 ID 列表；传入时应属于同一家庭", "设备 ID"),
            "areaIds": id_list_field("MCP 扩展字段：所属区域 ID 列表", "区域 ID"),
        },
    },
    "room.core.batch_create": {
        "context_required": ["houseId"],
        "payload_required": ["rooms"],
        "payload_properties": {
            "rooms": room_batch_field(True),
        },
    },
    "room.core.update": {
        "context_required": ["houseId", "roomId"],
        "payload_required": ["name"],
        "payload_properties": {
            "name": string_field("房间名称，可为空；MCP 建议更新时明确传入", True),
            "desc": string_field("房间描述，可为空；后端字段名为 desc"),
            "icon": string_field("房间图标，可为空"),
            "gatewayDeviceId": string_field("推荐网关设备 ID，可为空；传入时应属于同一家庭"),
            "gatewayIds": id_list_field("房间关联的网关设备 ID 列表；传入时应属于同一家庭", "设备 ID"),
            "rank": integer_field("房间排序值；数值越小越靠前"),
            "areaIds": id_list_field("MCP 扩展字段：所属区域 ID 列表", "区域 ID"),
        },
    },
    "room.core.delete": {
        "context_required": ["houseId", "roomId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "room.search.fuzzy": {
        "context_required": ["houseId"],
        "payload_required": ["fuzzyName"],
        "payload_properties": {
            "fuzzyName": string_field("房间模糊搜索关键词", True),
        },
    },
    "room.area.update": {
        "context_required": ["houseId", "roomId"],
        "payload_required": [],
        "payload_properties": {
            "areaIds": id_list_field("区域 ID 列表；便捷模式，MCP 会转换为 addAreaList。", "区域 ID"),
            "addAreaList": id_list_field("待添加区域 ID 列表；传该字段时 MCP 原样透传。", "区域 ID"),
            "removeAreaList": id_list_field("待移除区域 ID 列表；传该字段时 MCP 原样透传。", "区域 ID"),
        },
    },
    "area.core.list": {
        "context_required": ["houseId"],
        "payload_required": ["pageNo", "pageSize"],
        "payload_properties": {
            "pageNo": integer_field("页码", True),
            "pageSize": integer_field("每页数量", True),
        },
    },
    "area.core.get_detail": {
        "context_required": ["houseId", "areaId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "area.core.create": {
        "context_required": ["houseId"],
        "payload_required": ["name"],
        "payload_properties": {
            "name": string_field("区域名称，不能为空", True),
            "desc": string_field("区域描述，可为空；后端字段名为 desc"),
            "icon": string_field("区域图标，可为空"),
            "parentId": string_field("上级区域 ID，可为空；传入时应属于同一家庭"),
            "roomIds": id_list_field("区域关联的房间 ID 列表，可为空；传入时应属于同一家庭", "房间 ID"),
        },
    },
    "area.core.update": {
        "context_required": ["houseId", "areaId"],
        "payload_required": ["name"],
        "payload_properties": {
            "name": string_field("区域名称，可为空；MCP 建议更新时明确传入", True),
            "desc": string_field("区域描述，可为空；后端字段名为 desc"),
            "icon": string_field("区域图标，可为空"),
            "parentId": string_field("上级区域 ID，可为空；传入时应属于同一家庭"),
            "roomIds": id_list_field("区域关联的房间 ID 列表；传入时表示更新后的完整关联列表", "房间 ID"),
        },
    },
    "area.core.delete": {
        "context_required": ["houseId", "areaId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "area_group.legacy_group.list": {
        "context_required": ["houseId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "area_group.legacy_group.list_all": {
        "context_required": ["houseId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "area_group.legacy_group.fuzzy_search": {
        "context_required": ["houseId"],
        "payload_required": ["fuzzyName"],
        "payload_properties": {
            "fuzzyName": string_field("区域分组模糊搜索关键词", True),
        },
    },
    "area_group.legacy_group.create": {
        "context_required": ["houseId"],
        "payload_required": ["name"],
        "payload_properties": {
            "name": string_field("区域分组名称", True),
            "roomIds": room_ids_to_details_field("房间 ID 列表；MCP 会转换为 legacy details。"),
        },
    },
    "area_group.legacy_group.update": {
        "context_required": ["houseId", "groupId"],
        "payload_required": ["name"],
        "payload_properties": {
            "name": string_field("区域分组名称", True),
            "roomIds": room_ids_to_details_field("房间 ID 列表；MCP 会转换为 legacy details，并在更新时补 userGroupId。"),
        },
    },
    "area_group.legacy_group.delete": {
        "context_required": ["groupId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "house.member.get_current": {
        "context_required": ["houseId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "house.member.list": {
        "context_required": ["houseId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "house.member.search": {
        "context_required": ["houseId"],
        "payload_required": ["targetUser"],
        "payload_properties": {
            "targetUser": string_field("待搜索用户标识", True),
        },
    },
    "house.member.remove": {
        "context_required": ["houseId"],
        "payload_required": ["memberId"],
        "payload_properties": {
            "memberId": string_field("家庭成员 ID", True),
        },
    },
    "house.member.update_role": {
        "context_required": ["houseId"],
        "payload_required": ["memberId", "role"],
        "payload_properties": {
            "memberId": string_field("家庭成员 ID", True),
            "role": string_field("成员角色", True),
        },
    },
    "house.share.create_barcode": {
        "context_required": ["houseId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "house.share.list_history": {
        "context_required": [],
        "payload_required": ["toUid"],
        "payload_properties": {
            "toUid": string_field("被查询邀请历史的用户 ID", True),
        },
    },
    "house.share.send_invite": {
        "context_required": ["houseId"],
        "payload_required": ["targetUser"],
        "payload_properties": {
            "targetUser": string_field("被邀请用户标识", True),
            "role": string_field("邀请角色"),
        },
    },
    "house.share.accept_invite": {
        "context_required": [],
        "payload_required": ["shareId"],
        "payload_properties": {
            "shareId": string_field("分享 ID", True),
        },
    },
    "house.share.accept_barcode": {
        "context_required": [],
        "payload_required": ["barcode"],
        "payload_properties": {
            "barcode": string_field("家庭分享码", True),
        },
    },
    "house.membership.quit": {
        "context_required": ["houseId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "house.ownership.transfer": {
        "context_required": ["houseId"],
        "payload_required": ["memberId"],
        "payload_properties": {
            "memberId": string_field("目标管理员成员 ID", True),
        },
    },
    "device.slot.list_all": {
        "context_required": ["houseId"],
        "payload_required": [],
        "payload_properties": {
            "includeGroup": boolean_field("是否包含设备组；为 true 时列表中可包含灯组/设备组资源"),
            "roomId": string_field("房间 ID，可为空；传入时仅查询该房间下的设备"),
            "crop": boolean_field("是否裁剪返回结果；为 true 时返回更精简的设备信息"),
        },
    },
    "device.slot.get_detail": {
        "context_required": ["deviceId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "device.slot.create": {
        "context_required": ["houseId", "roomId"],
        "payload_required": ["name", "pid", "connectType"],
        "payload_excluded": ["description"],
        "payload_properties": {
            "name": string_field("设备名称，不能为空", True),
            "pid": string_field("产品 ID；与 pcId 按产品配置要求传入", True),
            "pcId": string_field("产品品类 ID；与 pid 按产品配置要求传入"),
            "type": string_field("设备类型；取值需与产品类型保持一致"),
            "desc": string_field("设备描述，可为空；后端字段名为 desc"),
            "icon": string_field("设备图标，可为空"),
            "gatewayDeviceId": string_field("网关设备 ID；子设备或需挂载网关的设备必须传入，且网关需属于同一家庭"),
            "mac": string_field("设备 MAC，可为空"),
            "connectType": string_field("连接类型，不能为空；取值需使用系统支持的连接类型", True),
            "virtual": boolean_field("是否虚拟设备；后端字段名为 virtual"),
            "isVirtual": boolean_field("是否虚拟设备；MCP 便捷字段，执行时会转换为后端字段 virtual"),
            "ipPort": string_field("IP 端口号，可为空；直连或网络类设备按需传入"),
        },
    },
    "device.slot.batch_create": {
        "context_required": ["houseId", "roomId"],
        "payload_required": ["devices"],
        "payload_properties": {
            "devices": device_batch_field(True),
        },
    },
    "device.slot.update": {
        "context_required": ["houseId", "deviceId"],
        "payload_required": [],
        "payload_excluded": ["description"],
        "payload_properties": {
            "name": string_field("设备名称，可为空"),
            "desc": string_field("设备描述，可为空；后端字段名为 desc"),
            "roomId": string_field("目标房间 ID，可为空；传入时应属于同一家庭"),
            "icon": string_field("设备图标，可为空"),
            "mac": string_field("设备 MAC，可为空"),
            "subDevices": sub_devices_field("子设备列表；用于修改多路设备或组件的名称、图标等展示信息"),
            "ipPort": string_field("IP 端口号，可为空；直连或网络类设备按需传入"),
        },
    },
    "device.slot.delete": {
        "context_required": ["deviceId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "device.slot.unbind": {
        "context_required": ["deviceId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "device.slot.unbind_and_clear_mac": {
        "context_required": ["deviceId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "device.relation.list_devices": {
        "context_required": [],
        "payload_required": ["resType", "resId"],
        "payload_properties": {
            "resType": string_field("资源类型", True),
            "resId": string_field("资源 ID", True),
        },
    },
    "device.attribute.update": {
        "context_required": ["deviceId"],
        "payload_required": ["nodeType", "attributes"],
        "payload_properties": {
            "nodeType": string_field("节点类型", True),
            "attributes": json_object_field("设备拓扑属性对象；按节点类型要求提交，MCP 不改写内部结构。", True, {"key": "value"}),
        },
    },
    "device_group.mesh_group.create": {
        "context_required": ["houseId", "roomId"],
        "payload_required": ["name", "deviceIds"],
        "payload_excluded": ["componentId"],
        "payload_properties": {
            "name": string_field("设备组名称，不能为空", True),
            "desc": string_field("设备组描述，可为空；后端字段名为 desc"),
            "icon": string_field("设备组图标，可为空"),
            "cid": string_field("组件 ID；v2 设备组必填，用于决定设备组支持的属性和动作能力；当前 MCP 运行路径仍是旧 meshgroup，建议调用方尽量传入"),
            "deviceIds": device_ids_field("初始设备 ID 列表；MCP 会转换为旧 meshgroup 接口的 details=[{deviceId: ...}]。", True),
        },
    },
    "device_group.mesh_group.get_detail": {
        "context_required": ["groupId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "device_group.mesh_group.update": {
        "context_required": ["groupId"],
        "payload_required": ["name"],
        "payload_properties": {
            "name": string_field("设备组名称，可为空；MCP 建议更新时明确传入", True),
            "desc": string_field("设备组描述，可为空；后端字段名为 desc"),
            "icon": string_field("设备组图标，可为空"),
            "roomId": string_field("房间 ID，可为空；传入时应属于同一家庭"),
        },
    },
    "device_group.mesh_group.delete": {
        "context_required": ["groupId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "device_group.member.update_devices": {
        "context_required": ["houseId", "groupId"],
        "payload_required": [],
        "payload_properties": {
            "deviceIds": device_ids_field("待添加的设备 ID 列表；便捷模式，MCP 会转换为 addDeviceList。"),
            "addDeviceList": device_group_member_field("待添加设备列表；每项至少包含 id。"),
            "removeDeviceList": device_group_member_field("待移除设备列表；每项至少包含 id。"),
        },
    },
    "gateway.core.list": {
        "context_required": ["houseId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "gateway.core.list_with_stats": {
        "context_required": ["houseId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "gateway.core.get_detail": {
        "context_required": ["houseId", "gatewayId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "gateway.core.create": {
        "context_required": ["houseId"],
        "payload_required": ["name"],
        "payload_properties": {
            "name": string_field("网关名称，不能为空", True),
            "desc": string_field("网关描述，可为空；后端字段名为 desc"),
            "pid": string_field("产品 ID；与 pcId 至少应提供一个，均为空时按默认网关品类处理"),
            "pcId": string_field("产品品类 ID；与 pid 至少应提供一个，均为空时按默认网关品类处理"),
            "icon": string_field("网关图标，可为空"),
            "mac": string_field("网关 MAC，可为空"),
        },
    },
    "gateway.core.update": {
        "context_required": ["houseId", "gatewayId"],
        "payload_required": ["name"],
        "payload_properties": {
            "name": string_field("网关名称，可为空；MCP 建议更新时明确传入", True),
            "desc": string_field("网关描述，可为空；后端字段名为 desc"),
            "icon": string_field("网关图标，可为空"),
            "mac": string_field("网关 MAC，可为空"),
            "roomIds": id_list_field("网关关联的房间 ID 集合；传入时应为同一家庭下的房间", "房间 ID"),
        },
    },
    "gateway.core.delete": {
        "context_required": ["houseId", "gatewayId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "gateway.thread.get_info": {
        "context_required": ["houseId", "gatewayId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "favorite.core.list_all": {
        "context_required": ["houseId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "favorite.core.batch_insert": {
        "context_required": ["houseId"],
        "payload_required": ["items"],
        "payload_properties": {
            "items": favorite_items_field("收藏项列表；最终发送数组 body，MCP 会补 houseId 并可将 resType 转 typeId。", True),
        },
    },
    "favorite.core.batch_update": {
        "context_required": ["houseId"],
        "payload_required": ["items"],
        "payload_properties": {
            "items": favorite_items_field("收藏项更新列表；最终发送数组 body，MCP 会补 houseId 并可将 resType 转 typeId。", True),
        },
    },
    "favorite.core.batch_delete": {
        "context_required": ["houseId"],
        "payload_required": ["items"],
        "payload_properties": {
            "items": favorite_items_field("待删除收藏项列表；最终发送数组 body，MCP 会补 houseId 并可将 resType 转 typeId。", True),
        },
    },
    "scene.sort.add": {
        "context_required": ["houseId"],
        "payload_required": ["type", "target", "items"],
        "payload_properties": {
            "type": string_field("排序类型", True),
            "target": string_field("排序目标", True),
            "items": sort_items_field(True),
        },
    },
    "scene.sort.list_room_scene": {
        "context_required": ["houseId", "roomId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "thing_schema.house_snapshot.get_house": {
        "context_required": ["houseId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "thing_schema.house_snapshot.list_device": {
        "context_required": ["houseId"],
        "payload_required": ["pageNo", "pageSize"],
        "payload_properties": {
            "pageNo": integer_field("页码", True),
            "pageSize": integer_field("每页数量", True),
        },
    },
    "thing_schema.house_snapshot.list_room": {
        "context_required": ["houseId"],
        "payload_required": ["pageNo", "pageSize"],
        "payload_properties": {
            "pageNo": integer_field("页码", True),
            "pageSize": integer_field("每页数量", True),
        },
    },
    "thing_schema.house_snapshot.list_group": {
        "context_required": ["houseId"],
        "payload_required": ["pageNo", "pageSize"],
        "payload_properties": {
            "pageNo": integer_field("页码", True),
            "pageSize": integer_field("每页数量", True),
        },
    },
    "thing_schema.house_snapshot.list_gateway": {
        "context_required": ["houseId"],
        "payload_required": ["pageNo", "pageSize"],
        "payload_properties": {
            "pageNo": integer_field("页码", True),
            "pageSize": integer_field("每页数量", True),
        },
    },
    "thing_schema.house_snapshot.list_scene": {
        "context_required": ["houseId"],
        "payload_required": ["pageNo", "pageSize"],
        "payload_properties": {
            "pageNo": integer_field("页码", True),
            "pageSize": integer_field("每页数量", True),
        },
    },
    "thing_schema.house_snapshot.list_automation": {
        "context_required": ["houseId"],
        "payload_required": ["pageNo", "pageSize"],
        "payload_properties": {
            "pageNo": integer_field("页码", True),
            "pageSize": integer_field("每页数量", True),
        },
    },
    "device.screen.pre_bind": {
        "context_required": ["houseId", "roomId"],
        "payload_required": ["deviceId"],
        "payload_properties": {
            "deviceId": string_field("Wi-Fi 屏设备 ID", True),
            "source": string_field("配网来源"),
        },
    },
    "matter.pairing_code.apply": {
        "context_required": ["houseId", "roomId"],
        "payload_required": ["manualCode"],
        "payload_properties": {
            "manualCode": string_field("Matter 手动配对码", True),
            "qrCode": string_field("Matter 二维码"),
        },
    },
    "matter.secondary_pairing.apply": {
        "context_required": ["houseId", "nodeId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "matter.secondary_pairing.get_progress": {
        "context_required": ["houseId", "nodeId"],
        "payload_required": [],
        "payload_properties": {
            "timeout": integer_field("轮询超时时间，单位秒"),
        },
    },
    "matter.secondary_pairing.cancel": {
        "context_required": ["houseId", "nodeId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "scene.management.list": {
        "context_required": ["houseId"],
        "payload_required": [],
        "payload_properties": {
            "roomId": string_field("房间 ID"),
        },
    },
    "scene.management.list_all": {
        "context_required": ["houseId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "scene.management.get_detail": {
        "context_required": ["sceneId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "scene.management.create": {
        "context_required": ["houseId"],
        "payload_required": ["name", "actions"],
        "payload_properties": {
            "name": string_field("情景名称", True),
            "desc": string_field("情景描述，可为空；后端字段名为 desc"),
            "icon": string_field("情景图标，可为空"),
            "actions": scene_actions_field("情景动作列表；MCP 会转换为后端 details，并序列化每个动作的 params。建议非空。", True),
        },
    },
    "scene.management.update": {
        "context_required": ["houseId", "sceneId"],
        "payload_required": ["name", "actions"],
        "payload_properties": {
            "name": string_field("情景名称，可为空；MCP 建议更新时明确传入", True),
            "desc": string_field("情景描述，可为空；后端字段名为 desc"),
            "icon": string_field("情景图标，可为空"),
            "actions": scene_actions_field("情景动作列表；MCP 会转换为后端 details，并序列化每个动作的 params；传入时表示更新后的动作列表。", True),
        },
    },
    "scene.management.delete": {
        "context_required": ["sceneId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "scene.management.test": {
        "context_required": ["houseId"],
        "payload_required": ["actions"],
        "payload_properties": {
            "actions": scene_actions_field("待测试情景动作列表；MCP 会转换为后端 details，并序列化每个动作的 params。", True),
            "name": string_field("情景名称，可选"),
            "desc": string_field("情景描述，可选；后端字段名为 desc"),
            "icon": string_field("情景图标，可选"),
            "addToFav": string_field("是否加入收藏"),
            "gatewayDeviceId": string_field("网关设备 ID"),
            "img": string_field("情景图片"),
            "valid": integer_field("是否有效"),
        },
    },
    "scene.search.fuzzy": {
        "context_required": ["houseId"],
        "payload_required": ["fuzzyName"],
        "payload_properties": {
            "fuzzyName": string_field("情景模糊搜索关键词", True),
        },
    },
    "upgrade.app.get_latest": {
        "context_required": [],
        "payload_required": ["type", "osType"],
        "payload_properties": {
            "type": integer_field("APP 类型，1 用户版，2 师傅版，3 TV", True),
            "osType": integer_field("系统类型，1 Android，2 iOS", True),
            "uid": integer_field("用户 ID"),
            "languageCode": string_field("语言编码"),
        },
    },
    "upgrade.device_stat.get_electricity": {
        "context_required": [],
        "payload_required": ["deviceIds", "startTime", "endTime"],
        "payload_properties": {
            "deviceIds": array_field("设备 ID 列表", True),
            "startTime": string_field("开始时间", True),
            "endTime": string_field("结束时间", True),
        },
    },
    "upgrade.ptx.list_devices": {
        "context_required": [],
        "payload_required": ["key", "theDl"],
        "payload_properties": {
            "key": string_field("网关编码", True),
            "theDl": integer_field("设备类型，1 空调，2 新风，3 地暖", True),
        },
    },
    "upgrade.ptx.list_ota_updates": {
        "context_required": [],
        "payload_required": ["deviceIds"],
        "payload_properties": {
            "deviceIds": array_field("设备 ID 列表", True),
        },
    },
    "account.user.get_info": {
        "context_required": [],
        "payload_required": [],
        "payload_properties": {},
    },
    "account.user.update_info": {
        "context_required": [],
        "payload_required": ["profile"],
        "payload_properties": {
            "profile": json_object_field("用户资料对象；按用户资料接口支持的键值提交，MCP 不改写内部结构。", True, {"nickname": "张三"}),
        },
    },
    "account.account.exists": {
        "context_required": [],
        "payload_required": ["targetUser"],
        "payload_properties": {
            "targetUser": string_field("账号标识", True),
        },
    },
    "account.scan_login.query_qrcode": {
        "context_required": [],
        "payload_required": ["device"],
        "payload_properties": {
            "device": string_field("扫码登录设备标识，通常为 DALI/Web 网关 MAC", True),
        },
    },
    "account.scan_login.check_qrcode": {
        "context_required": [],
        "payload_required": ["qrCodeId"],
        "payload_properties": {
            "qrCodeId": string_field("扫码登录二维码 ID", True),
        },
    },
    "account.scan_login.mark_scanned": {
        "context_required": [],
        "payload_required": ["qrCodeId"],
        "payload_properties": {
            "qrCodeId": string_field("扫码登录二维码 ID", True),
        },
    },
    "account.scan_login.confirm": {
        "context_required": [],
        "payload_required": ["qrCodeId"],
        "payload_properties": {
            "qrCodeId": string_field("扫码登录二维码 ID", True),
        },
    },
    "account.scan_login.login": {
        "context_required": [],
        "payload_required": ["qrCodeId"],
        "payload_properties": {
            "qrCodeId": string_field("扫码登录二维码 ID", True),
        },
    },
    "account.third_party_auth.generate_state": {
        "context_required": [],
        "payload_required": ["source"],
        "payload_properties": {
            "source": string_field("三方来源", True),
        },
    },
    "account.third_party_auth.login": {
        "context_required": [],
        "payload_required": ["source", "thirdPartyToken"],
        "payload_properties": {
            "source": string_field("三方来源", True),
            "thirdPartyToken": string_field("三方登录 token", True),
        },
    },
    "account.third_party_auth.bind": {
        "context_required": [],
        "payload_required": ["source", "thirdPartyToken"],
        "payload_properties": {
            "source": string_field("三方来源", True),
            "thirdPartyToken": string_field("三方绑定 token", True),
        },
    },
    "account.third_party_auth.list_bindings": {
        "context_required": [],
        "payload_required": [],
        "payload_properties": {},
    },
    "account.third_party_auth.unbind": {
        "context_required": [],
        "payload_required": ["source"],
        "payload_properties": {
            "source": string_field("三方来源", True),
        },
    },
    "location.area.search": {
        "context_required": [],
        "payload_required": ["keyword"],
        "payload_properties": {
            "keyword": string_field("国家城市搜索关键词", True),
        },
    },
    "location.area.list_children": {
        "context_required": [],
        "payload_required": ["parentId"],
        "payload_properties": {
            "parentId": string_field("上级区域 ID", True),
        },
    },
    "https://yeelight.com": {
        "context_required": [],
        "payload_required": [],
        "payload_properties": {
            "url": string_field("诊断 URL"),
        },
    },
    "ptx_ota_dynamic_file_url": {
        "context_required": [],
        "payload_required": ["url"],
        "payload_properties": {
            "url": string_field("动态 OTA 文件 URL", True),
        },
    },
    "realtime.lan_gateway.sync_nodes_groups": {
        "context_required": ["gatewayId"],
        "payload_required": [],
        "payload_properties": {
            "diagnosisType": string_field("诊断类型"),
        },
    },
    "sonos.group.discover_and_listen": {
        "context_required": [],
        "payload_required": [],
        "payload_properties": {
            "diagnosisType": string_field("诊断类型"),
        },
    },
    "panel.panel.get_detail": {
        "context_required": ["deviceId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "panel.button.get_info": {
        "context_required": ["deviceId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "panel.button.update_layout": {
        "context_required": ["deviceId"],
        "payload_required": [],
        "payload_properties": {
            "layout": panel_layout_field(False),
            "buttons": panel_layout_field(False),
        },
    },
    "panel.button_event.update": {
        "context_required": ["deviceId"],
        "payload_required": ["event"],
        "payload_properties": {
            "event": panel_event_field("单个按键动作配置；建议基于查询按键信息返回对象修改后提交。", True),
        },
    },
    "panel.button_event.batch_update": {
        "context_required": ["deviceId"],
        "payload_required": [],
        "payload_properties": {
            "events": panel_events_field(False),
            "buttonEvents": panel_events_field(False),
        },
    },
    "panel.button_event.reset": {
        "context_required": ["deviceId"],
        "payload_required": ["buttonEventId"],
        "payload_properties": {
            "buttonEventId": string_field("按键事件 ID", True),
        },
    },
    "knob.single.get_detail": {
        "context_required": ["deviceId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "knob.single.update": {
        "context_required": ["deviceId"],
        "payload_required": ["config"],
        "payload_properties": {
            "config": knob_config_field("单键旋钮完整配置；建议基于查询详情返回对象修改后提交。", True),
        },
    },
    "knob.single.reset": {
        "context_required": ["deviceId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "knob.multi.get_detail": {
        "context_required": ["deviceId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "knob.multi.update": {
        "context_required": ["deviceId"],
        "payload_required": ["config"],
        "payload_properties": {
            "config": knob_config_field("多键旋钮完整配置；建议基于查询详情返回对象修改后提交。", True),
        },
    },
    "knob.multi.reset": {
        "context_required": ["deviceId"],
        "payload_required": ["index"],
        "payload_properties": {
            "index": integer_field("多键旋钮按键序号", True),
        },
    },
    "device.storage.get": {
        "context_required": ["deviceId"],
        "payload_required": ["storageKey"],
        "payload_properties": {
            "storageKey": string_field("设备业务存储键", True),
            "storageValue": string_field("查询时可不传；写入接口使用该字段"),
        },
    },
    "device.storage.set": {
        "context_required": ["deviceId"],
        "payload_required": ["storageKey", "storageValue"],
        "payload_properties": {
            "storageKey": string_field("设备业务存储键", True),
            "storageValue": json_object_field("设备业务存储值；任意 JSON object，MCP 原样透传。", True, {"enabled": True}),
        },
    },
    "device.asset.upload_image": {
        "context_required": [],
        "payload_required": ["imageBytes"],
        "payload_properties": {
            "imageBytes": string_field("图片内容，建议使用 base64 编码；底层 /uploadPic 接口原生要求 multipart file，MCP 调用方应传可生成文件内容的 base64 字符串", True),
            "fileName": string_field("图片文件名；原生 multipart 字段名为 file"),
        },
    },
    "device.asset.delete_images": {
        "context_required": [],
        "payload_required": ["imageUrls"],
        "payload_properties": {
            "imageUrls": array_field("待删除图片 URL 列表", True),
        },
    },
    "device.asset.text_to_image": {
        "context_required": [],
        "payload_required": ["pid"],
        "payload_properties": {
            "pid": string_field("产品 ID", True),
            "texts": id_list_field("待生成图片的文字列表；每项不能为空，返回 key 为文字、value 为图片 base64", "文字"),
            "prompt": string_field("兼容旧入参：单条生成图片提示词；MCP 会转换为 texts=[prompt]"),
        },
    },
    "device.schema.get_by_pid": {
        "context_required": [],
        "payload_required": ["pid"],
        "payload_properties": {
            "pid": string_field("产品 ID", True),
        },
    },
    "ai.voice_product.list": {
        "context_required": [],
        "payload_required": [],
        "payload_properties": {},
    },
    "ai.control_node.list": {
        "context_required": ["houseId"],
        "payload_required": ["deviceIds"],
        "payload_properties": {
            "deviceIds": device_ids_field("语音服务屏设备 ID 列表；用于按屏设备过滤语音控制配置", True),
        },
    },
    "ai.control_node.update": {
        "context_required": ["houseId"],
        "payload_required": [],
        "payload_properties": {
            "controls": screen_voice_controls_field(False),
            "screenDeviceId": string_field("屏设备 ID；使用便捷 deviceIds/sceneIds 模式时必填"),
            "deviceIds": device_ids_field("便捷模式：可被语音控制的设备 ID 列表，MCP 会转换为 controls 项"),
            "sceneIds": id_list_field("便捷模式：可被语音控制的情景 ID 列表，MCP 会转换为 controls 项", "情景 ID"),
        },
    },
    "ai.name.recommend_device": {
        "context_required": [],
        "payload_required": ["deviceIds"],
        "payload_properties": {
            "deviceIds": device_ids_field("需要推荐名称的设备 ID 列表", True),
        },
    },
    "ai.name.recommend_scene": {
        "context_required": [],
        "payload_required": ["sceneIds"],
        "payload_properties": {
            "sceneIds": id_list_field("需要推荐名称的情景 ID 列表", "情景 ID", True),
        },
    },
    "ai.name.batch_update": {
        "context_required": ["houseId"],
        "payload_required": ["names"],
        "payload_properties": {
            "names": name_update_items_field(True),
        },
    },
    "ai.asr.get_temp_credential": {
        "context_required": [],
        "payload_required": [],
        "payload_properties": {},
    },
    "automation.capability.list": {
        "context_required": [],
        "payload_required": ["deviceId"],
        "payload_properties": {
            "deviceId": string_field("设备 ID", True),
        },
    },
    "automation.capability.list_v2": {
        "context_required": [],
        "payload_required": ["deviceId"],
        "payload_properties": {
            "deviceId": string_field("设备 ID", True),
            "pid": string_field("产品 ID"),
        },
    },
    "automation.rule.list": {
        "context_required": ["houseId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "automation.rule.page": {
        "context_required": ["houseId"],
        "payload_required": ["pageNo", "pageSize"],
        "payload_properties": {
            "pageNo": integer_field("页码", True),
            "pageSize": integer_field("每页数量", True),
        },
    },
    "automation.rule.create": {
        "context_required": ["houseId"],
        "payload_required": ["name", "startTime", "endTime", "repeatType", "params", "actions"],
        "payload_excluded": ["conditions", "version"],
        "payload_properties": {
            "name": string_field("自动化名称", True),
            "startTime": string_field("生效开始时间，建议 HH:mm:ss，例如 00:00:00", True),
            "endTime": string_field("生效结束时间，建议 HH:mm:ss，例如 23:59:59", True),
            "repeatType": integer_field("重复类型：1-仅一次，2-每天，3-工作日，4-自定义，5-周末，6-法定节假日，7-法定工作日；包含设备事件或设备状态条件时不能使用 1", True),
            "repeatValue": string_field("重复值，一周七天位图的十六进制字符串；2-每天通常传 0x7f，3-工作日传 0x3e，5-周末传 0x41，4-自定义按用户选择生成"),
            "params": automation_params_field(True),
            "actions": automation_actions_field("自动化行为列表，不能为空；单个自动化最多 200 个动作", True),
            "status": integer_field("状态：0-有效，1-已禁用；创建和更新通常不传，需要变更状态时优先调用启用/禁用 action"),
        },
    },
    "automation.rule.update": {
        "context_required": ["automationId"],
        "payload_required": ["name", "startTime", "endTime", "repeatType", "params", "actions"],
        "payload_excluded": ["conditions", "version"],
        "payload_properties": {
            "automationId": string_field("自动化 ID；建议放在 context 中，MCP 会用于路径参数", True),
            "name": string_field("自动化名称", True),
            "startTime": string_field("生效开始时间，建议 HH:mm:ss，例如 00:00:00", True),
            "endTime": string_field("生效结束时间，建议 HH:mm:ss，例如 23:59:59", True),
            "repeatType": integer_field("重复类型：1-仅一次，2-每天，3-工作日，4-自定义，5-周末，6-法定节假日，7-法定工作日；包含设备事件或设备状态条件时不能使用 1", True),
            "repeatValue": string_field("重复值，一周七天位图的十六进制字符串；2-每天通常传 0x7f，3-工作日传 0x3e，5-周末传 0x41，4-自定义按用户选择生成"),
            "params": automation_params_field(True),
            "actions": automation_actions_field("自动化行为列表，不能为空；单个自动化最多 200 个动作", True),
            "status": integer_field("状态：0-有效，1-已禁用；创建和更新通常不传，需要变更状态时优先调用启用/禁用 action"),
        },
    },
    "automation.rule.delete": {
        "context_required": ["automationId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "automation.rule.test": {
        "context_required": ["houseId"],
        "payload_required": ["actions"],
        "payload_excluded": ["conditions", "version"],
        "payload_properties": {
            "name": string_field("自动化名称"),
            "startTime": string_field("生效开始时间，建议 HH:mm:ss，例如 00:00:00"),
            "endTime": string_field("生效结束时间，建议 HH:mm:ss，例如 23:59:59"),
            "repeatType": integer_field("重复类型：1-仅一次，2-每天，3-工作日，4-自定义，5-周末，6-法定节假日，7-法定工作日"),
            "repeatValue": string_field("重复值，一周七天位图的十六进制字符串"),
            "params": automation_params_field(False, "测试动作主要要求 houseId 和非空 actions。"),
            "actions": automation_actions_field("待测试的自动化行为列表，不能为空", True),
        },
    },
    "automation.rule.enable": {
        "context_required": ["automationId"],
        "payload_required": [],
        "payload_properties": {},
    },
    "automation.rule.disable": {
        "context_required": ["automationId"],
        "payload_required": [],
        "payload_properties": {},
    },
}


def get_operation_schema(operations: List[str]) -> Dict[str, Any]:
    context_required = set()
    payload_required = set()
    payload_properties: Dict[str, Dict[str, Any]] = {}
    payload_excluded = set()
    matched = False

    for operation in operations:
        spec = OPERATION_SCHEMAS.get(operation)
        if not spec:
            continue
        matched = True
        context_required.update(spec.get("context_required", []))
        payload_required.update(spec.get("payload_required", []))
        payload_properties.update(spec.get("payload_properties", {}))
        payload_excluded.update(spec.get("payload_excluded", []))

    return {
        "matched": matched,
        "context_required": sorted(context_required),
        "payload_required": sorted(payload_required),
        "payload_properties": payload_properties,
        "payload_excluded": sorted(payload_excluded),
    }
