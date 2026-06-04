"""
Skill Expert 节点

处理技能执行意图。使用领域专精 Agent（只绑定 Skill 工具），
LLM-in-the-loop 自动完成技能选择和参数提取。

核心设计：
  - LLM-in-the-loop：技能选择和参数提取由 LLM 完成
  - 工具隔离：Agent 只看到 Skill 工具，从根源杜绝工具幻觉
  - 意图即上下文：将意图信息作为 Agent 输入的上下文提示
  - 无 fallback：失败则明确报告，不回退到其他路径
  - 结果写入 agent_results：由 Merge 节点统一润色，不直接写 answer
"""

from typing import Dict, Any, List
from langgraph.config import get_stream_writer
from modules.logger import log
from modules.context import AgentContext
from modules.langgraph.nodes.steps import Step
from modules.langgraph.multi_agent.subgraphs.base import BaseExpertNode


class SkillExpertNode(BaseExpertNode):
    """
    Skill Expert 节点

    调用领域专精 Agent 执行技能调用。
    Agent 内部通过 ReAct 循环完成技能选择、参数提取和执行。
    """

    target_prefix = "skill:"
    single_hint = "请使用 {target} 技能完成以下任务"
    multi_hint = "请完成以下技能任务："

    def __init__(self, agent):
        """
        Args:
            agent: Skill 领域专精 Agent 实例（只绑定 Skill 工具）
        """
        self._agent = agent

    def _extract_skill_name(self, skill_intents: List[Dict[str, Any]]) -> str:
        """
        从意图列表中提取技能名称

        target 格式固定为 "skill:{skill_name}"，如 "skill:drawio-skill"

        Args:
            skill_intents: Skill 意图列表

        Returns:
            技能名称，如 "drawio-skill"，空字符串表示未提取到
        """
        if not skill_intents:
            return ""
        target = skill_intents[0].get("target", "")
        if target.startswith(self.target_prefix):
            return target[len(self.target_prefix):]
        return ""

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行技能调用

        Args:
            state: 当前状态（包含 query、intents、session_id 等）

        Returns:
            更新后的状态（包含 agent_results）
        """
        writer = get_stream_writer()
        query = state["query"]
        intents = state.get("intents", [])
        skill_intents = [i for i in intents if i.get("category") == "skill"]

        input_text = self._build_input(query, skill_intents)

        writer(Step.SKILL_EXPERT.started_event())
        log(f"[SkillExpert] 处理 Skill 意图: {len(skill_intents)} 个, 输入: {input_text[:50]}...", "MultiAgent")

        skill_name = self._extract_skill_name(skill_intents)

        agent_context = AgentContext(
            session_id=state.get("session_id", "default"),
            chat_history=state.get("chat_history", []),
            feeling=state.get("feeling", {}),
            skill_name=skill_name,
        )

        result = self._agent.invoke(input_text, agent_context)
        answer = result.get("answer", "")

        intent_results = [
            {
                "type": "skill",
                "target": intent.get("target", ""),
                "content": answer,
                "success": True,
            }
            for intent in skill_intents
        ]

        writer(Step.SKILL_EXPERT.completed_event())
        log(f"[SkillExpert] 完成: {answer[:50]}...", "MultiAgent")

        return {
            "agent_results": [{"agent": "skill_expert", "answer": answer, "intent_results": intent_results}],
        }


def create_skill_expert(agent):
    """
    创建 Skill Expert 节点函数

    Args:
        agent: Skill 领域专精 Agent 实例

    Returns:
        SkillExpertNode 实例（可直接 add_node 到主图）
    """
    return SkillExpertNode(agent)
