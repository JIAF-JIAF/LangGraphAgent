"""
RAG Expert 节点

处理知识库检索意图。使用领域专精 Agent（只绑定 RAG 工具），
LLM-in-the-loop 自动完成知识库选择、检索和答案生成。

核心设计：
  - LLM-in-the-loop：知识库选择和检索策略由 LLM 决定
  - 工具隔离：Agent 只看到 RAG 工具，从根源杜绝工具幻觉
  - 意图即上下文：将意图信息（含知识库名称）作为 Agent 输入提示
  - 无 fallback：检索失败则明确报告，不回退到其他路径
  - 结果写入 agent_results：由 Merge 节点统一润色，不直接写 answer
"""

from typing import Dict, Any, List
from langgraph.config import get_stream_writer
from modules.logger import log
from modules.context import AgentContext
from modules.langgraph.nodes.steps import Step
from modules.langgraph.multi_agent.subgraphs.base import BaseExpertNode


class RAGExpertNode(BaseExpertNode):
    """
    RAG Expert 节点

    调用领域专精 Agent 执行知识库检索和答案生成。
    Agent 内部通过 ReAct 循环完成知识库选择、检索和生成。
    """

    target_prefix = "knowledge_base:"
    single_hint = "请在 {target} 知识库中检索以下内容"
    multi_hint = "请检索以下内容："

    def __init__(self, agent):
        """
        Args:
            agent: RAG 领域专精 Agent 实例（只绑定 RAG 工具）
        """
        self._agent = agent

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行 RAG 知识库检索

        Args:
            state: 当前状态（包含 query、intents、session_id 等）

        Returns:
            更新后的状态（包含 agent_results）
        """
        writer = get_stream_writer()
        query = state["query"]
        intents = state.get("intents", [])
        rag_intents = [i for i in intents if i.get("category") == "rag"]

        input_text = self._build_input(query, rag_intents)

        writer(Step.RAG_EXPERT.started_event())
        log(f"[RAGExpert] 处理 RAG 意图: {len(rag_intents)} 个, 输入: {input_text[:50]}...", "MultiAgent")

        agent_context = AgentContext(
            session_id=state.get("session_id", "default"),
            chat_history=state.get("chat_history", []),
            feeling=state.get("feeling", {}),
        )

        try:
            result = self._agent.invoke(input_text, agent_context)
            answer = result.get("answer", "")
        except Exception as e:
            error_msg = str(e)
            log(f"[RAGExpert] LLM 调用异常: {error_msg}", "MultiAgent")
            if "DataInspectionFailed" in error_msg or "inappropriate content" in error_msg.lower():
                answer = "抱歉，该话题的内容触发了平台内容安全审查，暂无法提供回答，请尝试其他问题。"
            else:
                answer = f"知识库查询过程中出现异常：{error_msg}，请稍后重试。"

        intent_results = [
            {
                "type": "rag",
                "target": intent.get("target", ""),
                "content": answer,
                "success": True,
            }
            for intent in rag_intents
        ]

        writer(Step.RAG_EXPERT.completed_event())
        log(f"[RAGExpert] 完成: {answer[:50]}...", "MultiAgent")

        return self._build_result(
            state, 
            "rag_expert",
             answer, 
             intent_results
        )


def create_rag_expert(agent):
    """
    创建 RAG Expert 节点函数

    Args:
        agent: RAG 领域专精 Agent 实例

    Returns:
        RAGExpertNode 实例（可直接 add_node 到主图）
    """
    return RAGExpertNode(agent)
