"""
SSE 事件处理器
对齐 AG-UI (Agent-User Interaction) 协议标准事件类型

事件类型定义见 events.py
"""

from typing import Any

from .events import EventType, StepStatus


class SSEEventProcessor:
    """SSE 事件处理器：将 LangGraph 多流输出转换为 AG-UI 标准事件"""

    # StepStatus → EventType 映射，消除 if-elif 链
    _STATUS_TO_EVENT: dict[StepStatus, EventType] = {
        StepStatus.STARTED: EventType.STEP_STARTED,
        StepStatus.PROGRESS: EventType.STEP_PROGRESS,
        StepStatus.THINKING: EventType.STEP_THINKING,
        StepStatus.COMPLETED: EventType.STEP_FINISHED,
    }

    def __init__(self):
        self.final_answer = ""
        self.final_feeling = {"feeling": "default", "score": 5}

    def process(self, mode: str, chunk: Any, session_id: str) -> dict | None:
        """
        统一处理 LangGraph 多流输出，根据 mode 分发到对应内部方法

        Args:
            mode: 流模式，"updates" | "custom" | "messages"
            chunk: 对应模式的 chunk 数据
            session_id: 会话 ID

        Returns:
            AG-UI 标准事件数据字典，或 None（无需发送前端时）
        """
        if mode == "updates":
            return self._process_updates(chunk, session_id)
        elif mode == "custom":
            return self._process_custom(chunk, session_id)
        elif mode == "messages":
            return self._process_token(chunk, session_id)
        return None

    def _process_custom(self, custom_data: dict, session_id: str) -> dict | None:
        """
        处理 custom 流事件（来自 get_stream_writer）

        将节点内部推送的自定义进度事件转换为 AG-UI STEP_STARTED / STEP_PROGRESS / STEP_FINISHED 事件

        Args:
            custom_data: get_stream_writer 推送的事件字典
                - step: 步骤名称
                - status: StepStatus 枚举值
                - label: 步骤显示名称
                - icon: 步骤图标
                - detail: 步骤详情（可选）
            session_id: 会话 ID

        Returns:
            AG-UI 标准事件数据字典
        """
        step = custom_data.get("step", "unknown")
        status = custom_data.get("status", StepStatus.STARTED)
        event_type = self._STATUS_TO_EVENT.get(status)

        if event_type is None:
            return None

        return {
            "type": event_type,
            "step": step,
            "label": custom_data.get("label", step),
            "icon": custom_data.get("icon", "🔄"),
            "detail": custom_data.get("detail", ""),
            "session_id": session_id,
        }

    def _process_updates(self, updates_data: dict, session_id: str) -> dict | None:
        """
        处理 updates 流事件（节点完成后的状态增量）

        仅用于提取 feeling 等最终状态信息，不生成前端事件
        （思考步骤由 custom 流的 STEP_STARTED/STEP_FINISHED 驱动）

        Args:
            updates_data: {node_name: state_delta} 字典
            session_id: 会话 ID

        Returns:
            None（不生成前端事件，仅更新内部状态）
        """
        for node_name, state_delta in updates_data.items():
            if isinstance(state_delta, dict) and "feeling" in state_delta:
                self.final_feeling = state_delta["feeling"]

        return None

    # 只转发 merge 节点的 token（最终润色结果）
    # - 前置节点和调度节点：中间过程，不需要展示
    # - Expert 节点：结果会由 merge 节点统一润色后输出，避免重复
    # - 用户通过 STEP_STARTED 事件看到各 Expert 的执行进度
    _ALLOWED_TOKEN_NODES = frozenset({
        "merge",
    })

    def _process_token(self, chunk: tuple, session_id: str) -> dict | None:
        """
        处理 messages 流模式的 token 事件

        只转发 merge 节点的 token 输出（最终润色结果），
        其他节点的 LLM 输出一律忽略，避免重复。

        Args:
            chunk: (AIMessageChunk, metadata) 元组
            session_id: 会话 ID

        Returns:
            AG-UI TEXT_MESSAGE_CONTENT 事件，或 None
        """
        message_chunk, metadata = chunk
        content = message_chunk.content
        if not content:
            return None

        node_name = metadata.get("langgraph_node", "unknown")

        if node_name not in self._ALLOWED_TOKEN_NODES:
            return None

        self.final_answer += content

        return {
            "type": EventType.TEXT_MESSAGE_CONTENT,
            "content": content,
            "node": node_name,
            "session_id": session_id,
        }

    def get_done_event(self, session_id: str) -> dict:
        """
        生成 RUN_FINISHED 事件

        Args:
            session_id: 会话 ID

        Returns:
            AG-UI RUN_FINISHED 事件数据字典
        """
        return {
            "type": EventType.RUN_FINISHED,
            "session_id": session_id,
            "reply": self.final_answer,
            "feeling": self.final_feeling,
        }

    def get_error_event(self, error: str, session_id: str) -> dict:
        """
        生成 RUN_ERROR 事件

        Args:
            error: 错误信息
            session_id: 会话 ID

        Returns:
            AG-UI RUN_ERROR 事件数据字典
        """
        return {
            "type": EventType.RUN_ERROR,
            "error": error,
            "session_id": session_id,
        }
