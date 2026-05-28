"""
图构建模块

负责构建 LangGraph 状态图，定义节点和边的连接关系。
"""

from typing import Any
from langgraph.graph import StateGraph, END, START
from modules.logger import log
from .states import AgentState
from .nodes.feeling import FeelingNode
from .nodes.intent import IntentRecognizeNode, IntentRouterNode
from .nodes.execute import ExecuteDirectNode, ExecuteTaskNode, CheckTaskCompleteNode
from .nodes.rag import RouterNode, RetrieveNode
from .nodes.plan import PlanNode
from .nodes.model import CallModelNode
from .edges import route_by_intent, should_retrieve, should_continue_tasks


class GraphBuilder:
    """状态图构建器"""

    def __init__(
        self,
        feeling_detector: Any,
        intent_router: Any,
        rag_workflow: Any,
        task_planner: Any,
        agent: Any,
        executors: Any,
        refiners: Any,
    ):
        """
        初始化图构建器
        
        Args:
            feeling_detector: 情绪检测器实例
            intent_router: 意图路由器实例
            rag_workflow: RAG工作流实例
            task_planner: 任务规划器实例
            agent: LangChain Agent 实例
            executors: 执行器注册表
            refiners: 精炼器注册表
        """
        self._feeling_node = FeelingNode(feeling_detector)
        self._intent_recognize_node = IntentRecognizeNode(intent_router)
        self._intent_router_node = IntentRouterNode()
        self._execute_direct_node = ExecuteDirectNode(executors)
        self._router_node = RouterNode(rag_workflow)
        self._retrieve_node = RetrieveNode(rag_workflow)
        self._plan_node = PlanNode(task_planner)
        self._execute_task_node = ExecuteTaskNode(agent)
        self._check_node = CheckTaskCompleteNode(task_planner)
        self._call_model_node = CallModelNode(agent, refiners)

    def build(self):
        """
        构建状态图
        
        流程图：
        START → feeling_detect → intent_recognize → intent_router → ┌── direct ──→ execute_direct → call_model
                                                                    │
                                                                    ├── plan ──→ router → ┌── retrieve → plan
                                                                    │                      │
                                                                    │                      └── plan
                                                                    │                              │
                                                                    └── system ──→ call_model      ▼
                                                                                        execute_task → check → call_model
        
        Returns:
            未编译的 StateGraph 实例
        """
        log("开始构建 LangGraph 状态图...", "LangGraph")
        self._graph = StateGraph(AgentState)

        # 添加节点
        self._graph.add_node("feeling_detect", self._feeling_node)
        self._graph.add_node("intent_recognize", self._intent_recognize_node)
        self._graph.add_node("intent_router", self._intent_router_node)
        self._graph.add_node("execute_direct", self._execute_direct_node)
        self._graph.add_node("router", self._router_node)
        self._graph.add_node("retrieve", self._retrieve_node)
        self._graph.add_node("plan", self._plan_node)
        self._graph.add_node("execute_task", self._execute_task_node)
        self._graph.add_node("check_task_complete", self._check_node)
        self._graph.add_node("call_model", self._call_model_node)

        # 基础流程：情绪检测 -> 意图识别 -> 意图路由
        self._graph.add_edge(START, "feeling_detect")
        self._graph.add_edge("feeling_detect", "intent_recognize")
        self._graph.add_edge("intent_recognize", "intent_router")

        # 意图路由分支：direct / plan / system
        self._graph.add_conditional_edges(
            "intent_router",
            route_by_intent,
            {
                "direct": "execute_direct", 
                "plan": "router", 
                "system": "call_model",
            }
        )

        # 直接执行路径
        self._graph.add_edge("execute_direct", "call_model")

        # 规划路径：路由 -> 检索或直接规划
        self._graph.add_conditional_edges(
            "router",
            should_retrieve,
            {"retrieve": "retrieve", "plan": "plan"}
        )

        # RAG 路径：检索后直接进入规划
        self._graph.add_edge("retrieve", "plan")

        # 任务执行主路径
        self._graph.add_edge("plan", "execute_task")
        self._graph.add_edge("execute_task", "check_task_complete")

        # 任务完成检查后的条件分支
        self._graph.add_conditional_edges(
            "check_task_complete",
            should_continue_tasks,
            {"execute_task": "execute_task", "call_model": "call_model"}
        )

        # 最终路径
        self._graph.add_edge("call_model", END)

        return self._graph
