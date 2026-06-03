"""
Merge 节点

合并所有 Expert 的 agent_results，统一润色后生成最终回答。

核心职责：
  1. 从 agent_results 收集各 Expert 的执行结果
  2. 将结果转换为 intent_results 格式
  3. 使用纯 LLM（无工具）润色生成最终回答，避免工具幻觉
  4. 更新 chat_history

设计说明：
  - 所有 Expert Subgraph 将结果写入 agent_results（operator.add reducer）
  - Merge 节点是所有 Expert 的汇聚点，确保回答质量一致
  - 使用 ai_client 直接调用 LLM 润色，不经过 Agent ReAct 循环
  - Chat Expert 已自行润色，Merge 直接取其 answer
"""

from typing import Dict, Any, List, Optional
from langgraph.config import get_stream_writer
from modules.logger import log
from modules.langgraph.nodes.steps import Step
from modules.langgraph.context_builder import ContextBuilder


MERGE_REFINE_PROMPT = """你是一个回答润色专家。请根据以下信息，结合用户的情绪状态，生成一个自然、友好的回复。

重要规则：
1. 只需将执行结果用自然的语言组织成回复，不要调用任何工具
2. 如果有多个执行结果，按逻辑顺序组织，确保回答连贯
3. 注意语气要符合用户情绪
4. 不要编造信息，只基于提供的执行结果生成回复
5. 你的角色设计：23岁女性，来自中国，热心帮助别人，喜欢跑步和看书，你的父亲是tomiezhang

当前日期：{current_date}
用户情绪：{feeling_name}（强度：{feeling_score}）

用户查询：{query}

执行结果：
{content}

请生成自然、友好的回复："""


class MergeNode:
    """
    Merge 节点

    合并各 Expert 的 agent_results，统一润色生成最终回答。
    使用纯 LLM（无工具）润色，避免 Agent ReAct 循环中的工具幻觉。
    """

    def __init__(self, ai_client=None, refiners: Optional[List] = None):
        """
        Args:
            ai_client: AIClient 实例（纯 LLM，用于润色，不绑定工具）
            refiners: 润色器实例列表（保留兼容，实际不再使用）
        """
        self._ai_client = ai_client
        self._refiners = refiners or []

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        合并各 Expert 结果并润色生成最终回答

        Args:
            state: 当前状态（包含 query、agent_results、feeling 等）

        Returns:
            更新后的状态（包含 answer、intent_results、chat_history）
        """
        query = state["query"]
        agent_results = state.get("agent_results", [])

        writer(Step.CALL_MODEL.started_event())
        log(f"[MergeNode] 合并 {len(agent_results)} 个 Expert 结果", "MultiAgent")

        # 如果只有一个 Chat Expert 结果，直接使用（已润色）
        if len(agent_results) == 1 and agent_results[0].get("agent") == "chat_expert":
            answer = agent_results[0].get("answer", "")
            log(f"[MergeNode] Chat Expert 直接结果: {answer[:50]}...", "MultiAgent")
        else:
            # 收集所有 Expert 的 intent_results
            intent_results = self._collect_intent_results(agent_results)

            # 构建润色内容
            content_parts = []
            for i, result in enumerate(intent_results):
                result_type = result.get("type", "unknown").upper()
                content = result.get("content", "")
                if content:
                    content_parts.append(f"【{i+1}. {result_type}】\n{content}")

            combined_content = "\n\n".join(content_parts)

            # 使用纯 LLM 润色（不经过 Agent ReAct 循环，避免工具幻觉）
            answer = self._refine_with_llm(query, combined_content, state)
            log(f"[MergeNode] 润色完成: {answer[:50]}...", "MultiAgent")

        writer(Step.CALL_MODEL.completed_event())

        return {
            "answer": answer,
            "intent_results": self._collect_intent_results(agent_results),
            "chat_history": ContextBuilder.build_chat_history(query, answer),
        }

    def _refine_with_llm(self, query: str, content: str, state: Dict[str, Any]) -> str:
        """
        使用纯 LLM 润色（不经过 Agent ReAct 循环）

        直接调用 ai_client.chat，不绑定任何工具，从根源杜绝工具幻觉。

        Args:
            query: 用户原始查询
            content: 拼接后的各 Expert 执行结果文本
            state: 当前状态（用于提取 feeling 等上下文）

        Returns:
            润色后的最终回答文本
        """
        from datetime import datetime

        feeling = state.get("feeling", {})
        feeling_name = feeling.get("feeling", "neutral")
        feeling_score = feeling.get("score", 5)
        current_date = datetime.now().strftime("%Y年%m月%d日")

        prompt = MERGE_REFINE_PROMPT.format(
            current_date=current_date,
            feeling_name=feeling_name,
            feeling_score=feeling_score,
            query=query,
            content=content,
        )

        try:
            # 直接调用 LLM，不经过 Agent（无工具绑定）
            response = self._ai_client.chat.invoke(prompt)
            answer = response.content if hasattr(response, "content") else str(response)
            return answer
        except Exception as e:
            log(f"[MergeNode] LLM 润色失败: {e}，使用原始内容", "MultiAgent")
            # 润色失败时，直接拼接结果
            return content

    def _collect_intent_results(self, agent_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        收集所有 Expert 的 intent_results

        Args:
            agent_results: 各 Expert 返回的结果列表

        Returns:
            合并后的 intent_results 列表
        """
        results = []
        for ar in agent_results:
            ir_list = ar.get("intent_results", [])
            if ir_list:
                results.extend(ir_list)
            else:
                results.append({
                    "type": ar.get("agent", "unknown"),
                    "target": "",
                    "content": ar.get("answer", ""),
                    "success": True,
                })
        return results
