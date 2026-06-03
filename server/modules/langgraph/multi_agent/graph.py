"""
多 Agent 图构建器

构建混合架构的多 Agent 主图：
  - 前置节点（feeling_detect, intent_recognize）复用旧节点
  - Supervisor 按意图类别细粒度分发，支持 Send API 并行
  - Chat/MCP/Skill/RAG/Planner Expert Subgraph 处理领域专精意图
  - Merge 节点合并所有 Expert 结果，统一润色生成最终回答
  - 旧路径节点（execute_direct, router, plan 等）保留用于兼容

图结构（Phase 2 专家架构）：

  START → feeling_detect → intent_recognize → supervisor
                                                │
              ┌───────┬───────┬───────┬────────┼────────┐
              ▼       ▼       ▼       ▼        ▼        │
        chat_expert mcp_expert skill_expert rag_expert   │
        planner_expert                                      │
              │       │         │           │        │     │
              └───────┴─────────┴───────────┴────────┘     │
                                    │                      │
                                    ▼                      │
                                  merge → END              │
                                                             │
              (Supervisor 并行分发: Send API → 多 Expert → merge)

路由策略（SUPERVISOR_ROUTE_TABLE 声明式定义）：
  1. 无意图 → chat_expert
  2. PLAN 意图 / 未知复杂意图 → planner_expert
  3. 纯 MCP 意图 → mcp_expert
  4. 纯 Skill 意图 → skill_expert
  5. 纯 RAG 意图 → rag_expert
  6. 混合可执行意图 → Send API 并行分发到多个 Expert
  7. 对话意图 → chat_expert

能力不降级保障：
  - Planner Expert 通过委托工具（delegate_to_*）调用其他 Expert Agent
  - 混合意图通过 Send API 并行执行，不再走旧 execute_direct
  - Merge 节点统一润色，与旧 CallModelNode + RefinerRegistry 行为一致
  - Chat Expert 内部已润色，Merge 直接取结果
"""

from typing import Any, Dict, List
from langgraph.graph import StateGraph, END, START
from modules.logger import log
from modules.langgraph.nodes.feeling import FeelingNode
from modules.langgraph.nodes.intent import IntentRecognizeNode
from modules.langgraph.nodes.execute import ExecuteDirectNode, ExecuteTaskNode, CheckTaskCompleteNode
from modules.langgraph.nodes.rag import RouterNode, RetrieveNode
from modules.langgraph.nodes.plan import PlanNode
from modules.langgraph.multi_agent.states import MultiAgentState
from modules.langgraph.multi_agent.nodes.supervisor import supervisor_node
from modules.langgraph.multi_agent.nodes.merge import MergeNode
from modules.langgraph.multi_agent.expert_agent_factory import ExpertAgentFactory
from modules.langgraph.multi_agent.subgraphs.chat_subgraph import create_chat_expert
from modules.langgraph.multi_agent.subgraphs.mcp_subgraph import create_mcp_expert
from modules.langgraph.multi_agent.subgraphs.skill_subgraph import create_skill_expert
from modules.langgraph.multi_agent.subgraphs.rag_subgraph import create_rag_expert
from modules.langgraph.multi_agent.subgraphs.planner_subgraph import create_planner_expert
from modules.langgraph.multi_agent import is_agent_enabled
from modules.intent import classify_intents, resolve_route, SUPERVISOR_ROUTE_TABLE


