"""
MCP Expert 插件

处理 MCP 工具调用意图。使用领域专精 Agent（只绑定 MCP 工具），
LLM-in-the-loop 自动完成参数提取和工具选择。

Manifest 驱动：routing/prompt/intents 从 PLUGIN.yaml 加载，
消除硬编码，新增 Expert 无需修改框架代码。
"""

from typing import Dict, Any, List

from modules.logger import log
from modules.langgraph.multi_agent.plugin_base import ExpertPlugin
from modules.langgraph.multi_agent.helpers import (
    filter_intents_by_category,
    build_hints_input,
    build_base_context,
    build_intent_results,
    push_progress_event,
)
from modules.langgraph.multi_agent.tools.mcp_tools import get_mcp_tools, mcp_execute
from modules.langgraph.multi_agent.expert_agent_factory import MCP_SYSTEM_PROMPT, _build_expert_prompt
from modules.assistant import Agent
from modules.intent.intent_types import IntentCategory
from modules.mcp import MCPToolService


class MCPPlugin(ExpertPlugin):
    """MCP 工具调用插件"""

    def __init__(self, manifest):
        """
        初始化 MCP 插件

        Args:
            manifest: PluginManifest 实例，从 PLUGIN.yaml 加载
        """
        super().__init__(manifest)

    def on_activate(self, context: Dict[str, Any]):
        """
        激活回调：创建 MCP 领域专精 Agent

        Args:
            context: 共享资源上下文，包含 ai_client 等
        """
        tools = get_mcp_tools()
        if not tools:
            tools = [mcp_execute]
            log("[MCPPlugin] 动态工具为空，使用兜底工具", "Plugin")

        ai_client = context["ai_client"]
        prompt = _build_expert_prompt(MCP_SYSTEM_PROMPT)
        self._agent = Agent(options={"prompt": prompt, "tools": tools, "aiClient": ai_client})
        log(f"[MCPPlugin] Agent 创建完成，工具: {[t.name for t in tools]}", "Plugin")

    def register_intents(self, intent_registry) -> int:
        """
        从 MCP 工具注册意图

        动态意图注册：从 MCP 工具列表逐个注册。
        静态意图由基类自动注册（Manifest intents.static）。

        Args:
            intent_registry: IntentRegistry 实例

        Returns:
            注册的意图数量
        """
        # 先注册 Manifest 中的静态意图
        count = super().register_intents(intent_registry)

        # 再注册动态意图
        try:
            mcp_tools = MCPToolService.get_tools()
            for tool in mcp_tools:
                intent_type = f"mcp_{tool.name}"
                intent_registry.register_intent(
                    intent_type=intent_type,
                    category=IntentCategory.MCP,
                    description=tool.description,
                    target=f"mcp:{tool.name}",
                    tool_name=tool.name,
                )
                count += 1
            return count
        except Exception as e:
            log(f"[MCPPlugin] MCP 意图注册失败: {e}", "Plugin")
            return count

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行 MCP 工具调用

        Args:
            state: LangGraph 状态（query, intents, __subtask_idx__ 等）

        Returns:
            状态更新字典，包含 agent_results
        """
        query = state["query"]
        intents = filter_intents_by_category(state.get("intents", []), self.meta.category)

        # 推送工具调用进度
        tool_names = [i.get("target", "").replace("mcp:", "") for i in intents]
        if tool_names:
            push_progress_event(self.meta, f"调用工具：{', '.join(tool_names)}")
        else:
            push_progress_event(self.meta, "选择合适的工具...")

        # 从 Manifest 获取 prompt 模板
        input_text = build_hints_input(
            query, intents,
            target_prefix=self.manifest.routing.target_prefix,
            single_hint=self.manifest.prompt.single_hint,
            multi_hint=self.manifest.prompt.multi_hint,
        )

        log(f"[MCPPlugin] 处理 MCP 意图: {len(intents)} 个, 输入: {input_text[:50]}...", "Plugin")

        context = build_base_context(state)
        answer = self._invoke_agent(self._agent, input_text, context, started_detail=f"处理：{query[:40]}")
        log(f"[MCPPlugin] 完成: {answer[:50]}...", "Plugin")

        intent_results = build_intent_results(intents, answer, self.meta.category)
        return self._build_result(answer, state, intent_results=intent_results)

    def render_capability(self) -> str:
        """
        渲染能力描述（用于 Planner DECOMPOSE_PROMPT）

        使用 Manifest 的 capability_template 模板。

        Returns:
            能力描述文本，包含当前可用工具列表
        """
        tools = get_mcp_tools()
        tool_names = ", ".join([t.name for t in tools]) if tools else "无"
        template = self.manifest.prompt.capability_template
        return template.format(
            category=self.meta.category,
            description=self.meta.description,
            tools=tool_names,
        )
