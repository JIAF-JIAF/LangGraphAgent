"""
MCP 服务器模块（独立部署）

目录结构：
- config.py: 配置常量
- logger.py: 日志模块
- mcp_server.py: MCP 服务器核心（支持 Streamable HTTP）
- tools/: 工具实现目录
"""

from .mcp_server import _server as mcp, get_server, run_server

__all__ = [
    'mcp',
    'get_server',
    'run_server',
]