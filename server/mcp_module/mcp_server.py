"""
MCP 服务器核心模块
提供独立部署的 MCP 服务，支持 Streamable HTTP 传输协议
"""

from mcp.server import FastMCP

from mcp_module.tools.registry import get_registered_tools
import mcp_module.logger as logger
import mcp_module.config as config

_server = FastMCP(
    name="ChartFlowMCP",
    instructions="智能体框架 MCP 服务器",
    host=config.MCP_HOST,
    port=config.MCP_PORT,
    streamable_http_path=config.MCP_PATH
)

def register_from_registry() -> None:
    """从工具注册表注册所有工具"""
    for tool_def in get_registered_tools():
        _server.tool(
            name=tool_def.name,
            description=tool_def.description
        )(tool_def.func)

        logger.logger.info(f"注册工具: {tool_def.name}")

def get_server() -> FastMCP:
    """
    获取 MCP 服务器实例

    Returns:
        FastMCP 服务器实例
    """
    return _server

def run_server(host: str = config.MCP_HOST, port: int = config.MCP_PORT) -> None:
    """
    启动 MCP 服务器（使用 Streamable HTTP 协议）

    Args:
        host: 服务器主机地址
        port: 服务器端口号
    """
    logger.logger.info(f"启动 MCP 服务器 (streamable-http): http://{host}:{port}{config.MCP_PATH}")
    _server.run(transport="streamable-http")

__all__ = ['_server', 'register_from_registry', 'get_server', 'run_server']