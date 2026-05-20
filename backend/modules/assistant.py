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
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.chains import LLMChain
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from modules.prompt import get_role_set_from_feeling
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
        print(f"[Agent] Prompt 已更新")

    def set_feeling(self, feeling: Dict[str, Any]):
        """
        设置当前情绪状态
        
        Args:
            feeling: 情绪对象，格式: {"feeling": str, "score": int}
        """
        self._feeling = feeling
        print(f"[Agent] 情绪状态已设置: {feeling}")

    def invoke(self, input: str, session_id: str = "default", chat_history: List = None, feeling: Dict[str, Any] = None, uid: Optional[str] = None) -> Dict[str, Any]:
        """
        执行 Agent 处理用户输入
        
        Args:
            input: 用户输入的文本
            session_id: 会话 ID（当前不使用，由上层 LangGraph 管理）
            chat_history: 对话历史列表，由 LangGraph 传入
            feeling: 情绪对象，格式: {"feeling": str, "score": int}
            uid: 用户 ID（用于钉钉等外部工具调用）
            
        Returns:
            包含 answer、intermediate_steps 和 tool_messages 的字典
        """
        self._feeling = feeling or {"feeling": "default", "score": 5}
        set_value("user_id", uid)

        # 获取当前日期时间，通过 invoke 注入到 prompt
        current_datetime = datetime.now()
        current_date_str = current_datetime.strftime("%Y年%m月%d日")

        # 构建运行时变量，注入到 prompt
        role_set = get_role_set_from_feeling(self._feeling.get("feeling", "default"))
        feel_score = self._feeling.get("score", 5)

        # 调用 AgentExecutor 执行
        result = self._agent_executor.invoke({
            "input": input,
            "chat_history": chat_history or [],
            "current_date": current_date_str,
            "role_set": role_set,
            "feelScore": feel_score
        })

        answer = result.get("output", str(result))
        intermediate_steps = result.get("intermediate_steps", [])

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
        print(f"\n[Agent] 收到消息 - Session: {session_id}, Message: {user_message}", flush=True)
        result = self.invoke(user_message, session_id)
        return {
            "content": result["answer"],
            "tool_calls": []
        }


__all__ = ['Agent']
