"""
思考步骤枚举定义

统一管理所有节点的步骤标识、显示名称和图标，
并提供事件生成方法，节点代码只需一行即可推送进度事件。

支持动态 Step 注册：新增 Expert 插件可通过 register_step() 注册自定义步骤，
SSE 事件推送自动支持新步骤标识。
"""

from enum import Enum
from typing import Dict, Optional
from modules.sse.events import StepStatus


# 动态 Step 注册表（供插件使用）
_DYNAMIC_STEPS: Dict[str, "DynamicStep"] = {}


class DynamicStep:
    """
    动态步骤（供插件注册使用）

    与 Step 枚举成员接口一致，提供 started_event / completed_event 方法。
    """

    def __init__(self, step: str, label: str, icon: str):
        """
        初始化动态步骤

        Args:
            step: 步骤标识，如 "code_expert"
            label: 显示名称，如 "代码生成 Agent"
            icon: 图标，如 "💻"
        """
        self._step = step
        self._label = label
        self._icon = icon

    @property
    def step(self):
        """
        步骤标识

        Returns:
            步骤标识字符串，如 "code_expert"
        """
        return self._step

    @property
    def label(self):
        """
        显示名称

        Returns:
            步骤显示名称，如 "代码生成 Agent"
        """
        return self._label

    @property
    def icon(self):
        """
        步骤图标

        Returns:
            步骤图标字符串，如 "💻"
        """
        return self._icon

    def started_event(self, detail=""):
        """
        生成 STEP_STARTED 事件字典

        Args:
            detail: 可选详情，如 "分析用户输入：查询天气"

        Returns:
            供 get_stream_writer 推送的事件字典
        """
        event = {
            "step": self._step,
            "status": StepStatus.STARTED,
            "label": self._label,
            "icon": self._icon,
        }
        if detail:
            event["detail"] = detail
        return event

    def progress_event(self, detail=""):
        """
        生成 STEP_PROGRESS 事件字典（中间进度）

        Args:
            detail: 进度详情

        Returns:
            供 get_stream_writer 推送的事件字典
        """
        return {
            "step": self._step,
            "status": StepStatus.PROGRESS,
            "label": self._label,
            "icon": self._icon,
            "detail": detail,
        }

    def completed_event(self, detail=""):
        """
        生成 STEP_COMPLETED 事件字典

        Args:
            detail: 完成详情，如 "检测到情绪：positive，强度 7"

        Returns:
            供 get_stream_writer 推送的事件字典
        """
        return {
            "step": self._step,
            "status": StepStatus.COMPLETED,
            "label": self._label,
            "icon": self._icon,
            "detail": detail,
        }


def register_step(step_id: str, label: str, icon: str) -> DynamicStep:
    """
    注册动态 Step（供插件使用）

    Args:
        step_id: 步骤标识，如 "code_expert"
        label: 显示名称，如 "代码生成 Agent"
        icon: 图标，如 "💻"

    Returns:
        DynamicStep 实例
    """
    step = DynamicStep(step_id, label, icon)
    _DYNAMIC_STEPS[step_id] = step
    return step


def get_step(step_id: str) -> Optional[DynamicStep]:
    """
    获取 Step（优先查固定枚举，再查动态注册表）

    Args:
        step_id: 步骤标识

    Returns:
        Step 枚举成员或 DynamicStep 实例，不存在返回 None
    """
    # 枚举成员名查找
    if step_id in Step.__members__:
        return Step[step_id]
    # 动态注册表查找
    return _DYNAMIC_STEPS.get(step_id)


class Step(Enum):
    """
    思考步骤枚举

    每个成员封装 step（标识）、label（显示名称）、icon（图标），
    并提供 started_event() / completed_event() 方法直接生成 writer 字典。

    用法:
        writer(Step.FEELING_DETECT.started_event())
        writer(Step.FEELING_DETECT.completed_event(detail="积极"))
    """

    FEELING_DETECT = ("feeling_detect", "情绪分析", "😊")
    INTENT_RECOGNIZE = ("intent_recognize", "意图识别", "🎯")

    SUPERVISOR = ("supervisor", "Agent 调度", "🔀")
    RAG_EXPERT = ("rag_expert", "知识检索 Agent", "📚")
    SKILL_EXPERT = ("skill_expert", "技能执行 Agent", "🎨")
    MCP_EXPERT = ("mcp_expert", "工具调用 Agent", "🔧")
    CHAT_EXPERT = ("chat_expert", "对话 Agent", "💬")
    PLANNER_DECOMPOSE = ("planner_decompose", "任务分解", "📋")
    PLANNER_DISPATCH = ("planner_dispatch", "任务调度", "🔀")
    MERGE = ("merge", "结果整合", "🔗")

    def __init__(self, step, label, icon):
        """
        初始化枚举成员

        Args:
            step: 步骤标识，如 "feeling_detect"
            label: 显示名称，如 "情绪分析"
            icon: 图标，如 "😊"
        """
        self._step = step
        self._label = label
        self._icon = icon

    @property
    def step(self):
        """
        步骤标识

        Returns:
            步骤标识字符串，如 "feeling_detect"
        """
        return self._step

    @property
    def label(self):
        """
        显示名称

        Returns:
            步骤显示名称，如 "情绪分析"
        """
        return self._label

    @property
    def icon(self):
        """
        步骤图标

        Returns:
            步骤图标字符串，如 "😊"
        """
        return self._icon

    def started_event(self, detail=""):
        """
        生成 STEP_STARTED 事件字典

        Args:
            detail: 可选详情

        Returns:
            供 get_stream_writer 推送的事件字典
        """
        event = {
            "step": self._step,
            "status": StepStatus.STARTED,
            "label": self._label,
            "icon": self._icon,
        }
        if detail:
            event["detail"] = detail
        return event

    def progress_event(self, detail=""):
        """
        生成 STEP_PROGRESS 事件字典（中间进度）

        Args:
            detail: 进度详情，如 "检索知识库：product_docs"

        Returns:
            供 get_stream_writer 推送的事件字典
        """
        return {
            "step": self._step,
            "status": StepStatus.PROGRESS,
            "label": self._label,
            "icon": self._icon,
            "detail": detail,
        }

    def completed_event(self, detail=""):
        """
        生成 STEP_COMPLETED 事件字典

        Args:
            detail: 完成详情，如 "检测到情绪：positive，强度 7"

        Returns:
            供 get_stream_writer 推送的事件字典
        """
        return {
            "step": self._step,
            "status": StepStatus.COMPLETED,
            "label": self._label,
            "icon": self._icon,
            "detail": detail,
        }
