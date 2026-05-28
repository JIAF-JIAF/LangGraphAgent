"""
LangGraph 模块

提供基于 LangGraph 的 Agent 实现，支持：
- 任务规划：将复杂需求拆分为子任务
- 状态持久化：通过 Checkpointer 管理会话状态
- 技能执行：通过 LangChain Agent tool calling 自主调用技能
- 意图执行：通过 ExecutorRegistry 管理各类意图执行器
- 回答润色：通过 RefinerRegistry 管理各类润色器

架构设计（P0级改造后）：
- agent.py：主入口，负责组件初始化和图编译
- nodes/：节点定义模块（单一职责）
- edges.py：条件路由函数
- graph.py：图构建器
- context_builder.py：上下文构建
- task_generators/：任务生成策略
"""

from .agent import LangGraphAgent
from .state import AgentState
from .planner import TaskPlanner
from .executors import ExecutorRegistry
from .refiners import RefinerRegistry
from .graph import GraphBuilder
from .nodes import (
    FeelingNode,
    IntentRecognizeNode,
    IntentRouterNode,
    ExecuteDirectNode,
    ExecuteTaskNode,
    CheckTaskCompleteNode,
    RouterNode,
    RetrieveNode,
    PlanNode,
    CallModelNode,
)

__all__ = [
    "LangGraphAgent",
    "AgentState",
    "TaskPlanner",
    "ExecutorRegistry",
    "RefinerRegistry",
    "GraphBuilder",
    "FeelingNode",
    "IntentRecognizeNode",
    "IntentRouterNode",
    "ExecuteDirectNode",
    "ExecuteTaskNode",
    "CheckTaskCompleteNode",
    "RouterNode",
    "RetrieveNode",
    "PlanNode",
    "CallModelNode",
]
