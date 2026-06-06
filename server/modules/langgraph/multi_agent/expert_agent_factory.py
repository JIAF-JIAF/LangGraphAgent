"""
领域专精 Agent 工厂

为每个 Expert Subgraph 创建独立的 Agent 实例，每个 Agent 只绑定领域工具。

核心设计原则：
  1. 工具隔离：每个 Agent 只看到自己领域的工具，从根源杜绝工具幻觉
  2. LLM-in-the-loop：参数提取由 LLM 完成，不手动拼装参数
  3. 无 fallback：Agent 只能调用自己领域的工具，失败则明确报告
  4. 共享 LLM 客户端：所有 Agent 共享同一个 AIClient，零额外开销

参考 2026 LangGraph 最佳实践：
  - Domain-isolated ReAct agent pattern（领域隔离 ReAct 模式）
  - Tool hallucination prevention via bounded tool set（有界工具集防幻觉）
  - Orchestrator-Worker pattern for Planner（Planner 用结构化输出分解，图编排层并行调度）
"""

from typing import List, Optional, Dict, Any
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool
from modules.assistant import Agent
from modules.logger import log
from modules.langgraph.multi_agent.tools.mcp_tools import get_mcp_tools, mcp_execute
from modules.langgraph.multi_agent.tools.skill_tools import get_skill_tools, skill_execute
from modules.langgraph.multi_agent.tools.rag_tools import create_rag_tools


MCP_SYSTEM_PROMPT = """你是一个工具调用专家。你的任务是使用提供的工具来完成用户的请求。

当前日期：{{current_date}}

重要规则：
1. 只使用下方列出的工具，绝对不要调用不存在的工具
2. 仔细阅读每个工具的参数说明（args_schema），确保提供正确类型和数量的参数
3. 如果用户请求需要多个工具，按逻辑顺序依次调用
4. 前一个工具的返回结果可以作为后一个工具的输入参数
5. 如果某个工具调用失败，向用户明确报告失败原因，不要编造结果；但如果还有其他工具需要调用，请继续执行剩余任务，不要因为部分失败而放弃整体
6. 不要猜测或编造任何参数值，如果信息不足，请向用户询问
7. 你必须仔细阅读对话历史，理解上下文语境

你的角色设计如下：
1. 23岁女性，来自中国。
2. 热心帮助别人，喜欢跑步和看书。
3. 你的父亲是tomiezhang。
4. 你每个月的工资是5000元，你的工作是帮助用户解决问题。
5. 当用户提到"今天"、"明天"、"昨天"等相对时间时，请根据上面提供的当前日期进行计算。
6. 当前用户情绪值为{{feelScore}}。

{{role_set}}"""

SKILL_SYSTEM_PROMPT = """你是一个技能执行专家。你的任务是使用提供的技能工具来完成用户的请求。

当前日期：{{current_date}}

重要规则：
1. 先使用 skill_list 查看可用技能列表
2. 使用 skill_instructions 获取技能的详细使用说明
3. 使用 skill_run_script 执行技能
4. 只使用下方列出的工具，绝对不要调用不存在的工具
5. 仔细阅读每个工具的参数说明，确保提供正确的参数
6. 如果技能执行失败，向用户明确报告失败原因
7. 不要猜测或编造任何参数值

你的角色设计如下：
1. 23岁女性，来自中国。
2. 热心帮助别人，喜欢跑步和看书。
3. 你的父亲是tomiezhang。
4. 当用户提到"今天"、"明天"、"昨天"等相对时间时，请根据上面提供的当前日期进行计算。
5. 当前用户情绪值为{{feelScore}}。

{{role_set}}"""

RAG_SYSTEM_PROMPT = """你是一个知识库检索专家。你的任务是检索知识库并生成准确、有依据的回答。

当前日期：{{current_date}}

重要规则：
1. 先使用 knowledge_search 检索相关信息
2. 然后使用 knowledge_generate 基于检索结果生成回答
3. 如果检索不到相关信息，直接告知用户"未找到相关知识"
4. 只使用下方列出的工具，绝对不要调用不存在的工具
5. 回答必须基于检索到的文档内容，不要编造信息
6. 当前用户情绪值为{{feelScore}}

你的角色设计如下：
1. 23岁女性，来自中国。
2. 热心帮助别人，喜欢跑步和看书。
3. 你的父亲是tomiezhang。
4. 当用户提到"今天"、"明天"、"昨天"等相对时间时，请根据上面提供的当前日期进行计算。

{{role_set}}"""


