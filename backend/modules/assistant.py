"""
LangChain Agent 模块
结合 LLM + Tools 的 Agent 实现

注意：会话管理由上层 LangGraph 负责，此模块不维护对话历史。
"""

from typing import Optional, Dict, Any, List
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor


class Agent:
    """LangChain Agent 封装"""

    def __init__(
        self,
        options: Optional[Dict] = None
    ):
        if options is None:
            options = {}

        self.llm_client = options.get('aiClient')
        self._tools = options.get('tools', [])
        self.prompt = options.get('prompt')

        self.verbose = True
        self._agent_executor = None

        self._build_agent()

    def _build_agent(self):
        """构建 Agent"""
        tools = self._tools.copy()

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

    def invoke(self, input: str, session_id: str = "default", chat_history: List = None) -> Dict[str, Any]:
        """执行 Agent 处理用户输入。

        Args:
            input: 用户输入的文本
            session_id: 会话 ID（当前不使用，由上层 LangGraph 管理）
            chat_history: 对话历史列表，由 LangGraph 传入

        Returns:
            包含 answer、intermediate_steps 和 tool_messages 的字典
        """
        result = self._agent_executor.invoke({
            "input": input,
            "chat_history": chat_history or []
        })

        return {
            "answer": result.get("output", str(result)),
            "intermediate_steps": result.get("intermediate_steps", []),
            "tool_messages": []
        }

    def process_message(self, session_id, user_message):
        """发送对话（兼容原有接口）。

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