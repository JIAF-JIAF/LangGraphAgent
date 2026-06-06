"""
Chat 润色器

用于 Chat Expert 的 Supervisor 直接调度路径。
直接调用 Agent 生成回答，无需额外润色（Agent 本身已生成自然语言回答）。
"""

from typing import Any
from .base import BaseRefiner, RefineContext
from modules.logger import log


class ChatRefiner(BaseRefiner):
    """
    Chat 润色器

    处理 Chat Expert 的 Supervisor 直接调度路径。
    直接调用 Agent 生成回答，Agent 输出即为最终回答，无需二次润色。
    """

    def __init__(self, **kwargs):
        pass

    @property
    def name(self) -> str:
        return "chat"

    def can_handle(self, context: RefineContext) -> bool:
        """
        兜底润色器：当没有其他润色器匹配时，总是能处理

        Chat Expert 的 Supervisor 直接调度路径走此润色器，
        直接调用 Agent 生成回答即可。
        """
        return True

    def refine(self, context: RefineContext, agent: Any) -> str:
        """
        直接调用 Agent 生成回答

        Args:
            context: 润色上下文
            agent: Agent 实例

        Returns:
            Agent 生成的回答
        """
        try:
            response = agent.invoke({
                "input": context.query,
                "chat_history": context.chat_history,
            })

            if isinstance(response, dict):
                answer = response.get("output", str(response))
            else:
                answer = str(response)

            log(f"[ChatRefiner] Agent 回答: {answer[:50]}...", "Refiner")
            return answer
        except Exception as e:
            log(f"[ChatRefiner] Agent 调用失败: {e}", "Refiner")
            return ""
