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
  - Chat Expert 只生成纯内容（不润色），Merge 统一润色
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from langgraph.config import get_stream_writer
from modules.logger import log
from modules.langgraph.nodes.steps import Step
from modules.langgraph.context_builder import ContextBuilder
from modules.langgraph.multi_agent.thinking_streamer import ThinkingStreamer


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

MERGE_CHAT_EXPERTS_PROMPT = """你是一个回答整合专家。以下是多个子任务专家分别给出的回答，请将它们整合为一个连贯、完整的回复。

关键规则：
1. **保留所有详细内容**：每个子任务的回答都包含重要信息，不要省略或压缩任何实质性内容
2. **去除重复**：多个子任务可能有重复的开场白、寒暄语或结尾，只保留一次
3. **逻辑组织**：按子任务顺序组织内容，确保整体结构清晰连贯
4. **统一语气**：保持一致的语气风格，符合角色设定
5. **不要编造**：只基于提供的子任务回答生成回复，不要添加新内容
6. 你的角色设计：23岁女性，来自中国，热心帮助别人，喜欢跑步和看书，你的父亲是tomiezhang

当前日期：{current_date}
用户情绪：{feeling_name}（强度：{feeling_score}）

用户原始查询：{query}

子任务回答：
{content}

请整合以上子任务回答，生成一个完整、连贯的回复（保留所有详细内容）："""


