"""
MCP 工具动态适配器

MCP 工具列表是动态的（通过 URL 从 MCP 服务器获取，可增删配置），不能硬编码枚举。

封装策略：
  1. get_mcp_tools() — 直接透传 MCPToolService.get_tools() 返回的 List[BaseTool]
  2. mcp_execute(tool_name, content) — 兜底工具，委托 ExecutorRegistry.build("mcp") 执行
  3. reload_mcp_tools() — 刷新 MCP 工具列表（配置变更后调用）

现有 API 对照：
  MCPToolService.get_tools() -> List[BaseTool]（weather, dingtalk_*, form 等）
  MCPToolService.reload() -> None
  ExecutorRegistry.build("mcp", agent=...) -> MCPExecutor
  MCPExecutor.execute(intent, context) -> ExecutionResult
"""

from typing import List
from langchain_core.tools import BaseTool, tool
from modules.mcp import MCPToolService
from modules.langgraph.executors.registry import ExecutorRegistry
from modules.logger import log


def get_mcp_tools() -> List[BaseTool]:
    """从 MCPToolService 动态获取 MCP 工具列表

    MCPToolService 通过 langchain-mcp-adapters 连接 MCP 服务器，
    返回的 BaseTool 已包含 name、description、args_schema，
    可直接用于 create_react_agent 或 bind_tools。

    Returns:
        LangChain BaseTool 列表，包含当前所有 MCP 服务器提供的工具
    """
    try:
        tools = MCPToolService.get_tools()
        tool_names = [t.name for t in tools]
        log(f"[MCPAdapter] 获取到 {len(tools)} 个 MCP 工具: {tool_names}", "MultiAgent")
        return tools
    except Exception as e:
        log(f"[MCPAdapter] 获取 MCP 工具失败: {e}", "MultiAgent")
        return []


def reload_mcp_tools() -> List[BaseTool]:
    """刷新 MCP 工具列表（配置变更后调用）

    Returns:
        刷新后的 LangChain BaseTool 列表
    """
    try:
        MCPToolService.reload()
        return get_mcp_tools()
    except Exception as e:
        log(f"[MCPAdapter] 刷新 MCP 工具失败: {e}", "MultiAgent")
        return []


@tool
def mcp_execute(tool_name: str, content: str) -> str:
    """执行指定 MCP 工具。当动态工具列表中无匹配项时使用此通用入口，委托 MCPExecutor 执行。

    Args:
        tool_name: MCP 工具名称（如 weather, dingtalk_todo, submit_form）
        content: 工具执行的内容描述
    """
    executor = ExecutorRegistry.build("mcp")
    intent = {
        "type": f"mcp_{tool_name}",
        "category": "mcp",
        "target": f"mcp:{tool_name}",
        "content": content,
    }
    result = executor.execute(intent, context={"chat_history": [], "feeling": {}})
    log(f"[MCPAdapter] 兜底执行工具: {tool_name}", "MultiAgent")
    return result.content if result.success else f"执行失败: {result.error}"
