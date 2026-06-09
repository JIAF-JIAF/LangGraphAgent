"""
Skill Expert 插件

处理技能执行意图。使用领域专精 Agent（只绑定 Skill 工具），
LLM-in-the-loop 自动完成技能选择和参数提取。
"""

from modules.langgraph.multi_agent.plugins.skill_plugin.plugin import SkillPlugin

__all__ = ["SkillPlugin"]