class MultiAgentGraphBuilder:
    """
    多 Agent 图构建器（Phase 2 专家架构）

    所有意图均走 Expert Subgraph：
    - 单一类别意图 → 直接路由到对应 Expert
    - 混合意图 → Send API 并行分发到多个 Expert
    - PLAN 意图 → planner_expert（通过委托工具编排跨领域子任务）
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
        executors: Dict[str, Any] = None,
        ai_client: Any = None,
        skill_manager: Any = None,
    ):
        self._feeling_detector = feeling_detector
        self._intent_router = intent_router
        self._agent = agent
        self._refiners = refiners
        self._rag_workflow = rag_workflow
        self._task_planner = task_planner
        self._executors = executors
        self._ai_client = ai_client
        self._skill_manager = skill_manager

    def build(self) -> StateGraph:
        """
        构建多 Agent 状态图

        Returns:
            未编译的 StateGraph 实例（使用 MultiAgentState）
        """
        log("开始构建多 Agent 状态图（Phase 2 专家架构）...", "MultiAgent")
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
        expert_agents = {}  # 用于 Planner 委托工具

        # 所有 Expert 节点名（始终注册到图中，确保 Send API 路由目标存在）
        ALL_EXPERT_NAMES = ["mcp_expert", "skill_expert", "rag_expert", "planner_expert"]

        # MCP Expert
        if is_agent_enabled("mcp_expert"):
            mcp_agent = expert_factory.create_mcp_agent()
            expert_nodes["mcp_expert"] = create_mcp_expert(mcp_agent)
            expert_agents["mcp"] = mcp_agent
            log("[MultiAgent] MCP Expert Subgraph 已启用", "MultiAgent")

        # Skill Expert
        if is_agent_enabled("skill_expert"):
            skill_agent = expert_factory.create_skill_agent()
            expert_nodes["skill_expert"] = create_skill_expert(skill_agent)
            expert_agents["skill"] = skill_agent
            log("[MultiAgent] Skill Expert Subgraph 已启用", "MultiAgent")

        # RAG Expert
        if is_agent_enabled("rag_expert"):
            rag_agent = expert_factory.create_rag_agent()
            if rag_agent:
                expert_nodes["rag_expert"] = create_rag_expert(rag_agent)
                expert_agents["rag"] = rag_agent
                log("[MultiAgent] RAG Expert Subgraph 已启用", "MultiAgent")

        # Planner Expert（传入 expert_agents 用于委托工具）
        if is_agent_enabled("planner_expert"):
            planner_agent = expert_factory.create_planner_agent(expert_agents)
            if planner_agent:
                expert_nodes["planner_expert"] = create_planner_expert(planner_agent)
                log("[MultiAgent] Planner Expert Subgraph 已启用（含委托工具）", "MultiAgent")

        # Chat Subgraph
        chat_expert = create_chat_expert(self._agent, self._refiners)
        graph.add_node("chat_expert", chat_expert)

        # 注册 Expert Subgraph 到主图
        for name, subgraph in expert_nodes.items():
            graph.add_node(name, subgraph)

        # 未启用的 Expert 注册空 subgraph（确保 Send API 路由目标存在）
        disabled_experts = [n for n in ALL_EXPERT_NAMES if n not in expert_nodes]
        for name in disabled_experts:
            graph.add_node(name, _create_disabled_expert_node(name))
            log(f"[MultiAgent] {name} 未启用，注册空节点", "MultiAgent")

        # === Merge 节点（合并所有 Expert 结果，使用纯 LLM 润色，避免工具幻觉） ===
        merge_node = MergeNode(ai_client=self._ai_client, refiners=self._refiners)
        graph.add_node("merge", merge_node)

        # === 旧路径节点（保留，处理兼容场景） ===
        graph.add_node("execute_direct", ExecuteDirectNode(self._executors))
        graph.add_node("router", RouterNode(self._rag_workflow))
        graph.add_node("retrieve", RetrieveNode(self._rag_workflow))
        graph.add_node("plan", PlanNode(self._task_planner))
        graph.add_node("execute_task", ExecuteTaskNode(self._agent))
        graph.add_node("check_task_complete", CheckTaskCompleteNode(self._task_planner))
        graph.add_node("call_model", self._create_call_model_node())

        # === 边 ===

        # 基础流程：情绪检测 → 意图识别 → Supervisor
        graph.add_edge(START, "feeling_detect")
        graph.add_edge("feeling_detect", "intent_recognize")
        graph.add_edge("intent_recognize", "supervisor")

        # Supervisor 条件路由
        # Send API 要求：路由函数返回 list[Send] 时，所有 Send 目标节点名必须在映射表中声明
        # 必须包含所有可能的 Expert 节点名（即使未启用），否则 Send 会报 "Ignoring unknown node name"
        route_targets = {
            "chat_expert": "chat_expert",
            "execute_direct": "execute_direct",
            "router": "router",
            "mcp_expert": "mcp_expert",
            "skill_expert": "skill_expert",
            "rag_expert": "rag_expert",
            "planner_expert": "planner_expert",
        }

        graph.add_conditional_edges(
            "supervisor",
            _route_from_supervisor,
            route_targets,
        )

        # Expert Subgraph → merge（包括已启用和未启用的）
        for name in expert_nodes:
            graph.add_edge(name, "merge")
        for name in disabled_experts:
            graph.add_edge(name, "merge")

        # Chat Subgraph → merge
        graph.add_edge("chat_expert", "merge")

        # merge → END
        graph.add_edge("merge", END)

        # === 旧路径边（保留兼容） ===
        graph.add_edge("execute_direct", "call_model")
        graph.add_conditional_edges(
            "router",
            lambda state: "retrieve" if state.get("need_retrieve") else "plan",
            {"retrieve": "retrieve", "plan": "plan"}
        )
        graph.add_edge("retrieve", "plan")
        graph.add_edge("plan", "execute_task")
        graph.add_edge("execute_task", "check_task_complete")
        graph.add_conditional_edges(
            "check_task_complete",
            lambda state: "execute_task" if not state.get("is_task_completed") else "call_model",
            {"execute_task": "execute_task", "call_model": "call_model"}
        )
        graph.add_edge("call_model", END)

        log(f"多 Agent 状态图构建完成（Phase 2 专家架构，Expert: {list(expert_nodes.keys())}）", "MultiAgent")
        return graph

    def _create_call_model_node(self):
        """创建旧路径的 CallModelNode"""
        from modules.langgraph.nodes.model import CallModelNode
        return CallModelNode(self._agent, self._refiners)


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

    # 检查 Expert 是否启用
    if target in ("mcp_expert", "skill_expert", "rag_expert", "planner_expert"):
        if not is_agent_enabled(target):
            log(f"[Supervisor] {target} 未启用，回退到 chat_expert", "MultiAgent")
            return "chat_expert"

    log(f"[Supervisor] 路由决策: → {target} ({detail})", "MultiAgent")
    return target


def _create_disabled_expert_node(expert_name: str):
    """
    创建未启用 Expert 的空节点

    未启用的 Expert 仍需注册到图中，确保 Send API 路由目标存在。
    空节点直接返回空的 agent_results，不会执行任何操作。

    Args:
        expert_name: Expert 节点名称

    Returns:
        空节点函数
    """
    def disabled_node(state: Dict[str, Any]) -> Dict[str, Any]:
        log(f"[{expert_name}] 未启用，跳过执行", "MultiAgent")
        return {
            "agent_results": [{
                "agent": expert_name,
                "answer": "",
                "intent_results": [],
                "success": False,
            }]
        }
    return disabled_node


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
    from langgraph.types import Send
    from modules.intent import IntentCategory

    CATEGORY_EXPERT_MAP = {
        IntentCategory.MCP: "mcp_expert",
        IntentCategory.SKILL: "skill_expert",
        IntentCategory.RAG: "rag_expert",
    }

    intents = state.get("intents", [])
    sends = []

    # 按类别分组意图
    category_intents: Dict[str, list] = {}
    for intent in intents:
        category = intent.get("category", "")
        expert_name = None
        for cat_enum, name in CATEGORY_EXPERT_MAP.items():
            if category == cat_enum.value:
                expert_name = name
                break
        if expert_name:
            category_intents.setdefault(expert_name, []).append(intent)

    # 为每个类别创建 Send
    for expert_name, category_intent_list in category_intents.items():
        if not is_agent_enabled(expert_name):
            log(f"[Supervisor] 并行分发跳过: {expert_name} 未启用", "MultiAgent")
            continue

        # 构建 Expert 专属 state（只包含该类别的意图）
        expert_state = dict(state)
        expert_state["intents"] = category_intent_list
        expert_state["agent_results"] = []

        sends.append(Send(expert_name, expert_state))
        log(f"[Supervisor] 并行分发: {len(category_intent_list)} 个意图 → {expert_name}", "MultiAgent")

    return sends
