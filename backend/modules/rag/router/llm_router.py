"""
基于LLM的智能路由器

使用大语言模型分析用户查询，智能判断是否需要检索知识库。

核心功能：
1. 判断是否需要检索（should_retrieve）- 使用LLM分析问题类型
2. 选择知识库（select_knowledge_base）- 根据问题领域选择合适的知识库
3. 选择检索策略（select_retrieval_strategy）- 根据问题复杂度选择策略

判断逻辑：
- 需要检索：产品文档、公司政策、技术规范、特定领域知识、事实查询
- 不需要检索：常识问题、创造性写作、数学计算、闲聊对话
"""

from typing import Optional, Dict, Any
from langchain_core.messages import HumanMessage

from .base import BaseRouter
from modules.knowledge_base import kb_manager


class LLMRouter(BaseRouter):
    """
    基于LLM的智能路由器

    使用大语言模型分析用户查询，智能判断是否需要检索知识库。

    属性：
        llm_client: LLM客户端实例，用于分析用户查询
        config: 配置字典
    """

    def __init__(self, llm_client, config: Optional[Dict] = None):
        """
        初始化LLM路由器

        Args:
            llm_client: LLM客户端实例（需要支持 chat.invoke 方法）
            config: 配置参数（可选）
        """
        super().__init__(config)
        self.llm_client = llm_client
        self._retrieval_threshold = self.config.get("retrieval_threshold", 0.7)

    def _call_llm(self, prompt: str) -> str:
        """
        调用LLM获取响应

        Args:
            prompt: 提示词文本

        Returns:
            LLM返回的响应文本
        """
        response = self.llm_client.chat.invoke([HumanMessage(content=prompt)])
        return response.content if hasattr(response, 'content') else str(response)

    def should_retrieve(self, query: str) -> bool:
        """
        使用LLM判断是否需要检索

        通过分析用户查询的语义特征，判断是否需要从知识库中检索信息。

        Args:
            query: 用户查询文本

        Returns:
            需要检索返回 True，否则返回 False
        """
        prompt = self._build_retrieval_prompt(query)

        try:
            response_text = self._call_llm(prompt)
            return self._parse_retrieval_decision(response_text)
        except Exception as e:
            print(f"[ERROR] LLMRouter.should_retrieve: {e}")
            # 如果LLM调用失败，默认进行检索
            return True

    def select_knowledge_base(self, query: str) -> Optional[str]:
        """
        根据问题领域选择知识库

        Args:
            query: 用户查询文本

        Returns:
            知识库名称，None 表示使用默认知识库
        """
        prompt = self._build_knowledge_base_prompt(query)

        try:
            response_text = self._call_llm(prompt)
            result = response_text.strip()
            if result.lower() == "default":
                return None
            return result
        except Exception as e:
            print(f"[ERROR] LLMRouter.select_knowledge_base: {e}")
            return None

    def select_retrieval_strategy(self, query: str) -> Dict[str, Any]:
        """
        根据问题复杂度选择检索策略

        Args:
            query: 用户查询文本

        Returns:
            检索策略配置字典
        """
        prompt = self._build_strategy_prompt(query)

        try:
            response_text = self._call_llm(prompt)
            return self._parse_strategy_response(response_text)
        except Exception as e:
            print(f"[ERROR] LLMRouter.select_retrieval_strategy: {e}")
            return {}

    def _build_retrieval_prompt(self, query: str) -> str:
        """
        构建判断是否需要检索的提示词

        Args:
            query: 用户查询文本

        Returns:
            完整的提示词字符串
        """
        # 动态获取知识库列表
        databases = kb_manager.get_databases()
        kb_descriptions = []
        for db in databases:
            desc = db.get("description", "暂无描述")
            kb_descriptions.append(f"- {db['name']}知识库：{desc}")
        
        kb_text = "\n".join(kb_descriptions) if kb_descriptions else "- default知识库：默认知识库"
        
        return f"""
        你是一个智能路由器，负责判断用户问题是否需要从知识库中检索信息。

        用户问题：{query}

        知识库包含以下内容：
        {kb_text}

        请根据以下标准判断：
        1. 需要检索的情况：
        - 查询知识库中包含的特定领域知识、事实信息、文档内容等
        - 任何与上述知识库内容相关的问题

        2. 不需要检索的情况：
        - 常识性问题
        - 创造性写作任务（如写文章、诗歌、故事）
        - 数学计算或逻辑推理
        - 闲聊对话或日常问候
        - 与知识库内容无关的问题

        请只回复 "需要检索" 或 "不需要检索"，不要添加其他任何内容。
        """ 

    def _parse_retrieval_decision(self, response: str) -> bool:
        """
        解析LLM返回的检索决策

        Args:
            response: LLM返回的响应文本

        Returns:
            True表示需要检索，False表示不需要检索
        """
        response = response.strip().lower()
        return response == "需要检索"

    def _build_knowledge_base_prompt(self, query: str) -> str:
        """
        构建选择知识库的提示词

        Args:
            query: 用户查询文本

        Returns:
            完整的提示词字符串
        """
        # 动态获取知识库列表
        databases = kb_manager.get_databases()
        kb_descriptions = []
        for db in databases:
            desc = db.get("description", "暂无描述")
            kb_descriptions.append(f"- {db['name']}: {desc}")
        
        kb_text = "\n".join(kb_descriptions) if kb_descriptions else "- default: 默认知识库"
        
        return f"""
        你是一个知识库选择器，请根据用户问题选择最合适的知识库。

        用户问题：{query}

        可用知识库列表：
        {kb_text}

        请分析问题领域，选择最合适的知识库名称。如果没有特别合适的，选择 default。

        请只回复知识库名称，不要添加其他任何内容。
        """

    def _parse_strategy_response(self, response: str) -> Dict[str, Any]:
        """
        解析LLM返回的策略配置

        Args:
            response: LLM返回的响应文本

        Returns:
            检索策略配置字典
        """
        try:
            import json
            return json.loads(response)
        except:
            # 如果解析失败，返回默认配置
            return {"k": 3}

    def _build_strategy_prompt(self, query: str) -> str:
        """
        构建选择检索策略的提示词

        Args:
            query: 用户查询文本

        Returns:
            完整的提示词字符串
        """
        return f"""
        你是一个检索策略专家，请根据用户问题的复杂度选择合适的检索策略。

        用户问题：{query}

        请分析问题的复杂度，并返回JSON格式的检索参数：
        - k: 返回的文档数量（简单问题选2-3，复杂问题选5-10）
        - search_type: 检索类型（"similarity"表示相似度检索，"mmr"表示多样性检索）

        请只返回JSON对象，例如：{{"k": 3, "search_type": "similarity"}}
        不要添加其他任何内容。
        """
