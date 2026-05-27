"""
MCP (Model Context Protocol) 工具模块

目录结构：
- config.py: 配置常量
- logger.py: 日志模块
- mcp_server.py: MCP 服务器核心（支持 Streamable HTTP）
- mcp_service.py: MCP 服务封装（工具获取）
- tools/: 工具实现目录
"""

from .mcp_server import _server as mcp, get_server, run_server
from .mcp_service import MCPToolService

__all__ = [
    'mcp',
    'get_server',
    'run_server',
    'MCPToolService',
]