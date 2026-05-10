"""
LangGraph 状态定义
"""

from typing import TypedDict, List, Dict, Any, Optional
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """Agent 状态定义"""
    query: str  # 用户查询
    session_id: str  # 会话 ID
    chat_history: List[BaseMessage]  # 对话历史（统一管理）
    need_retrieve: bool  # 是否需要检索
    documents: List[Document]  # 检索到的文档
    answer: str  # 生成的回答
    feeling: Dict[str, Any]  # 用户情绪状态 {"feeling": str, "score": int}
