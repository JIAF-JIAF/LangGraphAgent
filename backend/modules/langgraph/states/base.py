"""
LangGraph 状态定义

采用 Pydantic 子状态 + TypedDict 顶层模式：
- 子状态使用 Pydantic BaseModel（类型安全、自动校验、默认值）
- 顶层状态使用 TypedDict（支持 state["key"] 访问）
- chat_history 使用带裁剪的 add_messages reducer 实现增量追加
"""

from typing import TypedDict, Optional, List, Dict, Any, Annotated, Callable
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from langchain_core.documents import Document
from langgraph.graph.message import add_messages


def add_messages_with_truncation(max_messages: int = 20) -> Callable[[List[BaseMessage], List[BaseMessage]], List[BaseMessage]]:
    """
    创建带裁剪功能的消息追加 reducer

    Args:
        max_messages: 最大消息数（默认20条，即10轮对话）

    Returns:
        带裁剪功能的 reducer 函数
    """
    def reducer(existing: List[BaseMessage], updates: List[BaseMessage]) -> List[BaseMessage]:
        # 合并已有消息和新增消息
        combined = existing + updates
        # 超过最大消息数时，保留最新的消息
        if len(combined) > max_messages:
            return combined[-max_messages:]
        return combined
    return reducer


class FeelingState(BaseModel):
    feeling: str = "default"
    score: int = 5


class SubTaskState(BaseModel):
    task_id: str = ""
    task_description: str = ""
    dependencies: List[str] = Field(default_factory=list)
    status: str = "pending"
    result: str = ""


class ContextState(TypedDict):
    """上下文相关状态"""
    query: str                                       # 用户查询
    session_id: str                                  # 会话ID
    uid: Optional[str]                               # 用户ID
    chat_history: Annotated[List[BaseMessage], add_messages_with_truncation(20)]  # 对话历史（带裁剪）


class RAGState(TypedDict):
    """RAG 检索相关状态"""
    need_retrieve: bool                              # 是否需要检索
    documents: List[Document]                        # 检索到的文档
    answer: str                                      # 生成的回答
    feeling: FeelingState                            # 情绪状态
    rag_success: bool                                # RAG 是否成功


class TaskState(TypedDict):
    """任务规划相关状态"""
    subtasks: List[SubTaskState]                     # 子任务列表
    current_task_idx: int                            # 当前任务索引
    is_task_completed: bool                          # 任务是否完成


class IntentState(TypedDict):
    """意图识别相关状态"""
    intents: List[Dict[str, Any]]                    # 意图列表
    is_multi_intent: bool                            # 是否多意图
    current_intent_idx: int                          # 当前处理的意图索引
    current_intent: Optional[Dict[str, Any]]         # 当前意图
    execution_mode: str                              # 执行模式: direct / plan / system
    intent_results: List[Dict[str, Any]]             # 意图执行结果列表


class AgentState(ContextState, RAGState, TaskState, IntentState):
    """完整 Agent 状态（多重继承组合所有子状态）"""
    pass


def create_initial_state(
    query: str,
    session_id: str,
    uid: Optional[str] = None,
) -> AgentState:
    return {
        "query": query,
        "session_id": session_id,
        "uid": uid,
        "chat_history": [],
        "need_retrieve": False,
        "documents": [],
        "answer": "",
        "feeling": FeelingState(),
        "rag_success": False,
        "subtasks": [],
        "current_task_idx": 0,
        "is_task_completed": False,
        "intents": [],
        "is_multi_intent": False,
        "current_intent_idx": 0,
        "current_intent": None,
        "execution_mode": "plan",
        "intent_results": [],
    }
