"""
AG-UI (Agent-User Interaction) 协议事件类型定义

对齐 AG-UI 协议标准，统一管理所有 SSE 事件类型，
避免字符串硬编码散落各处，防止拼写错误。
"""

from enum import Enum


class EventType(str, Enum):
    """
    AG-UI 事件类型枚举

    继承 str 使枚举值可直接作为字符串使用（JSON 序列化、字典 key 等），
    无需手动调用 .value。
    """

    STEP_STARTED = "STEP_STARTED"
    STEP_PROGRESS = "STEP_PROGRESS"
    STEP_FINISHED = "STEP_FINISHED"
    TEXT_MESSAGE_CONTENT = "TEXT_MESSAGE_CONTENT"
    RUN_FINISHED = "RUN_FINISHED"
    RUN_ERROR = "RUN_ERROR"


class StepStatus(str, Enum):
    """
    步骤状态枚举

    用于节点内部 get_stream_writer 推送自定义事件时的 status 字段。
    """

    STARTED = "started"
    PROGRESS = "progress"
    COMPLETED = "completed"
