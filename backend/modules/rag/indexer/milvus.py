"""
Milvus Lite 索引器实现
"""

import os
from typing import List, Optional, Dict, Any
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

try:
    from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
    MILVUS_AVAILABLE = True
except ImportError:
    MILVUS_AVAILABLE = False

from .base import BaseIndexer


class MilvusIndexer(BaseIndexer):
    """
    Milvus Lite 索引器实现
    
    基于 Milvus Lite 的向量索引器，支持文档加载、分词、向量化存储和相似度检索。
    Milvus Lite 是一个轻量级的向量数据库，可以在本地运行。

    配置项（环境变量）：
        MILVUS_COLLECTION_NAME: 集合名称（默认knowledge_base）
        MILVUS_DIM: 向量维度（默认1536）
    """

    def __init__(self, ai_client=None):
        """
        初始化 Milvus 索引器
        
        Args:
            ai_client: AI 客户端实例，用于生成向量嵌入
        """
        if not MILVUS_AVAILABLE:
            raise ImportError("需要安装 pymilvus 依赖：pip install pymilvus")

        super().__init__(ai_client=ai_client)
        
        self.collection_name = os.getenv("MILVUS_COLLECTION_NAME", "knowledge_base")
        self.dim = int(os.getenv("MILVUS_DIM", 1536))
        self.index_params = {
            "metric_type": "L2",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128}
        }
        self.collection = None

    def _connect(self):
        """
        连接到 Milvus Lite 实例
        """
        try:
            # Milvus Lite 使用 'default' 连接，不需要端口
            connections.connect("default", host="localhost", port="19530")
            return True
        except Exception as e:
            print(f"连接 Milvus 失败: {e}")
            return False

    def build_index(self, source_dir: str) -> Dict[str, Any]:
        """
        构建索引
        
        Args:
            source_dir: 源文档目录路径
            
        Returns:
            包含 status、message、count 等信息的字典
        """
        if not self._connect():
            return {
                "status": "error",
                "message": "无法连接到 Milvus"
            }

        # 尝试加载已存在的集合
        if self.load_index():
            stats = self.get_collection_stats()
            return {
                "status": "loaded",
                "message": f"成功加载已存在的索引",
                "count": stats.get("vector_count", 0)
            }
        
        # 如果不存在，从源目录创建
        if source_dir and os.path.exists(source_dir):
            if self._load_and_embed_documents(source_dir):
                stats = self.get_collection_stats()
                return {
                    "status": "created",
                    "message": "成功创建新索引",
                    "count": stats.get("vector_count", 0)
                }
            else:
                return {
                    "status": "error",
                    "message": "创建索引失败"
                }
        else:
            return {
                "status": "empty",
                "message": "源目录不存在，索引为空"
            }

    def load_index(self) -> bool:
        """
        加载已存在的索引
        
        Returns:
            加载成功返回 True，失败返回 False
        """
        if not self._connect():
            return False

        try:
            if utility.has_collection(self.collection_name):
                self.collection = Collection(self.collection_name)
                self.collection.load()
                print(f"Milvus 集合加载成功: {self.collection_name}")
                return True
            return False
        except Exception as e:
            print(f"加载 Milvus 集合失败: {e}")
            return False

    def _create_collection(self):
        """
        创建新的 Milvus 集合
        """
        if utility.has_collection(self.collection_name):
            utility.drop_collection(self.collection_name)

        # 获取嵌入维度
        if self.ai_client and hasattr(self.ai_client, 'embeddings'):
            try:
                test_embedding = self.ai_client.embeddings.embed_query("test")
                self.dim = len(test_embedding)
            except:
                pass  # 使用默认维度

        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dim),
            FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=256)
        ]

        schema = CollectionSchema(fields, description="知识库向量集合")
        self.collection = Collection(self.collection_name, schema)
        
        # 创建索引
        self.collection.create_index(
            field_name="embedding",
            index_params=self.index_params
        )
        
        print(f"Milvus 集合创建成功: {self.collection_name} (维度: {self.dim})")

    def _load_and_embed_documents(self, source_dir: str) -> bool:
        """
        从目录加载文档并向量化
        
        Args:
            source_dir: 源文件目录路径
            
        Returns:
            向量化成功返回 True，失败返回 False
        """
        # 使用基类的通用方法加载和分割文档
        split_docs = self._load_and_split_documents(source_dir)
        if split_docs is None:
            return False

        try:
            self._create_collection()
            
            # 批量向量化
            contents = [doc.page_content for doc in split_docs]
            sources = [doc.metadata.get('source', '') for doc in split_docs]
            
            embeddings = self.ai_client.embeddings.embed_documents(contents)
            
            # 插入数据
            entities = [embeddings, contents, sources]
            insert_result = self.collection.insert(entities)
            self.collection.flush()
            self.collection.load()
            
            print(f"向量化完成，共生成 {insert_result.insert_count} 个向量")
            return True
        except Exception as e:
            print(f"向量化失败: {e}")
            return False

    def add_documents(self, documents: List[Document]) -> bool:
        """
        添加文档到索引
        
        Args:
            documents: Document 对象列表
            
        Returns:
            添加成功返回 True，失败返回 False
        """
        if not self.collection:
            print("索引未初始化")
            return False

        try:
            split_docs = self.text_splitter.split_documents(documents)
            
            contents = [doc.page_content for doc in split_docs]
            sources = [doc.metadata.get('source', '') for doc in split_docs]
            
            embeddings = self.ai_client.embeddings.embed_documents(contents)
            
            entities = [embeddings, contents, sources]
            self.collection.insert(entities)
            self.collection.flush()
            
            return True
        except Exception as e:
            print(f"添加文档失败: {e}")
            return False

    def similarity_search(self, query: str, k: int = 3) -> List[Document]:
        """
        相似度搜索
        
        Args:
            query: 查询文本
            k: 返回的文档数量，默认 3
            
        Returns:
            匹配的 Document 对象列表
        """
        if not self.collection:
            raise ValueError("索引未初始化")

        try:
            # 获取查询向量
            query_embedding = self.ai_client.embeddings.embed_query(query)
            
            # 执行搜索
            search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=k,
                output_fields=["content", "source"]
            )
            
            # 转换为 Document 对象
            docs = []
            for hit in results[0]:
                content = hit.entity.get("content")
                source = hit.entity.get("source", "")
                doc = Document(page_content=content, metadata={"source": source, "score": hit.distance})
                docs.append(doc)
            
            return docs
        except Exception as e:
            print(f"相似度搜索失败: {e}")
            return []

    def get_retriever(self, **kwargs):
        """
        获取检索器
        
        Args:
            kwargs: 检索参数，如 search_kwargs={"k": 3}
            
        Returns:
            对应的检索器实例
        """
        search_kwargs = kwargs.get("search_kwargs", {"k": 3})
        
        class MilvusRetriever(BaseRetriever):
            def __init__(self, indexer, search_kwargs):
                self.indexer = indexer
                self.search_kwargs = search_kwargs
                
            def _get_relevant_documents(self, query):
                return self.indexer.similarity_search(query, **self.search_kwargs)
        
        return MilvusRetriever(self, search_kwargs)

    def persist(self) -> None:
        """
        持久化索引到磁盘
        Milvus Lite 会自动持久化，此方法保持接口一致性
        """
        if self.collection:
            self.collection.flush()

    def delete_collection(self) -> bool:
        """
        删除集合
        
        Returns:
            删除成功返回 True，失败返回 False
        """
        try:
            if utility.has_collection(self.collection_name):
                utility.drop_collection(self.collection_name)
                self.collection = None
            return True
        except Exception as e:
            print(f"删除集合失败: {e}")
            return False

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        获取集合统计信息
        
        Returns:
            包含向量数量等统计信息的字典
        """
        if not self.collection:
            return {"vector_count": 0}
        
        try:
            count = self.collection.num_entities
            return {
                "vector_count": count,
                "collection_name": self.collection_name,
                "dimension": self.dim
            }
        except Exception as e:
            print(f"获取统计信息失败: {e}")
            return {"vector_count": 0}
