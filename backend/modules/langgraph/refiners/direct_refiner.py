"""
直接生成润色器

负责直接生成回答（system 路径或无结果情况）。
"""

from typing import Any
from modules.logger import log
from modules.context import AgentContext
from .base import BaseRefiner, RefineContext


class DirectRefiner(BaseRefiner):
    """
    直接生成润色器
    
    处理 system 路径或无结果情况的直接生成。
    """

    @property
    def name(self) -> str:
        return "direct"
    
    def can_handle(self, context: RefineContext) -> bool:
        return not context.intent_results and not context.answer
    
    def refine(self, context: RefineContext, agent: Any) -> str:
        """
        直接生成回答
        
        Args:
            context: 润色上下文
            agent: Agent 实例
            
        Returns:
            生成的回答
        """
        log(f"[DirectRefiner] 直接生成回答", "Refiner")
        
        agent_context = AgentContext(
            chat_history=context.chat_history,
            feeling=context.feeling
        )
        
        result = agent.invoke(context.query, agent_context)
        answer = result.get("answer", "")
        
        log(f"[DirectRefiner] 生成完成: {answer[:50]}...", "Refiner")
        return answer


from .refiner_registry import RefinerRegistry
RefinerRegistry.register("direct", DirectRefiner)
