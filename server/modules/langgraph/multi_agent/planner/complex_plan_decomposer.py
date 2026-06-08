"""
Complex Plan 分解器

负责将 complex_plan 意图通过 LLM 分解为子任务列表。
独立于 PlannerDecomposeNode，职责单一：LLM 调用 + 结果转换。

使用方式：
    decomposer = ComplexPlanDecomposer(ai_client, plugin_registry)
    subtasks = decomposer.decompose(plan_intent, existing_count=3)
"""

from typing import Dict, Any, List, Optional
from modules.logger import log
from modules.langgraph.multi_agent.planner.prompts import DECOMPOSE_PROMPT
from modules.langgraph.multi_agent.planner.models import TaskDecomposition


class ComplexPlanDecomposer:
    """
    Complex Plan 分解器

    将 complex_plan 意图通过 LLM 独立分解为子任务列表。
    每个复杂意图独立调用 LLM，保证分解质量不受上下文干扰。

    Attributes:
        _ai_client: AIClient 实例，用于调用 with_structured_output
        _plugin_registry: PluginRegistry 实例，用于动态获取能力描述
    """

    def __init__(self, ai_client, plugin_registry):
        """
        Args:
            ai_client: AIClient 实例，用于调用 with_structured_output
            plugin_registry: PluginRegistry 实例，用于动态获取能力描述
        """
        self._ai_client = ai_client
        self._plugin_registry = plugin_registry

    def decompose(self, plan_intent: Dict[str, Any], existing_count: int) -> List[Dict[str, Any]]:
        """
        分解单个 complex_plan 意图为子任务列表

        Args:
            plan_intent: 单个 complex_plan 意图
            existing_count: 已有子任务数量（用于偏移 depends_on 索引）

        Returns:
            分解后的子任务列表（depends_on 已偏移为全局索引）
        """
        content = plan_intent.get("content", "")
        if not content:
            return []

        log(f"[ComplexPlanDecomposer] 分解: {content[:40]}...", "MultiAgent")

        decomposition = self._invoke_llm(content)
        if decomposition is None:
            log(f"[ComplexPlanDecomposer] 分解失败，回退为 chat 子任务: {content[:30]}...", "MultiAgent")
            return [{
                "description": content,
                "category": "chat",
                "depends_on": [],
            }]

        subtasks = self._convert_decomposition(decomposition, existing_count)
        self._log_subtasks(subtasks, prefix=f"分解完成({decomposition.reasoning[:30]}...)")

        return subtasks

    def _invoke_llm(self, query: str) -> Optional[TaskDecomposition]:
        """
        调用 LLM 进行任务分解

        Args:
            query: 待分解的用户请求

        Returns:
            TaskDecomposition 实例，失败返回 None
        """
        capability_descriptions = self._plugin_registry.build_capability_descriptions()
        prompt = DECOMPOSE_PROMPT.format(
            query=query,
            capability_descriptions=capability_descriptions,
        )

        try:
            structured_llm = self._ai_client.chat.with_structured_output(
                TaskDecomposition, method="json_mode"
            )
            return structured_llm.invoke(prompt)
        except Exception as e:
            log(f"[ComplexPlanDecomposer] LLM 调用失败: {e}", "MultiAgent")
            return None

    @staticmethod
    def _convert_decomposition(decomposition: TaskDecomposition, existing_count: int) -> List[Dict[str, Any]]:
        """
        将 TaskDecomposition 转换为子任务字典列表，并偏移 depends_on 索引

        Args:
            decomposition: LLM 返回的分解结果
            existing_count: 已有子任务数量

        Returns:
            子任务字典列表（depends_on 已偏移为全局索引）
        """
        subtasks = []
        for sub in decomposition.subtasks:
            sub_dict = sub.model_dump()
            sub_dict["depends_on"] = [d + existing_count for d in sub_dict.get("depends_on", [])]
            subtasks.append(sub_dict)
        return subtasks

    @staticmethod
    def _log_subtasks(subtasks: List[Dict[str, Any]], prefix: str = ""):
        """
        记录子任务列表日志

        Args:
            subtasks: 子任务列表
            prefix: 日志前缀描述
        """
        log(f"[ComplexPlanDecomposer] {prefix} {len(subtasks)} 个子任务", "MultiAgent")
        for i, sub in enumerate(subtasks):
            deps = sub.get("depends_on", [])
            log(
                f"[ComplexPlanDecomposer]   [{i}]: category={sub['category']}, "
                f"depends_on={deps}, desc={sub['description'][:40]}...",
                "MultiAgent",
            )