class MergeNode:
    """
    Merge 节点

    合并各 Expert 的 agent_results，统一润色生成最终回答。
    使用纯 LLM（无工具）润色，避免 Agent ReAct 循环中的工具幻觉。
    """

    def __init__(self, ai_client=None, plugin_registry=None):
        """
        Args:
            ai_client: AIClient 实例（纯 LLM，用于润色，不绑定工具）
            plugin_registry: PluginRegistry 实例（用于获取默认回退 Expert 名称）
        """
        self._ai_client = ai_client
        self._plugin_registry = plugin_registry

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        合并各 Expert 结果并润色生成最终回答

        Args:
            state: 当前状态（包含 query、agent_results、feeling 等）

        Returns:
            更新后的状态（包含 answer、intent_results、chat_history）
        """
        writer = get_stream_writer()
        query = state["query"]
        agent_results = state.get("agent_results", [])

        writer(Step.MERGE.started_event(detail=f"合并 {len(agent_results)} 个 Expert 结果"))
        log(f"[MergeNode] 合并 {len(agent_results)} 个 Expert 结果", "MultiAgent")

        # 统一 Planner 路由后，所有 Expert 结果都带有 subtask_idx
        # 默认回退 Expert（通常是 chat_expert）只生成纯内容（不润色），需要由 MergeNode 统一润色
        default_expert_name = self._get_default_expert_name()
        if len(agent_results) == 1 and agent_results[0].get("agent") == default_expert_name:
            # 单个 chat_expert 结果，需要润色（chat_expert 只生成了纯内容）
            answer = self._refine_single_chat(query, agent_results[0], state)
            log(f"[MergeNode] 单个 Chat Expert 结果润色完成", "MultiAgent")
        elif len(agent_results) > 1:
            # 多个子任务结果，用 LLM 整合润色（保留详细内容）
            answer = self._merge_and_refine_subtasks(query, agent_results, state)
            log(f"[MergeNode] 子任务结果整合润色: {answer[:50]}...", "MultiAgent")
        else:
            # 单个非 chat_expert 结果，走通用润色
            intent_results = self._collect_intent_results(agent_results)
            content_parts = []
            for i, result in enumerate(intent_results):
                result_type = result.get("type", "unknown").upper()
                content = result.get("content", "")
                if content:
                    content_parts.append(f"【{i+1}. {result_type}】\n{content}")

            combined_content = "\n\n".join(content_parts)
            answer = self._refine_with_llm(query, combined_content, state)
            log(f"[MergeNode] 润色完成: {answer[:50]}...", "MultiAgent")

        writer(Step.MERGE.completed_event(detail=f"完成（{len(answer)} 字）"))

        return {
            "answer": answer,
            "intent_results": self._collect_intent_results(agent_results),
            "chat_history": ContextBuilder.build_chat_history(query, answer),
        }

    def _refine_single_chat(
        self, query: str, agent_result: Dict[str, Any], state: Dict[str, Any]
    ) -> str:
        """
        润色单个默认回退 Expert 结果

        统一 Planner 路由后，默认回退 Expert 只生成纯内容（不润色），
        需要由 MergeNode 统一润色，保证回答质量一致。

        Args:
            query: 用户原始查询
            agent_result: 单个 Expert 结果
            state: 当前状态

        Returns:
            润色后的回答
        """
        raw_answer = agent_result.get("answer", "")
        if not raw_answer:
            return ""

        return self._refine_with_llm(query, raw_answer, state)

    def _get_default_expert_name(self) -> str:
        """
        获取默认回退 Expert 名称

        从 PluginRegistry 的 Manifest 获取，
        替代硬编码的 "chat_expert"。

        Returns:
            默认回退 Expert 名称
        """
        if self._plugin_registry:
            return self._plugin_registry.get_default_fallback_expert_name()
        return "chat_expert"

    def _merge_and_refine_subtasks(
        self, query: str, agent_results: List[Dict[str, Any]], state: Dict[str, Any]
    ) -> str:
        """
        整合润色多个子任务结果（Planner 分解的子任务）

        子任务只生成了纯内容（未润色），这里统一整合和润色：
          1. 按 subtask_idx 排序，拼接所有子任务回答
          2. 使用 MERGE_CHAT_EXPERTS_PROMPT 让 LLM 整合润色
          3. 保留所有详细内容，去除重复寒暄，统一语气

        支持混合 Expert 类型（chat_expert + skill_expert + mcp_expert 等），
        非 chat_expert 的结果从 intent_results 中提取内容。

        Args:
            query: 用户原始查询
            agent_results: 各 Expert 返回的结果列表
            state: 当前状态（用于提取 feeling 等上下文）

        Returns:
            整合润色后的最终回答
        """
        # 按 subtask_idx 排序，确保顺序正确
        sorted_results = sorted(
            agent_results,
            key=lambda ar: ar.get("subtask_idx", 0)
        )

        # 拼接子任务回答
        content_parts = []
        for i, ar in enumerate(sorted_results):
            agent_name = ar.get("agent", "unknown")
            # chat_expert 直接取 answer
            answer = ar.get("answer", "")
            if answer:
                content_parts.append(f"【子任务 {i+1} - {agent_name}】\n{answer}")
            # 非 chat_expert 从 intent_results 取内容
            else:
                ir_list = ar.get("intent_results", [])
                for ir in ir_list:
                    ir_content = ir.get("content", "")
                    if ir_content:
                        content_parts.append(f"【子任务 {i+1} - {agent_name}】\n{ir_content}")

        combined_content = "\n\n".join(content_parts)

        # 使用 LLM 整合润色
        return self._refine_chat_experts_with_llm(query, combined_content, state)

    def _refine_chat_experts_with_llm(
        self, query: str, content: str, state: Dict[str, Any]
    ) -> str:
        """
        使用 MERGE_CHAT_EXPERTS_PROMPT 整合润色多个子任务回答

        Args:
            query: 用户原始查询
            content: 拼接后的子任务回答
            state: 当前状态

        Returns:
            整合润色后的回答
        """
        feeling = state.get("feeling", {})
        feeling_name = feeling.get("feeling", "neutral")
        feeling_score = feeling.get("score", 5)
        current_date = datetime.now().strftime("%Y年%m月%d日")

        prompt = MERGE_CHAT_EXPERTS_PROMPT.format(
            current_date=current_date,
            feeling_name=feeling_name,
            feeling_score=feeling_score,
            query=query,
            content=content,
        )

        try:
            return ThinkingStreamer.stream_llm_structured(
                self._ai_client.chat, prompt
            )
        except Exception as e:
            log(f"[MergeNode] Chat Experts 整合润色失败: {e}，使用原始拼接", "MultiAgent")
            return content

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
            return ThinkingStreamer.stream_llm_structured(
                self._ai_client.chat, prompt
            )
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
