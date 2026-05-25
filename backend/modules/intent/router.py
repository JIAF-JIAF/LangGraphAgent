"""
分层漏斗路由器

业界 2026 年标准架构：
L1 关键词/正则（<1ms，60-80% 请求）
L2 向量语义（30-100ms，15-25% 请求）- 保留入口
L3 大模型 FC（1-2s，5-15% 请求）
"""

import re
from typing import List, Dict, Any, Optional

from .intent_types import Intent, IntentCategory, IntentConstants
from .intent_registry import IntentRegistry
from .recognizer import IntentRecognizer
from modules.logger import log


class IntentRouter:
    """
    分层漏斗路由器
    
    按优先级依次尝试：
    1. L1 关键词/正则匹配（快速处理固定指令）
    2. L2 向量语义匹配（保留入口，暂未实现）
    3. L3 大模型 FC（处理复杂请求和多意图）
    
    设计原则：
    - 先快后慢
    - 先低成本后高智能
    - 80% 高频请求在 L1/L2 处理
    """
    
    def __init__(
        self,
        llm_client: Any,
        intent_registry: IntentRegistry,
        vector_store: Any = None,
    ):
        """
        初始化路由器
        
        Args:
            llm_client: LLM 客户端
            intent_registry: 意图注册表
            vector_store: 向量存储（L2 层，可选）
        """
        self.registry = intent_registry
        self.recognizer = IntentRecognizer(llm_client, intent_registry)
        self.vector_store = vector_store
        
        self._init_keyword_patterns()
        
        log("分层漏斗路由器初始化完成", module="Intent.Router")
    
    def _init_keyword_patterns(self):
        """初始化关键词匹配模式"""
        self._keyword_patterns = {
            r"^/help$": ("system_help", "系统帮助"),
            r"^help$": ("system_help", "系统帮助"),
            r"^exit$": ("system_exit", "退出系统"),
            r"^quit$": ("system_exit", "退出系统"),
            r"^(是|yes|确认|确定|ok|好的)$": ("system_confirm", "确认"),
            r"^(否|no|取消|不要|算了)$": ("system_cancel", "取消"),
        }
    
    def route(self, query: str) -> List[Intent]:
        """
        路由用户请求
        
        按分层漏斗依次尝试匹配
        
        Args:
            query: 用户请求
            
        Returns:
            意图列表（可能包含多个意图）
        """
        log(f"开始路由: {query[:50] if len(query) > 50 else query}...", module="Intent.Router")
        
        intents = self._match_by_keywords(query)
        if intents:
            log(f"L1 关键词匹配成功: {intents[0].type}", module="Intent.Router")
            return intents
        
        intents = self._match_by_vector(query)
        if intents:
            log(f"L2 向量匹配成功: {intents[0].type}", module="Intent.Router")
            return intents
        
        intents = self._match_by_llm(query)
        log(f"L3 LLM 匹配完成，识别到 {len(intents)} 个意图", module="Intent.Router")
        return intents
    
    def _match_by_keywords(self, query: str) -> Optional[List[Intent]]:
        """
        L1: 关键词/正则匹配
        
        处理固定指令，延迟 <1ms
        
        Args:
            query: 用户请求
            
        Returns:
            意图列表，未匹配返回 None
        """
        query_stripped = query.strip().lower()
        
        for pattern, (intent_type, description) in self._keyword_patterns.items():
            if re.match(pattern, query_stripped, re.IGNORECASE):
                intent = Intent(
                    type=intent_type,
                    category=IntentCategory.SYSTEM,
                    content=query,
                    target="system",
                    order=1,
                    confidence=1.0,
                )
                return [intent]
        
        return None
    
    def _match_by_vector(self, query: str) -> Optional[List[Intent]]:
        """
        L2: 向量语义匹配
        
        处理同义改写，延迟 30-100ms
        
        Args:
            query: 用户请求
            
        Returns:
            意图列表，未匹配返回 None
        """
        if not self.vector_store:
            return None
        
        examples = self.registry.get_intent_examples()
        if not examples:
            return None
        
        log("L2 向量匹配暂未实现", module="Intent.Router")
        return None
    
    def _match_by_llm(self, query: str) -> List[Intent]:
        """
        L3: 大模型 FC
        
        处理复杂请求和多意图，延迟 1-2s
        
        Args:
            query: 用户请求
            
        Returns:
            意图列表
        """
        return self.recognizer.recognize(query)
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """
        获取路由统计信息
        
        Returns:
            统计信息字典
        """
        return {
            "total_intents": self.registry.get_intent_count(),
            "mcp_intents": len(self.registry.get_intents_by_category(IntentCategory.MCP)),
            "skill_intents": len(self.registry.get_intents_by_category(IntentCategory.SKILL)),
            "rag_intents": len(self.registry.get_intents_by_category(IntentCategory.RAG)),
            "vector_store_enabled": self.vector_store is not None,
        }
