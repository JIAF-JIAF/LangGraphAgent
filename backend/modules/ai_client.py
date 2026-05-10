"""
LangChain LLM 模块
封装 LangChain 的 ChatOpenAI 客户端
支持从环境变量读取配置
"""

import os
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_community.embeddings.dashscope import DashScopeEmbeddings
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class LLMClient:
    """LangChain LLM 客户端封装"""

    def __init__(
        self,
        temperature: float = 0.7
    ):
        """初始化 LLM 客户端。

        Args:
            temperature: 模型温度参数
        """
        self.temperature = temperature
        self._client = None
        self._embedding_client = None
        self._openai_client = None

        self._load_config()
        self._init_clients()

    def _load_config(self):
        """从环境变量加载 API 配置。"""
        self.api_key = os.getenv("API_KEY")
        self.base_url = os.getenv("BASE_URL")
        self.model = os.getenv("MODEL")

    def _init_clients(self):
        """初始化 LangChain ChatOpenAI 客户端。"""
        self._client = ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=self.temperature,
        )

        self._embedding_client = DashScopeEmbeddings(
            model="text-embedding-v3",
            dashscope_api_key=self.api_key,
        )

        self._openai_client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

        print(f"LangChain LLM 客户端初始化成功 (model={self.model})")

    @property
    def chat(self):
        """获取 ChatOpenAI 客户端。"""
        if self._client is None:
            raise RuntimeError("LLM client 未初始化")
        return self._client

    @property
    def embeddings(self):
        """获取 Embeddings 客户端。"""
        if self._embedding_client is None:
            raise RuntimeError("Embedding client 未初始化")
        return self._embedding_client

    def create_embedding(self, text: str) -> list[float]:
        """创建文本嵌入向量。

        Args:
            text: 要嵌入的文本内容

        Returns:
            文本的嵌入向量表示，失败时返回空列表
        """
        try:
            return self.embeddings.embed_query(text)
        except Exception as e:
            print(f"生成嵌入失败: {e}")
            return []


class AIClient(LLMClient):
    """兼容原有 AIClient 接口"""
    pass


__all__ = ['LLMClient', 'AIClient']
