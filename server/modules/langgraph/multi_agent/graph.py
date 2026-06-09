"""
多 Agent 图构建器

构建多 Agent 主图：
  - 前置节点（feeling_detect, intent_recognize）
  - Supervisor 统一路由到 Planner
  - Planner 区分处理：可执行意图直接构建子任务 + complex_plan LLM 分解
  - Planner 波次调度：按依赖关系 Send API 并行分发到 Expert
  - Expert 执行后回到 planner_dispatch 继续波次调度
  - Merge 节点合并所有 Expert 结果，统一润色生成最终回答

图结构（统一 Planner 路由）：

  START → feeling_detect → intent_recognize → supervisor
                                                │
                                                ▼
                                        planner_decompose
                                                │
                                                ▼
                                        planner_dispatch ──→ Send(expert) ──→ planner_dispatch (循环)
                                                                ↓ (全部完成)
                                                              merge → END

插件化架构：
  Expert 通过 PluginRegistry 动态注册，新增 Expert 只需：
    1. 继承 ExpertPlugin，实现 meta + execute
    2. registry.register(YourPlugin())
    3. 框架自动完成图注册、边连接、路由映射

  框架代码零改动。
"""

from typing import Any, Dict, List
from langgraph.graph import StateGraph, END, START
from modules.logger import log
from modules.langgraph.nodes.feeling import FeelingNode
from modules.langgraph.nodes.intent import IntentRecognizeNode
from modules.langgraph.multi_agent.states import MultiAgentState
from modules.langgraph.multi_agent.nodes.supervisor import supervisor_node
from modules.langgraph.multi_agent.nodes.merge import MergeNode
from modules.langgraph.multi_agent.plugin_registry import PluginRegistry
from modules.langgraph.multi_agent.planner.decompose import create_planner_decompose
from modules.langgraph.multi_agent.planner.dispatch import PlannerDispatchNode

# Supervisor 条件路由目标映射（统一路由到 planner_decompose）
SUPERVISOR_ROUTE_TARGETS = {"planner_decompose": "planner_decompose"}


class MultiAgentGraphBuilder:
    """
    多 Agent 图构建器（插件化架构）

    Expert 通过 PluginRegistry 动态注册，框架自动完成：
    - graph.add_node(name, plugin) + graph.add_edge(name, "planner_dispatch")
    - CATEGORY_EXPERT_MAP 映射
    - PLANNER_DISPATCH_TARGETS 路由目标
    - DECOMPOSE_PROMPT 能力描述

    新增 Expert 不需要修改任何框架代码。
    """

    def __init__(
        self,
        plugin_registry: PluginRegistry,
        feeling_detector: Any,
        intent_router: Any,
        ai_client: Any = None,
    ):
        """
        Args:
            plugin_registry: 插件注册表（已注册所有 Expert 插件）
            feeling_detector: 情绪检测器
            intent_router: 意图路由器
            ai_client: AIClient 实例
        """
        self._registry = plugin_registry
        self._feeling_detector = feeling_detector
        self._intent_router = intent_router
        self._ai_client = ai_client

    def build(self) -> StateGraph:
        """
        构建多 Agent 状态图

        Returns:
            未编译的 StateGraph 实例（使用 MultiAgentState）
        """
        log("开始构建多 Agent 状态图（插件化 Orchestrator-Worker 架构）...", "MultiAgent")
        graph = StateGraph(MultiAgentState)

        # === 前置节点（直接复用旧节点） ===
        graph.add_node("feeling_detect", FeelingNode(self._feeling_detector))
        graph.add_node("intent_recognize", IntentRecognizeNode(self._intent_router))

        # === Supervisor 路由节点 ===
        graph.add_node("supervisor", supervisor_node)

        # === Expert 节点：从注册表动态注册（替代硬编码） ===
        self._registry.register_graph_nodes(graph)

        # === Planner 节点（Orchestrator-Worker 模式） ===
        planner_decompose = create_planner_decompose(
            self._ai_client,
            plugin_registry=self._registry,
        )

        self._planner_dispatch = PlannerDispatchNode(self._registry)
        graph.add_node("planner_decompose", planner_decompose)
        graph.add_node("planner_dispatch", self._planner_dispatch)
        log("[MultiAgent] Planner Orchestrator-Worker 已启用", "MultiAgent")

        # === Merge 节点（合并所有 Expert 结果，使用纯 LLM 润色，避免工具幻觉） ===
        merge_node = MergeNode(ai_client=self._ai_client, plugin_registry=self._registry)
        graph.add_node("merge", merge_node)

        # === 边 ===

        # 基础流程：情绪检测 → 意图识别 → Supervisor
        graph.add_edge(START, "feeling_detect")
        graph.add_edge("feeling_detect", "intent_recognize")
        graph.add_edge("intent_recognize", "supervisor")

        # Supervisor 统一路由到 planner_decompose
        graph.add_conditional_edges(
            "supervisor",
            self._route_from_supervisor,
            SUPERVISOR_ROUTE_TARGETS,
        )

        # === Planner Orchestrator-Worker 边 ===
        # planner_decompose → planner_dispatch（固定边）
        graph.add_edge("planner_decompose", "planner_dispatch")

        # planner_dispatch 条件路由：从注册表动态获取目标映射
        graph.add_conditional_edges(
            "planner_dispatch",
            self._route_from_planner_dispatch,
            self._registry.build_dispatch_targets(),
        )

        # merge → END
        graph.add_edge("merge", END)

        registered_plugins = list(self._registry.get_all_plugins().keys())
        log(f"多 Agent 状态图构建完成（插件化架构，Expert: {registered_plugins}）", "MultiAgent")
        return graph

    def _route_from_planner_dispatch(self, state: Dict[str, Any]):
        """
        Planner Dispatch 条件路由

        - 有就绪子任务 → 返回 list[Send] 并行分发到 Expert
        - 全部完成 → "merge"

        Args:
            state: 当前状态

        Returns:
            目标节点名或 Send 列表
        """
        if state.get("__dispatch_complete__"):
            return "merge"

        sends = self._planner_dispatch.build_sends(state)
        if sends:
            return sends

        return "merge"

    @staticmethod
    def _route_from_supervisor(state: Dict[str, Any]):
        """
        Supervisor 条件路由（统一 Planner 路由）

        所有意图统一路由到 planner_decompose，由 Planner 内部区分处理。

        Args:
            state: 当前状态（包含 intents 等）

        Returns:
            "planner_decompose"
        """
        intents = state.get("intents", [])

        if not intents:
            log("[Supervisor] 路由决策: → planner_decompose (无意图，Planner 兜底处理)", "MultiAgent")
        else:
            categories = ", ".join(sorted(set(i.get("category", "") for i in intents)))
            log(f"[Supervisor] 路由决策: → planner_decompose (类别: {categories})", "MultiAgent")

        return "planner_decompose"
