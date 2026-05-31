"""
Chat Agent Subgraph

处理闲聊、系统指令、情绪响应等简单对话。
直接调用 Agent + RefinerRegistry 生成回答，与旧 CallModelNode 逻辑一致。

设计说明：
  - 不使用独立 SubgraphState，直接复用 MultiAgentState
  - 原因：Subgraph 编译后作为主图节点，LangGraph 按字段名自动映射
  - Chat 节点需要访问 feeling、chat_history 等字段，独立状态会导致丢失
  - 复用 CallModelNode 的 RefinerRegistry 润色流程，保证回答质量不降
"""

from typing import Dict, Any, List
from langgraph.graph import StateGraph, START, END
from langgraph.config import get_stream_writer
from modules.logger import log
from modules.langgraph.nodes.steps import Step
from modules.langgraph.context_builder import ContextBuilder
from modules.langgraph.refiners import RefineContext, RefinerRegistry
from modules.langgraph.multi_agent.states import MultiAgentState


class ChatRespondNode:
    """
    Chat 响应节点

    与 CallModelNode 逻辑一致：
      1. 从 state 构建 RefineContext
      2. 通过 RefinerRegistry.refine() 选择合适的润色器
      3. 调用 agent 生成回答
      4. 构建 chat_history 增量
    """

    def __init__(self, agent, refiners):
        self._agent = agent
        self._refiners = refiners

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        writer = get_stream_writer()
        query = state["query"]
        feeling = state["feeling"]

        writer(Step.CHAT_EXPERT.started_event())
        log(f"[ChatExpert] 处理对话: {query[:30]}...", "MultiAgent")

        context = RefineContext.from_state(state)
        answer = RefinerRegistry.refine(context, self._agent, self._refiners)

        writer(Step.CHAT_EXPERT.completed_event())
        log(f"[ChatExpert] 完成: {answer[:50]}...", "MultiAgent")

        return {
            "answer": answer,
            "current_agent": "chat_expert",
            "feeling": feeling,
            "chat_history": ContextBuilder.build_chat_history(query, answer),
        }


def create_chat_subgraph(agent, refiners: List) -> StateGraph:
    """
    创建 Chat Agent Subgraph

    Args:
        agent: LangChain Agent 实例
        refiners: 润色器实例列表

    Returns:
        编译后的 Chat Subgraph（可直接 add_node 到主图）
    """
    graph = StateGraph(MultiAgentState)
    graph.add_node("chat_respond", ChatRespondNode(agent, refiners))
    graph.add_edge(START, "chat_respond")
    graph.add_edge("chat_respond", END)

    return graph.compile(name="chat_expert")
