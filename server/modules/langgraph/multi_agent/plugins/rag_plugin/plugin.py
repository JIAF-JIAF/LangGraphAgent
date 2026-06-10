"""
RAG Expert 插件

处理知识库检索意图。使用领域专精 Agent（只绑定 RAG 工具），
LLM-in-the-loop 自动完成知识库选择、检索和答案生成。

Manifest 驱动：routing/prompt/intents 从 PLUGIN.yaml 加载，
消除硬编码，新增 Expert 无需修改框架代码。
"""

from typing import Dict, Any, List

from modules.logger import log
from modules.langgraph.multi_agent.plugin_base import ExpertPlugin
from modules.langgraph.multi_agent.helpers import (
    filter_intents_by_category,
    build_hints_input,
    build_base_context,
    build_intent_results,
    push_progress_event,
)
from modules.langgraph.multi_agent.tools.rag_tools import create_rag_tools
from modules.langgraph.multi_agent.expert_agent_factory import RAG_SYSTEM_PROMPT, _build_expert_prompt
from modules.assistant import Agent
from modules.rag import RAGWorkflow
from modules.intent.intent_types import IntentCategory


class RAGPlugin(ExpertPlugin):
    """知识库检索插件"""

    def __init__(self, manifest):
        """
        初始化 RAG 插件

        Args:
            manifest: PluginManifest 实例，从 PLUGIN.yaml 加载
        """
        super().__init__(manifest)
        self._rag_workflow = None

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

        动态意图注册：从知识库列表逐个注册。
        静态意图由基类自动注册（Manifest intents.static）。

        Args:
            intent_registry: IntentRegistry 实例

        Returns:
            注册的意图数量
        """
        # 先注册 Manifest 中的静态意图
        count = super().register_intents(intent_registry)

        # 再注册动态意图
        if not self._rag_workflow:
            log("[RAGPlugin] RAGWorkflow 不可用，跳过意图注册", "Plugin")
            return count

        try:
            knowledge_bases = self._rag_workflow.get_available_knowledge_bases()
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
            return count

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行知识库检索

        Args:
            state: LangGraph 状态（query, intents, __subtask_idx__ 等）

        Returns:
            状态更新字典，包含 agent_results
        """
        query = state["query"]
        intents = filter_intents_by_category(state.get("intents", []), self.meta.category)

        # 推送检索进度
        kb_names = [i.get("target", "").replace("knowledge_base:", "") for i in intents]
        if kb_names:
            push_progress_event(self.meta, f"检索知识库：{', '.join(kb_names)}")
        else:
            push_progress_event(self.meta, "检索知识库...")

        # 从 Manifest 获取 prompt 模板
        input_text = build_hints_input(
            query, intents,
            target_prefix=self.manifest.routing.target_prefix,
            single_hint=self.manifest.prompt.single_hint,
            multi_hint=self.manifest.prompt.multi_hint,
        )

        log(f"[RAGPlugin] 处理 RAG 意图: {len(intents)} 个, 输入: {input_text[:50]}...", "Plugin")

        context = build_base_context(state)
        answer = self._invoke_agent(self._agent, input_text, context, started_detail=f"处理：{query[:40]}")
        log(f"[RAGPlugin] 完成: {answer[:50]}...", "Plugin")

        intent_results = build_intent_results(intents, answer, self.meta.category)
        return self._build_result(answer, state, intent_results=intent_results)

    def render_capability(self) -> str:
        """
        渲染能力描述（用于 Planner DECOMPOSE_PROMPT）

        使用 Manifest 的 capability_template 模板。

        Returns:
            能力描述文本，包含当前可用知识库列表
        """
        if not self._rag_workflow:
            return f"{self.meta.category}: {self.meta.description}（当前不可用）"
        tools = create_rag_tools(self._rag_workflow)
        kb_names = ", ".join([t.name for t in tools]) if tools else "无"
        template = self.manifest.prompt.capability_template
        return template.format(
            category=self.meta.category,
            description=self.meta.description,
            tools=kb_names,
        )
