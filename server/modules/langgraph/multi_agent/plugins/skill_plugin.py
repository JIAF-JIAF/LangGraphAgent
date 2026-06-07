"""
Skill Expert 插件

处理技能执行意图。使用领域专精 Agent（只绑定 Skill 工具），
LLM-in-the-loop 自动完成技能选择和参数提取。
"""

import re
from typing import Dict, Any, List

from langchain_core.tools import BaseTool
from modules.logger import log
from modules.langgraph.multi_agent.meta import ExpertMeta
from modules.langgraph.multi_agent.plugin_base import ExpertPlugin
from modules.langgraph.multi_agent.helpers import (
    filter_intents_by_category,
    build_hints_input,
    build_base_context,
    build_intent_results,
)
from modules.langgraph.multi_agent.tools.skill_tools import get_skill_tools, skill_execute
from modules.langgraph.multi_agent.expert_agent_factory import SKILL_SYSTEM_PROMPT, _build_expert_prompt
from modules.assistant import Agent


class SkillPlugin(ExpertPlugin):
    """技能执行插件"""

    def __init__(self):
        """初始化 Skill 插件"""
        self._meta = ExpertMeta(
            name="skill_expert",
            category="skill",
            description="技能执行（画图、数据分析、文档生成等）",
            icon="🎨",
            label="技能执行 Agent",
        )

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
        激活回调：创建 Skill 领域专精 Agent

        Args:
            context: 共享资源上下文，包含 ai_client/skill_manager 等
        """
        self._skill_manager = context.get("skill_manager")
        ai_client = context["ai_client"]

        tools = get_skill_tools(self._skill_manager) if self._skill_manager else []
        if not tools:
            tools = [skill_execute]
            log("[SkillPlugin] 动态工具为空，使用兜底工具", "Plugin")

        prompt = _build_expert_prompt(SKILL_SYSTEM_PROMPT)
        self._agent = Agent(options={"prompt": prompt, "tools": tools, "aiClient": ai_client})
        log(f"[SkillPlugin] Agent 创建完成，工具: {[t.name for t in tools]}", "Plugin")

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行技能调用

        Args:
            state: LangGraph 状态（query, intents, __subtask_idx__ 等）

        Returns:
            状态更新字典，包含 agent_results
        """
        query = state["query"]
        intents = filter_intents_by_category(state.get("intents", []), "skill")
        input_text = build_hints_input(
            query, intents,
            target_prefix="skill:",
            single_hint="请使用 {target} 技能完成以下任务",
            multi_hint="请完成以下技能任务：",
        )

        log(f"[SkillPlugin] 处理 Skill 意图: {len(intents)} 个, 输入: {input_text[:50]}...", "Plugin")

        # Skill 特有：提取 skill_name 注入上下文
        skill_name = self._extract_skill_name(intents)
        context = build_base_context(state, skill_name=skill_name)

        answer = self._invoke_agent(self._agent, input_text, context)
        log(f"[SkillPlugin] 完成: {answer[:50]}...", "Plugin")

        intent_results = build_intent_results(intents, answer, "skill")
        return self._build_result(answer, state, intent_results=intent_results)

    def _extract_skill_name(self, skill_intents: List[Dict[str, Any]]) -> str:
        """
        从意图列表中提取技能名称

        target 格式固定为 "skill:{skill_name}"，如 "skill:drawio-skill"

        Args:
            skill_intents: Skill 类意图列表

        Returns:
            技能名称（不含 "skill:" 前缀），无效时返回空字符串
        """
        if not skill_intents:
            return ""
        target = skill_intents[0].get("target", "")
        if target.startswith("skill:"):
            name = target[6:]
            if name and not re.search(r'[\s,，。；;！!？?]', name):
                return name
        return ""

    def render_capability(self) -> str:
        """
        渲染能力描述（用于 Planner DECOMPOSE_PROMPT）

        Returns:
            能力描述文本，包含当前可用技能列表
        """
        tools = get_skill_tools(self._skill_manager) if hasattr(self, '_skill_manager') and self._skill_manager else []
        skill_names = ", ".join([t.name for t in tools]) if tools else "无"
        return f"skill: 技能执行。当前可用技能：{skill_names}"
