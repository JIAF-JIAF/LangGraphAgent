"""
MCP 客户端模块

负责连接远程 MCP 服务器、获取工具列表、转换为 LangChain BaseTool。
配置文件：server/config/mcp_servers.yaml
"""

from modules.mcp.client import MCPToolService, wrap_async_tool
from modules.mcp.config_manager import mcp_config_manager

__all__ = [
    'MCPToolService',
    'wrap_async_tool',
    'mcp_config_manager',
]
