"""
Planner 分解节点（纯编排者）

所有意图统一进入 Planner，由 Planner 委托给两个 Decomposer：
  - ExecutableIntentDecomposer：可执行意图（mcp/skill/rag/chat/system）→ 规则映射，不调 LLM
  - ComplexPlanDecomposer：complex_plan 意图 → LLM 独立分解，保留完整规划能力

本节点只负责意图分离 + 结果合并，不包含任何分解逻辑。

执行流程：
  supervisor → planner_decompose → planner_dispatch ──→ Send(expert) ──→ planner_dispatch (循环)
                                                              ↓ (全部完成)
                                                            merge → END
"""

from typing import Dict, Any, List
from langgraph.config import get_stream_writer
from modules.logger import log
from modules.langgraph.nodes.steps import Step
from modules.langgraph.multi_agent.planner.models import COMPLEX_PLAN_CATEGORY
from modules.langgraph.multi_agent.planner.executable_intent_decomposer import ExecutableIntentDecomposer
from modules.langgraph.multi_agent.planner.complex_plan_decomposer import ComplexPlanDecomposer


# ==================== Planner 分解节点 ====================

class PlannerDecomposeNode:
    """
    Planner 分解节点（纯编排者）

    所有意图统一进入此节点，Planner 内部委托给两个 Decomposer：
      1. ExecutableIntentDecomposer：可执行意图 → 规则映射构建子任务（无 LLM）
      2. ComplexPlanDecomposer：complex_plan 意图 → LLM 独立分解

    本类只负责意图分离 + 结果合并，不包含任何分解逻辑。
    分解结果写入 state["planned_subtasks"]，由 planner_dispatch 节点按波次调度。
    """

    def __init__(self, ai_client, plugin_registry):
        """
        Args:
            ai_client: AIClient 实例，用于调用 with_structured_output
            plugin_registry: PluginRegistry 实例，用于动态获取能力描述和路由映射
        """
        self._ai_client = ai_client
        self._plugin_registry = plugin_registry
        self._executable_decomposer = ExecutableIntentDecomposer(plugin_registry)
        self._complex_plan_decomposer = ComplexPlanDecomposer(ai_client, plugin_registry)

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        分解任务为子任务列表（纯编排入口）

        Args:
            state: 当前状态（包含 query、intents 等）

        Returns:
            更新后的状态（包含 planned_subtasks）
        """
        writer = get_stream_writer()
        query = state["query"]
        intents = state.get("intents", [])

        writer(Step.PLANNER_DECOMPOSE.started_event(detail=f"分解任务：{query[:40]}"))
        writer(Step.PLANNER_DECOMPOSE.progress_event(detail="正在分析意图并分解子任务..."))
        log(f"[PlannerDecompose] 分解任务: {query[:50]}...", "MultiAgent")

        # 分离意图
        executable_intents, plan_intents = self._separate_intents(intents)

        # 步骤 1：可执行意图 → 委托 ExecutableIntentDecomposer
        subtasks = self._executable_decomposer.decompose(executable_intents)

        # 步骤 2：每个 complex_plan 意图 → 委托 ComplexPlanDecomposer
        for plan_intent in plan_intents:
            plan_subtasks = self._complex_plan_decomposer.decompose(plan_intent, existing_count=len(subtasks))
            subtasks.extend(plan_subtasks)

        # 兜底：无任何子任务
        if not subtasks:
            subtasks = self._build_fallback_subtask(query)
            log("[PlannerDecompose] 无子任务，回退到 chat", "MultiAgent")

        subtask_desc = "、".join(
            f"{s.get('category', '?')}:{s.get('description', '')[:15]}"
            for s in subtasks
        )
        writer(Step.PLANNER_DECOMPOSE.completed_event(detail=f"{len(subtasks)} 个子任务：{subtask_desc}"))

        return {
            "planned_subtasks": subtasks,
            "agent_results": None,  # 重置，避免跨请求累积
        }

    # -------------------- 意图分离 --------------------

    def _separate_intents(self, intents: List[Dict[str, Any]]) -> tuple:
        """
        将意图列表分离为可执行意图和复杂规划意图

        可执行类别从 plugin_registry 动态获取，新增插件时无需修改此方法。

        Args:
            intents: 原始意图列表

        Returns:
            (executable_intents, plan_intents) 元组
        """
        executable_categories = self._plugin_registry.build_executable_categories()
        executable_intents = []
        plan_intents = []

        for intent in intents:
            category = intent.get("category", "")

            if category in executable_categories:
                executable_intents.append(intent)
            elif category == COMPLEX_PLAN_CATEGORY:
                plan_intents.append(intent)
            else:
                executable_intents.append(intent)

        return executable_intents, plan_intents

    # -------------------- 兜底 --------------------

    @staticmethod
    def _build_fallback_subtask(query: str) -> List[Dict[str, Any]]:
        """
        构建兜底子任务（当所有分解均失败时）

        Args:
            query: 用户原始请求

        Returns:
            包含单个 chat 子任务的列表
        """
        return [{
            "description": query,
            "category": "chat",
            "depends_on": [],
        }]


# ==================== 工厂函数 ====================


def create_planner_decompose(ai_client, plugin_registry):
    """
    创建 Planner 分解节点

    Args:
        ai_client: AIClient 实例
        plugin_registry: PluginRegistry 实例

    Returns:
        PlannerDecomposeNode 实例
    """
    return PlannerDecomposeNode(ai_client, plugin_registry)
