"""
MCP 服务模块

使用 langchain-mcp-adapters 官方库集成 MCP 工具。
支持 Tool Interceptors 注入 user_id 等上下文信息。

核心功能：
- 从配置的 MCP 服务器获取工具列表
- 使用 Tool Interceptors 注入 user_id
- 将 MCP 工具转换为 LangChain BaseTool
"""

import asyncio
from typing import List, Any, Optional

from langchain_core.tools import BaseTool, StructuredTool

import mcp_module.logger as logger
from mcp_module.mcp_config_manager import mcp_config_manager

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.interceptors import MCPToolCallRequest


def wrap_async_tool(tool: BaseTool) -> BaseTool:
    """
    将异步工具包装为支持同步调用的工具
    
    langchain-mcp-adapters 返回的工具只实现了 _arun，
    需要包装以支持同步调用 _run。
    
    Args:
        tool: 原始异步工具
        
    Returns:
        支持同步调用的工具
    """
    async def _arun(**kwargs):
        return await tool.ainvoke(kwargs)
    
    def _run(**kwargs):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        
        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _arun(**kwargs))
                return future.result()
        else:
            return asyncio.run(_arun(**kwargs))
    
    wrapped_tool = StructuredTool(
        name=tool.name,
        description=tool.description,
        args_schema=tool.args_schema if hasattr(tool, 'args_schema') else None,
        func=_run,
        coroutine=_arun,
    )
    
    return wrapped_tool


class MCPToolService:
    """
    MCP 工具服务类
    
    使用 langchain-mcp-adapters 连接 MCP 服务器并获取工具。
    通过 Tool Interceptors 注入 user_id 到工具调用参数。
    """
    
    _client: Any = None
    _tools_cache: Optional[List[BaseTool]] = None
    
    @classmethod
    def _build_server_configs(cls) -> dict:
        """
        从配置管理器构建服务器配置
        
        Returns:
            服务器配置字典，格式符合 MultiServerMCPClient 要求
        """
        servers = mcp_config_manager.get_all_servers()
        server_configs = {}
        
        for server in servers:
            server_name = server.get('name', 'unknown')
            server_url = server.get('url', '')
            
            if not server_url:
                continue
            
            server_configs[server_name] = {
                "transport": "http",
                "url": server_url,
            }
            
            logger.logger.info(f"配置 MCP 服务器: {server_name} -> {server_url}")
        
        return server_configs
    
    @classmethod
    async def _inject_user_context(cls, request: MCPToolCallRequest, handler):
        """
        Tool Interceptor: 注入 user_id 到 MCP 工具调用
        
        从 RunnableConfig.configurable 获取 user_id，注入到工具参数中。
        
        Args:
            request: MCP 工具调用请求
            handler: 下一个处理器
            
        Returns:
            工具调用结果
        """
        runtime = request.runtime
        
        user_id = ""
        if runtime and hasattr(runtime, 'context') and runtime.context:
            user_id = runtime.context.get("user_id", "")
        
        if user_id:
            logger.logger.info(f"MCP Interceptor: 注入 user_id={user_id}")
            modified_request = request.override(
                args={**request.args, "user_id": user_id}
            )
            return await handler(modified_request)
        
        return await handler(request)
    
    @classmethod
    def _init_client(cls):
        """
        初始化 MultiServerMCPClient
        
        如果已初始化则跳过。
        """
        if cls._client is not None:
            return
        
        server_configs = cls._build_server_configs()
        
        if not server_configs:
            logger.logger.warning("没有配置任何 MCP 服务器")
            return
        
        try:
            cls._client = MultiServerMCPClient(
                server_configs,
                tool_interceptors=[cls._inject_user_context]
            )
            logger.logger.info(f"MCP 客户端初始化完成，共 {len(server_configs)} 个服务器")
        except Exception as e:
            logger.logger.error(f"MCP 客户端初始化失败: {e}")
            cls._client = None
    
    @classmethod
    async def get_tools_async(cls) -> List[BaseTool]:
        """
        异步获取所有 MCP 工具
        
        Returns:
            LangChain BaseTool 列表
        """
        if cls._tools_cache is not None:
            return cls._tools_cache
        
        cls._init_client()
        
        if cls._client is None:
            return []
        
        try:
            tools = await cls._client.get_tools()
            wrapped_tools = [wrap_async_tool(t) for t in tools]
            logger.logger.info(f"获取到 {len(wrapped_tools)} 个 MCP 工具")
            cls._tools_cache = wrapped_tools
            return wrapped_tools
        except Exception as e:
            logger.logger.error(f"获取 MCP 工具失败: {type(e).__name__}: {e}")
            return []
    
    @classmethod
    def get_tools(cls) -> List[BaseTool]:
        """
        获取所有 MCP 工具（同步接口）
        
        Returns:
            LangChain BaseTool 列表
        """
        return asyncio.run(cls.get_tools_async())
    
    @classmethod
    def reload(cls):
        """
        重新加载 MCP 工具
        
        清除缓存，下次调用 get_tools() 时重新获取。
        """
        cls._tools_cache = None
        cls._client = None
        logger.logger.info("MCP 工具缓存已清除")


__all__ = ['MCPToolService']
