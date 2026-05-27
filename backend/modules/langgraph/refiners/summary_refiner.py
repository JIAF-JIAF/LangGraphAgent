"""
汇总结果润色器

负责润色任务汇总结果（plan 路径）。
"""

from typing import Any
from modules.logger import log
from modules.context import AgentContext
from .base import BaseRefiner, RefineContext


class SummaryRefiner(BaseRefiner):
    """
    汇总结果润色器
    
    处理 plan 路径的任务汇总结果润色。
    """

    @property
    def name(self) -> str:
        return "summary"
    
    def can_handle(self, context: RefineContext) -> bool:
        return bool(context.answer) and not context.intent_results
    
    def refine(self, context: RefineContext, agent: Any) -> str:
        """
        润色汇总结果
        
        Args:
            context: 润色上下文
            agent: Agent 实例
            
        Returns:
            润色后的回答
        """
        prompt = self.build_prompt(
            query=context.query,
            content=context.answer,
            feeling=context.feeling,
            content_label="任务执行结果",
        )
        
        log(f"[SummaryRefiner] 开始润色汇总结果", "Refiner")
        
        agent_context = AgentContext(
            chat_history=context.chat_history,
            feeling=context.feeling
        )
        
        result = agent.invoke(prompt, agent_context)
        answer = result.get("answer", "")
        
        log(f"[SummaryRefiner] 润色完成: {answer[:50]}...", "Refiner")
        return answer


from .refiner_registry import RefinerRegistry
RefinerRegistry.register("summary", SummaryRefiner)
