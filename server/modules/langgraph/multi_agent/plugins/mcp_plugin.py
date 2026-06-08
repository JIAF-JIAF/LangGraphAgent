"""
MCP Expert 插件

处理 MCP 工具调用意图。使用领域专精 Agent（只绑定 MCP 工具），
LLM-in-the-loop 自动完成参数提取和工具选择。

插件化职责：
  - on_activate: 创建 MCP Agent
  - register_intents: 从 MCP 工具注册意图
  - execute: 执行 MCP 工具调用
"""

from typing import Dict, Any, List

from modules.logger import log
from modules.langgraph.multi_agent.meta import ExpertMeta
from modules.langgraph.multi_agent.plugin_base import ExpertPlugin
from modules.langgraph.multi_agent.helpers import (
    filter_intents_by_category,
    build_hints_input,
    build_base_context,
    build_intent_results,
)
from modules.langgraph.multi_agent.tools.mcp_tools import get_mcp_tools, mcp_execute
from modules.langgraph.multi_agent.expert_agent_factory import MCP_SYSTEM_PROMPT, _build_expert_prompt
from modules.assistant import Agent
from modules.intent.intent_types import IntentCategory
from mcp_module import MCPToolService


class MCPPlugin(ExpertPlugin):
    """MCP 工具调用插件"""

    def __init__(self):
        """初始化 MCP 插件"""
        self._meta = ExpertMeta(
            name="mcp_expert",
            category="mcp",
            description="外部工具调用（天气查询、钉钉日程、消息推送等）",
            icon="🔧",
            label="工具调用 Agent",
        )

    @property
    def meta(self) -> ExpertMeta:
        """
        插件元信息

        Returns:
            ExpertMeta 实例，包含 name/category/description/icon/label
        """
        return self._meta

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

        直接调用 register_intent 逐个注册，不依赖 IntentRegistry 的
        特定方法，保持插件化一致性。新增 Expert 无需修改 IntentRegistry。

        Args:
            intent_registry: IntentRegistry 实例

        Returns:
            注册的意图数量
        """
        try:
            mcp_tools = MCPToolService.get_tools()
            count = 0
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
            return 0

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行 MCP 工具调用

        Args:
            state: LangGraph 状态（query, intents, __subtask_idx__ 等）

        Returns:
            状态更新字典，包含 agent_results
        """
        query = state["query"]
        intents = filter_intents_by_category(state.get("intents", []), "mcp")

        input_text = build_hints_input(
            query, intents,
            target_prefix="mcp:",
            single_hint="请使用 {target} 工具完成以下任务",
            multi_hint="请完成以下工具调用任务：",
        )

        log(f"[MCPPlugin] 处理 MCP 意图: {len(intents)} 个, 输入: {input_text[:50]}...", "Plugin")

        context = build_base_context(state)
        answer = self._invoke_agent(self._agent, input_text, context)
        log(f"[MCPPlugin] 完成: {answer[:50]}...", "Plugin")

        intent_results = build_intent_results(intents, answer, "mcp")
        return self._build_result(answer, state, intent_results=intent_results)

    def render_capability(self) -> str:
        """
        渲染能力描述（用于 Planner DECOMPOSE_PROMPT）

        Returns:
            能力描述文本，包含当前可用工具列表
        """
        tools = get_mcp_tools()
        tool_names = ", ".join([t.name for t in tools]) if tools else "无"
        return f"mcp: 外部工具调用。当前可用工具：{tool_names}"
