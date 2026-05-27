"""
LangChain Agent 模块

结合 LLM + Tools 的 Agent 实现。

注意：会话管理由上层 LangGraph 负责，此模块不维护对话历史。

核心功能：
- 构建工具调用 Agent
- 支持动态更新提示模板
- 支持情绪状态设置
- 执行用户输入并返回结果
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from langchain_classic.tools import BaseTool
from pydantic import BaseModel, Field

from modules.logger import log
from modules.prompt import get_role_set_from_feeling
from modules.context import AgentContext
from mcp_module.context import set_value, remove_value


class DefaultToolInput(BaseModel):
    """默认工具的输入参数"""
    query: str = Field(description="用户查询")


class DefaultTool(BaseTool):
    """
    默认空操作工具
    
    当没有实际工具时使用，确保 Agent 能正常工作。
    此工具什么也不做，仅返回提示信息。
    """
    name: str = "default_tool"
    description: str = "默认工具，用于保持 Agent 正常运行"
    args_schema: type = DefaultToolInput

    def _run(self, query: str) -> str:
        return "已收到您的请求，我将直接为您回答。"


class Agent:
    """
    LangChain Agent 封装
    
    提供工具调用能力的 Agent 实现，支持动态更新 prompt 和情绪状态。
    """

    def __init__(
        self,
        options: Optional[Dict] = None
    ):
        """
        初始化 Agent
        
        Args:
            options: 配置选项字典，包含:
                - aiClient: LLM 客户端实例
                - tools: 工具列表
                - prompt: 提示模板
        """
        if options is None:
            options = {}

        self.llm_client = options.get('aiClient')
        self._tools = options.get('tools', [])
        self.prompt = options.get('prompt')
        self._feeling = None

        self.verbose = True
        self._agent_executor = None

        self._build_agent()

    def _build_agent(self):
        """构建 Agent Executor"""
        tools = self._tools.copy() if self._tools else [DefaultTool()]

        self._agent = create_tool_calling_agent(
            llm=self.llm_client.chat,
            tools=tools,
            prompt=self.prompt
        )

        self._agent_executor = AgentExecutor(
            agent=self._agent,
            tools=tools,
            verbose=self.verbose,
            handle_parsing_errors=True
        )

    def update_prompt(self, new_prompt):
        """
        动态更新提示模板
        
        Args:
            new_prompt: 新的 ChatPromptTemplate 实例
        """
        self.prompt = new_prompt
        self._build_agent()
        log(f"Prompt 已更新", "Agent")

    def set_feeling(self, feeling: Dict[str, Any]):
        """
        设置当前情绪状态
        
        Args:
            feeling: 情绪对象，格式: {"feeling": str, "score": int}
        """
        self._feeling = feeling
        log(f"情绪状态已设置: {feeling}", "Agent")

    def invoke(self, input: str, context: Optional[AgentContext] = None) -> Dict[str, Any]:
        """
        执行 Agent 处理用户输入
        
        Args:
            input: 用户输入的文本
            context: Agent 执行上下文（包含会话信息、情绪状态等）
            
        Returns:
            包含 answer、intermediate_steps 和 tool_messages 的字典
            
        参考 2026 年 LangChain Context Engineering 最佳实践：
        https://docs.langchain.com/oss/python/langchain/context-engineering
        """
        # 使用默认上下文或传入的上下文
        ctx = context or AgentContext()
        
        # 设置全局上下文变量
        if ctx.user_id:
            set_value("user_id", ctx.user_id)
        
        # 获取当前日期时间，通过 invoke 注入到 prompt
        current_datetime = datetime.now()
        current_date_str = current_datetime.strftime("%Y年%m月%d日")

        # 构建运行时变量，注入到 prompt
        feeling = ctx.get_feeling()
        role_set = get_role_set_from_feeling(feeling.get("feeling", "default"))
        feel_score = ctx.get_score()

        # 调用 AgentExecutor 执行
        result = self._agent_executor.invoke(
            {
                "input": input,
                "chat_history": ctx.chat_history,
                "current_date": current_date_str,
                "role_set": role_set,
                "feelScore": feel_score
            },
            config={
                "configurable": {
                    "skill_name": ctx.skill_name,
                }
            }
        )

        answer = result.get("output", str(result))
        intermediate_steps = result.get("intermediate_steps", [])

        # 清理全局上下文变量
        remove_value("user_id")

        return {
            "answer": answer,
            "intermediate_steps": intermediate_steps,
            "tool_messages": [],
            "feeling": self._feeling
        }

    def process_message(self, session_id, user_message):
        """
        发送对话（兼容原有接口）
        
        Args:
            session_id: 会话 ID
            user_message: 用户消息内容
            
        Returns:
            包含 content 和 tool_calls 的字典
        """
        log(f"收到消息 - Session: {session_id}, Message: {user_message}", "Agent")
        result = self.invoke(user_message, AgentContext(session_id=session_id))
        return {
            "content": result["answer"],
            "tool_calls": []
        }


__all__ = ['Agent']
