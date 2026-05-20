"""
系统组件初始化工厂
提供共享的 LangGraph Agent 初始化逻辑
"""

import os
from modules.ai_client import AIClient
from modules.langgraph import LangGraphAgent, TaskPlanner, ReflectionChecker
from modules.rag import RAGWorkflow
from modules.checkpoint import CheckpointFactory
from modules.assistant import Agent as LangChainAgent
from modules.prompt import create_prompt
from modules.feeling import FeelingDetector
from modules.skill import SkillManager
from mcp_module import MCPToolService


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
        print("\n[1/4] 初始化 AI 客户端...")
        ai_client = AIClient()
        print("AI 客户端初始化完成")

        print("\n[2/4] 初始化 RAG 工作流...")
        rag_workflow = AssistantFactory._try_init_rag_workflow(ai_client)
        print("RAG 工作流初始化完成")

        print("\n[3/4] 初始化 LangChain Agent...")
        langchain_agent = AssistantFactory._try_init_langchain_agent(ai_client)
        print("LangChain Agent 初始化完成")

        print("\n[4/4] 初始化 LangGraph 调度层...")
        checkpointer, task_planner, reflection_checker, skill_manager = AssistantFactory._init_langgraph_components(ai_client)
        feeling_detector = AssistantFactory._try_init_feeling_detector(ai_client)

        assistant = LangGraphAgent(
            agent=langchain_agent,
            rag_workflow=rag_workflow,
            checkpointer=checkpointer,
            feeling_detector=feeling_detector,
            task_planner=task_planner,
            reflection_checker=reflection_checker,
            skill_manager=skill_manager
        )
        print("LangGraph 调度层初始化完成")

        return {
            'assistant': assistant,
            'ai_client': ai_client,
            'feeling_detector': feeling_detector,
            'rag_workflow': rag_workflow,
            'langchain_agent': langchain_agent,
            'checkpointer': checkpointer,
            'task_planner': task_planner,
            'reflection_checker': reflection_checker,
            'skill_manager': skill_manager,
        }

    @staticmethod
    def _try_init_feeling_detector(ai_client):
        try:
            return FeelingDetector(llm_client=ai_client)
        except Exception as e:
            print("感情侦测器初始化失败: {}".format(e))
            return None

    @staticmethod
    def _try_init_rag_workflow(ai_client):
        try:
            workflow = RAGWorkflow(llm_client=ai_client)
            workflow.build_index()
            return workflow
        except Exception as e:
            print("RAG 工作流初始化警告: {}".format(e))
            return None

    @staticmethod
    def _try_init_langchain_agent(ai_client):
        try:
            tools = MCPToolService.get_tools()
            return LangChainAgent(options={
                "prompt": create_prompt(feeling={"feeling": "default", "score": 5}),
                "tools": tools,
                "aiClient": ai_client
            })
        except Exception as e:
            print("LangChain Agent 初始化失败: {}".format(e))
            return None

    @staticmethod
    def _init_langgraph_components(ai_client):
        checkpoint_storage = os.getenv("CHECKPOINT_STORAGE", "memory").lower()
        checkpointer = CheckpointFactory.build(name=checkpoint_storage)
        task_planner = TaskPlanner(llm_client=ai_client)
        reflection_checker = ReflectionChecker(llm_client=ai_client)
        skill_manager = SkillManager(llm_client=ai_client)
        return checkpointer, task_planner, reflection_checker, skill_manager


__all__ = ['AssistantFactory']
