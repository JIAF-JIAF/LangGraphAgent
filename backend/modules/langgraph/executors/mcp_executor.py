"""
MCP 意图执行器

负责执行 MCP 工具调用任务。
"""

from typing import Dict, Any
from modules.logger import log
from modules.context import AgentContext
from .base import BaseExecutor, ExecutionResult


class MCPExecutor(BaseExecutor):
    """
    MCP 意图执行器
    
    通过 Agent 执行 MCP 工具调用。
    """

    def __init__(self, agent: Any = None, **kwargs):
        """
        初始化 MCP 执行器
        
        Args:
            agent: LangChain Agent 实例
        """
        self._agent = agent
    
    @property
    def category(self) -> str:
        return "mcp"
    
    def execute(
        self,
        intent: Dict[str, Any],
        context: Dict[str, Any],
    ) -> ExecutionResult:
        """
        执行 MCP 工具调用
        
        Args:
            intent: 意图数据
            context: 执行上下文
            
        Returns:
            执行结果
        """
        content = intent["content"]
        target = intent["target"]
        tool_name = target.replace("mcp:", "")
        
        # 构建 AgentContext
        agent_context = AgentContext(
            chat_history=context.get("chat_history", []),
            feeling=context.get("feeling", {})
        )
        
        log(f"[MCPExecutor] 执行工具: {tool_name}", "Executor")
        
        result = self._agent.invoke(content, agent_context)
        answer = result.get("answer", "")
        
        log(f"[MCPExecutor] 工具执行完成: {answer[:50]}...", "Executor")
        
        return ExecutionResult(
            success=True,
            content=answer,
            metadata={"tool_name": tool_name}
        )


from .registry import ExecutorRegistry
ExecutorRegistry.register("mcp", MCPExecutor)
