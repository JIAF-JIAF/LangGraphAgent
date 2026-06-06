"""
多 Agent 图构建器

构建多 Agent 主图：
  - 前置节点（feeling_detect, intent_recognize）
  - Supervisor 按意图类别细粒度分发，支持 Send API 并行
  - Chat/MCP/Skill/RAG Expert 处理领域专精意图
  - Planner 使用 Orchestrator-Worker 模式：分解 → 波次调度 → Expert 并行
  - Merge 节点合并所有 Expert 结果，统一润色生成最终回答

图结构（Orchestrator-Worker 架构）：

  START → feeling_detect → intent_recognize → supervisor
                                                │
              ┌───────┬───────┬───────┬────────┤
              ▼       ▼       ▼       ▼        │
        chat_expert mcp_expert skill_expert rag_expert
              │       │         │           │   │
              └───────┴─────────┴───────────┘   │
                          │                      │
                          ▼                      │
                        merge → END              │
                                                   │
              (Supervisor 并行分发: Send API → 多 Expert → merge)

  Planner 路径（Orchestrator-Worker）：
  supervisor → planner_decompose → planner_dispatch ──→ Send(expert) ──→ planner_dispatch (循环)
                                                              ↓ (全部完成)
                                                            merge → END

路由策略（SUPERVISOR_ROUTE_TABLE 声明式定义）：
  1. 无意图 → chat_expert
  2. COMPLEX_PLAN 意图 / 未知复杂意图 → planner_decompose（Orchestrator-Worker 模式）
  3. 纯 MCP 意图 → mcp_expert
  4. 纯 Skill 意图 → skill_expert
  5. 纯 RAG 意图 → rag_expert
  6. 混合可执行意图 → Send API 并行分发到多个 Expert
  7. 对话意图 → chat_expert
"""

from typing import Any, Dict, List
from langgraph.graph import StateGraph, END, START
from langgraph.types import Send
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
    CATEGORY_EXPERT_MAP,
)
from modules.intent import classify_intents, resolve_route, SUPERVISOR_ROUTE_TABLE

