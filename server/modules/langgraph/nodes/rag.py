"""
RAG检索相关节点

负责：
1. 路由决策：判断是否需要检索
2. 文档检索：从知识库检索相关文档
"""

from typing import Dict, Any
from modules.logger import log


class RouterNode:
    """路由节点 - 判断是否需要检索"""

    def __init__(self, rag_workflow: Any):
        """
        初始化路由节点
        
        Args:
            rag_workflow: RAG工作流实例
        """
        self._rag_workflow = rag_workflow

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        判断是否需要检索
        
        Args:
            state: 当前状态（包含 query, session_id, chat_history, feeling）
        
        Returns:
            更新后的状态（包含 need_retrieve）
        """
        query = state["query"]
        log(f"[节点: router] 开始执行查询: {query[:30]}...", "LangGraph")

        need_retrieve = self._rag_workflow.should_retrieve(query)
        log(f"[节点: router] 决策: {'需要检索' if need_retrieve else '不需要检索'}", "LangGraph")

        return {"need_retrieve": need_retrieve}


class RetrieveNode:
    """检索节点 - 执行文档检索"""

    def __init__(self, rag_workflow: Any):
        """
        初始化检索节点
        
        Args:
            rag_workflow: RAG工作流实例
        """
        self._rag_workflow = rag_workflow

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行文档检索
        
        Args:
            state: 当前状态
        
        Returns:
            更新后的状态（documents 使用 list_append，返回增量）
        """
        query = state["query"]
        log(f"[节点: retrieve] 开始执行", "LangGraph")

        # 选择最合适的知识库
        kb = self._rag_workflow.select_knowledge_base(query)
        self._rag_workflow.switch_knowledge_base(kb)

        # 执行检索
        documents = self._rag_workflow.retrieve(query)
        log(f"[节点: retrieve] 检索到 {len(documents)} 个文档", "LangGraph")

        # 设置 RAG 成功标志（用于后续节点判断）
        rag_success = len(documents) > 0
        log(f"[节点: retrieve] RAG 成功: {rag_success}", "LangGraph")

        # 使用 list_append reducer，返回新文档（增量）
        return {
            "documents": documents,
            "rag_success": rag_success,
        }
