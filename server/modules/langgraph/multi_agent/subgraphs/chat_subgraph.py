"""
Chat Agent 节点

处理闲聊、系统指令、情绪响应等简单对话。
直接调用 Agent + RefinerRegistry 生成回答，与旧 CallModelNode 逻辑一致。

设计说明：
  - 使用 RefinerRegistry 润色流程，保证回答质量不降
  - 结果写入 agent_results：由 Merge 节点统一处理
  - chat_history 有 add_messages_with_truncation reducer，并行写入安全

注意：不使用编译后的 Subgraph，直接使用节点函数。
  编译后的 Subgraph 会将 MultiAgentState 的所有字段映射回主图 state，
  导致并行执行时 query 等无 reducer 字段冲突。
"""

from typing import Dict, Any, List
from langgraph.config import get_stream_writer
from modules.logger import log
from modules.langgraph.nodes.steps import Step
from modules.langgraph.context_builder import ContextBuilder
from modules.langgraph.refiners import RefineContext, RefinerRegistry


class ChatExpertNode:
    """
    Chat Expert 节点

    与 CallModelNode 逻辑一致：
      1. 从 state 构建 RefineContext
      2. 通过 RefinerRegistry.refine() 选择合适的润色器
      3. 调用 agent 生成回答
      4. 构建 chat_history 增量
    """

    def __init__(self, agent, refiners):
        """
        Args:
            agent: LangChain Agent 实例
            refiners: 润色器实例列表
        """
        self._agent = agent
        self._refiners = refiners

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行对话处理

        Args:
            state: 当前状态（包含 query、chat_history、feeling 等）

        Returns:
            更新后的状态（包含 agent_results 和 chat_history）
        """
        writer = get_stream_writer()
        query = state["query"]

        writer(Step.CHAT_EXPERT.started_event())
        log(f"[ChatExpert] 处理对话: {query[:30]}...", "MultiAgent")

        context = RefineContext.from_state(state)
        answer = RefinerRegistry.refine(context, self._agent, self._refiners)

        writer(Step.CHAT_EXPERT.completed_event())
        log(f"[ChatExpert] 完成: {answer[:50]}...", "MultiAgent")

        return {
            "agent_results": [{"agent": "chat_expert", "answer": answer}],
            "chat_history": ContextBuilder.build_chat_history(query, answer),
        }


def create_chat_expert(agent, refiners: List):
    """
    创建 Chat Expert 节点函数

    Args:
        agent: LangChain Agent 实例
        refiners: 润色器实例列表

    Returns:
        Chat Expert 节点函数（可直接 add_node 到主图）
    """
    return ChatExpertNode(agent, refiners)
