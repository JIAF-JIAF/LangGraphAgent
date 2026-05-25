"""
RAG 业务模块

提供 RAG 相关的业务方法，供 LangGraph 调用
不包含图结构，只负责具体业务逻辑
"""

from typing import Optional, Dict, Any, List
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage

from modules.logger import log, exception
from modules.rag.indexer import ChromaIndexer
from modules.rag.retriever import SimpleVectorRetriever
from modules.rag.generator import BaseGenerator
from modules.rag.router import LLMRouter
from knowledge_base import kb_manager


class RAGWorkflow:
    """
    RAG 业务模块

    提供 RAG 相关的业务方法：
    - should_retrieve: 判断是否需要检索
    - retrieve: 执行检索
    - generate: 生成回答
    """

    def __init__(self, llm_client=None, verbose: bool = True):
        """
        初始化 RAG 业务模块

        Args:
            llm_client: LLM 客户端（用于路由器和生成器）
            verbose: 是否输出详细日志
        """
        self.llm_client = llm_client
        self._verbose = verbose
        log("初始化 RAG 业务模块...", "RAG")

        # 动态初始化索引器（从知识库管理器获取所有知识库）
        self.indexers = {}
        db_names = kb_manager.get_all_collection_names()
        for db_name in db_names:
            self.indexers[db_name] = ChromaIndexer(
                ai_client=llm_client,
                collection_name=db_name
            )
            log(f"已初始化知识库索引器: {db_name}", "RAG")

        # 初始化检索器
        self.retriever = SimpleVectorRetriever()

        # 初始化路由器（只初始化一次，复用）
        self.router = LLMRouter(llm_client=llm_client)

        log("RAG 业务模块初始化完成", "RAG")

    def should_retrieve(self, query: str) -> bool:
        """
        判断是否需要检索

        Args:
            query: 用户查询

        Returns:
            True - 需要检索
            False - 不需要检索
        """
        log(f"[RAG] 判断是否需要检索: {query[:30]}...", "RAG")

        need = self.router.should_retrieve(query)

        log(f"[RAG] 检索决策: {need}", "RAG")
        return need

    def get_available_knowledge_bases(self) -> List[Dict[str, str]]:
        """
        获取所有可用知识库信息

        Returns:
            知识库信息列表，每个元素包含 name 和 description
        """
        result = []
        for kb_name in self.indexers.keys():
            kb_info = kb_manager.get_database(kb_name)
            result.append({
                "name": kb_name,
                "description": kb_info.get("description", f"查询 {kb_name} 知识库") if kb_info else f"查询 {kb_name} 知识库"
            })
        return result

    def select_knowledge_base(self, query: str) -> str:
        """
        选择知识库

        Args:
            query: 用户查询

        Returns:
            知识库名称
        """
        kb = self.router.select_knowledge_base(query)

        log(f"[RAG] 选择的知识库: {kb}", "RAG")
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
            log(f"[RAG] 已切换到知识库: {name}", "RAG")
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
            exception(f"[RAG] 查询扩展失败: {e}", "RAG", e)
            return [query]

    def retrieve(self, query: str) -> List[Document]:
        """
        执行检索（支持查询扩展）

        Args:
            query: 用户查询

        Returns:
            检索到的文档列表
        """
        log(f"[RAG] 执行检索: {query[:30]}...", "RAG")

        # 使用查询扩展
        expanded_queries = self._expand_query(query)
        log(f"[RAG] 扩展查询词: {expanded_queries}", "RAG")

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
        log(f"[RAG] 检索到 {len(documents)} 个文档", "RAG")

        return documents

    def generate(self, query: str, documents: List[Document], session_id: str = "default") -> Dict[str, Any]:
        """
        生成回答

        Args:
            query: 用户查询
            documents: 检索到的文档列表
            session_id: 会话 ID

        Returns:
            包含生成结果的字典：
            - success: 是否成功
            - answer: 生成的回答
            - error: 错误信息（如果失败）
        """
        log(f"[RAG] 生成回答 (文档数: {len(documents)})", "RAG")

        try:
            if not documents:
                answer = "未找到相关知识"
                success = False
            else:
                context = "\n\n".join([doc.page_content for doc in documents])
                answer = context
                success = len(context) > 50  # 只有内容足够长才认为成功
                # context = "\n\n".join([doc.page_content for doc in documents])
                
                # prompt = f"""基于以下参考资料回答用户问题。如果参考资料中没有相关信息，请如实告知用户。
                #     参考资料：
                #     {context}

                #     用户问题：{query}

                #     请根据参考资料生成回答："""

                # try:
                #     response = self.llm_client.chat.invoke([HumanMessage(content=prompt)])
                #     answer = response.content
                #     success = True
                # except Exception as e:
                #     self._log(f"[RAG] LLM 调用失败，使用原始文档: {e}", "WARNING")
                #     answer = context
                #     success = len(context) > 50
            
            log(f"[RAG] 生成回答完成: {answer[:50]}...", "RAG")

            return {
                "success": success,
                "answer": answer,
                "error": None
            }
        except Exception as e:
            exception(f"[RAG] 生成回答失败: {e}", "RAG", e)
            return {
                "success": False,
                "answer": "",
                "error": str(e)
            }

    def build_index(self, source_dir: str = "knowledge_base"):
        """
        构建索引（可选，供初始化调用）

        Args:
            source_dir: 知识库目录
        """
        log(f"[RAG] 构建索引...", "RAG")

        for kb_name, indexer in self.indexers.items():
            kb_source_dir = f"{source_dir}/{kb_name}"
            if hasattr(indexer, 'build_index'):
                try:
                    indexer.build_index(kb_source_dir)
                    log(f"[RAG] 知识库 {kb_name} 索引构建完成", "RAG")
                except Exception as e:
                    exception(f"[RAG] 知识库 {kb_name} 索引构建失败: {e}", "RAG", e)
