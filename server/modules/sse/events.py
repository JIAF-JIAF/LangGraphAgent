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

    # 步骤开始，前端显示步骤图标+标签（如"😊 情绪分析 ..."）
    STEP_STARTED = "STEP_STARTED"
    # 步骤进行中，前端显示进度提示（如"正在调用模型..."）
    STEP_PROGRESS = "STEP_PROGRESS"
    # 思考过程，前端打字机效果逐 token 展示 LLM 输出
    STEP_THINKING = "STEP_THINKING"
    # 步骤完成，前端显示完成状态+摘要（如"✓ 检测到情绪：cheerful"）
    STEP_FINISHED = "STEP_FINISHED"
    # 最终回答内容，前端打字机输出正文
    TEXT_MESSAGE_CONTENT = "TEXT_MESSAGE_CONTENT"
    # 整轮对话结束
    RUN_FINISHED = "RUN_FINISHED"
    # 出错
    RUN_ERROR = "RUN_ERROR"


class StepStatus(str, Enum):
    """
    步骤状态枚举

    用于节点内部 get_stream_writer 推送自定义事件时的 status 字段。
    """

    # 步骤开始 → 映射为 STEP_STARTED
    STARTED = "started"
    # 步骤进行中 → 映射为 STEP_PROGRESS
    PROGRESS = "progress"
    # 思考过程 → 映射为 STEP_THINKING
    THINKING = "thinking"
    # 步骤完成 → 映射为 STEP_FINISHED
    COMPLETED = "completed"
