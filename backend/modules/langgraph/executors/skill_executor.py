"""
Skill 意图执行器

负责执行技能调用任务。
"""

from typing import Dict, Any
from modules.logger import log
from modules.context import AgentContext
from modules.mcp_module.context import set_value, remove_value
from .base import BaseExecutor, ExecutionResult


class SkillExecutor(BaseExecutor):
    """
    Skill 意图执行器
    
    通过 Agent 执行技能调用。
    """

    def __init__(self, agent: Any = None, **kwargs):
        """
        初始化 Skill 执行器
        
        Args:
            agent: LangChain Agent 实例
        """
        self._agent = agent
    
    @property
    def category(self) -> str:
        return "skill"
    
    def execute(
        self,
        intent: Dict[str, Any],
        context: Dict[str, Any],
    ) -> ExecutionResult:
        """
        执行技能调用
        
        Args:
            intent: 意图数据
            context: 执行上下文
            
        Returns:
            执行结果
        """
        content = intent["content"]
        target = intent["target"]
        skill_name = target.replace("skill:", "")
        
        # 构建 AgentContext
        agent_context = AgentContext(
            chat_history=context.get("chat_history", []),
            feeling=context.get("feeling", {}),
            skill_name=skill_name
        )
        
        log(f"[SkillExecutor] 执行技能: {skill_name}", "Executor")
        
        # 设置全局 skill_name，供工具调用时使用
        set_value("skill_name", skill_name)
        
        try:
            result = self._agent.invoke(content, agent_context)
            answer = result.get("answer", "")
        finally:
            # 确保清理全局变量
            remove_value("skill_name")
        
        log(f"[SkillExecutor] 技能执行完成: {answer[:50]}...", "Executor")
        
        return ExecutionResult(
            success=True,
            content=answer,
            metadata={"skill_name": skill_name}
        )


from .registry import ExecutorRegistry
ExecutorRegistry.register("skill", SkillExecutor)
