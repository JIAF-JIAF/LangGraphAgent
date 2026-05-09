"""
RAG 业务模块

提供 RAG 相关的业务方法，供 LangGraph 调用
不包含图结构，只负责具体业务逻辑
"""

import time
from typing import Optional, Dict, Any, List
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage

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

    def _expand_query(self, query: str) -> list:
        """
        扩展用户查询，生成多个相关查询词

        Args:
            query: 用户原始查询

        Returns:
            查询词列表（包含原始查询和扩展查询）
        """
        if not self.llm_client:
            return [query]

        prompt = f"""
        你是一个查询扩展专家，请根据用户的查询生成多个相关的查询词，用于检索知识库。

        用户查询：{query}

        请生成3-5个相关的查询词，每个查询词应该：
        1. 与原始查询含义相同或相关
        2. 使用不同的表达方式
        3. 包含同义词或相关术语
        4. 考虑可能的缩写或简称

        请只返回查询词列表，每个查询词占一行，不要添加其他任何内容。
        """

        try:
            response = self.llm_client.chat.invoke([HumanMessage(content=prompt)])
            queries = [q.strip() for q in response.content.strip().split('\n') if q.strip()]
            # 确保包含原始查询
            if query not in queries:
                queries.insert(0, query)
            return queries[:5]  # 最多返回5个
        except Exception as e:
            self._log(f"[RAG] 查询扩展失败: {e}")
            return [query]

    def retrieve(self, query: str) -> List[Document]:
        """
        执行检索（支持查询扩展）

        Args:
            query: 用户查询

        Returns:
            检索到的文档列表
        """
        self._log(f"[RAG] 执行检索: {query[:30]}...")

        # 使用查询扩展
        expanded_queries = self._expand_query(query)
        self._log(f"[RAG] 扩展查询词: {expanded_queries}")

        # 合并多次检索结果（去重）
        all_documents = {}
        for q in expanded_queries:
            docs = self.retriever.retrieve(q)
            for doc in docs:
                # 使用文档内容作为key去重
                key = doc.page_content[:50] if doc.page_content else str(id(doc))
                if key not in all_documents:
                    all_documents[key] = doc

        documents = list(all_documents.values())
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
