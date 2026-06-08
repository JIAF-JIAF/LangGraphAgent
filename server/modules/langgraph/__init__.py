"""
LangGraph 模块

提供基于 LangGraph 的 Agent 实现，支持：
- 任务规划：将复杂需求拆分为子任务
- 状态持久化：通过 Checkpointer 管理会话状态
- 技能执行：通过 LangChain Agent tool calling 自动调用技能
- 意图执行：通过 ExecutorRegistry 管理各类意图执行器

架构设计（多 Agent 架构）：
- agent.py：主入口，负责组件初始化和图编译
- nodes/：前置节点定义（feeling_detect, intent_recognize）
- multi_agent/：多 Agent 协作模块（Supervisor, Expert, Planner, Merge）
"""

from .agent import LangGraphAgent
from .state import AgentState
from .executors import ExecutorRegistry
from .nodes import FeelingNode, IntentRecognizeNode

__all__ = [
    "LangGraphAgent",
    "AgentState",
    "ExecutorRegistry",
    "FeelingNode",
    "IntentRecognizeNode",
]
