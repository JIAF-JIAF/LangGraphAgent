"""
可执行意图分解器

负责将可执行意图（mcp/skill/rag/chat/system）直接构建为子任务列表。
无需 LLM 调用，纯规则映射。

与 ComplexPlanDecomposer 对称：
  - ExecutableIntentDecomposer：规则映射，无 LLM
  - ComplexPlanDecomposer：LLM 分解，保留完整规划能力

使用方式：
    decomposer = ExecutableIntentDecomposer(plugin_registry)
    subtasks = decomposer.decompose(executable_intents)
"""

from typing import Dict, Any, List
from modules.logger import log


class ExecutableIntentDecomposer:
    """
    可执行意图分解器

    将可执行意图按类别分组，
    同一类别的多个意图合并为一个子任务（该 Expert 内部会串行处理）。
    纯规则映射，无需 LLM 调用。

    可执行类别从 plugin_registry 动态获取，新增插件时无需修改此代码。
    """

    def __init__(self, plugin_registry):
        """
        Args:
            plugin_registry: PluginRegistry 实例，用于动态获取可执行类别
        """
        self._plugin_registry = plugin_registry

    def decompose(self, intents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从可执行意图直接构建子任务列表

        同一类别的多个意图合并为一个子任务（该 Expert 内部会串行处理）。

        Args:
            intents: 可执行意图列表

        Returns:
            子任务列表
        """
        executable_categories = self._plugin_registry.build_executable_categories()
        category_data = self._group_intents_by_category(intents, executable_categories)

        subtasks = []
        for cat, data in category_data.items():
            subtask_category = "chat" if cat in ("chat", "system") else cat
            subtasks.append({
                "description": "；".join(data["contents"]),
                "category": subtask_category,
                "depends_on": [],
                "targets": data["targets"],
            })

        self._log_subtasks(subtasks, prefix="可执行意图构建")
        return subtasks

    @staticmethod
    def _group_intents_by_category(intents: List[Dict[str, Any]], executable_categories: set) -> Dict[str, Dict[str, Any]]:
        """
        按类别分组可执行意图

        同一类别的意图合并为一条记录，保留 contents 和 targets 列表。
        chat 和 system 意图合并到同一组（统一由 chat_expert 处理）。

        Args:
            intents: 可执行意图列表
            executable_categories: 从插件注册表动态获取的可执行类别集合

        Returns:
            {category: {"contents": [...], "targets": [...]}}
        """
        category_data: Dict[str, Dict[str, Any]] = {}

        for intent in intents:
            cat = intent.get("category", "")
            group_key = "chat" if cat in ("chat", "system") else cat

            if group_key not in executable_categories:
                continue

            content = intent.get("content", "")
            target = intent.get("target", "")

            if group_key not in category_data:
                category_data[group_key] = {"contents": [], "targets": []}

            category_data[group_key]["contents"].append(content)
            category_data[group_key]["targets"].append(target)

        return category_data

    @staticmethod
    def _log_subtasks(subtasks: List[Dict[str, Any]], prefix: str = ""):
        """
        记录子任务列表日志

        Args:
            subtasks: 子任务列表
            prefix: 日志前缀描述
        """
        log(f"[ExecutableIntentDecomposer] {prefix} {len(subtasks)} 个子任务", "MultiAgent")
        for i, sub in enumerate(subtasks):
            deps = sub.get("depends_on", [])
            log(
                f"[ExecutableIntentDecomposer]   子任务[{i}]: category={sub['category']}, "
                f"depends_on={deps}, desc={sub['description'][:40]}...",
                "MultiAgent",
            )
