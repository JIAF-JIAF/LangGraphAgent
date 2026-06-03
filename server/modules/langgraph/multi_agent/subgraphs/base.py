"""
Expert 基类

仅提供 _build_input 公共逻辑，子类继承后保持各自的 __call__ 等实现。
"""

from typing import Dict, Any, List


class BaseExpertNode:
    """
    Expert 节点基类

    仅提供 _build_input 公共逻辑。
    子类需设置 target_prefix / single_hint / multi_hint，可覆写 _build_input。
    """

    target_prefix: str = ""
    single_hint: str = ""
    multi_hint: str = ""

    def _build_input(self, query: str, intents: List[Dict[str, Any]]) -> str:
        """
        构建 Agent 输入

        只使用当前 Expert 相关类别的意图内容，避免其他类别意图污染。
        子类可覆写此方法实现自定义逻辑（如 Planner）。

        Args:
            query: 用户原始查询
            intents: 当前 Expert 相关类别的意图列表

        Returns:
            构建后的 Agent 输入文本
        """
        if not intents:
            return query

        if len(intents) == 1:
            return self._build_single_intent_input(query, intents[0])
        return self._build_multi_intent_input(query, intents)

    def _build_single_intent_input(self, query: str, intent: Dict[str, Any]) -> str:
        """
        构建单意图输入：用 hint 引导 Agent 聚焦到具体目标

        示例输出（RAG Expert）：
            "请在 exams 知识库中检索以下内容\n行测蒙题技巧"

        Args:
            query: 用户原始查询
            intent: 单个意图对象

        Returns:
            构建后的 Agent 输入文本
        """
        parts = []
        target = intent.get("target", "").replace(self.target_prefix, "")
        content = intent.get("content", "")
        if target:
            parts.append(self.single_hint.format(target=target))
        parts.append(content if content else query)
        return "\n".join(parts)

    def _build_multi_intent_input(self, query: str, intents: List[Dict[str, Any]]) -> str:
        """
        构建多意图输入：列出所有意图，让 Agent 依次处理

        示例输出（MCP Expert）：
            "请完成以下工具调用任务：
              1. [weather] 查询杭州天气
              2. [weather_recommend] 推荐游玩地点"

        Args:
            query: 用户原始查询
            intents: 意图列表

        Returns:
            构建后的 Agent 输入文本
        """
        parts = [self.multi_hint]
        for i, intent in enumerate(intents, 1):
            target = intent.get("target", "").replace(self.target_prefix, "")
            content = intent.get("content", "")
            if target:
                parts.append(f"  {i}. [{target}] {content}")
            else:
                parts.append(f"  {i}. {content}")
        return "\n".join(parts)
