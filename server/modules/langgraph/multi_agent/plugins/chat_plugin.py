"""
Chat Expert 插件

处理简单闲聊、问候、简单问答等对话意图，以及系统指令（帮助、退出等）。
统一 Planner 路由后，chat_expert 始终由 Planner 通过 Send API 调度，
只生成纯内容，润色和整合由 MergeNode 统一处理。

插件化职责：
  - on_activate: 使用外部注入的通用 Agent
  - register_intents: 注册 chat 和 system 意图（system 意图路由到 chat_expert 处理）
  - execute: 执行对话生成
"""

from typing import Dict, Any, List

from modules.logger import log
from modules.langgraph.multi_agent.meta import ExpertMeta
from modules.langgraph.multi_agent.plugin_base import ExpertPlugin
from modules.langgraph.multi_agent.helpers import (
    build_base_context,
    inject_no_tool_hint,
)
from modules.intent.intent_types import IntentCategory, IntentConstants


class ChatPlugin(ExpertPlugin):
    """对话生成插件"""

    def __init__(self):
        """初始化 Chat 插件"""
        self._meta = ExpertMeta(
            name="chat_expert",
            category="chat",
            description="简单对话处理（闲聊、问候、简单问答）",
            icon="💬",
            label="对话 Agent",
            priority=50,
        )

    @property
    def meta(self) -> ExpertMeta:
        """
        插件元信息

        Returns:
            ExpertMeta 实例，包含 name/category/description/icon/label/priority
        """
        return self._meta

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
        注册 chat 和 system 意图

        system 意图（帮助、退出等）路由到 chat_expert 处理，
        与 chat 意图统一由本插件管理。

        Args:
            intent_registry: IntentRegistry 实例

        Returns:
            注册的意图数量
        """
        count = 0

        # 注册 chat 意图
        for intent_type, description in IntentConstants.CHAT_INTENTS.items():
            intent_registry.register_intent(
                intent_type=intent_type,
                category=IntentCategory.CHAT,
                description=description,
                target="chat",
            )
            count += 1

        # 注册 system 意图（路由到 chat_expert 处理）
        for intent_type, description in IntentConstants.SYSTEM_INTENTS.items():
            intent_registry.register_intent(
                intent_type=intent_type,
                category=IntentCategory.SYSTEM,
                description=description,
                target="system",
            )
            count += 1

        return count

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
        answer = self._invoke_agent(self._agent, actual_query, context)
        log(f"[ChatPlugin] 完成: {answer[:50]}...", "Plugin")

        # Chat 特有：无 intent_results
        return self._build_result(answer, state)

    def render_capability(self) -> str:
        """
        渲染能力描述（用于 Planner DECOMPOSE_PROMPT）

        Returns:
            能力描述文本
        """
        return "chat: 简单对话（闲聊、问候、简单问答，LLM 直接回答即可）"
