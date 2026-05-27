"""
意图结果润色器

负责润色意图执行结果（direct 路径）。
"""

from typing import Any
from modules.logger import log
from modules.context import AgentContext
from .base import BaseRefiner, RefineContext


class IntentResultRefiner(BaseRefiner):
    """
    意图结果润色器
    
    处理 direct 路径的意图执行结果润色。
    """

    @property
    def name(self) -> str:
        return "intent_result"
    
    def can_handle(self, context: RefineContext) -> bool:
        return bool(context.intent_results)
    
    def refine(self, context: RefineContext, agent: Any) -> str:
        """
        润色意图执行结果
        
        Args:
            context: 润色上下文
            agent: Agent 实例
            
        Returns:
            润色后的回答
        """
        context_parts = []
        for i, result in enumerate(context.intent_results):
            result_type = result.get("type", "unknown").upper()
            content = result.get("content", "")
            context_parts.append(f"【{i+1}. {result_type}】\n{content}")
        
        combined_content = "\n\n".join(context_parts)
        
        prompt = self.build_prompt(
            query=context.query,
            content=combined_content,
            feeling=context.feeling,
            content_label="执行结果",
        )
        
        log(f"[IntentResultRefiner] 开始润色 {len(context.intent_results)} 个意图结果", "Refiner")
        
        agent_context = AgentContext(
            chat_history=context.chat_history,
            feeling=context.feeling
        )
        
        result = agent.invoke(prompt, agent_context)
        answer = result.get("answer", "")
        
        log(f"[IntentResultRefiner] 润色完成: {answer[:50]}...", "Refiner")
        return answer


from .refiner_registry import RefinerRegistry
RefinerRegistry.register("intent_result", IntentResultRefiner)
