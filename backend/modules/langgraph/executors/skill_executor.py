"""
Skill 意图执行器

负责执行技能调用任务。
"""

from typing import Dict, Any
from modules.logger import log
from modules.context import AgentContext
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
        
        result = self._agent.invoke(content, agent_context)
        answer = result.get("answer", "")
        
        log(f"[SkillExecutor] 技能执行完成: {answer[:50]}...", "Executor")
        
        return ExecutionResult(
            success=True,
            content=answer,
            metadata={"skill_name": skill_name}
        )


from .registry import ExecutorRegistry
ExecutorRegistry.register("skill", SkillExecutor)
