"""
思考步骤枚举定义

统一管理所有节点的步骤标识、显示名称和图标，
并提供事件生成方法，节点代码只需一行即可推送进度事件。
"""

from enum import Enum
from modules.sse.events import StepStatus


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
        self._step = step
        self._label = label
        self._icon = icon

    @property
    def step(self):
        return self._step

    @property
    def label(self):
        return self._label

    @property
    def icon(self):
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

    def completed_event(self, detail=""):
        """
        生成 STEP_COMPLETED 事件字典

        Args:
            detail: 完成详情

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
