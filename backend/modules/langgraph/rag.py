"""
RAG 业务模块

提供 RAG 相关的业务方法，供 LangGraph 调用
不包含图结构，只负责具体业务逻辑
"""

import time
from typing import Optional, Dict, Any, List
from langchain_core.documents import Document

from modules.rag.indexer import ChromaIndexer
from modules.rag.retriever import SimpleVectorRetriever
from modules.rag.generator import BaseGenerator
from modules.rag.memory import ConversationMemory
from modules.rag.router import LLMRouter


class RAGWorkflow:
    """
    RAG 业务模块

    提供 RAG 相关的业务方法：
    - should_retrieve: 判断是否需要检索
    - retrieve: 执行检索
    - generate: 生成回答
    """

    def __init__(self, llm_client=None, config: Optional[Dict] = None, verbose: bool = True):
        """
        初始化 RAG 业务模块

        Args:
            llm_client: LLM 客户端（用于路由器和生成器）
            config: 配置字典
            verbose: 是否输出详细日志
        """
        self.llm_client = llm_client
        self.config = config or {}
        self._verbose = verbose
        self._log("初始化 RAG 业务模块...")

        # 初始化索引器（支持多知识库）
        self.indexers = {}
        self.indexers["default"] = ChromaIndexer(
            ai_client=llm_client,
            config=self.config.get("indexer", {}),
            collection_name="default"
        )
        self.indexers["politics"] = ChromaIndexer(
            ai_client=llm_client,
            config=self.config.get("indexer", {}),
            collection_name="politics"
        )

        # 初始化检索器
        self.retriever = SimpleVectorRetriever(config=self.config.get("retriever", {}))

        # 初始化路由器（只初始化一次，复用）
        self.router = LLMRouter(
            llm_client=llm_client,
            config=self.config.get("router", {})
        )

        # 初始化记忆模块
        self.memory = ConversationMemory(config=self.config.get("memory", {}))

        self._log("RAG 业务模块初始化完成")

    def _log(self, message: str, level: str = "INFO"):
        if self._verbose:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [RAG] [{level}] {message}", flush=True)

    def should_retrieve(self, query: str) -> bool:
        """
        判断是否需要检索

        Args:
            query: 用户查询

        Returns:
            True - 需要检索
            False - 不需要检索
        """
        self._log(f"[RAG] 判断是否需要检索: {query[:30]}...")

        need = self.router.should_retrieve(query)

        self._log(f"[RAG] 检索决策: {need}")
        return need

    def select_knowledge_base(self, query: str) -> str:
        """
        选择知识库

        Args:
            query: 用户查询

        Returns:
            知识库名称
        """
        kb = self.router.select_knowledge_base(query)

        self._log(f"[RAG] 选择的知识库: {kb}")
        return kb

    def switch_knowledge_base(self, name: str) -> bool:
        """
        切换知识库

        Args:
            name: 知识库名称

        Returns:
            是否切换成功
        """
        if name in self.indexers:
            self.retriever.indexer = self.indexers[name]
            self.retriever._init_retriever()
            self._log(f"[RAG] 已切换到知识库: {name}")
            return True
        return False

    def retrieve(self, query: str) -> List[Document]:
        """
        执行检索

        Args:
            query: 用户查询

        Returns:
            检索到的文档列表
        """
        self._log(f"[RAG] 执行检索: {query[:30]}...")

        documents = self.retriever.retrieve(query)
        self._log(f"[RAG] 检索到 {len(documents)} 个文档")

        return documents

    def generate(self, query: str, documents: List[Document], session_id: str = "default") -> str:
        """
        生成回答

        Args:
            query: 用户查询
            documents: 检索到的文档列表
            session_id: 会话 ID

        Returns:
            生成的回答
        """
        self._log(f"[RAG] 生成回答 (文档数: {len(documents)})")

        self.memory.add_message(session_id, "human", query)

        # generator = BaseGenerator(
        #     llm_client=self.llm_client,
        #     config=self.config.get("generator", {})
        # )
        # answer = generator.generate(query, documents)

        if not documents:
            answer = "未找到相关知识"
        else:
            context = "\n\n".join([doc.page_content for doc in documents])
            answer = context

        self.memory.add_message(session_id, "assistant", answer)

        self._log(f"[RAG] 生成回答完成: {answer[:50]}...")
        return answer

    def build_index(self, source_dir: str = "knowledge_base"):
        """
        构建索引（可选，供初始化调用）

        Args:
            source_dir: 知识库目录
        """
        self._log(f"[RAG] 构建索引...")

        for kb_name, indexer in self.indexers.items():
            kb_source_dir = f"{source_dir}/{kb_name}"
            if hasattr(indexer, 'build_index'):
                try:
                    indexer.build_index(kb_source_dir)
                    self._log(f"[RAG] 知识库 {kb_name} 索引构建完成")
                except Exception as e:
                    self._log(f"[RAG] 知识库 {kb_name} 索引构建失败: {e}")
