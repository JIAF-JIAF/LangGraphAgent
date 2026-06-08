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
                log(f"  [{intent.order}] {intent.type} (category={intent.category.value}): {content_preview}...", module="Intent.Recognizer")
            
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
        5. content 必须保留用户原文中的约束条件，不得省略或概括
        6. 问候语（如"你好"、"嗨"）只是语气修饰，不是独立意图，不要拆分为 general_chat
           例如："你好呀，帮我查天气" → 只识别为 mcp_get_weather，不要额外拆出 general_chat

        类别判断规则（category 必须从以下选项中选择）：
        - mcp: 需要调用外部工具/服务（如天气查询、消息推送）
        - skill: 需要执行已注册技能（如绘图、文档生成）
        - rag: 需要检索知识库（如考试题库、政策文档）
        - complex_plan: 复杂需求，需要拆分子任务、多步骤执行（如创建应用、设计方案、开发系统）
        - chat: 简单对话（闲聊、问候、感谢、简单问答，LLM 直接回答即可）
        - system: 系统指令（帮助、退出、确认、取消）

        关键区分：
        - "帮我查天气" → mcp（直接调用工具）
        - "帮我画个图" → skill（直接执行技能）
        - "开发一个在线表格应用" → complex_plan（需要拆分子任务，多步骤执行）
        - "设计一个微服务架构方案" → complex_plan（需要多步骤规划）
        - "杭州天气怎么样，适合去哪玩" → 两个意图：mcp_get_weather(查天气) + mcp_get_weather_recommendation(推荐游玩)
        - "你好" → chat（简单对话）
        - "什么是量子力学" → chat（简单问答，LLM 直接回答）
        - "帮我写一首诗" → chat（简单创作，LLM 直接回答）

        ⚠️ 重要：意图匹配优先级
        - 判断顺序：先判断请求性质（是否需要多步骤执行），再匹配具体意图
        - 优先级：skill > mcp > rag > complex_plan > chat > system
        - 当可用意图列表中有能处理该请求的具体意图时，必须选择该意图
        - 例如：可用意图中有 skill_drawio-skill，"帮我画个流程图" → skill_drawio-skill（不是 complex_plan）
        - 例如：可用意图中有 mcp_get_weather_recommendation，"适合去哪玩" → mcp_get_weather_recommendation（不是 complex_plan）

        complex_plan 的判断标准（主动判断，不是兜底）：
        - 用户请求涉及"创建/开发/设计/构建/实现/搭建"等动作，且目标是"应用/系统/项目/平台/网站/方案/架构"等复杂产物
        - 需要拆分为多个子任务，无法通过单个 skill/mcp/rag 意图一步完成
        - 例如："创建在线表格应用" → complex_plan（创建应用，需要多步骤实现）
        - 例如："开发一个管理系统" → complex_plan（开发系统，需要多步骤实现）
        - 例如："设计微服务架构方案" → complex_plan（设计方案，需要多步骤规划）

        请返回 JSON 格式（不要包含其他内容）：
        {{
            "is_multi_intent": true或false,
            "intents": [
                {{
                    "type": "意图类型（从可用意图中选择，如 skill_drawio-skill）",
                    "category": "意图类别（mcp/skill/rag/complex_plan/chat/system）",
                    "content": "意图具体内容（保留用户原文的约束条件）",
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

                # 后处理：chat → complex_plan 修正
                # LLM 可能将"创建应用"等误判为 chat，通过关键词二次校验
                content = item.get("content", query)
                if category == IntentCategory.CHAT:
                    category = self._correct_chat_to_complex_plan(content, category)

                intent = Intent(
                    type=item.get("type", "general_chat"),
                    category=category,
                    content=content,
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

    # 复杂规划关键词模式：动词 + 名词
    _COMPLEX_PLAN_VERBS = ["创建", "开发", "设计", "构建", "实现", "搭建", "制作", "编写", "部署"]
    _COMPLEX_PLAN_NOUNS = ["应用", "系统", "项目", "工具", "平台", "网站", "方案", "架构", "程序", "软件", "服务", "框架"]

    def _correct_chat_to_complex_plan(self, content: str, current_category: IntentCategory) -> IntentCategory:
        """
        后处理修正：chat → complex_plan

        LLM 可能将"创建应用"等需要多步骤执行的意图误判为 chat。
        通过关键词模式二次校验，确保复杂规划意图不被遗漏。

        Args:
            content: 意图内容
            current_category: 当前 LLM 判定的类别

        Returns:
            修正后的类别
        """
        if current_category != IntentCategory.CHAT:
            return current_category

        # 检查是否包含 动词 + 名词 的组合
        has_verb = any(v in content for v in self._COMPLEX_PLAN_VERBS)
        has_noun = any(n in content for n in self._COMPLEX_PLAN_NOUNS)

        if has_verb and has_noun:
            log(f"  [修正] chat → complex_plan: {content[:40]}...", module="Intent.Recognizer")
            return IntentCategory.COMPLEX_PLAN

        return current_category
    
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
