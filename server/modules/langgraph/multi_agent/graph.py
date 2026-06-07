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

路由策略（统一 Planner 路由）：
  所有意图统一走 planner_decompose，Planner 内部区分处理：
    - 可执行意图（mcp/skill/rag/chat/system）→ 直接构建子任务，不调 LLM，单波次完成
    - complex_plan 意图 → LLM 独立分解，保留完整规划能力
    - 混合意图 → 可执行直接构建 + complex_plan LLM 分解，合并后波次调度
"""

from typing import Any, Dict, List
from langgraph.graph import StateGraph, END, START
from modules.logger import log
from modules.langgraph.nodes.feeling import FeelingNode
from modules.langgraph.nodes.intent import IntentRecognizeNode
from modules.langgraph.multi_agent.states import MultiAgentState
from modules.langgraph.multi_agent.nodes.supervisor import supervisor_node
from modules.langgraph.multi_agent.nodes.merge import MergeNode
from modules.langgraph.multi_agent.expert_agent_factory import ExpertAgentFactory
from modules.langgraph.multi_agent.subgraphs.chat_subgraph import create_chat_expert
from modules.langgraph.multi_agent.subgraphs.mcp_subgraph import create_mcp_expert
from modules.langgraph.multi_agent.subgraphs.skill_subgraph import create_skill_expert
from modules.langgraph.multi_agent.subgraphs.rag_subgraph import create_rag_expert
from modules.langgraph.multi_agent.subgraphs.planner_subgraph import (
    create_planner_decompose,
    planner_dispatch,
    build_planner_sends,
)

# Supervisor 条件路由目标映射（统一路由到 planner_decompose）
# LangGraph add_conditional_edges 要求提供目标映射
SUPERVISOR_ROUTE_TARGETS = {"planner_decompose": "planner_decompose"}

# Planner Dispatch 条件路由目标映射
PLANNER_DISPATCH_TARGETS = {
    "mcp_expert": "mcp_expert",
    "skill_expert": "skill_expert",
    "rag_expert": "rag_expert",
    "chat_expert": "chat_expert",
    "merge": "merge",
}


class MultiAgentGraphBuilder:
    """
    多 Agent 图构建器（统一 Planner 路由）

    所有意图统一走 planner_decompose，Planner 内部区分处理：
    - 可执行意图（mcp/skill/rag/chat/system）→ 直接构建子任务，不调 LLM，单波次完成
    - complex_plan 意图 → LLM 独立分解，保留完整规划能力
    - 混合意图 → 可执行直接构建 + complex_plan LLM 分解，合并后波次调度

    所有 Expert 结果汇聚到 Merge 节点统一润色。
    """

    def __init__(
        self,
        feeling_detector: Any,
        intent_router: Any,
        agent: Any,
        rag_workflow: Any = None,
        task_planner: Any = None,
        ai_client: Any = None,
        skill_manager: Any = None,
    ):
        self._feeling_detector = feeling_detector
        self._intent_router = intent_router
        self._agent = agent
        self._rag_workflow = rag_workflow
        self._task_planner = task_planner
        self._ai_client = ai_client
        self._skill_manager = skill_manager

    def build(self) -> StateGraph:
        """
        构建多 Agent 状态图

        Returns:
            未编译的 StateGraph 实例（使用 MultiAgentState）
        """
        log("开始构建多 Agent 状态图（Orchestrator-Worker 架构）...", "MultiAgent")
        graph = StateGraph(MultiAgentState)

        # === 前置节点（直接复用旧节点） ===
        graph.add_node("feeling_detect", FeelingNode(self._feeling_detector))
        graph.add_node("intent_recognize", IntentRecognizeNode(self._intent_router))

        # === Supervisor 路由节点 ===
        graph.add_node("supervisor", supervisor_node)

        # === Expert Subgraphs ===
        expert_factory = ExpertAgentFactory(
            ai_client=self._ai_client,
            rag_workflow=self._rag_workflow,
            task_planner=self._task_planner,
            skill_manager=self._skill_manager,
        )

        expert_nodes = {}

        # MCP Expert
        mcp_agent = expert_factory.create_mcp_agent()
        expert_nodes["mcp_expert"] = create_mcp_expert(mcp_agent)
        log("[MultiAgent] MCP Expert Subgraph 已注册", "MultiAgent")

        # Skill Expert
        skill_agent = expert_factory.create_skill_agent()
        expert_nodes["skill_expert"] = create_skill_expert(skill_agent)
        log("[MultiAgent] Skill Expert Subgraph 已注册", "MultiAgent")

        # RAG Expert
        rag_agent = expert_factory.create_rag_agent()
        if rag_agent:
            expert_nodes["rag_expert"] = create_rag_expert(rag_agent)
            log("[MultiAgent] RAG Expert Subgraph 已注册", "MultiAgent")

        # Chat Subgraph
        chat_expert = create_chat_expert(self._agent)
        graph.add_node("chat_expert", chat_expert)

        # 注册 Expert Subgraph 到主图
        for name, subgraph in expert_nodes.items():
            graph.add_node(name, subgraph)

        # === Planner 节点（Orchestrator-Worker 模式） ===
        intent_registry = getattr(self._intent_router, 'registry', None) if self._intent_router else None
        planner_decompose = create_planner_decompose(self._ai_client, intent_registry=intent_registry)
        graph.add_node("planner_decompose", planner_decompose)
        graph.add_node("planner_dispatch", planner_dispatch)
        log("[MultiAgent] Planner Orchestrator-Worker 已启用", "MultiAgent")

        # === Merge 节点（合并所有 Expert 结果，使用纯 LLM 润色，避免工具幻觉） ===
        merge_node = MergeNode(ai_client=self._ai_client)
        graph.add_node("merge", merge_node)

        # === 边 ===

        # 基础流程：情绪检测 → 意图识别 → Supervisor
        graph.add_edge(START, "feeling_detect")
        graph.add_edge("feeling_detect", "intent_recognize")
        graph.add_edge("intent_recognize", "supervisor")

        # Supervisor 统一路由到 planner_decompose
        graph.add_conditional_edges(
            "supervisor",
            _route_from_supervisor,
            SUPERVISOR_ROUTE_TARGETS,
        )

        # 所有 Expert 执行后回到 planner_dispatch（统一由 Planner 调度）
        for name in expert_nodes:
            graph.add_edge(name, "planner_dispatch")

        # Chat Expert 执行后也回到 planner_dispatch
        graph.add_edge("chat_expert", "planner_dispatch")

        # === Planner Orchestrator-Worker 边 ===
        # planner_decompose → planner_dispatch（固定边）
        graph.add_edge("planner_decompose", "planner_dispatch")

        # planner_dispatch 条件路由：
        #   - 有就绪子任务 → Send(expert) 并行分发
        #   - 全部完成 → merge
        graph.add_conditional_edges(
            "planner_dispatch",
            _route_from_planner_dispatch,
            PLANNER_DISPATCH_TARGETS,
        )

        # merge → END
        graph.add_edge("merge", END)

        log(f"多 Agent 状态图构建完成（Orchestrator-Worker 架构，Expert: {list(expert_nodes.keys())}）", "MultiAgent")
        return graph


def _route_from_supervisor(state: Dict[str, Any]):
    """
    Supervisor 条件路由函数（统一 Planner 路由）

    所有意图统一路由到 planner_decompose，由 Planner 内部区分处理：
      - 可执行意图（mcp/skill/rag/chat/system）→ 直接构建子任务
      - complex_plan 意图 → LLM 独立分解
      - 混合意图 → 两者合并

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


def _route_from_planner_dispatch(state: Dict[str, Any]):
    """
    Planner Dispatch 条件路由函数

    根据 planner_dispatch 节点的输出决定下一步：
      - 有就绪子任务 → 返回 list[Send] 并行分发到 Expert
      - 全部完成 → "merge"

    Args:
        state: 当前状态（包含 __ready_indices__、__dispatch_complete__ 等）

    Returns:
        目标节点名（str）或 Send 列表（list[Send]）
    """
    # 检查是否全部完成
    if state.get("__dispatch_complete__"):
        return "merge"

    # 构建并行 Send
    sends = build_planner_sends(state)
    if sends:
        return sends

    # 无就绪子任务，去 merge
    return "merge"
