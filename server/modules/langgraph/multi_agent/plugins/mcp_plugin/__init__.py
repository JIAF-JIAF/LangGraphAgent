"""
MCP Expert 插件

处理 MCP 工具调用意图。使用领域专精 Agent（只绑定 MCP 工具），
LLM-in-the-loop 自动完成参数提取和工具选择。
"""

from modules.langgraph.multi_agent.plugins.mcp_plugin.plugin import MCPPlugin

__all__ = ["MCPPlugin"]