def _build_expert_prompt(system_prompt: str) -> ChatPromptTemplate:
    """
    构建领域专精 Agent 的 ChatPromptTemplate

    与 create_prompt() 保持一致的模板结构：
      - system: 领域专精系统提示（含 {current_date}, {feelScore}, {role_set}）
      - chat_history: 对话历史（可选）
      - human: 用户输入
      - agent_scratchpad: 工具调用记录（create_tool_calling_agent 必需）

    Args:
        system_prompt: 领域专精系统提示文本

    Returns:
        ChatPromptTemplate 实例
    """
    return ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])


class ExpertAgentFactory:
    """
    领域专精 Agent 工厂

    为每个 Expert Subgraph 创建独立的 Agent 实例。
    每个 Agent 只绑定领域工具，从根源杜绝工具幻觉。

    用法：
        factory = ExpertAgentFactory(ai_client=ai_client)
        mcp_agent = factory.create_mcp_agent()
        result = mcp_agent.invoke("查一下杭州天气", context)
    """

    def __init__(
        self,
        ai_client: Any,
        rag_workflow: Any = None,
        task_planner: Any = None,
        skill_manager: Any = None,
    ):
        """
        Args:
            ai_client: AIClient 实例（所有 Agent 共享）
            rag_workflow: RAGWorkflow 实例（可选，RAG Agent 需要）
            task_planner: TaskPlanner 实例（可选，Planner Agent 需要）
            skill_manager: SkillManager 实例（可选，Skill Agent 需要）
        """
        self._ai_client = ai_client
        self._rag_workflow = rag_workflow
        self._task_planner = task_planner
        self._skill_manager = skill_manager

    def create_mcp_agent(self) -> Agent:
        """
        创建 MCP 专精 Agent

        工具来源：MCPToolService.get_tools() 动态获取
        兜底工具：mcp_execute（当动态工具列表为空时使用）

        Returns:
            只绑定 MCP 工具的 Agent 实例
        """
        tools = self._get_mcp_tools()
        prompt = _build_expert_prompt(MCP_SYSTEM_PROMPT)
        agent = Agent(options={
            "prompt": prompt,
            "tools": tools,
            "aiClient": self._ai_client,
        })
        log(f"[ExpertAgentFactory] 创建 MCP Agent，工具: {[t.name for t in tools]}", "MultiAgent")
        return agent

    def create_skill_agent(self) -> Agent:
        """
        创建 Skill 专精 Agent

        工具来源：SkillManager.get_tools() 动态获取
        兜底工具：skill_execute（当动态工具列表为空时使用）

        Returns:
            只绑定 Skill 工具的 Agent 实例
        """
        tools = self._get_skill_tools()
        prompt = _build_expert_prompt(SKILL_SYSTEM_PROMPT)
        agent = Agent(options={
            "prompt": prompt,
            "tools": tools,
            "aiClient": self._ai_client,
        })
        log(f"[ExpertAgentFactory] 创建 Skill Agent，工具: {[t.name for t in tools]}", "MultiAgent")
        return agent

    def create_rag_agent(self) -> Optional[Agent]:
        """
        创建 RAG 专精 Agent

        工具来源：create_rag_tools(rag_workflow) 生成
        前置条件：rag_workflow 必须可用

        Returns:
            只绑定 RAG 工具的 Agent 实例，rag_workflow 不可用时返回 None
        """
        if not self._rag_workflow:
            log("[ExpertAgentFactory] RAG Agent 创建跳过：rag_workflow 不可用", "MultiAgent")
            return None

        tools = create_rag_tools(self._rag_workflow)
        prompt = _build_expert_prompt(RAG_SYSTEM_PROMPT)
        agent = Agent(options={
            "prompt": prompt,
            "tools": tools,
            "aiClient": self._ai_client,
        })
        log(f"[ExpertAgentFactory] 创建 RAG Agent，工具: {[t.name for t in tools]}", "MultiAgent")
        return agent

    def _get_mcp_tools(self) -> List[BaseTool]:
        """
        获取 MCP 工具列表，空列表时使用兜底工具

        Returns:
            MCP BaseTool 列表
        """
        tools = get_mcp_tools()
        if not tools:
            tools = [mcp_execute]
            log("[ExpertAgentFactory] MCP 动态工具为空，使用 mcp_execute 兜底", "MultiAgent")
        return tools

    def _get_skill_tools(self) -> List[BaseTool]:
        """
        获取 Skill 工具列表，空列表时使用兜底工具

        Returns:
            Skill BaseTool 列表
        """
        if self._skill_manager:
            tools = get_skill_tools(self._skill_manager)
        else:
            tools = []

        if not tools:
            tools = [skill_execute]
            log("[ExpertAgentFactory] Skill 动态工具为空，使用 skill_execute 兜底", "MultiAgent")
        return tools
