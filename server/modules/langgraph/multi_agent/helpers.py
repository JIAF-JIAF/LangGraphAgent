"""
Expert 插件公共工具函数

插件按需 import 使用，不强制继承。
每个函数都是纯函数或简单工具，插件可以自由组合、替换、忽略。
"""

from typing import Dict, Any, List, Optional
from langchain_core.tools import BaseTool
from langgraph.config import get_stream_writer

from modules.logger import log
from modules.context import AgentContext
from modules.langgraph.context_builder import ContextBuilder
from modules.langgraph.multi_agent.meta import ExpertMeta


# ===== 意图过滤 =====

def filter_intents_by_category(intents: List[Dict], category: str) -> List[Dict]:
    """
    按 category 过滤意图

    Args:
        intents: 意图列表（Planner 分解结果）
        category: 目标类别（如 "mcp"、"skill"、"rag"）

    Returns:
        过滤后的意图列表
    """
    if not intents:
        return []

    return [i for i in intents if i.get("category") == category]


# ===== 输入构建 =====

def build_hints_input(
    query: str,
    intents: List[Dict],
    target_prefix: str = "",
    single_hint: str = "",
    multi_hint: str = "",
) -> str:
    """
    基于 hint 模板构建 Agent 输入

    Args:
        query: 原始查询
        intents: 当前 Expert 的意图列表
        target_prefix: target 前缀（如 "mcp:"、"skill:"）
        single_hint: 单意图模板，支持 {target} 占位符
        multi_hint: 多意图前缀

    Returns:
        构建后的输入文本
    """
    if not intents:
        return query

    # 单意图：直接指令，LLM 注意力聚焦
    if len(intents) == 1:
        target = intents[0].get("target", "").replace(target_prefix, "")
        content = intents[0].get("content", "") or query
        hint = single_hint.format(target=target) if target and single_hint else ""
        return f"{hint}\n{content}" if hint else content

    # 多意图：编号列表，LLM 依次处理
    lines = [multi_hint] if multi_hint else []
    for i, intent in enumerate(intents, 1):
        target = intent.get("target", "").replace(target_prefix, "")
        content = intent.get("content", "")
        line = f"  {i}. [{target}] {content}" if target else f"  {i}. {content}"
        lines.append(line)
    return "\n".join(lines)


# ===== Agent 上下文 =====

def build_base_context(state: Dict[str, Any], **extra) -> AgentContext:
    """
    构建基础 AgentContext

    Args:
        state: LangGraph 状态
        **extra: 额外字段（如 skill_name="xxx"）

    Returns:
        AgentContext 实例
    """
    return AgentContext(
        session_id=state.get("session_id", "default"),
        chat_history=state.get("chat_history", []),
        feeling=state.get("feeling", {}),
        **extra,
    )


# ===== Agent 调用 =====

def invoke_agent_safely(agent, input_text: str, context: AgentContext) -> str:
    """
    安全调用 Agent，返回 answer 或错误提示

    Args:
        agent: Agent 实例（需实现 invoke 方法）
        input_text: 输入文本
        context: 执行上下文

    Returns:
        Agent 回答文本
    """
    try:
        result = agent.invoke(input_text, context)
        return result.get("answer", "")
    except Exception as e:
        return handle_agent_error(e)


def handle_agent_error(error: Exception) -> str:
    """
    处理 Agent 调用异常

    识别内容安全审查异常，其他返回通用错误。
    """
    error_msg = str(error)
    if "DataInspectionFailed" in error_msg or "inappropriate content" in error_msg.lower():
        return "抱歉，该操作触发了平台内容安全审查，暂无法处理，请尝试其他请求。"
    return f"执行过程中出现异常：{error_msg[:100]}，请稍后重试。"


# ===== 结果构建 =====

def build_intent_results(
    intents: List[Dict],
    answer: str,
    category: str,
) -> List[Dict[str, Any]]:
    """
    构建意图执行结果列表

    Args:
        intents: 意图列表
        answer: Agent 回答
        category: 意图类别

    Returns:
        意图结果列表，每个元素包含 type/target/content/success
    """
    return [
        {"type": category, "target": i.get("target", ""), "content": answer, "success": True}
        for i in intents
    ]


def build_agent_result(
    agent_name: str,
    answer: str,
    intent_results: Optional[List[Dict]] = None,
    subtask_idx: Optional[int] = None,
    chat_history: Optional[list] = None,
) -> Dict[str, Any]:
    """
    构建标准状态更新字典

    Args:
        agent_name: Expert 名称
        answer: 回答内容
        intent_results: 意图结果列表（可选）
        subtask_idx: Planner 调度标记（可选）
        chat_history: 对话历史增量（可选）

    Returns:
        状态更新字典
    """
    result_entry = {"agent": agent_name, "answer": answer}
    if intent_results is not None:
        result_entry["intent_results"] = intent_results
    if subtask_idx is not None:
        result_entry["subtask_idx"] = subtask_idx

    update = {"agent_results": [result_entry]}
    if subtask_idx is not None:
        update["__subtask_idx__"] = subtask_idx
    if chat_history is not None:
        update["chat_history"] = chat_history

    return update


# ===== SSE 事件 =====

def push_step_event(meta: ExpertMeta, status: str, detail: str = ""):
    """
    推送 SSE 步骤事件

    Args:
        meta: 插件元信息（包含 name/label/icon）
        status: 状态（"started" / "progress" / "completed" / "error"）
        detail: 详细信息（可选）
    """
    writer = get_stream_writer()
    event = {
        "step": meta.name,
        "status": status,
        "label": meta.label,
        "icon": meta.icon,
    }
    if detail:
        event["detail"] = detail
    writer(event)


def push_progress_event(meta: ExpertMeta, detail: str):
    """
    推送 SSE 中间进度事件

    Args:
        meta: 插件元信息（包含 name/label/icon）
        detail: 进度详情（必填）
    """
    writer = get_stream_writer()
    writer({
        "step": meta.name,
        "status": "progress",
        "label": meta.label,
        "icon": meta.icon,
        "detail": detail,
    })


# ===== 无工具提示 =====

def inject_no_tool_hint(query: str) -> str:
    """
    注入无工具提示（Chat 类插件使用）

    Args:
        query: 用户原始查询

    Returns:
        添加提示后的查询文本
    """
    return (
        f"[重要提示：此请求已确认无匹配的工具、技能或知识库，"
        f"请直接通过对话回答，不要调用任何工具。]\n\n"
        f"用户请求：{query}"
    )
