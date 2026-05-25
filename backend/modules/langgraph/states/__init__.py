"""
LangGraph 状态模块

采用 Pydantic 子状态 + TypedDict 顶层 + Annotated Reducer 模式：
- 子状态使用 Pydantic BaseModel（类型安全、自动校验、默认值）
- 顶层状态使用 TypedDict（支持 state["key"] 访问）
- List 字段使用 Annotated + Reducer 实现自动追加

模块划分：
- ContextState: 上下文（query, session_id, uid, chat_history）
- RAGState: RAG 检索（documents, answer, feeling, need_retrieve）
- TaskState: 任务规划（subtasks, current_task_idx, is_task_completed）
- IntentState: 意图识别（intents, is_multi_intent, current_intent_idx）
"""

from .base import (
    AgentState,
    ContextState,
    RAGState,
    TaskState,
    IntentState,
    FeelingState,
    SubTaskState,
    create_initial_state,
)

__all__ = [
    "AgentState",
    "ContextState",
    "RAGState",
    "TaskState",
    "IntentState",
    "FeelingState",
    "SubTaskState",
    "create_initial_state",
]
