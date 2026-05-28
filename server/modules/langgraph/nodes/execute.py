"""
执行节点

负责：
1. 直接执行：按顺序执行简单意图（RAG/Skill/MCP）
2. 任务执行：执行单个子任务
3. 任务完成检查：判断是否有更多任务需要执行
"""

from typing import Dict, Any
from modules.logger import log
from modules.context import AgentContext
from ..context_builder import ContextBuilder
from ..executors import ExecutorRegistry


class ExecuteDirectNode:
    """直接执行节点"""

    def __init__(self, executors: Dict[str, Any]):
        """
        初始化直接执行节点
        
        Args:
            executors: 执行器注册表
        """
        self._executors = executors

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        按顺序执行简单意图
        
        Args:
            state: 当前状态（包含 intents）
        
        Returns:
            更新后的状态（包含 intent_results）
        """
        intents = state.get("intents", [])
        
        log(f"[节点: execute_direct] 开始直接执行 {len(intents)} 个意图", "LangGraph")
        
        context = {
            "query": state["query"],
            "feeling": state["feeling"],
            "chat_history": state.get("chat_history", []),
        }
        
        results = ExecutorRegistry.execute_all(intents, context, self._executors)
        
        log(f"[节点: execute_direct] 执行完成，收集到 {len(results)} 个结果", "LangGraph")

        return {
            "intent_results": results,
        }


class ExecuteTaskNode:
    """任务执行节点"""

    def __init__(self, agent: Any):
        """
        初始化任务执行节点
        
        Args:
            agent: LangChain Agent 实例
        """
        self._agent = agent

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行当前子任务
        
        Args:
            state: 当前状态（包含 subtasks, current_task_idx, feeling）
        
        Returns:
            更新后的状态（包含执行结果）
        """
        subtasks = state["subtasks"]
        current_idx = state["current_task_idx"]
        feeling = state["feeling"]

        current_task = subtasks[current_idx]
        task_desc = current_task["task_description"]
        log(f"[节点: execute_task] 执行任务 {current_idx + 1}/{len(subtasks)}: {task_desc[:30]}...", "LangGraph")

        # 使用 ContextBuilder 构建完整任务 prompt
        documents = state.get("documents", [])
        enhanced_task = ContextBuilder.build_task_with_context(task_desc, documents)
        if documents:
            log(f"[节点: execute_task] 注入 {len(documents)} 个RAG文档作为上下文", "LangGraph")

        # 调用 Agent 执行任务
        agent_context = AgentContext(
            session_id=state.get("session_id", "default"),
            chat_history=state.get("chat_history", []),
            feeling=feeling
        )
        
        result = self._agent.invoke(enhanced_task, agent_context)
        task_result = result.get("answer", "")

        log(f"[节点: execute_task] 任务执行完成: {task_result[:50]}...", "LangGraph")

        # 更新任务结果
        subtasks[current_idx]["result"] = task_result
        subtasks[current_idx]["status"] = "completed"

        return {
            "subtasks": subtasks,
            "answer": task_result,
            "is_task_completed": True
        }


class CheckTaskCompleteNode:
    """任务完成检查节点"""

    def __init__(self, task_planner: Any):
        """
        初始化任务完成检查节点
        
        Args:
            task_planner: 任务规划器实例
        """
        self._planner = task_planner

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        判断是否有更多任务需要执行
        
        Args:
            state: 当前状态（包含 subtasks, current_task_idx, answer）
        
        Returns:
            更新后的状态（汇总最终答案或更新任务索引）
        """
        subtasks = state["subtasks"]
        current_idx = state["current_task_idx"]
        answer = state["answer"]

        log(f"[节点: check_task_complete] 检查任务完成情况", "LangGraph")

        # 如果已完成所有任务
        if current_idx >= len(subtasks) - 1:
            log(f"[节点: check_task_complete] 所有任务已完成", "LangGraph")

            # 生成汇总结果
            summary = self._planner.get_summary(subtasks)
            if summary:
                answer = summary
                log(f"[节点: check_task_complete] 生成汇总结果: {summary[:50]}...", "LangGraph")
            return {
                "answer": answer,
                "is_task_completed": True,
                "current_task_idx": current_idx
            }

        # 还有更多任务
        next_idx = current_idx + 1
        log(f"[节点: check_task_complete] 准备执行下一个任务: {next_idx + 1}/{len(subtasks)}", "LangGraph")

        return {
            "current_task_idx": next_idx,
            "is_task_completed": False,
        }