# Supervisor 条件路由目标映射（路由函数返回值 → 图中节点名）
SUPERVISOR_ROUTE_TARGETS = {
    "chat_expert": "chat_expert",
    "mcp_expert": "mcp_expert",
    "skill_expert": "skill_expert",
    "rag_expert": "rag_expert",
    "planner_decompose": "planner_decompose",
}

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
    多 Agent 图构建器（Orchestrator-Worker 架构）

    所有意图均走 Expert Subgraph：
    - 单一类别意图 → 直接路由到对应 Expert
    - 混合意图 → Send API 并行分发到多个 Expert
    - PLAN 意图 → planner_decompose + planner_dispatch（Orchestrator-Worker 波次调度）
    - 对话意图 → chat_expert

    所有 Expert 结果汇聚到 Merge 节点统一润色。
    """

    def __init__(
        self,
        feeling_detector: Any,
        intent_router: Any,
        agent: Any,
        refiners: List,
        rag_workflow: Any = None,
        task_planner: Any = None,
        ai_client: Any = None,
        skill_manager: Any = None,
    ):
        self._feeling_detector = feeling_detector
        self._intent_router = intent_router
        self._agent = agent
        self._refiners = refiners
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

        # === Expert Subgraphs（Feature Flag 控制） ===
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
        chat_expert = create_chat_expert(self._agent, self._refiners)
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
        merge_node = MergeNode(ai_client=self._ai_client, refiners=self._refiners)
        graph.add_node("merge", merge_node)

        # === 边 ===

        # 基础流程：情绪检测 → 意图识别 → Supervisor
        graph.add_edge(START, "feeling_detect")
        graph.add_edge("feeling_detect", "intent_recognize")
        graph.add_edge("intent_recognize", "supervisor")

        # Supervisor 条件路由
        graph.add_conditional_edges(
            "supervisor",
            _route_from_supervisor,
            SUPERVISOR_ROUTE_TARGETS,
        )

        # Expert Subgraph → 条件路由（Supervisor 调度 → merge，Planner 调度 → planner_dispatch）
        # 所有 Expert 节点统一使用条件边，根据 __subtask_idx__ 标记判断来源
        for name in expert_nodes:
            graph.add_conditional_edges(
                name,
                _route_expert_after_execution,
                {"merge": "merge", "planner_dispatch": "planner_dispatch"},
            )

        # Chat Subgraph → 条件路由（Supervisor 调度 → merge，Planner 调度 → planner_dispatch）
        graph.add_conditional_edges(
            "chat_expert",
            _route_expert_after_execution,
            {"merge": "merge", "planner_dispatch": "planner_dispatch"},
        )

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
    Supervisor 条件路由函数

    返回值：
      - str: 单个目标节点名（如 "mcp_expert"）
      - list[Send]: 并行分发到多个 Expert（Send API 标准用法）

    路由优先级与 SUPERVISOR_ROUTE_TABLE 一致。

    Args:
        state: 当前状态（包含 intents 等）

    Returns:
        目标节点名（str）或 Send 列表（list[Send]）
    """
    intents = state.get("intents", [])

    if not intents:
        return "chat_expert"

    info = classify_intents(intents)
    target, detail = resolve_route(info, SUPERVISOR_ROUTE_TABLE, fallback="chat_expert")

    # 混合可执行意图 → 返回 list[Send] 并行分发
    if target == "__parallel__":
        sends = _build_parallel_sends(state, info)
        if sends:
            expert_names = [s.node for s in sends]
            log(f"[Supervisor] 路由决策: → 并行 {len(sends)} 个 Expert: {expert_names}", "MultiAgent")
            return sends
        log("[Supervisor] 路由决策: → chat_expert (无可用 Expert)", "MultiAgent")
        return "chat_expert"

    # COMPLEX_PLAN 意图 → planner_decompose（Orchestrator-Worker 模式）
    if target == "planner_expert":
        log(f"[Supervisor] 路由决策: → planner_decompose ({detail})", "MultiAgent")
        return "planner_decompose"

    log(f"[Supervisor] 路由决策: → {target} ({detail})", "MultiAgent")
    return target


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


def _route_expert_after_execution(state: Dict[str, Any]):
    """
    Expert 执行完成后的路由

    判断 Expert 是由 Supervisor 还是 Planner 调度的：
      - Supervisor 调度 → merge（直接汇总）
      - Planner 调度 → planner_dispatch（继续波次调度）

    通过 __subtask_idx__ 标记判断：Planner 调度的 Expert 会携带此标记。

    Args:
        state: 当前状态

    Returns:
        "merge" 或 "planner_dispatch"
    """
    # 如果 state 中有 __subtask_idx__，说明是 Planner 调度的
    if state.get("__subtask_idx__") is not None:
        return "planner_dispatch"
    return "merge"


def _build_parallel_sends(state: Dict[str, Any], info: Dict[str, Any]) -> list:
    """
    构建并行 Send 列表

    将混合可执行意图按类别分组，每个类别创建一个 Send 到对应 Expert。
    每个 Expert 只接收属于自己类别的意图。

    Args:
        state: 当前状态（包含 intents 等）
        info: classify_intents 返回的分类信息

    Returns:
        Send 对象列表，每个 Send 指向一个 Expert 节点
    """
    intents = state.get("intents", [])
    sends = []

    # 按类别分组意图
    category_intents: Dict[str, list] = {}
    for intent in intents:
        category = intent.get("category", "")
        expert_name = CATEGORY_EXPERT_MAP.get(category)
        if expert_name:
            category_intents.setdefault(expert_name, []).append(intent)

    # 为每个类别创建 Send
    for expert_name, category_intent_list in category_intents.items():
        # 构建 Expert 专属 state（只包含该类别的意图）
        expert_state = dict(state)
        expert_state["intents"] = category_intent_list
        expert_state["agent_results"] = []

        sends.append(Send(expert_name, expert_state))
        log(f"[Supervisor] 并行分发: {len(category_intent_list)} 个意图 → {expert_name}", "MultiAgent")

    return sends
