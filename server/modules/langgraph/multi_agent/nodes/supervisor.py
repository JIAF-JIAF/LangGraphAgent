"""
Supervisor 路由节点

负责流式事件推送和状态重置。实际路由逻辑在 graph.py 的 _route_from_supervisor 中，
通过 add_conditional_edges 实现。

统一路由策略：所有意图均走 planner_decompose，由 Planner 内部区分处理：
  - 可执行意图（mcp/skill/rag/chat/system）→ 直接构建子任务，不调 LLM，单波次完成
  - complex_plan 意图 → LLM 独立分解，保留完整规划能力
  - 混合意图 → 可执行直接构建 + complex_plan LLM 分解，合并后波次调度
"""

from typing import Dict, Any
from langgraph.config import get_stream_writer
from modules.langgraph.nodes.steps import Step


def supervisor_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Supervisor 路由节点

    负责流式事件推送和状态重置。
    所有意图统一路由到 planner_decompose，由 Planner 内部区分处理。

    Args:
        state: 当前状态

    Returns:
        重置 agent_results 和 planner 相关字段的状态更新字典
    """
    writer = get_stream_writer()
    writer(Step.SUPERVISOR.started_event())
    writer(Step.SUPERVISOR.completed_event(detail="routing → planner_decompose"))
    return {
        "agent_results": None,          # 重置（add_agent_results reducer: None → []）
        "planned_subtasks": [],          # 重置（keep_last reducer: 空列表覆盖旧值）
        "__dispatch_complete__": False,   # 重置调度完成标记
    }
