"""
条件路由函数

负责定义状态图中各节点之间的条件分支逻辑。
"""

from typing import Dict, Any, Literal
from modules.logger import log
from modules.intent import IntentCategory, IntentConstants


def route_by_intent(state: Dict[str, Any]) -> Literal["direct", "plan", "system"]:
    """
    条件路由：根据意图类型决定执行路径
    
    Args:
        state: 当前状态（包含 intents）
    
    Returns:
        "direct": 简单意图直接执行
        "plan": 复杂意图需要规划
        "system": 系统指令
    """
    intents = state.get("intents", [])

    if not intents:
        return "plan"

    for intent_data in intents:
        category = IntentCategory(intent_data["category"])
        if category == IntentCategory.SYSTEM:
            return "system"

    for intent_data in intents:
        category = IntentCategory(intent_data["category"])
        if category not in IntentConstants.SIMPLE_CATEGORIES:
            return "plan"

    return "direct"


def should_retrieve(state: Dict[str, Any]) -> Literal["retrieve", "plan"]:
    """
    条件路由：判断是否需要检索
    
    Args:
        state: 当前状态（包含 need_retrieve）
    
    Returns:
        "retrieve" 或 "plan"，决定下一步流向
    """
    decision = "retrieve" if state["need_retrieve"] else "plan"
    log(f"[条件路由] 决策: {decision}", "LangGraph")
    return decision


def should_continue_tasks(state: Dict[str, Any]) -> Literal["execute_task", "call_model"]:
    """
    条件路由：判断是否继续执行下一个任务
    
    Args:
        state: 当前状态（包含 subtasks, current_task_idx, is_task_completed）
    
    Returns:
        "execute_task" 或 "call_model"，决定下一步流向
    """
    subtasks = state.get("subtasks", [])
    current_idx = state.get("current_task_idx", 0)
    is_task_completed = state.get("is_task_completed", False)

    if not subtasks:
        log(f"[条件路由] 无子任务，进入最终回答", "LangGraph")
        return "call_model"

    if is_task_completed or current_idx > len(subtasks) - 1:
        log(f"[条件路由] 所有任务已完成，进入最终回答", "LangGraph")
        return "call_model"
    else:
        log(f"[条件路由] 还有任务未完成，继续执行任务 {current_idx + 1}/{len(subtasks)}", "LangGraph")
        return "execute_task"
