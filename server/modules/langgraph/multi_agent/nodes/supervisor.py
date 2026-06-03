"""
Supervisor 路由节点

负责流式事件推送和 agent_results 重置。实际路由逻辑在 graph.py 的 _route_from_supervisor 中，
通过 add_conditional_edges 实现（Send API 标准用法）。

路由策略（最重意图优先，由 SUPERVISOR_ROUTE_TABLE 声明式定义）：
  1. 无意图 → chat_expert（兜底对话）
  2. PLAN 意图 → planner_expert（Planner 通过委托工具编排跨领域子任务）
  3. 纯单类别意图 → 对应 Expert（mcp_expert / skill_expert / rag_expert）
  4. 混合可执行意图 → 多 Expert 并行（Send API）
  5. 对话意图 → chat_expert
"""

from typing import Dict, Any
from langgraph.config import get_stream_writer
from modules.langgraph.nodes.steps import Step


def supervisor_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Supervisor 路由节点

    负责流式事件推送和 agent_results 重置。
    实际路由决策和日志由 graph.py 的 _route_from_supervisor（add_conditional_edges）处理，
    此处不再重复打印路由日志。

    Args:
        state: 当前状态

    Returns:
        重置 agent_results 的状态更新字典
    """
    writer = get_stream_writer()
    writer(Step.SUPERVISOR.started_event())
    writer(Step.SUPERVISOR.completed_event(detail="routing"))
    return {"agent_results": None}
