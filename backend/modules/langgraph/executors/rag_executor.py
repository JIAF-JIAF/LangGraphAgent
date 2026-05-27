"""
RAG 意图执行器

负责执行知识库检索和生成任务。
"""

from typing import Dict, Any
from modules.logger import log
from .base import BaseExecutor, ExecutionResult


class RAGExecutor(BaseExecutor):
    """
    RAG 意图执行器
    
    执行知识库检索和答案生成。
    """

    def __init__(self, rag_workflow: Any = None, **kwargs):
        """
        初始化 RAG 执行器
        
        Args:
            rag_workflow: RAG 工作流实例
        """
        self._rag_workflow = rag_workflow
    
    @property
    def category(self) -> str:
        return "rag"
    
    def execute(
        self,
        intent: Dict[str, Any],
        context: Dict[str, Any],
    ) -> ExecutionResult:
        """
        执行 RAG 检索和生成
        
        Args:
            intent: 意图数据
            context: 执行上下文
            
        Returns:
            执行结果
        """
        target = intent["target"]
        content = intent["content"]
        
        kb_name = target.replace("knowledge_base:", "")
        
        log(f"[RAGExecutor] 切换知识库: {kb_name}", "Executor")
        self._rag_workflow.switch_knowledge_base(kb_name)
        
        log(f"[RAGExecutor] 执行检索: {content[:30]}...", "Executor")
        documents = self._rag_workflow.retrieve(content)
        
        if documents:
            log(f"[RAGExecutor] 检索到 {len(documents)} 个文档，开始生成", "Executor")
            result = self._rag_workflow.generate(content, documents)
            return ExecutionResult(
                success=True,
                content=result,
                metadata={"kb_name": kb_name, "doc_count": len(documents)}
            )
        else:
            log(f"[RAGExecutor] 未检索到文档", "Executor")
            return ExecutionResult(
                success=False,
                content=f"未在知识库 {kb_name} 中找到相关信息。",
                metadata={"kb_name": kb_name, "doc_count": 0}
            )


from .registry import ExecutorRegistry
ExecutorRegistry.register("rag", RAGExecutor)
