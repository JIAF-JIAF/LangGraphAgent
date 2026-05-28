"""
任务规划节点

负责将复杂需求拆分为子任务，使用责任链模式处理任务生成。
"""

from typing import Dict, Any
from modules.logger import log
from ..task_generators import TaskGeneratorChain


class PlanNode:
    """任务规划节点"""

    def __init__(self, task_planner):
        """
        初始化任务规划节点
        
        Args:
            task_planner: 任务规划器实例
        """
        self._planner = task_planner

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        将复杂需求拆分为子任务
        
        Args:
            state: 当前状态（包含 query, documents, answer, rag_success）
        
        Returns:
            更新后的状态（包含子任务队列和初始状态）
        """
        query = state["query"]
        log(f"[节点: plan] 开始任务规划", "LangGraph")

        # 使用责任链模式生成子任务
        chain = TaskGeneratorChain.build()
        subtasks = chain.handle(state, self._planner, query)

        log(f"[节点: plan] 生成 {len(subtasks)} 个子任务", "LangGraph")
        for i, task in enumerate(subtasks):
            log(f"  [{i+1}] {task['task_description'][:30]}...", "LangGraph")

        return {
            "subtasks": subtasks,
            "current_task_idx": 0,
            "is_task_completed": False,
        }
