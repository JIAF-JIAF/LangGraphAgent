"""
Planner 工具封装

将 TaskPlanner 封装为 LangChain @tool，供 Planner Subgraph 内部使用。

对照现有 TaskPlanner：
  TaskPlanner.plan(query, context="") -> List[Dict[str, Any]]
  TaskPlanner.get_summary(subtasks) -> str

封装后：
  decompose_task(query, context) — 分解复杂任务为子任务列表
  delegate_to_mcp_expert(task) — 委托 MCP 专家执行工具调用子任务
  delegate_to_skill_expert(task) — 委托技能专家执行技能子任务
  delegate_to_rag_expert(task) — 委托知识库专家执行检索子任务
  summarize_results(query, results) — 汇总子任务结果为最终回答

核心设计：
  - 委托工具让 Planner 能跨领域编排，同时保持工具隔离
  - Planner Agent 只看到委托工具（不直接看到 MCP/Skill/RAG 工具）
  - 委托工具内部调用对应 Expert Agent，由 LLM-in-the-loop 完成参数提取
"""

import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import tool
from modules.langgraph.planner.task_planner import TaskPlanner
from modules.context import AgentContext
from modules.logger import log


class SubTaskResult(BaseModel):
    """子任务结果结构（Pydantic 约束，引导 LLM 传入列表格式而非字典）"""
    task_description: str = Field(description="子任务描述")
    result: str = Field(description="子任务执行结果")
    status: str = Field(default="completed", description="任务状态：completed 或 failed")


def create_planner_tools(
    task_planner: TaskPlanner,
    expert_agents: Optional[Dict[str, Any]] = None,
) -> List:
    """将 TaskPlanner + 委托工具封装为 LangChain @tool

    Args:
        task_planner: TaskPlanner 实例
        expert_agents: 各领域 Expert Agent 实例字典
            {"mcp": Agent, "skill": Agent, "rag": Agent}

    Returns:
        [decompose_task, delegate_to_mcp_expert, delegate_to_skill_expert,
         delegate_to_rag_expert, summarize_results] 工具列表
    """
    agents = expert_agents or {}

    @tool
    def decompose_task(query: str, context: str = "") -> str:
        """将复杂任务分解为子任务列表。当用户的问题需要多步骤处理时使用。

        Args:
            query: 用户的问题或任务描述
            context: 额外上下文信息（可选）
        """
        log(f"[PlannerTool] 分解任务: {query[:30]}...", "MultiAgent")
        subtasks = task_planner.plan(query, context)
        return json.dumps(subtasks, ensure_ascii=False, indent=2)

    @tool
    def delegate_to_mcp_expert(task_description: str) -> str:
        """将子任务委托给 MCP 工具调用专家执行。
        当子任务需要调用外部工具（如天气查询、日程管理、钉钉操作等）时使用。

        Args:
            task_description: 子任务的详细描述，需要包含足够信息让专家完成
        """
        agent = agents.get("mcp")
        if not agent:
            return "MCP 专家不可用，请尝试其他方式完成此任务。"
        log(f"[PlannerTool] 委托 MCP 专家: {task_description[:30]}...", "MultiAgent")
        result = agent.invoke(task_description, AgentContext())
        return result.get("answer", "执行失败")

    @tool
    def delegate_to_skill_expert(task_description: str) -> str:
        """将子任务委托给技能执行专家执行。
        当子任务需要执行技能（如绘制流程图、数据分析、在线表格等）时使用。

        Args:
            task_description: 子任务的详细描述，需要包含足够信息让专家完成
        """
        agent = agents.get("skill")
        if not agent:
            return "技能专家不可用，请尝试其他方式完成此任务。"
        log(f"[PlannerTool] 委托 Skill 专家: {task_description[:30]}...", "MultiAgent")
        result = agent.invoke(task_description, AgentContext())
        return result.get("answer", "执行失败")

    @tool
    def delegate_to_rag_expert(task_description: str) -> str:
        """将子任务委托给知识库检索专家执行。
        当子任务需要从知识库中检索信息（如考试资料、政策文件等）时使用。

        Args:
            task_description: 子任务的详细描述，需要包含足够信息让专家完成
        """
        agent = agents.get("rag")
        if not agent:
            return "知识库专家不可用，请尝试其他方式完成此任务。"
        log(f"[PlannerTool] 委托 RAG 专家: {task_description[:30]}...", "MultiAgent")
        result = agent.invoke(task_description, AgentContext())
        return result.get("answer", "执行失败")

    @tool
    def summarize_results(query: str, results: List[SubTaskResult]) -> str:
        """将多个子任务的结果汇总为最终回答。当所有子任务完成后使用。

        Args:
            query: 原始用户问题
            results: 各子任务的执行结果列表（必须是列表，每个元素包含 task_description、result、status）
        """
        log("[PlannerTool] 汇总结果", "MultiAgent")
        subtasks = [r.model_dump() for r in results]

        summary = task_planner.get_summary(subtasks)
        return summary if summary else str(subtasks)

    tools = [
        decompose_task, 
        delegate_to_mcp_expert, 
        delegate_to_skill_expert,
        delegate_to_rag_expert,
        summarize_results
    ]
    log(f"[PlannerTool] 创建 {len(tools)} 个工具（含 3 个委托工具）", "MultiAgent")
    return tools
