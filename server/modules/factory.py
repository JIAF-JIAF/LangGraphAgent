"""
系统组件初始化工厂
提供共享的 LangGraph Agent 初始化逻辑
"""

import os
from modules.ai_client import AIClient
from modules.langgraph import LangGraphAgent
from modules.checkpoint import CheckpointFactory
from modules.assistant import Agent as LangChainAgent
from modules.prompt import create_prompt
from modules.feeling import FeelingDetector
from modules.tools import ToolManager
from modules.logger import log


class AssistantFactory:
    """Assistant 实例工厂"""

    @staticmethod
    def create_assistant():
        """
        创建 Assistant 实例

        Returns:
            tuple: (assistant_instance, components_dict)
        """
        components = AssistantFactory._init_components()
        assistant = components['assistant']
        return assistant, components

    @staticmethod
    def _init_components():
        """初始化所有系统组件"""
        log("初始化 AI 客户端...", "Factory")
        ai_client = AIClient()
        log("AI 客户端初始化完成", "Factory")

        log("初始化 LangChain Agent（含工具）...", "Factory")
        langchain_agent = AssistantFactory._try_init_langchain_agent(ai_client)
        log("LangChain Agent 初始化完成", "Factory")

        log("初始化 LangGraph 调度层...", "Factory")
        checkpointer = AssistantFactory._init_checkpointer()
        feeling_detector = AssistantFactory._try_init_feeling_detector(ai_client)

        assistant = LangGraphAgent(
            agent=langchain_agent,
            checkpointer=checkpointer,
            feeling_detector=feeling_detector,
            verbose=True,
            ai_client=ai_client,
        )
        log("LangGraph 调度层初始化完成", "Factory")

        return {
            'assistant': assistant,
            'ai_client': ai_client,
            'feeling_detector': feeling_detector,
            'langchain_agent': langchain_agent,
            'checkpointer': checkpointer,
        }

    @staticmethod
    def _try_init_feeling_detector(ai_client):
        try:
            return FeelingDetector(llm_client=ai_client)
        except Exception as e:
            log("感情侦测器初始化失败: {}".format(e), "Factory")
            return None

    @staticmethod
    def _try_init_langchain_agent(ai_client):
        try:
            # 使用工具管理器获取所有工具
            tool_manager = ToolManager(llm_client=ai_client)
            all_tools = tool_manager.get_all_tools()

            return LangChainAgent(options={
                "prompt": create_prompt(feeling={"feeling": "default", "score": 5}),
                "tools": all_tools,
                "aiClient": ai_client
            })
        except Exception as e:
            log("LangChain Agent 初始化失败: {}".format(e), "Factory")
            return None

    @staticmethod
    def _init_checkpointer():
        checkpoint_storage = os.getenv("CHECKPOINT_STORAGE", "memory").lower()
        return CheckpointFactory.build(name=checkpoint_storage)


__all__ = ['AssistantFactory']
