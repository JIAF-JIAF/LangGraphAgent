"""
Planner 工具封装（精简版）

仅保留 decompose_task 工具，供旧路径兼容使用。
委托工具（delegate_to_*）和汇总工具（summarize_results）已移除，
Planner 并行委托改由 Orchestrator-Worker 模式实现：
  - planner_decompose：结构化输出分解子任务
  - planner_dispatch：Send API 按波次调度到 Expert
  - merge：统一汇总润色

对照旧架构：
  - 旧：decompose_task + delegate_to_mcp/skill/rag + summarize_results（ReAct 串行）
  - 新：decompose（结构化输出）+ dispatch（Send API 并行）+ merge（统一润色）
"""

import json
from typing import List, Optional
from langchain_core.tools import tool
from modules.langgraph.planner.task_planner import TaskPlanner
from modules.logger import log


def create_planner_tools(
    task_planner: TaskPlanner,
    expert_agents: Optional[dict] = None,
) -> List:
    """
    将 TaskPlanner 封装为 LangChain @tool（精简版，仅保留 decompose_task）

    Args:
        task_planner: TaskPlanner 实例
        expert_agents: 兼容参数，不再使用

    Returns:
        [decompose_task] 工具列表
    """
    @tool
    def decompose_task(query: str, context: str = "") -> str:
        """
        将复杂任务分解为子任务列表。当用户的问题需要多步骤处理时使用。

        Args:
            query: 用户的问题或任务描述
            context: 额外上下文信息（可选）
        """
        log(f"[PlannerTool] 分解任务: {query[:30]}...", "MultiAgent")
        subtasks = task_planner.plan(query, context)
        return json.dumps(subtasks, ensure_ascii=False, indent=2)

    tools = [decompose_task]
    log(f"[PlannerTool] 创建 {len(tools)} 个工具（精简版，无委托工具）", "MultiAgent")
    return tools
