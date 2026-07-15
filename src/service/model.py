from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SideEffectLevel(str, Enum):
    S0 = "S0"
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"


class ExecutionMode(str, Enum):
    cloud_api = "cloud_api"
    cloud_api_with_polling = "cloud_api_with_polling"
    requires_qr_scan = "requires_qr_scan"
    requires_ble = "requires_ble"
    requires_lan = "requires_lan"
    requires_mobile_app = "requires_mobile_app"
    manual_assist = "manual_assist"


class InterfaceStatus(str, Enum):
    confirmed = "confirmed"
    candidate = "candidate"
    external = "external"
    non_rest = "non_rest"


class TaskContext(BaseModel):
    houseId: Optional[str] = Field(None, description="家庭 ID")
    roomId: Optional[str] = Field(None, description="房间 ID")
    deviceId: Optional[str] = Field(None, description="设备 ID")
    nodeId: Optional[str] = Field(None, description="节点 ID")
    userId: Optional[str] = Field(None, description="用户 ID")
    runtimeEnv: Optional[str] = Field(None, description="调用方运行环境，例如 local/test/prod")

    model_config = ConfigDict(extra="allow")


class ExecuteOptions(BaseModel):
    dryRun: bool = Field(True, description="是否只返回执行计划，不调用底层接口")
    confirmSideEffect: bool = Field(False, description="是否确认 S2/S3 副作用")
    allowCandidate: bool = Field(False, description="是否允许执行 candidate action")
    reason: Optional[str] = Field(None, description="执行原因，建议 S2/S3 操作填写")

    model_config = ConfigDict(extra="allow")


class TaskExecutionRequest(BaseModel):
    task: str = Field(..., description="任务 ID，例如 family_space.manage_room")
    action: str = Field(..., description="动作 ID，例如 create/list/delete")
    context: TaskContext = Field(default_factory=TaskContext, description="执行上下文")
    payload: Dict[str, Any] = Field(default_factory=dict, description="动作入参")
    options: ExecuteOptions = Field(default_factory=ExecuteOptions, description="执行选项")


class ValidationRequest(BaseModel):
    task: str = Field(..., description="任务 ID")
    action: str = Field(..., description="动作 ID")
    context: TaskContext = Field(default_factory=TaskContext, description="执行上下文")
    payload: Dict[str, Any] = Field(default_factory=dict, description="动作入参")
    options: ExecuteOptions = Field(default_factory=ExecuteOptions, description="执行选项")


class InterfaceRef(BaseModel):
    ref: str = Field(..., description="任务地图中的接口引用")
    status: InterfaceStatus = Field(..., description="接口确认状态")
    operation: str = Field(..., description="domain.resource.action 操作名")
    method: Optional[str] = Field(None, description="HTTP 方法")
    path: Optional[str] = Field(None, description="文档路径")
    runtimePath: Optional[str] = Field(None, description="运行时路径")
    title: Optional[str] = Field(None, description="接口说明")
    sourceType: Optional[str] = Field(None, description="来源类型")
    yapiStatus: Optional[str] = Field(None, description="YApi 命中状态")


class ActionSchema(BaseModel):
    contextRequired: List[str] = Field(default_factory=list, description="必填上下文字段")
    payloadRequired: List[str] = Field(default_factory=list, description="必填 payload 字段")
    payloadProperties: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="payload 字段说明")
    optionHints: Dict[str, Any] = Field(default_factory=dict, description="执行选项提示")


class TaskAction(BaseModel):
    id: str = Field(..., description="动作 ID")
    title: str = Field(..., description="动作名称")
    description: str = Field(..., description="动作说明")
    executionMode: ExecutionMode = Field(..., description="执行模式")
    sideEffect: SideEffectLevel = Field(..., description="真实副作用等级")
    status: InterfaceStatus = Field(..., description="默认执行确认状态")
    interfaceRefs: List[InterfaceRef] = Field(default_factory=list, description="底层接口映射")
    parameterSchema: ActionSchema = Field(default_factory=ActionSchema, description="动作参数 schema")
    directExecutionSupported: bool = Field(True, description="是否支持 MCP 直接执行")


class TaskCard(BaseModel):
    id: str = Field(..., description="任务 ID")
    group: str = Field(..., description="分组 ID")
    title: str = Field(..., description="任务标题")
    summary: str = Field(..., description="任务摘要")
    userPhrases: List[str] = Field(default_factory=list, description="常见说法")
    priority: str = Field(..., description="优先级")
    maxSideEffect: SideEffectLevel = Field(..., description="任务最高风险等级")
    requiredContext: List[str] = Field(default_factory=list, description="原始必要上下文")
    commonInputs: List[str] = Field(default_factory=list, description="原始常见入参")
    interfaceRefs: List[str] = Field(default_factory=list, description="原始接口引用")
    actions: List[TaskAction] = Field(default_factory=list, description="动作列表")


class TaskGroup(BaseModel):
    id: str = Field(..., description="分组 ID")
    title: str = Field(..., description="分组标题")
    summary: str = Field(..., description="分组摘要")
    tasks: List[Dict[str, Any]] = Field(default_factory=list, description="分组下任务摘要")


class ValidationResult(BaseModel):
    valid: bool = Field(..., description="是否校验通过")
    errors: List[str] = Field(default_factory=list, description="错误列表")
    warnings: List[str] = Field(default_factory=list, description="警告列表")
    task: Optional[str] = Field(None, description="任务 ID")
    action: Optional[str] = Field(None, description="动作 ID")
    sideEffect: Optional[SideEffectLevel] = Field(None, description="动作副作用等级")
    executionMode: Optional[ExecutionMode] = Field(None, description="动作执行模式")
    status: Optional[InterfaceStatus] = Field(None, description="动作确认状态")
    code: str = Field("OK", description="校验结果代码")


class ExecutionPlan(BaseModel):
    task: str = Field(..., description="任务 ID")
    action: str = Field(..., description="动作 ID")
    dryRun: bool = Field(..., description="是否 dryRun")
    sideEffect: SideEffectLevel = Field(..., description="动作副作用等级")
    executionMode: ExecutionMode = Field(..., description="执行模式")
    status: InterfaceStatus = Field(..., description="动作确认状态")
    directExecutionSupported: bool = Field(..., description="是否支持直接执行")
    interfaces: List[InterfaceRef] = Field(default_factory=list, description="计划调用接口")
    context: Dict[str, Any] = Field(default_factory=dict, description="执行上下文")
    payload: Dict[str, Any] = Field(default_factory=dict, description="执行入参")
    httpRequest: Optional[Dict[str, Any]] = Field(None, description="单接口动作的 HTTP 请求预览")
    guidance: List[str] = Field(default_factory=list, description="执行指引，说明扫码、轮询、移动端等要求")


class ExecutionResult(BaseModel):
    ok: bool = Field(..., description="是否成功")
    dryRun: bool = Field(..., description="是否 dryRun")
    code: str = Field("OK", description="结果代码")
    plan: ExecutionPlan = Field(..., description="执行计划")
    validation: ValidationResult = Field(..., description="校验结果")
    response: Optional[Any] = Field(None, description="底层接口响应")
    normalizedResponse: Optional[Dict[str, Any]] = Field(None, description="归一化后的响应")
    message: Optional[str] = Field(None, description="结果说明")
