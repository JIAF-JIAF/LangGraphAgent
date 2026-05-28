"""
模型调用节点

负责生成最终回答，更新对话历史。
"""

from typing import Dict, Any
from modules.logger import log
from ..context_builder import ContextBuilder
from ..refiners import RefineContext, RefinerRegistry


class CallModelNode:
    """调用模型节点"""

    def __init__(self, agent: Any, refiners: Dict[str, Any]):
        """
        初始化模型调用节点
        
        Args:
            agent: LangChain Agent 实例
            refiners: 精炼器注册表
        """
        self._agent = agent
        self._refiners = refiners

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成最终回答，更新对话历史
        
        Args:
            state: 当前状态（包含 query, answer, chat_history, feeling, intent_results）
        
        Returns:
            更新后的状态（包含最终回答和新消息增量）
        """
        query = state["query"]
        answer = state.get("answer", "")
        chat_history = state.get("chat_history", [])
        feeling = state["feeling"]
        intent_results = state.get("intent_results", [])

        log(f"[节点: call_model] 开始执行，回答长度: {len(answer)}，对话历史长度: {len(chat_history)}，意图结果数量: {len(intent_results)}", "LangGraph")
        
        context = RefineContext.from_state(state)
        answer = RefinerRegistry.refine(context, self._agent, self._refiners)

        log(f"[节点: call_model] 执行完成: {answer[:50]}...", "LangGraph")

        return {
            "answer": answer,
            "feeling": feeling,
            "chat_history": ContextBuilder.build_chat_history(query, answer)
        }
