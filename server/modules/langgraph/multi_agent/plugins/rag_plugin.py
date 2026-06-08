"""
RAG Expert 插件

处理知识库检索意图。使用领域专精 Agent（只绑定 RAG 工具），
LLM-in-the-loop 自动完成知识库选择、检索和答案生成。

插件化职责：
  - on_activate: 自建 RAGWorkflow + 创建 RAG Agent
  - register_intents: 从知识库注册意图
  - execute: 执行知识库检索
"""

from typing import Dict, Any, List

from modules.logger import log
from modules.langgraph.multi_agent.meta import ExpertMeta
from modules.langgraph.multi_agent.plugin_base import ExpertPlugin
from modules.langgraph.multi_agent.helpers import (
    filter_intents_by_category,
    build_hints_input,
    build_base_context,
    build_intent_results,
)
from modules.langgraph.multi_agent.tools.rag_tools import create_rag_tools
from modules.langgraph.multi_agent.expert_agent_factory import RAG_SYSTEM_PROMPT, _build_expert_prompt
from modules.assistant import Agent
from modules.rag import RAGWorkflow
from modules.intent.intent_types import IntentCategory


class RAGPlugin(ExpertPlugin):
    """知识库检索插件"""

    def __init__(self):
        """初始化 RAG 插件"""
        self._meta = ExpertMeta(
            name="rag_expert",
            category="rag",
            description="知识库检索（考试题库、政治理论等）",
            icon="📚",
            label="知识检索 Agent",
        )
        self._rag_workflow = None

    @property
    def meta(self) -> ExpertMeta:
        """
        插件元信息

        Returns:
            ExpertMeta 实例，包含 name/category/description/icon/label
        """
        return self._meta

    def on_activate(self, context: Dict[str, Any]):
        """
        激活回调：自建 RAGWorkflow + 创建 RAG 领域专精 Agent

        Args:
            context: 共享资源上下文，包含 ai_client 等
        """
        ai_client = context["ai_client"]

        # 自建 RAGWorkflow（依赖自治，不依赖外部注入）
        try:
            self._rag_workflow = RAGWorkflow(llm_client=ai_client)
            self._rag_workflow.build_index()
            log("[RAGPlugin] RAGWorkflow 创建完成", "Plugin")
        except Exception as e:
            log(f"[RAGPlugin] RAGWorkflow 创建失败: {e}", "Plugin")
            self._rag_workflow = None

        if not self._rag_workflow:
            log("[RAGPlugin] rag_workflow 不可用，跳过 Agent 创建", "Plugin")
            return

        tools = create_rag_tools(self._rag_workflow)
        prompt = _build_expert_prompt(RAG_SYSTEM_PROMPT)

        self._agent = Agent(options={"prompt": prompt, "tools": tools, "aiClient": ai_client})
        log(f"[RAGPlugin] Agent 创建完成，工具: {[t.name for t in tools]}", "Plugin")

    def register_intents(self, intent_registry) -> int:
        """
        从知识库注册意图

        直接调用 register_intent 逐个注册，不依赖 IntentRegistry 的
        特定方法，保持插件化一致性。新增 Expert 无需修改 IntentRegistry。

        Args:
            intent_registry: IntentRegistry 实例

        Returns:
            注册的意图数量
        """
        if not self._rag_workflow:
            log("[RAGPlugin] RAGWorkflow 不可用，跳过意图注册", "Plugin")
            return 0

        try:
            knowledge_bases = self._rag_workflow.get_available_knowledge_bases()
            count = 0
            for kb_info in knowledge_bases:
                kb_name = kb_info.get("name", "")
                if not kb_name:
                    continue

                kb_description = kb_info.get("description", f"查询 {kb_name} 知识库")
                intent_type = f"rag_{kb_name}"
                intent_registry.register_intent(
                    intent_type=intent_type,
                    category=IntentCategory.RAG,
                    description=kb_description,
                    target=f"knowledge_base:{kb_name}",
                    knowledge_base=kb_name,
                )
                count += 1
            return count
        except Exception as e:
            log(f"[RAGPlugin] 知识库意图注册失败: {e}", "Plugin")
            return 0

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行知识库检索

        Args:
            state: LangGraph 状态（query, intents, __subtask_idx__ 等）

        Returns:
            状态更新字典，包含 agent_results
        """
        query = state["query"]
        intents = filter_intents_by_category(state.get("intents", []), "rag")
        input_text = build_hints_input(
            query, intents,
            target_prefix="knowledge_base:",
            single_hint="请在 {target} 知识库中检索以下内容",
            multi_hint="请检索以下内容：",
        )

        log(f"[RAGPlugin] 处理 RAG 意图: {len(intents)} 个, 输入: {input_text[:50]}...", "Plugin")

        context = build_base_context(state)
        answer = self._invoke_agent(self._agent, input_text, context)
        log(f"[RAGPlugin] 完成: {answer[:50]}...", "Plugin")

        intent_results = build_intent_results(intents, answer, "rag")
        return self._build_result(answer, state, intent_results=intent_results)

    def render_capability(self) -> str:
        """
        渲染能力描述（用于 Planner DECOMPOSE_PROMPT）

        Returns:
            能力描述文本，包含当前可用知识库列表
        """
        if not self._rag_workflow:
            return "rag: 知识库检索（当前不可用）"
        tools = create_rag_tools(self._rag_workflow)
        kb_names = ", ".join([t.name for t in tools]) if tools else "无"
        return f"rag: 知识库检索。当前可用知识库：{kb_names}"
