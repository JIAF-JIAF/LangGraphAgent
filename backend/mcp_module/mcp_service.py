"""
MCP 服务模块

封装 MCP 工具获取逻辑，支持从单个或多个远程 MCP 服务器获取工具。

核心功能：
- 从单个 MCP 服务器获取工具列表
- 从配置的所有 MCP 服务器获取工具并合并
- 将 MCP 工具转换为 LangChain 可调用的工具对象
"""

import os
import asyncio
import concurrent.futures
from typing import List, Any, Optional, Dict

from langchain_core.tools import StructuredTool
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

import mcp_module.mcp_client as mcp_client
import mcp_module.logger as logger
import mcp_module.config as config


def _normalize_tool_args(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """
    统一规范工具调用参数格式
    
    确保传递给 MCP 服务器的参数格式统一为 {'param1': value1, 'param2': value2, ...}
    
    Args:
        kwargs: 原始参数（可能被包装在 'kwargs' 键下）
        
    Returns:
        标准化后的参数字典
    """
    if not isinstance(kwargs, dict):
        return {}
    
    if len(kwargs) == 1 and 'kwargs' in kwargs:
        args = kwargs['kwargs']
        if isinstance(args, dict):
            return args
        return {}
    
    return kwargs


class MCPToolService:
    """
    MCP 工具服务类
    
    提供从远程 MCP 服务器获取工具的统一接口。
    """

    @staticmethod
    def get_tools(server_url: Optional[str] = None) -> List[Any]:
        """
        从 MCP 服务器获取工具列表（兼容旧版接口）
        
        Args:
            server_url: MCP 服务器地址，若为 None 则从配置的所有启用服务器获取工具
            
        Returns:
            工具列表
        """
        if server_url:
            # 从指定单个服务器获取工具
            return MCPToolService._get_tools_from_server(server_url)
        else:
            # 从配置的所有启用服务器获取工具
            return MCPToolService.get_tools_from_all_servers()

    @staticmethod
    def get_tools_from_all_servers() -> List[Any]:
        """
        从配置中所有 MCP 服务器获取工具列表
        
        Returns:
            合并后的工具列表（来自所有 MCP 服务器）
        """
        all_tools = []

        for server_config in config.MCP_SERVERS:
            server_url = server_config['url']
            server_name = server_config['name']

            try:
                logger.logger.info(f"连接 MCP 服务器 [{server_name}]: {server_url}")
                tools = MCPToolService._get_tools_from_server(server_url)
                logger.logger.info(f"从 MCP 服务器 [{server_name}] 获取到 {len(tools)} 个工具")
                all_tools.extend(tools)
            except Exception as e:
                logger.logger.error(f"连接 MCP 服务器 [{server_name}] 失败: {str(e)}")

        logger.logger.info(f"共获取到 {len(all_tools)} 个工具（来自 {len(config.MCP_SERVERS)} 个服务器）")
        return all_tools

    @staticmethod
    def _get_tools_from_server(server_url: str) -> List[Any]:
        """
        从单个 MCP 服务器获取工具列表
        
        Args:
            server_url: MCP 服务器地址
            
        Returns:
            该服务器提供的工具列表
        """
        mcp_tools = asyncio.run(mcp_client.get_tools_from_server(server_url))
        return MCPToolService._create_callable_tools(mcp_tools, server_url)

    @staticmethod
    def _create_callable_tools(mcp_tools: List[Any], server_url: str) -> List[StructuredTool]:
        """
        将 MCP 工具转换为 LangChain 可调用的工具对象
        
        Args:
            mcp_tools: MCP 工具列表
            server_url: MCP 服务器地址
            
        Returns:
            LangChain StructuredTool 对象列表
        """
        tools = []
        
        for mcp_tool in mcp_tools:
            name = getattr(mcp_tool, 'name', 'unknown')
            description = getattr(mcp_tool, 'description', '').strip()
            
            def create_tool_call(tool_name: str = name, url: str = server_url):
                def call_tool(**kwargs):
                    args = _normalize_tool_args(kwargs)
                    
                    # 自动传递当前用户ID给工具
                    current_user_id = os.getenv("DINGTALK_CURRENT_USER_ID")
                    if current_user_id:
                        args["user_id"] = current_user_id
                    
                    async def _call():
                        async with streamable_http_client(url) as (read_stream, write_stream, get_session_id):
                            async with ClientSession(
                                read_stream=read_stream,
                                write_stream=write_stream,
                                client_info={"name": "chartflow-client", "version": "1.0.0"}
                            ) as session:
                                await session.initialize()
                                result = await session.call_tool(tool_name, args)
                                return result
                    
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        return asyncio.run(_call())
                    else:
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            future = pool.submit(asyncio.run, _call())
                            return future.result()
                
                return call_tool
            
            tool_func = create_tool_call()
            tool_func.__name__ = name
            tool_func.__doc__ = description
            
            tool = StructuredTool.from_function(
                func=tool_func,
                name=name,
                description=description
            )
            
            tools.append(tool)
            
        return tools


__all__ = ['MCPToolService']
