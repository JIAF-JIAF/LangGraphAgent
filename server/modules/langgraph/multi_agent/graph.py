"""
多 Agent 图构建器

构建混合架构的多 Agent 主图：
  - 前置节点（feeling_detect, intent_recognize）复用旧节点
  - Supervisor 替代 intent_router，按意图类别细粒度分发
  - Chat Subgraph 作为新节点处理闲聊/系统指令
  - 旧路径节点（execute_direct, router, plan 等）保留，Phase 2 逐步替代

图结构（Phase 1 混合架构）：

  START → feeling_detect → intent_recognize → supervisor
                                                │
                          ┌─────────┬───────────┼──────────────┐
                          ▼         ▼           ▼              ▼
                    chat_expert  execute_direct  router        (Phase 2)
                          │         │          ╱    ╲
                          │         │     retrieve  plan
                          │         │        │        │
                          │         │        ▼        ▼
                          │         │     (RAG文档) execute_task
                          │         │                │
                          │         │         check_task_complete
                          │         │              │
                          └─────────┴──────────────┘
                                    │
                                    ▼
                              call_model → END
"""

from typing import Any, Dict, List
from langgraph.graph import StateGraph, END, START
from modules.logger import log
from modules.langgraph.nodes.feeling import FeelingNode
from modules.langgraph.nodes.intent import IntentRecognizeNode
from modules.langgraph.nodes.execute import ExecuteDirectNode, ExecuteTaskNode, CheckTaskCompleteNode
from modules.langgraph.nodes.rag import RouterNode, RetrieveNode
from modules.langgraph.nodes.plan import PlanNode
from modules.langgraph.nodes.model import CallModelNode
from modules.langgraph.edges import should_retrieve, should_continue_tasks
from modules.langgraph.multi_agent.states import MultiAgentState
from modules.langgraph.multi_agent.nodes.supervisor import supervisor_node
from modules.intent import classify_intents, resolve_route, SUPERVISOR_ROUTE_TABLE
from modules.langgraph.multi_agent.subgraphs.chat_subgraph import create_chat_subgraph


class MultiAgentGraphBuilder:
    """
    多 Agent 图构建器（混合架构）

    Phase 1：Chat 意图走新路径（supervisor → chat_expert → call_model），
    其余意图走旧路径（supervisor → execute_direct/router → ... → call_model）。
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
    ):
        self._feeling_detector = feeling_detector
        self._intent_router = intent_router
        self._agent = agent
        self._refiners = refiners
        self._rag_workflow = rag_workflow
        self._task_planner = task_planner
        self._executors = executors

    def build(self) -> StateGraph:
        """
        构建多 Agent 状态图

        Returns:
            未编译的 StateGraph 实例（使用 MultiAgentState）
        """
        log("开始构建多 Agent 状态图（混合架构）...", "MultiAgent")
        graph = StateGraph(MultiAgentState)

        # === 前置节点（直接复用旧节点） ===
        graph.add_node("feeling_detect", FeelingNode(self._feeling_detector))
        graph.add_node("intent_recognize", IntentRecognizeNode(self._intent_router))

        # === Supervisor 路由节点 ===
        graph.add_node("supervisor", supervisor_node)

        # === Chat Subgraph（新） ===
        chat_subgraph = create_chat_subgraph(self._agent, self._refiners)
        graph.add_node("chat_expert", chat_subgraph)

        # === 旧路径节点（Phase 1 保留，Phase 2 逐步替代） ===
        graph.add_node("execute_direct", ExecuteDirectNode(self._executors))
        graph.add_node("router", RouterNode(self._rag_workflow))
        graph.add_node("retrieve", RetrieveNode(self._rag_workflow))
        graph.add_node("plan", PlanNode(self._task_planner))
        graph.add_node("execute_task", ExecuteTaskNode(self._agent))
        graph.add_node("check_task_complete", CheckTaskCompleteNode(self._task_planner))

        # === 最终回答节点（保留 RefinerRegistry） ===
        graph.add_node("call_model", CallModelNode(self._agent, self._refiners))

        # === 边 ===

        # 基础流程：情绪检测 → 意图识别 → Supervisor
        graph.add_edge(START, "feeling_detect")
        graph.add_edge("feeling_detect", "intent_recognize")
        graph.add_edge("intent_recognize", "supervisor")

        # Supervisor 条件路由
        graph.add_conditional_edges(
            "supervisor",
            _route_from_supervisor,
            {
                "chat_expert": "chat_expert",
                "execute_direct": "execute_direct",
                "router": "router",
            }
        )

        # Chat Subgraph → call_model
        graph.add_edge("chat_expert", "call_model")

        # 直接执行路径（旧）
        graph.add_edge("execute_direct", "call_model")

        # 规划路径（旧）：router → retrieve 或 plan
        graph.add_conditional_edges(
            "router",
            should_retrieve,
            {"retrieve": "retrieve", "plan": "plan"}
        )
        graph.add_edge("retrieve", "plan")

        # 任务执行路径（旧）
        graph.add_edge("plan", "execute_task")
        graph.add_edge("execute_task", "check_task_complete")
        graph.add_conditional_edges(
            "check_task_complete",
            should_continue_tasks,
            {"execute_task": "execute_task", "call_model": "call_model"}
        )

        # 最终路径
        graph.add_edge("call_model", END)

        log("多 Agent 状态图构建完成（混合架构）", "MultiAgent")
        return graph


def _route_from_supervisor(state: Dict[str, Any]) -> str:
    """
    Supervisor 条件路由辅助函数

    与 supervisor_node 共享 SUPERVISOR_ROUTE_TABLE，保持一致。
    路由优先级（最重意图优先）：
      1. 无意图 → chat_expert
      2. 有复杂意图 → router（规划路径可处理所有意图）
      3. 有可执行意图 → execute_direct
      4. 仅对话意图 → chat_expert
    """
    intents = state.get("intents", [])

    if not intents:
        return "chat_expert"

    info = classify_intents(intents)
    target, _ = resolve_route(info, SUPERVISOR_ROUTE_TABLE, fallback="chat_expert")
    return target
