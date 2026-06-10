"""
Chat Expert 插件

处理简单闲聊、问候、简单问答等对话意图，以及系统指令（帮助、退出等）。
统一 Planner 路由后，chat_expert 始终由 Planner 通过 Send API 调度，
只生成纯内容，润色和整合由 MergeNode 统一处理。

Manifest 驱动：routing/prompt/intents 从 PLUGIN.yaml 加载，
静态意图（chat + system）由基类自动注册，无需手写。
"""

from typing import Dict, Any, List

from modules.logger import log
from modules.langgraph.multi_agent.plugin_base import ExpertPlugin
from modules.langgraph.multi_agent.helpers import (
    build_base_context,
    inject_no_tool_hint,
)


class ChatPlugin(ExpertPlugin):
    """对话生成插件"""

    def __init__(self, manifest):
        """
        初始化 Chat 插件

        Args:
            manifest: PluginManifest 实例，从 PLUGIN.yaml 加载
        """
        super().__init__(manifest)

    def on_activate(self, context: Dict[str, Any]):
        """
        激活回调：使用外部注入的通用 Agent

        Args:
            context: 共享资源上下文，包含 base_agent
        """
        self._agent = context.get("base_agent")
        log("[ChatPlugin] 使用外部 Agent", "Plugin")

    def register_intents(self, intent_registry) -> int:
        """
        注册意图

        静态意图（chat + system）由基类从 Manifest 自动注册，
        无需手写。此方法直接调用 super()。

        Args:
            intent_registry: IntentRegistry 实例

        Returns:
            注册的意图数量
        """
        return super().register_intents(intent_registry)

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行对话生成

        Args:
            state: LangGraph 状态（query, intents, __subtask_idx__ 等）

        Returns:
            状态更新字典，包含 agent_results 和 chat_history
        """
        query = state["query"]
        intents = state.get("intents", [])

        # 优先使用 intent content 作为实际查询
        actual_query = intents[0].get("content", query) if intents else query

        # 如果意图类别为 chat（Planner 已确认无匹配能力），注入无工具提示
        if any(i.get("category") == "chat" for i in intents):
            actual_query = inject_no_tool_hint(actual_query)
            log("[ChatPlugin] chat 类别意图，注入无工具提示", "Plugin")

        log(f"[ChatPlugin] 处理对话: {actual_query[:30]}...", "Plugin")

        context = build_base_context(state)
        answer = self._invoke_agent(self._agent, actual_query, context, started_detail=f"处理：{query[:40]}")
        log(f"[ChatPlugin] 完成: {answer[:50]}...", "Plugin")

        # Chat 特有：无 intent_results
        return self._build_result(answer, state)
