"""
LLM 意图识别器

使用大模型进行意图识别，支持多意图检测。
这是 L3 层，处理 L1 和 L2 未命中的请求。
"""

import json
import re
from typing import List, Dict, Any, Optional
from langchain_core.messages import HumanMessage

from .intent_types import Intent, IntentCategory, IntentConstants
from .intent_registry import IntentRegistry
from modules.logger import log, exception


class IntentRecognizer:
    """
    LLM 意图识别器
    
    使用大模型分析用户请求，识别所有意图（支持多意图）。
    
    特点：
    - 支持多意图识别（"先...再..."）
    - 动态获取可用意图（从注册表）
    - 返回结构化意图列表
    """
    
    def __init__(self, llm_client: Any, intent_registry: IntentRegistry):
        """
        初始化意图识别器
        
        Args:
            llm_client: LLM 客户端
            intent_registry: 意图注册表
        """
        self.llm = llm_client
        self.registry = intent_registry
        log("LLM 意图识别器初始化完成", module="Intent.Recognizer")
    
    def recognize(self, query: str) -> List[Intent]:
        """
        识别用户意图
        
        Args:
            query: 用户请求
            
        Returns:
            意图列表（可能包含多个意图）
        """
        log(f"开始意图识别: {query[:50] if len(query) > 50 else query}...", module="Intent.Recognizer")
        
        prompt = self._build_prompt(query)
        
        try:
            response = self.llm.chat.invoke([HumanMessage(content=prompt)])
            intents = self._parse_response(query, response.content)
            
            log(f"识别到 {len(intents)} 个意图", module="Intent.Recognizer")
            for intent in intents:
                content_preview = intent.content[:30] if len(intent.content) > 30 else intent.content
                log(f"  [{intent.order}] {intent.type}: {content_preview}...", module="Intent.Recognizer")
            
            return intents
            
        except Exception as e:
            exception(f"意图识别失败: {e}", "Intent.Recognizer", e)
            return self._fallback_intent(query)
    
    def _build_prompt(self, query: str) -> str:
        """
        构建 LLM Prompt
        
        Args:
            query: 用户请求
            
        Returns:
            完整的 Prompt
        """
        intent_descriptions = self.registry.get_intent_descriptions()
        
        return f"""你是一个意图识别专家。请分析用户请求，识别所有意图。

        用户请求：{query}

        可用意图类型：
        {intent_descriptions}

        多意图识别规则：
        1. 如果用户使用"先...再..."、"然后"、"接着"等连接词，表示多个意图
        2. 每个意图应独立执行，按顺序返回结果
        3. 为每个意图选择最合适的意图类型和目标处理器
        4. 如果无法确定意图类型，使用 "general_chat"

        请返回 JSON 格式（不要包含其他内容）：
        {{
            "is_multi_intent": true或false,
            "intents": [
                {{
                    "type": "意图类型（从可用意图中选择，如 skill_drawio-skill）",
                    "category": "意图类别（mcp/skill/rag/system）",
                    "content": "意图具体内容",
                    "target": "目标处理器（如 skill:drawio-skill, knowledge_base:exams）",
                    "order": 执行顺序（从1开始）
                }}
            ]
        }}
        """
    
    def _parse_response(self, query: str, response: str) -> List[Intent]:
        """
        解析 LLM 响应
        
        Args:
            query: 原始用户请求
            response: LLM 响应
            
        Returns:
            意图列表
        """
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if not json_match:
                return self._fallback_intent(query)
            
            data = json.loads(json_match.group())
            intents_data = data.get("intents", [])
            
            if not intents_data:
                return self._fallback_intent(query)
            
            intents = []
            for item in intents_data:
                category_str = item.get("category", "system")
                try:
                    category = IntentCategory(category_str)
                except ValueError:
                    category = IntentCategory.SYSTEM
                
                intent = Intent(
                    type=item.get("type", "general_chat"),
                    category=category,
                    content=item.get("content", query),
                    target=item.get("target", ""),
                    order=item.get("order", 1),
                    confidence=1.0,
                )
                intents.append(intent)
            
            intents.sort(key=lambda x: x.order)
            
            return intents
            
        except Exception as e:
            exception(f"解析 LLM 响应失败: {e}", "Intent.Recognizer", e)
            return self._fallback_intent(query)
    
    def _fallback_intent(self, query: str) -> List[Intent]:
        """
        兜底意图：当解析失败时返回默认意图
        
        Args:
            query: 用户请求
            
        Returns:
            默认意图列表
        """
        return [
            Intent(
                type="general_chat",
                category=IntentCategory.SYSTEM,
                content=query,
                target="call_model",
                order=1,
                confidence=0.5,
            )
        ]
    
    def is_multi_intent(self, query: str) -> bool:
        """
        快速判断是否为多意图请求
        
        Args:
            query: 用户请求
            
        Returns:
            是否为多意图
        """
        for connector in IntentConstants.MULTI_INTENT_CONNECTORS:
            if connector in query:
                return True
        return False
