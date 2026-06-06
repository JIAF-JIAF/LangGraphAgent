"""
多 Agent 状态定义

扩展现有 AgentState，保留全部字段，新增多 Agent 协作所需字段。

设计原则：
- 完全兼容现有 AgentState（所有字段原样保留，类型一致）
- chat_history 保留 add_messages_with_truncation reducer（裁剪逻辑不丢失）
- agent_results 使用 add_agent_results reducer（支持并行追加 + Supervisor 重置）
- current_agent 为普通字段（同一时刻只有一个活跃 Agent）

类型对照（与 states/base.py 严格一致）：
- feeling: FeelingState（Pydantic BaseModel），不是 Dict
- subtasks: List[SubTaskState]（Pydantic BaseModel），不是 List[Dict]
"""

from typing import TypedDict, Annotated, Optional, List, Dict, Any
from langchain_core.messages import BaseMessage
from langchain_core.documents import Document

from modules.langgraph.states.base import add_messages_with_truncation, FeelingState, SubTaskState


def keep_last(existing: Any, updates: Any) -> Any:
    """
    并行安全 reducer：取最后一个值

    用于 query、session_id 等只读字段。
    并行节点不会修改这些字段，但 LangGraph Send API 并行执行时
    会将同一 state 传给多个节点，合并输出时需要 reducer 避免冲突。
    由于这些字段值不变，取任意一个都等价，取最后一个即可。

    Args:
        existing: 当前 state 中的值
        updates: 新写入的值

    Returns:
        updates（如果非 None），否则返回 existing
    """
    return updates if updates is not None else existing


def add_agent_results(existing: List[Dict[str, Any]], updates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    agent_results 专用 reducer

    支持两种场景：
    1. 并行 Expert 写入：多个 Expert 同时返回各自的 agent_results，使用 operator.add 追加
    2. Supervisor 重置：Supervisor 节点返回 {"agent_results": None} 触发重置为空列表

    跨请求累积问题：LangGraph Checkpointer 会恢复历史状态，导致上一轮的
    agent_results 残留。Supervisor 在每轮开始时返回 agent_results=None 重置。

    Args:
        existing: 当前 agent_results 列表
        updates: 新写入的 agent_results（None 表示重置）

    Returns:
        重置后返回空列表，否则返回追加后的列表
    """
    if updates is None:
        return []
    return existing + updates


class MultiAgentState(TypedDict):
    """
    多 Agent 状态（扩展 AgentState，保留全部现有字段）

    现有字段与 AgentState 完全一致，新增：
    - current_agent: 当前活跃 Agent 名称
    - agent_results: 各 Agent 结果（支持并行追加）

    注意：query、session_id 等只读字段使用 keep_last reducer，
    因为 LangGraph Send API 并行执行时需要 reducer 处理多个节点
    对同一 state key 的并发写入（虽然值不变，但框架要求有 reducer）。
    """
    # === ContextState：对话上下文 ===
    query: Annotated[str, keep_last]                        # 用户原始输入
    session_id: Annotated[str, keep_last]                   # 会话唯一标识
    uid: Annotated[Optional[str], keep_last]                # 用户标识
    chat_history: Annotated[List[BaseMessage], add_messages_with_truncation(20)]  # 对话历史

    # === RAGState：知识检索 ===
    need_retrieve: Annotated[bool, keep_last]               # 是否需要触发知识库检索
    documents: Annotated[List[Document], keep_last]         # RAG 检索到的文档片段列表
    answer: Annotated[str, keep_last]                       # 最终生成的回答文本
    feeling: Annotated[FeelingState, keep_last]             # 情绪检测结果
    rag_success: Annotated[bool, keep_last]                 # RAG 检索是否成功

    # === TaskState：任务规划 ===
    subtasks: Annotated[List[SubTaskState], keep_last]      # 子任务列表
    current_task_idx: Annotated[int, keep_last]             # 当前子任务索引
    is_task_completed: Annotated[bool, keep_last]           # 所有子任务是否完成

    # === IntentState：意图识别 ===
    intents: Annotated[List[Dict[str, Any]], keep_last]     # 意图列表
    is_multi_intent: Annotated[bool, keep_last]             # 是否多意图
    current_intent_idx: Annotated[int, keep_last]           # 当前意图索引
    current_intent: Annotated[Optional[Dict[str, Any]], keep_last]  # 当前意图对象
    execution_mode: Annotated[str, keep_last]               # 执行模式
    intent_results: Annotated[List[Dict[str, Any]], keep_last]  # 意图执行结果

    # === 多 Agent 协作字段 ===
    current_agent: Annotated[str, keep_last]                # 当前活跃 Agent 名称
    agent_results: Annotated[List[Dict[str, Any]], add_agent_results]  # 各 Agent 结果，自定义 reducer
    planned_subtasks: Annotated[List[Dict[str, Any]], keep_last]  # Planner 分解的子任务列表（含依赖关系）

    # === Planner 调度内部字段（以 __ 开头，每轮由 Supervisor 重置，不依赖 Checkpointer 持久化值） ===
    __ready_indices__: Annotated[Optional[List[int]], keep_last]       # 本轮就绪子任务索引列表
    __dispatch_complete__: Annotated[bool, keep_last]                  # 所有子任务是否已调度完成
    __subtask_idx__: Annotated[Optional[int], keep_last]               # 当前 Expert 处理的子任务索引（Planner 调度标记）


def create_multi_agent_initial_state(
    query: str,
    session_id: str,
    uid: Optional[str] = None,
) -> Dict[str, Any]:
    """
    创建多 Agent 初始状态

    Args:
        query: 用户原始输入
        session_id: 会话唯一标识
        uid: 用户标识（可选）

    Returns:
        MultiAgentState 的初始值字典
    """
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
        "current_agent": "",
        "agent_results": [],
        "planned_subtasks": [],
        "__ready_indices__": None,
        "__dispatch_complete__": False,
        "__subtask_idx__": None,
    }
