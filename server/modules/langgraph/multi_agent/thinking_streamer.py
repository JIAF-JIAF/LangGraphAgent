"""
LLM 思考过程流式输出器

单一职责：封装 llm.stream() / agent.astream() → 逐 token 推送 STEP_THINKING 事件。
节点只需将 llm.invoke() 替换为 ThinkingStreamer 的方法调用，即可获得思考过程实时输出。

设计原则（LangGraph 原生方案）：
  - 内部通过 get_stream_writer() 获取 writer，业务层无需传递
  - 无活跃 SSE 连接时 writer 为 no-op，不影响非流式场景
  - 业务层（Detector/Recognizer/Node）完全不感知流式/同步差异

使用方式：
    # 1. LLM 直接调用
    result = ThinkingStreamer.stream_llm(llm, messages, step_meta)

    # 2. Agent 调用
    result = ThinkingStreamer.stream_agent(agent, input_text, context, step_meta)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from langchain_core.messages import HumanMessage
from langgraph.config import get_stream_writer

from modules.logger import log
from modules.sse.events import StepStatus


# ===== 统一流式事件协议 =====

class StreamEventType(str, Enum):
    """Agent astream 事件类型"""
    TEXT = "text"              # LLM 生成的文本 token
    TOOL_CALL = "tool_call"   # 工具调用开始
    TOOL_RESULT = "tool_result"  # 工具调用结果
    DONE = "done"             # 执行结束


@dataclass
class StreamEvent:
    """
    Agent astream 统一输出格式

    所有实现 astream 的 Agent 必须 yield 此类型，
    ThinkingStreamer 无需做格式判断，直接读取 token 字段即可。
    """
    token: str                                  # 文本内容（TEXT 时为 token，TOOL_CALL/RESULT 时为描述）
    event_type: StreamEventType = StreamEventType.TEXT
    metadata: dict = field(default_factory=dict)  # 可选附加信息（如工具名、调用耗时等）


class ThinkingStreamer:
    """
    LLM 思考过程流式输出器

    将 LLM 的 stream() 输出逐 token 通过 writer 推送为 STEP_THINKING 事件，
    同时收集完整响应供节点后续使用。
    """

    @staticmethod
    def _push(step: Any, status: str, detail: str) -> None:
        """推送事件，内部通过 get_stream_writer() 获取 writer"""
        writer = get_stream_writer()
        writer({
            "step": _get_step_name(step),
            "status": status,
            "label": _get_step_label(step),
            "icon": _get_step_icon(step),
            "detail": detail,
        })

    @staticmethod
    def _push_thinking(step: Any, token: str) -> None:
        """推送 THINKING 事件（最频繁的操作，单独提取）"""
        ThinkingStreamer._push(step, StepStatus.THINKING, token)

    @staticmethod
    def stream_llm(
        llm: Any,
        messages: list,
        step: Any,
        detail_prefix: str = "",
    ) -> str:
        """
        流式调用 LLM，逐 token 推送思考过程

        内部通过 get_stream_writer() 获取 writer，业务层无需传递。
        无活跃 SSE 连接时 writer 为 no-op，不影响非流式场景。

        Args:
            llm: LangChain ChatOpenAI 实例（需支持 stream()）
            messages: 消息列表（str 或 BaseMessage 列表）
            step: Step 枚举或 ExpertMeta 实例（需有 step/name, label, icon 属性）
            detail_prefix: 思考内容前缀（可选，如 "情绪分析："）

        Returns:
            完整 LLM 响应文本
        """
        full_response = ""

        if isinstance(messages, str):
            messages = [HumanMessage(content=messages)]

        try:
            for chunk in llm.stream(messages):
                token = chunk.content if hasattr(chunk, 'content') else str(chunk)
                if token:
                    full_response += token
                    ThinkingStreamer._push_thinking(step, token)
        except Exception as e:
            log(f"[ThinkingStreamer] LLM 流式调用失败: {e}，回退到 invoke", "ThinkingStreamer")
            try:
                response = llm.invoke(messages)
                full_response = response.content if hasattr(response, 'content') else str(response)
            except Exception as invoke_err:
                log(f"[ThinkingStreamer] LLM invoke 也失败: {invoke_err}", "ThinkingStreamer")
                raise

        return full_response

    @staticmethod
    def stream_llm_structured(
        llm: Any,
        messages: list,
    ) -> str:
        """
        流式调用 LLM 收集结构化输出（JSON），不推送 THINKING 事件

        适用于 FeelingDetector / IntentRecognizer 等输出为 JSON 的场景。
        用户不需要看到原始 JSON，节点层的 PROGRESS + COMPLETED 事件已提供足够反馈。

        Args:
            llm: LangChain ChatOpenAI 实例（需支持 stream()）
            messages: 消息列表（str 或 BaseMessage 列表）

        Returns:
            完整 LLM 响应文本
        """
        full_response = ""

        if isinstance(messages, str):
            messages = [HumanMessage(content=messages)]

        try:
            for chunk in llm.stream(messages):
                token = chunk.content if hasattr(chunk, 'content') else str(chunk)
                if token:
                    full_response += token
        except Exception as e:
            log(f"[ThinkingStreamer] LLM 流式调用失败: {e}，回退到 invoke", "ThinkingStreamer")
            try:
                response = llm.invoke(messages)
                full_response = response.content if hasattr(response, 'content') else str(response)
            except Exception as invoke_err:
                log(f"[ThinkingStreamer] LLM invoke 也失败: {invoke_err}", "ThinkingStreamer")
                raise

        return full_response

    @staticmethod
    def stream_llm_with_progress(
        llm: Any,
        messages: list,
        step: Any,
        progress_detail: str = "",
        detail_prefix: str = "",
    ) -> str:
        """
        流式调用 LLM，先推送 progress 事件，再逐 token 推送思考过程

        Args:
            llm: LangChain ChatOpenAI 实例
            messages: 消息列表
            step: Step 枚举或 ExpertMeta 实例
            progress_detail: 开始思考前的进度提示（可选）
            detail_prefix: 思考内容前缀（可选）

        Returns:
            完整 LLM 响应文本
        """
        if progress_detail:
            ThinkingStreamer._push(step, StepStatus.PROGRESS, progress_detail)

        return ThinkingStreamer.stream_llm(llm, messages, step, detail_prefix)

    @staticmethod
    def stream_agent(
        agent: Any,
        input_text: str,
        context: Any,
        step: Any,
    ) -> str:
        """
        调用 Agent 并推送思考过程

        优先使用 astream 逐 token 推送；若 Agent 未实现 astream，回退到 invoke。

        Args:
            agent: Agent 实例（需实现 invoke 或 astream 方法）
            input_text: 输入文本
            context: AgentContext 实例
            step: Step 枚举或 ExpertMeta 实例

        Returns:
            Agent 回答文本
        """
        if hasattr(agent, 'astream'):
            return ThinkingStreamer._stream_agent_async(agent, input_text, context, step)

        # 回退到同步调用（Agent 未实现 astream）
        # 不推送完整回答作为 THINKING：回答是最终结果，由 merge 节点输出
        try:
            result = agent.invoke(input_text, context)
            answer = result.get("answer", "") if isinstance(result, dict) else str(result)
            return answer
        except Exception as e:
            log(f"[ThinkingStreamer] Agent 调用失败: {e}", "ThinkingStreamer")
            return f"执行过程中出现异常：{str(e)[:100]}，请稍后重试。"

    @staticmethod
    def _stream_agent_async(
        agent: Any,
        input_text: str,
        context: Any,
        step: Any,
    ) -> str:
        """
        Agent astream 流式调用，逐 token 推送思考过程

        Agent 必须实现 astream 方法，yield StreamEvent 实例。
        """
        full_response = ""
        try:
            for event in agent.astream(input_text, context):
                if isinstance(event, StreamEvent):
                    token = event.token
                    if token and event.event_type == StreamEventType.TEXT:
                        full_response += token
                        ThinkingStreamer._push_thinking(step, token)
                else:
                    log(f"[ThinkingStreamer] Agent astream 返回非 StreamEvent 类型: {type(event)}", "ThinkingStreamer")
        except Exception as e:
            log(f"[ThinkingStreamer] Agent astream 失败: {e}，回退到 invoke", "ThinkingStreamer")
            result = agent.invoke(input_text, context)
            full_response = result.get("answer", "") if isinstance(result, dict) else str(result)

        return full_response


# ===== 工具函数 =====

def _get_step_name(step: Any) -> str:
    """获取步骤名称，兼容 Step 枚举和 ExpertMeta"""
    if hasattr(step, 'step'):
        return step.step
    if hasattr(step, 'name'):
        return step.name
    return str(step)


def _get_step_label(step: Any) -> str:
    """获取步骤标签，兼容 Step 枚举和 ExpertMeta"""
    if hasattr(step, 'label'):
        return step.label
    if hasattr(step, 'name'):
        return step.name
    return str(step)


def _get_step_icon(step: Any) -> str:
    """获取步骤图标，兼容 Step 枚举和 ExpertMeta"""
    if hasattr(step, 'icon'):
        return step.icon
    return "💭"
