"""
Supervisor 路由节点

替代旧 intent_router 的三选一路由，改为按意图类别细粒度分发。

路由策略（最重意图优先，由 SUPERVISOR_ROUTE_TABLE 声明式定义）：
  1. 无意图 → chat_expert（兜底对话）
  2. 有复杂意图 → router（规划路径可处理所有意图）
  3. 有可执行意图 → execute_direct（按序执行）
  4. 仅对话意图 → chat_expert

核心原则：router（规划路径）能处理所有意图（简单意图变成子任务），
但 execute_direct 无法处理复杂意图。因此复杂意图优先级最高。

Phase 2 后，execute_direct/router 将被 rag_expert/skill_expert/mcp_expert/planner_expert 替代。
Phase 3 后，多意图通过 Send API 并行分发到多个 Agent。
"""

from typing import Dict, Any
from langgraph.config import get_stream_writer
from langgraph.types import Command
from modules.logger import log
from modules.intent import classify_intents, resolve_route, SUPERVISOR_ROUTE_TABLE
from modules.langgraph.nodes.steps import Step


def supervisor_node(state: Dict[str, Any]) -> Command:
    """
    Supervisor 路由节点

    根据意图类别决定分发到哪个 Agent 或旧路径节点。
    返回 Command(goto=...) 由 LangGraph 自动处理路由。

    路由优先级由 SUPERVISOR_ROUTE_TABLE 声明，resolve_route 按表顺序匹配。

    Args:
        state: 当前状态（包含 intents, feeling 等）

    Returns:
        Command 对象，指定下一个要执行的节点
    """
    writer = get_stream_writer()
    intents = state.get("intents", [])

    writer(Step.SUPERVISOR.started_event())

    if not intents:
        writer(Step.SUPERVISOR.completed_event(detail="→ chat_expert (无意图)"))
        log("[Supervisor] 路由决策: → chat_expert (无意图)", "MultiAgent")
        return Command(goto="chat_expert")

    info = classify_intents(intents)
    target, detail = resolve_route(info, SUPERVISOR_ROUTE_TABLE, fallback="chat_expert", fallback_label="无匹配规则")

    writer(Step.SUPERVISOR.completed_event(detail=f"→ {target} ({detail})"))
    log(f"[Supervisor] 路由决策: → {target} ({detail})", "MultiAgent")
    return Command(goto=target)
